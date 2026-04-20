"""Hermes Function Schema 定义 - OpenAI 格式的工具定义。

Hermes 模型使用 OpenAI 兼容的 Function Calling 格式，支持:
- 函数名称和描述
- 参数定义 (JSON Schema)
- 必填参数标记
- 多工具并行调用
"""

from typing import Any, Callable, Dict, List, Optional, TypedDict
from dataclasses import dataclass, field
import json


class FunctionParameter(TypedDict, total=False):
    """函数参数定义"""
    type: str
    description: str
    enum: Optional[List[str]]
    default: Optional[Any]


class FunctionDefinition(TypedDict, total=False):
    """函数定义 (OpenAI 格式)"""
    name: str
    description: str
    parameters: Dict[str, Any]


class ToolDefinition(TypedDict):
    """工具定义 (OpenAI 格式)"""
    type: str
    function: FunctionDefinition


@dataclass
class FunctionSchema:
    """Function Schema 封装类"""

    name: str
    description: str
    parameters: Dict[str, FunctionParameter]
    required: List[str] = field(default_factory=list)
    handler: Optional[Callable] = None

    def to_openai_format(self) -> ToolDefinition:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                }
            }
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_openai_format(), ensure_ascii=False)

    def execute(self, **kwargs) -> Any:
        """执行函数"""
        if self.handler is None:
            raise ValueError(f"Function {self.name} has no handler")
        return self.handler(**kwargs)


class ToolRegistry:
    """工具注册中心 - 管理所有可用的 Function Calling 工具"""

    def __init__(self):
        self._tools: Dict[str, FunctionSchema] = {}

    def register(self, schema: FunctionSchema) -> None:
        """注册工具"""
        self._tools[schema.name] = schema

    def register_function(
        self,
        name: str,
        description: str,
        parameters: Dict[str, FunctionParameter],
        required: List[str],
        handler: Callable,
    ) -> None:
        """快捷注册函数"""
        schema = FunctionSchema(
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            handler=handler,
        )
        self.register(schema)

    def get(self, name: str) -> Optional[FunctionSchema]:
        """获取工具"""
        return self._tools.get(name)

    def get_all_schemas(self) -> List[ToolDefinition]:
        """获取所有工具的 OpenAI 格式定义"""
        return [schema.to_openai_format() for schema in self._tools.values()]

    def get_all_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())

    def execute(self, name: str, **kwargs) -> Any:
        """执行指定工具"""
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool {name} not found")
        return tool.execute(**kwargs)

    def count(self) -> int:
        """获取工具数量"""
        return len(self._tools)

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()


# 全局工具注册中心
_global_registry: Optional[ToolRegistry] = None


def get_global_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry