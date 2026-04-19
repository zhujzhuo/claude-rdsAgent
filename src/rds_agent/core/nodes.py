"""LangGraph节点实现。"""

import json
import re
from datetime import datetime
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_community.llms import Ollama

from rds_agent.core.state import AgentState, IntentType
from rds_agent.core.prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    RESPONSE_GENERATION_PROMPT,
    INSTANCE_CONFIRMATION_PROMPT,
    SYSTEM_PROMPT,
)
from rds_agent.tools import get_all_langchain_tools
from rds_agent.tools.instance import get_instance_list
from rds_agent.utils.config import settings
from rds_agent.utils.logger import get_logger

logger = get_logger("nodes")


def get_llm() -> Ollama:
    """获取LLM实例"""
    return Ollama(
        model=settings.ollama.model,
        base_url=settings.ollama.host,
        temperature=0.1,
    )


# 意图关键词映射
INTENT_KEYWORDS = {
    IntentType.INSTANCE_QUERY: [
        "实例", "列表", "规格", "版本", "架构", "部署",
        "有哪些", "查看实例", "实例信息",
    ],
    IntentType.PERFORMANCE_DIAG: [
        "性能", "QPS", "TPS", "慢", "延迟", "响应",
        "慢查询", "慢SQL", "Buffer", "命中率",
        "性能问题", "性能情况", "运行状态",
    ],
    IntentType.SQL_DIAG: [
        "SQL", "慢SQL", "慢查询", "语句", "查询分析",
        "执行", "processlist", "正在执行",
    ],
    IntentType.CONNECTION_DIAG: [
        "连接", "会话", "连接数", "活跃", "锁", "等待",
        "连接池", "超时", "中断",
    ],
    IntentType.STORAGE_DIAG: [
        "空间", "存储", "容量", "大小", "表大小",
        "索引", "碎片", "磁盘", "数据量",
    ],
    IntentType.PARAMETER_QUERY: [
        "参数", "配置", "设置", "innodb", "max_connections",
        "参数值", "优化建议",
    ],
    IntentType.KNOWLEDGE_QA: [
        "为什么", "怎么", "如何", "是什么", "解释",
        "原理", "区别", "优化方法", "最佳实践",
    ],
}


def classify_intent(state: AgentState) -> AgentState:
    """意图识别节点"""
    logger.info("执行意图识别节点")

    # 获取最后一条用户消息
    user_message = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break

    if not user_message:
        state["intent"] = IntentType.UNKNOWN
        state["current_node"] = "classify"
        return state

    # 使用关键词匹配进行意图识别（快速模式）
    intent = IntentType.GENERAL_CHAT
    max_score = 0

    user_lower = user_message.lower()

    for intent_type, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in user_lower)
        if score > max_score:
            max_score = score
            intent = intent_type

    # 提取实例名称
    instance_name = extract_instance_name(user_message)

    # 如果没有匹配到明确意图，使用LLM进行识别
    if max_score == 0:
        try:
            llm = get_llm()
            prompt = INTENT_CLASSIFICATION_PROMPT.format(user_input=user_message)
            response = llm.invoke(prompt)

            # 解析JSON响应
            json_match = re.search(r"\{[^}]+\}", response)
            if json_match:
                result = json.loads(json_match.group())
                intent_str = result.get("intent", "general_chat")
                intent = IntentType(intent_str) if intent_str in [i.value for i in IntentType] else IntentType.GENERAL_CHAT
                if not instance_name:
                    instance_name = result.get("instance")
        except Exception as e:
            logger.warning(f"LLM意图识别失败: {e}")

    state["intent"] = intent
    state["target_instance"] = instance_name
    state["current_node"] = "classify"
    state["needs_tool_call"] = intent != IntentType.GENERAL_CHAT and intent != IntentType.UNKNOWN

    logger.info(f"识别意图: {intent}, 实例: {instance_name}")

    return state


def extract_instance_name(message: str) -> Optional[str]:
    """从消息中提取实例名称"""
    # 匹配模式：db-xxx, inst-xxx, 或 "实例xxx"
    patterns = [
        r"(db-[a-zA-Z0-9_-]+)",
        r"(inst-[a-zA-Z0-9_-]+)",
        r"实例\s*[\"']?([a-zA-Z0-9_-]+)[\"']?",
        r"([a-zA-Z0-9_-]+)\s*实例",
    ]

    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1)

    return None


