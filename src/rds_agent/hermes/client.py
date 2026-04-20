"""Hermes 模型客户端 - 通过 Ollama 调用 Hermes 模型。

支持:
- Hermes-2-Pro-Llama-3
- Hermes-3-Llama-3.1
- Function Calling (原生支持)
- 多轮对话
- 工具调用结果回传
"""

import json
from typing import Any, Dict, List, Optional, Union
import httpx

from rds_agent.utils.config import get_settings
from rds_agent.utils.logger import get_logger
from .function_schema import ToolDefinition, ToolRegistry

logger = get_logger("hermes_client")


class HermesClient:
    """Hermes 模型客户端 (通过 Ollama API)"""

    def __init__(
        self,
        model: str = "hermes3",
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        """
        初始化 Hermes 客户端

        Args:
            model: Hermes 模型名称 (hermes2pro, hermes3)
            base_url: Ollama API 地址
            timeout: 请求超时时间
        """
        settings = get_settings()
        self.model = self._resolve_model_name(model)
        self.base_url = base_url or settings.ollama.host
        self.timeout = timeout
        self.api_url = f"{self.base_url.rstrip('/')}/api"

        logger.info(f"Hermes Client initialized: model={self.model}, url={self.base_url}")

    def _resolve_model_name(self, model: str) -> str:
        """解析模型名称"""
        model_mapping = {
            "hermes2pro": "hermes2pro-llama3",
            "hermes2": "hermes2pro-llama3",
            "hermes3": "hermes3-llama3.1",
            "hermes": "hermes3-llama3.1",
        }
        return model_mapping.get(model.lower(), model)

    def _build_system_prompt(self, tools: Optional[List[ToolDefinition]] = None) -> str:
        """构建系统提示词，包含工具说明"""
        base_prompt = """You are Hermes, a helpful AI assistant with function calling capabilities.
You have access to various tools for MySQL database diagnosis and inspection.

When you need to use a tool:
1. Analyze the user's request to determine which tool to use
2. Call the tool with the appropriate parameters
3. Use the tool results to provide a helpful response

Always respond in Chinese (中文) when the user asks in Chinese."""

        if tools:
            tools_desc = "\n\nAvailable Tools:\n"
            for tool in tools:
                func = tool.get("function", {})
                name = func.get("name", "")
                desc = func.get("description", "")
                params = func.get("parameters", {})
                tools_desc += f"- {name}: {desc}\n"
                if params.get("properties"):
                    for param_name, param_info in params.get("properties", {}).items():
                        param_desc = param_info.get("description", "")
                        tools_desc += f"  - {param_name}: {param_desc}\n"
            return base_prompt + tools_desc

        return base_prompt

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> Dict[str, Any]:
        """
        发送对话请求，支持 Function Calling

        Args:
            messages: 对话消息列表
            tools: 可用工具列表 (OpenAI 格式)
            tool_registry: 工具注册中心 (用于执行工具调用)

        Returns:
            包含响应和可能的工具调用的结果
        """
        # 构建请求
        system_prompt = self._build_system_prompt(tools)

        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
            ] + messages,
            "stream": False,
            "format": "json" if tools else None,  # Hermes 需要 JSON 格式来支持 function calling
            "options": {
                "temperature": 0.7,
                "num_ctx": 4096,
            }
        }

        # 如果有工具，添加到请求
        if tools:
            request_body["tools"] = tools

        try:
            response = httpx.post(
                f"{self.api_url}/chat",
                json=request_body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()

            # 解析响应
            message = result.get("message", {})
            content = message.get("content", "")

            # 检查是否有工具调用 (Hermes 格式)
            tool_calls = self._parse_tool_calls(content, message)

            # 如果有工具调用，执行并返回结果
            if tool_calls and tool_registry:
                tool_results = []
                for call in tool_calls:
                    try:
                        result = tool_registry.execute(
                            call["name"],
                            **call.get("arguments", {})
                        )
                        tool_results.append({
                            "tool_call_id": call.get("id"),
                            "name": call["name"],
                            "result": result,
                        })
                    except Exception as e:
                        logger.error(f"Tool execution failed: {call['name']} - {e}")
                        tool_results.append({
                            "tool_call_id": call.get("id"),
                            "name": call["name"],
                            "error": str(e),
                        })

                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "tool_results": tool_results,
                }

            return {
                "content": content,
                "tool_calls": None,
                "tool_results": None,
            }

        except httpx.HTTPError as e:
            logger.error(f"Hermes API error: {e}")
            raise RuntimeError(f"Hermes API request failed: {e}")

    def _parse_tool_calls(
        self,
        content: str,
        message: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        解析工具调用 (Hermes 特有格式)

        Hermes 的 function calling 格式示例:
        ```json
        {
            "tool_calls": [
                {
                    "name": "get_instance_info",
                    "arguments": {"instance_name": "db-prod-01"}
                }
            ]
        }
        ```
        """
        # 尝试从 content 中解析 JSON
        try:
            if content.strip().startswith("{"):
                parsed = json.loads(content)
                if "tool_calls" in parsed:
                    return parsed["tool_calls"]
                # 单个工具调用格式
                if "name" in parsed and "arguments" in parsed:
                    return [parsed]
        except json.JSONDecodeError:
            pass

        # 检查 message 中是否有工具调用字段
        if "tool_calls" in message:
            return message["tool_calls"]

        return None

    def chat_with_tool_loop(
        self,
        user_message: str,
        tools: List[ToolDefinition],
        tool_registry: ToolRegistry,
        max_iterations: int = 5,
    ) -> str:
        """
        带工具调用循环的对话

        持续调用工具直到模型返回最终回复
        """
        messages = [{"role": "user", "content": user_message}]

        for iteration in range(max_iterations):
            result = self.chat(messages, tools, tool_registry)

            # 如果有工具调用结果，添加到消息历史
            if result.get("tool_results"):
                tool_results = result["tool_results"]
                messages.append({
                    "role": "assistant",
                    "content": result["content"],
                })

                for tool_result in tool_results:
                    messages.append({
                        "role": "tool",
                        "name": tool_result["name"],
                        "content": json.dumps(tool_result.get("result") or tool_result.get("error")),
                    })

                # 继续对话，让模型处理工具结果
                continue

            # 没有工具调用，返回最终回复
            return result["content"]

        return result.get("content", "未能完成任务，达到最大迭代次数")

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
    ):
        """
        流式对话
        """
        system_prompt = self._build_system_prompt(tools)

        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
            ] + messages,
            "stream": True,
            "format": "json" if tools else None,
        }

        if tools:
            request_body["tools"] = tools

        with httpx.stream(
            "POST",
            f"{self.api_url}/chat",
            json=request_body,
            timeout=self.timeout,
        ) as response:
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk:
                            yield chunk["message"]
                    except json.JSONDecodeError:
                        continue

    def check_model_available(self) -> bool:
        """检查模型是否可用"""
        try:
            response = httpx.get(
                f"{self.api_url}/tags",
                timeout=10.0,
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            return any(self.model in m.get("name", "") for m in models)
        except Exception as e:
            logger.warning(f"Failed to check model availability: {e}")
            return False

    def pull_model(self) -> bool:
        """拉取模型 (如果未安装)"""
        try:
            response = httpx.post(
                f"{self.api_url}/pull",
                json={"name": self.model},
                timeout=300.0,  # 下载可能需要较长时间
            )
            response.raise_for_status()
            logger.info(f"Model {self.model} pulled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False