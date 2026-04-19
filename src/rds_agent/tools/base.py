"""工具基类和注册机制。"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from langchain_core.tools import BaseTool, StructuredTool, tool
from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger

logger = get_logger("tools")


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool = Field(default=True, description="执行是否成功")
    data: Any = Field(default=None, description="返回数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    message: Optional[str] = Field(default=None, description="执行消息")


class BaseRDSTool(ABC):
    """RDS工具基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, *args, **kwargs) -> ToolResult:
        """执行工具"""
        pass

    def to_langchain_tool(self) -> BaseTool:
        """转换为LangChain工具"""
        return StructuredTool(
            name=self.name,
            description=self.description,
            func=self._run_wrapper,
        )

    def _run_wrapper(self, *args, **kwargs) -> str:
        """包装执行结果为字符串"""
        result = self.run(*args, **kwargs)
        if result.success:
            import json
            return json.dumps(result.data, ensure_ascii=False, indent=2)
        return f"错误: {result.error}"


# 工具注册表
_tool_registry: dict[str, BaseRDSTool] = {}


def register_tool(tool: BaseRDSTool) -> None:
    """注册工具"""
    _tool_registry[tool.name] = tool
    logger.debug(f"注册工具: {tool.name}")


def get_tool(name: str) -> Optional[BaseRDSTool]:
    """获取工具"""
    return _tool_registry.get(name)


def list_tools() -> list[str]:
    """列出所有工具"""
    return list(_tool_registry.keys())


def get_all_tools() -> list[BaseTool]:
    """获取所有LangChain工具"""
    return [t.to_langchain_tool() for t in _tool_registry.values()]