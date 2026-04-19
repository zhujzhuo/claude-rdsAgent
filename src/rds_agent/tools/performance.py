"""性能监控工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data import get_platform_client
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.performance")


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
def get_performance_metrics(instance_name: str) -> str:
    """获取MySQL实例的性能指标。

    包括QPS、TPS、Buffer Pool命中率、线程状态、IO统计等关键指标。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        性能指标的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        metrics = mysql_client.get_performance_metrics()
        mysql_client.close()

        result = {
            "instance": instance_name,
            "qps": metrics.qps,
            "tps": metrics.tps,
            "buffer_pool_hit_rate": f"{metrics.buffer_pool_hit_rate}%",
            "thread_running": metrics.thread_running,
            "thread_cached": metrics.thread_cached,
            "innodb_reads": metrics.innodb_reads,
            "innodb_writes": metrics.innodb_writes,
            "disk_reads": metrics.disk_reads,
            "disk_writes": metrics.disk_writes,
            "analysis": _analyze_performance(metrics),
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取性能指标失败: {instance_name} - {e}")
        return f"错误: 获取性能指标失败 - {str(e)}"


def _analyze_performance(metrics) -> dict:
    """分析性能指标"""
    analysis = {
        "status": "正常",
        "warnings": [],
        "suggestions": [],
    }

    # Buffer Pool命中率分析
    if metrics.buffer_pool_hit_rate < 95:
        analysis["warnings"].append(
            f"Buffer Pool命中率偏低({metrics.buffer_pool_hit_rate}%)"
        )
        analysis["suggestions"].append(
            "建议增大innodb_buffer_pool_size参数"
        )

    # 线程状态分析
    if metrics.thread_running > 50:
        analysis["warnings"].append(
            f"活跃线程数较高({metrics.thread_running})"
        )
        analysis["suggestions"].append(
            "检查是否有大量并发查询或锁等待"
        )

    # IO分析
    if metrics.disk_reads > metrics.innodb_reads * 0.1:
        analysis["warnings"].append("磁盘读取比例较高")
        analysis["suggestions"].append(
            "检查Buffer Pool配置和查询是否有大量扫描"
        )

    if analysis["warnings"]:
        analysis["status"] = "需要关注"

    return analysis


@tool
def get_innodb_status(instance_name: str) -> str:
    """获取MySQL InnoDB引擎状态。

    包括缓冲池状态、锁等待、事务信息、日志状态等。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        InnoDB状态信息
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        status = mysql_client.get_innodb_status()
        mysql_client.close()

        if not status:
            return "无法获取InnoDB状态"

        # 解析关键信息
        result = {
            "instance": instance_name,
            "raw_status": status[:2000],  # 截取前2000字符
            "summary": _parse_innodb_status(status),
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取InnoDB状态失败: {instance_name} - {e}")
        return f"错误: 获取InnoDB状态失败 - {str(e)}"


def _parse_innodb_status(status: str) -> dict:
    """解析InnoDB状态"""
    summary = {}

    # 提取缓冲池信息
    if "Buffer pool size" in status:
        for line in status.split("\n"):
            if "Buffer pool size" in line:
                summary["buffer_pool"] = line.strip()
            if "Buffer pool hit rate" in line:
                summary["hit_rate"] = line.strip()
            if "transactions" in line.lower():
                summary["transactions"] = line.strip()

    return summary