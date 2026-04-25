"""工具执行器 - 包装工具调用，记录执行结果

工具执行器提供：
1. 标准化的工具调用接口
2. 执行结果记录
3. 错误处理和重试
4. 执行超时控制

参考 Hermes Agent 的函数调用架构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import time
import traceback

from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger

logger = get_logger("tool_executor")


class ToolStatus(str, Enum):
    """工具执行状态"""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRY = "retry"
    PENDING = "pending"
    RUNNING = "running"


@dataclass
class ToolResult:
    """工具执行结果"""

    # 基本信息
    tool_name: str
    status: ToolStatus
    result: Optional[Any] = None
    error: Optional[str] = None

    # 执行详情
    arguments: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

    # 元数据
    iteration: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    # 重试信息
    retry_count: int = 0
    max_retries: int = 3

    def is_success(self) -> bool:
        """是否成功"""
        return self.status == ToolStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "arguments": self.arguments,
            "execution_time_ms": self.execution_time_ms,
            "iteration": self.iteration,
            "retry_count": self.retry_count,
        }

    def to_context_string(self) -> str:
        """转换为上下文字符串"""
        if self.is_success():
            result_str = str(self.result)[:500] if self.result else "None"
            return f"Tool {self.tool_name} succeeded: {result_str}"
        else:
            return f"Tool {self.tool_name} failed: {self.error}"


class ToolConfig(BaseModel):
    """工具配置"""

    # 超时设置
    default_timeout_ms: float = Field(default=30000, description="默认超时时间(ms)")
    max_timeout_ms: float = Field(default=60000, description="最大超时时间(ms)")

    # 重试设置
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay_ms: float = Field(default=1000, description="重试延迟(ms)")

    # 执行限制
    max_concurrent_calls: int = Field(default=5, description="最大并发调用数")
    enable_parallel: bool = Field(default=True, description="启用并行执行")

    # 日志设置
    log_tool_calls: bool = Field(default=True, description="记录工具调用日志")
    log_arguments: bool = Field(default=False, description="记录参数详情")


class ToolRegistry:
    """工具注册表 - 管理可用工具"""

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, Callable] = {}
        self._tool_info: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        func: Callable,
        description: str = "",
        parameters: Optional[Dict] = None,
    ) -> None:
        """注册工具

        Args:
            name: 工具名称
            func: 工具函数
            description: 工具描述
            parameters: 参数定义
        """
        self._tools[name] = func
        self._tool_info[name] = {
            "name": name,
            "description": description,
            "parameters": parameters or {},
        }

        logger.debug(f"Tool registered: {name}")

    def get(self, name: str) -> Optional[Callable]:
        """获取工具"""
        return self._tools.get(name)

    def get_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        return self._tool_info.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """获取工具定义（用于 LLM）"""
        definitions = []
        for name, info in self._tool_info.items():
            definitions.append({
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"],
            })
        return definitions

    def unregister(self, name: str) -> None:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            del self._tool_info[name]


# 全局工具注册表
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


class ToolExecutor:
    """工具执行器 - 执行工具调用并记录结果

    功能：
    1. 执行工具调用
    2. 处理错误和重试
    3. 控制超时
    4. 记录执行历史

    支持：
    - 单次执行
    - 并行执行
    - 重试机制
    - 超时控制
    """

    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        """初始化工具执行器

        Args:
            config: 工具配置
            registry: 工具注册表
        """
        self.config = config or ToolConfig()
        self.registry = registry or get_tool_registry()

        # 执行历史
        self._execution_history: List[ToolResult] = []

        # 统计
        self._stats = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "retry_calls": 0,
            "timeout_calls": 0,
        }

        logger.info(f"ToolExecutor initialized: max_retries={self.config.max_retries}")

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        iteration: int = 0,
        timeout_ms: Optional[float] = None,
    ) -> ToolResult:
        """执行工具

        Args:
            tool_name: 工具名称
            arguments: 参数
            iteration: 当前迭代
            timeout_ms: 超时时间

        Returns:
            ToolResult 执行结果
        """
        start_time = time.time()
        timeout_ms = timeout_ms or self.config.default_timeout_ms

        # 获取工具
        tool_func = self.registry.get(tool_name)
        if not tool_func:
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.FAILED,
                error=f"Tool not found: {tool_name}",
                arguments=arguments,
                iteration=iteration,
            )
            self._record_execution(result)
            return result

        # 执行（支持重试）
        retry_count = 0
        last_error = None

        while retry_count <= self.config.max_retries:
            try:
                # 调用工具
                execution_result = self._call_tool(
                    tool_func,
                    arguments,
                    timeout_ms,
                )

                # 成功
                execution_time_ms = (time.time() - start_time) * 1000
                result = ToolResult(
                    tool_name=tool_name,
                    status=ToolStatus.SUCCESS,
                    result=execution_result,
                    arguments=arguments,
                    execution_time_ms=execution_time_ms,
                    iteration=iteration,
                    retry_count=retry_count,
                )

                self._record_execution(result)
                return result

            except TimeoutError:
                retry_count += 1
                last_error = f"Timeout after {timeout_ms}ms"
                self._stats["timeout_calls"] += 1

                if retry_count < self.config.max_retries:
                    time.sleep(self.config.retry_delay_ms / 1000)

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                self._stats["retry_calls"] += 1

                if retry_count < self.config.max_retries:
                    time.sleep(self.config.retry_delay_ms / 1000)

        # 失败
        execution_time_ms = (time.time() - start_time) * 1000
        result = ToolResult(
            tool_name=tool_name,
            status=ToolStatus.FAILED,
            error=last_error,
            arguments=arguments,
            execution_time_ms=execution_time_ms,
            iteration=iteration,
            retry_count=retry_count,
        )

        self._record_execution(result)
        return result

    def execute_batch(
        self,
        tool_calls: List[Dict[str, Any]],
        iteration: int = 0,
        parallel: bool = True,
    ) -> List[ToolResult]:
        """批量执行工具

        Args:
            tool_calls: 工具调用列表
            iteration: 当前迭代
            parallel: 是否并行执行

        Returns:
            List[ToolResult] 执行结果列表
        """
        results = []

        if parallel and self.config.enable_parallel:
            # 并行执行（简化实现）
            for call in tool_calls:
                result = self.execute(
                    call["name"],
                    call.get("arguments", {}),
                    iteration,
                )
                results.append(result)
        else:
            # 顺序执行
            for call in tool_calls:
                result = self.execute(
                    call["name"],
                    call.get("arguments", {}),
                    iteration,
                )
                results.append(result)

        return results

    def _call_tool(
        self,
        tool_func: Callable,
        arguments: Dict[str, Any],
        timeout_ms: float,
    ) -> Any:
        """调用工具函数"""
        # 简化实现：直接调用
        # 实际应用中可添加超时控制（如使用 threading.Timer）
        try:
            return tool_func(**arguments)
        except TypeError as e:
            # 参数错误
            raise ValueError(f"Invalid arguments: {e}")

    def _record_execution(self, result: ToolResult) -> None:
        """记录执行"""
        self._execution_history.append(result)

        # 更新统计
        self._stats["total_calls"] += 1
        if result.is_success():
            self._stats["success_calls"] += 1
        else:
            self._stats["failed_calls"] += 1

        # 日志
        if self.config.log_tool_calls:
            logger.info(
                f"Tool executed: {result.tool_name}, "
                f"status={result.status}, time={result.execution_time_ms:.0f}ms"
            )

    def get_history(self) -> List[ToolResult]:
        """获取执行历史"""
        return self._execution_history

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "success_rate": (
                self._stats["success_calls"] / self._stats["total_calls"]
                if self._stats["total_calls"] > 0 else 0
            ),
            "avg_execution_time_ms": (
                sum(r.execution_time_ms for r in self._execution_history)
                / len(self._execution_history)
                if self._execution_history else 0
            ),
        }

    def clear_history(self) -> None:
        """清空历史"""
        self._execution_history.clear()


class HermesStyleToolExecutor(ToolExecutor):
    """Hermes 风格工具执行器

    特点：
    1. 直接函数调用（无需 LangChain/LangGraph）
    2. 原生错误处理
    3. 简洁的执行流程
    4. 适配 LLM function calling
    """

    def __init__(
        self,
        config: Optional[ToolConfig] = None,
    ):
        """初始化"""
        super().__init__(config=config)

    def execute_from_llm_output(
        self,
        llm_tool_call: Dict[str, Any],
        iteration: int = 0,
    ) -> ToolResult:
        """从 LLM 输出执行工具

        Args:
            llm_tool_call: LLM 返回的工具调用
            iteration: 当前迭代

        Returns:
            ToolResult 执行结果
        """
        # 解析 LLM 输出
        tool_name = llm_tool_call.get("name", "")
        arguments = llm_tool_call.get("arguments", {})

        # 如果 arguments 是字符串，尝试解析
        if isinstance(arguments, str):
            try:
                import json
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        return self.execute(tool_name, arguments, iteration)

    def format_for_llm(self, results: List[ToolResult]) -> str:
        """格式化结果供 LLM 使用

        Args:
            results: 执行结果列表

        Returns:
            格式化的上下文字符串
        """
        lines = []
        for result in results:
            if result.is_success():
                result_str = str(result.result)[:1000] if result.result else "None"
                lines.append(
                    f"Tool '{result.tool_name}' executed successfully:\n{result_str}"
                )
            else:
                lines.append(
                    f"Tool '{result.tool_name}' failed: {result.error}"
                )

        return "\n\n".join(lines)


def register_default_tools(executor: ToolExecutor) -> None:
    """注册默认工具"""
    registry = executor.registry

    # 注册基础工具（示例）
    def echo(message: str) -> str:
        """Echo message"""
        return message

    def get_time() -> str:
        """Get current time"""
        return datetime.now().isoformat()

    registry.register(
        "echo",
        echo,
        description="Echo a message back",
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message to echo",
                }
            },
            "required": ["message"],
        }
    )

    registry.register(
        "get_time",
        get_time,
        description="Get current time",
        parameters={"type": "object", "properties": {}}
    )


def create_tool_executor(
    max_retries: int = 3,
    timeout_ms: float = 30000,
) -> ToolExecutor:
    """创建工具执行器"""
    config = ToolConfig(
        max_retries=max_retries,
        default_timeout_ms=timeout_ms,
    )
    executor = ToolExecutor(config=config)
    register_default_tools(executor)
    return executor