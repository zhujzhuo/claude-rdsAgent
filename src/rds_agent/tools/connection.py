"""连接诊断工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data import get_platform_client
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.connection")


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
def get_connection_status(instance_name: str) -> str:
    """获取MySQL实例的连接状态。

    包括最大连接数、当前连接数、活跃连接、连接错误数等。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        连接状态的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        status = mysql_client.get_connection_status()
        mysql_client.close()

        result = {
            "instance": instance_name,
            "max_connections": status.max_connections,
            "current_connections": status.current_connections,
            "active_connections": status.active_connections,
            "idle_connections": status.idle_connections,
            "connection_usage_ratio": f"{status.connection_usage_ratio}%",
            "connection_errors": status.connection_errors,
            "aborted_connections": status.aborted_connections,
            "analysis": _analyze_connection_status(status),
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取连接状态失败: {instance_name} - {e}")
        return f"错误: 获取连接状态失败 - {str(e)}"


def _analyze_connection_status(status) -> dict:
    """分析连接状态"""
    analysis = {
        "status": "正常",
        "warnings": [],
        "suggestions": [],
    }

    # 连接使用率分析
    if status.connection_usage_ratio > 80:
        analysis["status"] = "告警"
        analysis["warnings"].append(
            f"连接使用率过高({status.connection_usage_ratio}%)"
        )
        analysis["suggestions"].append(
            "建议增大max_connections参数或优化应用连接池配置"
        )
    elif status.connection_usage_ratio > 60:
        analysis["status"] = "需要关注"
        analysis["warnings"].append(
            f"连接使用率较高({status.connection_usage_ratio}%)"
        )

    # 连接错误分析
    if status.connection_errors > 100:
        analysis["warnings"].append(
            f"连接错误数较多({status.connection_errors})"
        )
        analysis["suggestions"].append(
            "检查网络稳定性或客户端配置"
        )

    # 中断连接分析
    if status.aborted_connections > 50:
        analysis["warnings"].append(
            f"中断连接数较多({status.aborted_connections})"
        )
        analysis["suggestions"].append(
            "检查是否有客户端异常断开或超时配置问题"
        )

    return analysis


@tool
def get_lock_info(instance_name: str) -> str:
    """获取MySQL实例的锁等待信息。

    检查是否存在锁等待或死锁情况。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        锁等待信息的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        lock_info = mysql_client.get_lock_info()
        processlist = mysql_client.get_processlist()
        mysql_client.close()

        # 查找锁等待的进程
        locked_processes = [
            p for p in processlist
            if p.get("State") and ("lock" in p.get("State", "").lower() or "waiting" in p.get("State", "").lower())
        ]

        result = {
            "instance": instance_name,
            "lock_waits_detected": len(lock_info),
            "locked_processes": len(locked_processes),
            "lock_details": lock_info[:5] if lock_info else [],  # 只显示前5个
            "waiting_processes": [
                {
                    "id": p.get("Id"),
                    "user": p.get("User"),
                    "state": p.get("State"),
                    "time_seconds": p.get("Time", 0),
                    "sql": p.get("Info", "")[:100] if p.get("Info") else "",
                }
                for p in locked_processes[:10]
            ],
            "analysis": _analyze_lock_info(lock_info, locked_processes),
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取锁信息失败: {instance_name} - {e}")
        return f"错误: 获取锁信息失败 - {str(e)}"


def _analyze_lock_info(lock_info: list, locked_processes: list) -> dict:
    """分析锁信息"""
    analysis = {
        "status": "正常",
        "warnings": [],
        "suggestions": [],
    }

    if lock_info:
        analysis["status"] = "告警"
        analysis["warnings"].append(
            f"发现{len(lock_info)}个锁等待"
        )
        analysis["suggestions"].append(
            "建议检查长时间运行的UPDATE/DELETE操作，考虑优化事务逻辑"
        )

    long_locked = [p for p in locked_processes if p.get("Time", 0) > 30]
    if long_locked:
        analysis["warnings"].append(
            f"发现{len(long_locked)}个长时间锁等待进程(>30秒)"
        )
        analysis["suggestions"].append(
            "考虑kill长时间锁等待的进程，或检查相关事务的执行计划"
        )

    return analysis