"""Agent状态定义。"""

from enum import Enum
from typing import Annotated, Any, Optional

from langchain_core.messages import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class IntentType(str, Enum):
    """用户意图类型"""

    INSTANCE_QUERY = "instance_query"  # 实例信息查询
    PERFORMANCE_DIAG = "performance_diag"  # 性能诊断
    SQL_DIAG = "sql_diag"  # SQL诊断
    CONNECTION_DIAG = "connection_diag"  # 连接诊断
    STORAGE_DIAG = "storage_diag"  # 存储分析
    PARAMETER_QUERY = "parameter_query"  # 参数查询
    KNOWLEDGE_QA = "knowledge_qa"  # 知识问答
    GENERAL_CHAT = "general_chat"  # 通用聊天
    UNKNOWN = "unknown"  # 未识别


class AgentState(TypedDict):
    """Agent状态定义"""

    # 消息历史（使用add_messages自动合并）
    messages: Annotated[list[BaseMessage], add_messages]

    # 当前意图
    intent: IntentType

    # 目标实例名称
    target_instance: Optional[str]

    # 工具调用记录
    tool_calls: list[dict]

    # 工具执行结果
    tool_results: list[str]

    # 上下文信息
    context: dict[str, Any]

    # 当前节点
    current_node: str

    # 是否需要调用工具
    needs_tool_call: bool

    # 响应内容
    response: Optional[str]

    # 错误信息
    error: Optional[str]


class ConversationContext(BaseModel):
    """对话上下文"""

    session_id: str = Field(default="", description="会话ID")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    current_instance: Optional[str] = Field(default=None, description="当前操作的实例")
    mentioned_instances: list[str] = Field(default_factory=list, description="提及过的实例")
    previous_intents: list[IntentType] = Field(default_factory=list, description="之前的意图")
    turn_count: int = Field(default=0, description="对话轮数")


class ToolCallRecord(BaseModel):
    """工具调用记录"""

    tool_name: str = Field(..., description="工具名称")
    arguments: dict = Field(default_factory=dict, description="调用参数")
    result: Optional[str] = Field(default=None, description="执行结果")
    success: bool = Field(default=True, description="是否成功")
    timestamp: str = Field(default="", description="调用时间")