def check_instance(state: AgentState) -> AgentState:
    """检查实例是否存在"""
    logger.info("执行实例检查节点")

    intent = state.get("intent")
    target_instance = state.get("target_instance")

    # 如果不需要实例，直接返回
    if intent in [IntentType.KNOWLEDGE_QA, IntentType.GENERAL_CHAT]:
        state["current_node"] = "check_instance"
        return state

    # 如果没有指定实例，获取实例列表让用户选择
    if not target_instance:
        try:
            result = get_instance_list.invoke({})
            instances = json.loads(result)

            if len(instances) == 0:
                state["error"] = "没有可用的实例"
                state["needs_tool_call"] = False
            elif len(instances) == 1:
                # 只有一个实例，自动选择
                state["target_instance"] = instances[0]["name"]
            else:
                # 多个实例，提示用户选择
                instance_names = [i["name"] for i in instances]
                state["context"]["available_instances"] = instance_names
                state["response"] = f"请指定要查询的实例，可用实例：{', '.join(instance_names)}"
                state["needs_tool_call"] = False

        except Exception as e:
            logger.error(f"获取实例列表失败: {e}")
            state["error"] = str(e)

    state["current_node"] = "check_instance"
    return state


def select_tools(state: AgentState) -> AgentState:
    """选择要调用的工具"""
    logger.info("执行工具选择节点")

    intent = state.get("intent")
    target_instance = state.get("target_instance")

    # 根据意图选择工具
    tool_mapping = {
        IntentType.INSTANCE_QUERY: ["get_instance_info"],
        IntentType.PERFORMANCE_DIAG: ["get_performance_metrics", "get_slow_queries"],
        IntentType.SQL_DIAG: ["get_slow_queries", "analyze_processlist"],
        IntentType.CONNECTION_DIAG: ["get_connection_status", "get_lock_info"],
        IntentType.STORAGE_DIAG: ["get_storage_usage", "get_table_stats"],
        IntentType.PARAMETER_QUERY: ["get_parameters"],
        IntentType.KNOWLEDGE_QA: ["search_knowledge"],
    }

    tools_to_call = tool_mapping.get(intent, [])
    state["tool_calls"] = []
    state["current_node"] = "select_tools"

    for tool_name in tools_to_call:
        call_record = {
            "tool_name": tool_name,
            "arguments": {},
            "timestamp": datetime.now().isoformat(),
        }

        # 如果需要实例参数，添加实例名称
        if target_instance and tool_name not in ["get_instance_list", "search_knowledge"]:
            call_record["arguments"]["instance_name"] = target_instance

        state["tool_calls"].append(call_record)

    logger.info(f"选择工具: {tools_to_call}")

    return state


def execute_tools(state: AgentState) -> AgentState:
    """执行工具调用"""
    logger.info("执行工具执行节点")

    tool_calls = state.get("tool_calls", [])
    state["tool_results"] = []
    state["current_node"] = "execute_tools"

    # 获取所有工具
    tools_dict = {tool.name: tool for tool in get_all_langchain_tools()}

    for call in tool_calls:
        tool_name = call.get("tool_name")
        arguments = call.get("arguments", {})

        logger.info(f"调用工具: {tool_name}, 参数: {arguments}")

        try:
            tool = tools_dict.get(tool_name)
            if tool:
                result = tool.invoke(arguments)
                state["tool_results"].append(result)
                call["result"] = result
                call["success"] = True
            else:
                state["tool_results"].append(f"错误: 工具 {tool_name} 不存在")
                call["success"] = False
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name} - {e}")
            state["tool_results"].append(f"错误: {str(e)}")
            call["success"] = False

    return state


def generate_response(state: AgentState) -> AgentState:
    """生成响应"""
    logger.info("执行响应生成节点")

    intent = state.get("intent")
    tool_results = state.get("tool_results", [])

    # 获取用户原始问题
    user_question = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            user_question = msg.content
            break

    # 构建上下文
    context = f"""
意图: {intent}
目标实例: {state.get('target_instance', '无')}
工具结果: {json.dumps(tool_results, ensure_ascii=False, indent=2) if tool_results else '无'}
"""

    # 使用LLM生成响应
    try:
        llm = get_llm()
        prompt = RESPONSE_GENERATION_PROMPT.format(
            user_question=user_question,
            intent=intent,
            tool_results=json.dumps(tool_results, ensure_ascii=False) if tool_results else "无",
        )

        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        response = llm.invoke(full_prompt)
        state["response"] = response

        # 添加AI消息到历史
        state["messages"].append(AIMessage(content=response))

    except Exception as e:
        logger.error(f"响应生成失败: {e}")
        state["response"] = f"生成响应时发生错误: {str(e)}"
        state["error"] = str(e)

    state["current_node"] = "respond"
    state["needs_tool_call"] = False

    return state


def handle_error(state: AgentState) -> AgentState:
    """处理错误"""
    logger.info("执行错误处理节点")

    error = state.get("error", "")

    response = f"处理请求时发生错误：{error}\n\n请检查输入是否正确，或稍后重试。"
    state["response"] = response
    state["messages"].append(AIMessage(content=response))
    state["current_node"] = "error"

    return state