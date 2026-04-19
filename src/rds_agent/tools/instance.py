"""实例信息工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data import (
    InstanceInfo,
    InstancePlatformClient,
    MockInstancePlatformClient,
    get_platform_client,
)
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.tools.base import ToolResult
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.instance")


@tool
def get_instance_list() -> str:
    """获取所有MySQL实例列表。

    返回所有可查询的MySQL实例信息，包括实例ID、名称、状态等。

    Returns:
        实例列表的JSON字符串
    """
    try:
        client = get_platform_client()
        instances = client.list_instances()
        client.close()

        result = [
            {
                "id": inst.id,
                "name": inst.name,
                "host": inst.host,
                "port": inst.port,
                "version": inst.version,
                "status": inst.status,
                "architecture": inst.architecture,
                "spec": inst.spec,
            }
            for inst in instances
        ]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取实例列表失败: {e}")
        return f"错误: 获取实例列表失败 - {str(e)}"


@tool
def get_instance_info(instance_name: str) -> str:
    """获取指定MySQL实例的详细信息。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        实例详细信息的JSON字符串，包括规格、版本、架构、存储等
    """
    try:
        client = get_platform_client()

        # 搜索实例
        instance = client.search_instance_by_name(instance_name)
        if not instance:
            client.close()
            return f"错误: 未找到实例 '{instance_name}'"

        result = {
            "id": instance.id,
            "name": instance.name,
            "host": instance.host,
            "port": instance.port,
            "version": instance.version,
            "architecture": instance.architecture,
            "spec": instance.spec,
            "storage_size_gb": instance.storage_size,
            "status": instance.status,
            "region": instance.region,
            "zone": instance.zone,
            "create_time": instance.create_time,
        }

        client.close()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取实例信息失败: {instance_name} - {e}")
        return f"错误: 获取实例信息失败 - {str(e)}"


@tool
def get_mysql_version(instance_name: str) -> str:
    """获取MySQL实例的版本信息。

    Args:
        instance_name: 实例名称或实例ID

    Returns:
        MySQL版本信息
    """
    try:
        platform_client = get_platform_client()
        instance = platform_client.search_instance_by_name(instance_name)

        if not instance:
            platform_client.close()
            return f"错误: 未找到实例 '{instance_name}'"

        # 获取连接配置
        conn_config = platform_client.get_instance_connection(instance.id)
        platform_client.close()

        if not conn_config:
            return f"错误: 无法获取实例 '{instance_name}' 的连接配置"

        # 直连MySQL获取版本
        mysql_client = MySQLClient(conn_config)
        version = mysql_client.get_version()
        mysql_client.close()

        return f"实例 '{instance_name}' 的MySQL版本: {version}"
    except Exception as e:
        logger.error(f"获取MySQL版本失败: {instance_name} - {e}")
        return f"错误: 获取MySQL版本失败 - {str(e)}"