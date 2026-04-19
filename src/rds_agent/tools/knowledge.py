"""知识库检索工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data.vector_store import get_knowledge_store
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.knowledge")


@tool
def search_knowledge(query: str, top_k: int = 5) -> str:
    """从MySQL运维知识库中检索相关信息。

    用于回答MySQL相关的技术问题，如参数配置、性能优化、故障处理等。

    Args:
        query: 查询问题，如"如何优化慢查询"
        top_k: 返回结果数量，默认5

    Returns:
        相关知识文档的内容
    """
    try:
        store = get_knowledge_store()
        results = store.search(query, k=top_k)

        if not results:
            return f"知识库中未找到与 '{query}' 相关的信息"

        response = {
            "query": query,
            "total_results": len(results),
            "results": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "source": doc.metadata.get("source", "未知"),
                }
                for doc in results
            ],
        }

        return json.dumps(response, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"知识库检索失败: {query} - {e}")
        return f"错误: 知识库检索失败 - {str(e)}"


@tool
def search_mysql_performance_knowledge(query: str) -> str:
    """检索MySQL性能优化相关知识。

    Args:
        query: 性能相关问题

    Returns:
        性能优化相关知识
    """
    return search_knowledge.invoke({
        "query": f"性能优化 {query}",
        "top_k": 3
    })


@tool
def search_mysql_troubleshooting_knowledge(query: str) -> str:
    """检索MySQL故障处理相关知识。

    Args:
        query: 故障相关问题

    Returns:
        故障处理相关知识
    """
    return search_knowledge.invoke({
        "query": f"故障处理 {query}",
        "top_k": 3
    })


@tool
def search_mysql_parameter_knowledge(param_name: str) -> str:
    """检索MySQL参数配置相关知识。

    Args:
        param_name: 参数名称

    Returns:
        参数配置相关知识
    """
    return search_knowledge.invoke({
        "query": f"参数配置 {param_name}",
        "top_k": 3
    })