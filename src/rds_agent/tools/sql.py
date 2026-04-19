"""SQL诊断工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data import get_platform_client
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.sql")


def _get_mysql_client(instance_name: str) -> tuple[Optional[MySQLClient], str]:
    """获取MySQL客户端的辅助函数"""
    platform_client = get_platform_client()
    instance = platform_client.search_instance_by_name(instance_name)

    if not instance:
        platform_client.close()
        return None, f"错误: 未找到实例 '{instance_name}'"

    conn_config = platform_client.get_instance_connection(instance.id)
    platform_client.close()

    if not conn_config:
        return None, f"错误: 无法获取实例 '{instance_name}' 的连接配置"

    return MySQLClient(conn_config), ""


@tool
def get_slow_queries(
    instance_name: str,
    limit: int = 10,
    min_time: float = 1.0
) -> str:
    """获取MySQL实例的慢查询列表。

    从performance_schema获取执行时间超过阈值的SQL语句。

    Args:
        instance_name: 实例名称或实例ID
        limit: 返回条数，默认10
        min_time: 最小执行时间(秒)，默认1.0

    Returns:
        慢查询列表的JSON字符串，包含SQL文本、执行时间、扫描行数等
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        slow_queries = mysql_client.get_slow_queries(limit=limit, min_time=min_time)
        mysql_client.close()

        if not slow_queries:
            return f"实例 '{instance_name}' 暂无慢查询记录（阈值: {min_time}秒）"

        result = {
            "instance": instance_name,
            "threshold_seconds": min_time,
            "total_count": len(slow_queries),
            "queries": [
                {
                    "sql_text": sq.sql_text[:200] + "..." if len(sq.sql_text) > 200 else sq.sql_text,
                    "avg_time_seconds": round(sq.query_time, 3),
                    "rows_examined": sq.rows_examined,
                    "rows_sent": sq.rows_sent,
                    "last_seen": sq.timestamp,
                    "scan_ratio": round(sq.rows_examined / sq.rows_sent, 2) if sq.rows_sent > 0 else 0,
                    "analysis": _analyze_slow_query(sq),
                }
                for sq in slow_queries
            ],
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取慢查询失败: {instance_name} - {e}")
        return f"错误: 获取慢查询失败 - {str(e)}"


def _analyze_slow_query(query) -> dict:
    """分析单个慢查询"""
    analysis = {
        "type": "未知",
        "suggestions": [],
    }

    sql_lower = query.sql_text.lower()

    # 判断查询类型
    if "select" in sql_lower:
        analysis["type"] = "SELECT查询"

        # 扫描行数与返回行数比例分析
        if query.rows_sent > 0:
            scan_ratio = query.rows_examined / query.rows_sent
            if scan_ratio > 100:
                analysis["suggestions"].append(
                    f"扫描/返回比例过高({scan_ratio:.1f})，可能缺少索引或索引失效"
                )
            elif scan_ratio > 10:
                analysis["suggestions"].append(
                    "扫描行数较多，建议检查查询条件和索引"
                )

        if "join" in sql_lower:
            analysis["suggestions"].append(
                "涉及JOIN操作，建议检查连接条件和关联表的索引"
            )

        if "like" in sql_lower and "%" in sql_lower:
            analysis["suggestions"].append(
                "使用LIKE模糊匹配，可能导致索引失效"
            )

        if "order by" in sql_lower:
            analysis["suggestions"].append(
                "包含ORDER BY，建议检查排序字段是否有索引"
            )

    elif "insert" in sql_lower:
        analysis["type"] = "INSERT操作"
        analysis["suggestions"].append("批量插入建议使用批量INSERT语句")

    elif "update" in sql_lower or "delete" in sql_lower:
        analysis["type"] = "UPDATE/DELETE操作"
        analysis["suggestions"].append(
            "检查WHERE条件的索引，避免全表扫描"
        )

    if query.query_time > 5:
        analysis["suggestions"].append(
            f"执行时间较长({query.query_time:.1f}秒)，建议重点优化"
        )

    return analysis


@tool
def analyze_processlist(instance_name: str) -> str:
    """分析MySQL实例当前的执行进程。

    获取当前正在执行的SQL语句和会话状态。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        进程列表分析结果
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        processlist = mysql_client.get_processlist()
        mysql_client.close()

        if not processlist:
            return f"实例 '{instance_name}' 当前无活跃进程"

        # 分析进程列表
        analysis = {
            "instance": instance_name,
            "total_processes": len(processlist),
            "by_command": {},
            "by_state": {},
            "long_running": [],
            "locked": [],
        }

        for proc in processlist:
            command = proc.get("Command", "")
            state = proc.get("State", "")
            time = proc.get("Time", 0)
            info = proc.get("Info", "")

            # 按命令类型统计
            analysis["by_command"][command] = analysis["by_command"].get(command, 0) + 1

            # 按状态统计
            if state:
                analysis["by_state"][state] = analysis["by_state"].get(state, 0) + 1

            # 长时间运行的查询
            if time > 60 and command == "Query":
                analysis["long_running"].append({
                    "id": proc.get("Id"),
                    "user": proc.get("User"),
                    "time_seconds": time,
                    "sql": info[:100] if info else "",
                })

            # 锁等待状态
            if state and ("lock" in state.lower() or "waiting" in state.lower()):
                analysis["locked"].append({
                    "id": proc.get("Id"),
                    "user": proc.get("User"),
                    "state": state,
                    "time_seconds": time,
                })

        return json.dumps(analysis, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"分析进程列表失败: {instance_name} - {e}")
        return f"错误: 分析进程列表失败 - {str(e)}"