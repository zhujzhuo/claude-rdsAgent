"""存储空间分析工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data import get_platform_client
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.storage")


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
def get_storage_usage(instance_name: str) -> str:
    """获取MySQL实例的存储空间使用情况。

    包括总大小、数据库大小、最大的表等信息。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        存储使用情况的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        storage = mysql_client.get_storage_usage()
        mysql_client.close()

        result = {
            "instance": instance_name,
            "total_size_gb": storage.total_size_gb,
            "used_size_gb": storage.used_size_gb,
            "database_count": storage.database_count,
            "table_count": storage.table_count,
            "largest_tables": storage.largest_tables[:10],
            "analysis": _analyze_storage(storage),
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取存储使用情况失败: {instance_name} - {e}")
        return f"错误: 获取存储使用情况失败 - {str(e)}"


def _analyze_storage(storage) -> dict:
    """分析存储情况"""
    analysis = {
        "status": "正常",
        "warnings": [],
        "suggestions": [],
    }

    # 表数量过多
    if storage.table_count > 1000:
        analysis["warnings"].append(
            f"表数量较多({storage.table_count})"
        )
        analysis["suggestions"].append(
            "建议评估是否需要清理无用表或分库分表"
        )

    # 大表分析
    if storage.largest_tables:
        for table in storage.largest_tables[:3]:
            size_mb = float(table.get("total_size_mb", 0))
            if size_mb > 1024:  # 超过1GB
                analysis["warnings"].append(
                    f"大表 {table.get('schema_name')}.{table.get('table_name')} 大小 {size_mb:.2f}MB"
                )
                analysis["suggestions"].append(
                    f"建议对 {table.get('table_name')} 进行归档或分区"
                )

    return analysis


@tool
def get_table_stats(instance_name: str, schema_name: Optional[str] = None) -> str:
    """获取MySQL实例的表统计信息。

    包括表大小、行数、索引大小、碎片等详细信息。

    Args:
        instance_name: 实例名称或实例ID
        schema_name: 数据库名（可选，不指定则返回所有库）

    Returns:
        表统计信息的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        table_stats = mysql_client.get_table_stats(schema_name)
        mysql_client.close()

        if not table_stats:
            return f"实例 '{instance_name}' 暂无表统计信息"

        result = {
            "instance": instance_name,
            "schema_filter": schema_name or "全部",
            "total_tables": len(table_stats),
            "tables": [
                {
                    "schema": ts.schema_name,
                    "table": ts.table_name,
                    "rows": ts.table_rows,
                    "data_size_mb": ts.data_size_mb,
                    "index_size_mb": ts.index_size_mb,
                    "total_size_mb": round(ts.data_size_mb + ts.index_size_mb, 2),
                    "data_free_mb": ts.data_free_mb,
                    "engine": ts.engine,
                    "fragmentation_ratio": round(ts.data_free_mb / (ts.data_size_mb + 1), 2) * 100,
                }
                for ts in table_stats[:30]  # 只显示前30个
            ],
            "fragmented_tables": [
                {
                    "schema": ts.schema_name,
                    "table": ts.table_name,
                    "fragmentation_mb": ts.data_free_mb,
                }
                for ts in table_stats
                if ts.data_free_mb > 100  # 碎片超过100MB
            ][:10],
            "analysis": _analyze_table_stats(table_stats),
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取表统计信息失败: {instance_name} - {e}")
        return f"错误: 获取表统计信息失败 - {str(e)}"


def _analyze_table_stats(table_stats: list) -> dict:
    """分析表统计"""
    analysis = {
        "total_data_size_mb": 0,
        "total_index_size_mb": 0,
        "total_fragmentation_mb": 0,
        "high_fragmentation_tables": 0,
        "suggestions": [],
    }

    for ts in table_stats:
        analysis["total_data_size_mb"] += ts.data_size_mb
        analysis["total_index_size_mb"] += ts.index_size_mb
        analysis["total_fragmentation_mb"] += ts.data_free_mb
        if ts.data_free_mb > 100:
            analysis["high_fragmentation_tables"] += 1

    # 碎片率分析
    if analysis["high_fragmentation_tables"] > 0:
        analysis["suggestions"].append(
            f"发现{analysis['high_fragmentation_tables']}个高碎片表，建议执行OPTIMIZE TABLE"
        )

    # 索引占比分析
    total = analysis["total_data_size_mb"] + analysis["total_index_size_mb"]
    if total > 0:
        index_ratio = analysis["total_index_size_mb"] / total * 100
        if index_ratio > 50:
            analysis["suggestions"].append(
                f"索引占比较高({index_ratio:.1f}%)，建议检查是否有冗余索引"
            )

    return analysis


@tool
def get_index_usage(instance_name: str) -> str:
    """获取MySQL实例的索引使用情况统计。

    分析索引的有效性和使用频率。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        索引使用情况的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        # 查询索引统计信息
        sql = """
        SELECT
            OBJECT_SCHEMA as schema_name,
            OBJECT_NAME as table_name,
            INDEX_NAME as index_name,
            COUNT_STAR as usage_count,
            SUM_TIMER_WAIT/1000000000 as total_time_ms
        FROM performance_schema.table_io_waits_summary_by_index_usage
        WHERE INDEX_NAME IS NOT NULL
        AND OBJECT_SCHEMA NOT IN ('mysql', 'performance_schema', 'information_schema')
        ORDER BY COUNT_STAR DESC
        LIMIT 50
        """
        results = mysql_client.execute_query(sql)

        # 查询从未使用的索引
        unused_sql = """
        SELECT
            s.table_schema as schema_name,
            s.table_name as table_name,
            s.index_name as index_name,
            s.non_unique,
            s.seq_in_index,
            s.column_name
        FROM information_schema.statistics s
        LEFT JOIN performance_schema.table_io_waits_summary_by_index_usage p
        ON s.table_schema = p.OBJECT_SCHEMA
        AND s.table_name = p.OBJECT_NAME
        AND s.index_name = p.INDEX_NAME
        WHERE s.table_schema NOT IN ('mysql', 'performance_schema', 'information_schema')
        AND p.COUNT_STAR IS NULL OR p.COUNT_STAR = 0
        AND s.index_name != 'PRIMARY'
        """
        unused_results = mysql_client.execute_query(unused_sql)

        mysql_client.close()

        result = {
            "instance": instance_name,
            "top_used_indexes": [
                {
                    "schema": r.get("schema_name"),
                    "table": r.get("table_name"),
                    "index": r.get("index_name"),
                    "usage_count": r.get("usage_count", 0),
                }
                for r in results[:20]
            ],
            "unused_indexes": [
                {
                    "schema": r.get("schema_name"),
                    "table": r.get("table_name"),
                    "index": r.get("index_name"),
                    "column": r.get("column_name"),
                }
                for r in unused_results[:20]
            ],
            "analysis": {
                "unused_index_count": len(unused_results),
                "suggestions": [
                    f"发现{len(unused_results)}个未使用索引，建议评估是否删除冗余索引"
                ] if unused_results else [],
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取索引使用情况失败: {instance_name} - {e}")
        return f"错误: 获取索引使用情况失败 - {str(e)}"