"""参数优化分析工具 - 自动分析MySQL参数配置并提供优化建议。"""

import json
from typing import Optional, Union, Dict, Any

from langchain_core.tools import tool

from rds_agent.data import MySQLClient, get_platform_client
from rds_agent.data.models import ParameterInfo
from rds_agent.utils.logger import get_logger

logger = get_logger("parameter_optimizer")


# 参数检查辅助函数
def check_buffer_pool_size(v: str, context: dict) -> dict:
    """检查Buffer Pool大小"""
    memory_gb = context.get("memory_gb")
    if memory_gb and int(v) >= memory_gb * 0.7 * 1024**3:
        score = 100
    else:
        score = 50
    return {
        "score": score,
        "suggestion": f"当前值: {int(v)/1024**3:.1f}GB, 建议设置为内存({context.get('memory_gb', '未知')}GB)的70-80%"
    }


def check_max_connections(v: str, context: dict) -> dict:
    """检查最大连接数"""
    score = 100 if int(v) >= 500 else 70
    return {
        "score": score,
        "suggestion": f"当前值: {v}, 建议根据应用并发量设置，一般500-1000"
    }


def check_flush_log_trx(v: str, context: dict) -> dict:
    """检查事务日志刷盘策略"""
    if v == "1":
        score = 100
    elif v == "2":
        score = 80
    else:
        score = 60
    return {
        "score": score,
        "suggestion": f"当前: {v}, 建议生产环境设为1(最安全)或2(高性能)"
    }


def check_sync_binlog(v: str, context: dict) -> dict:
    """检查Binlog同步策略"""
    score = 100 if v == "1" else 70
    return {
        "score": score,
        "suggestion": f"当前: {v}, 主从复制场景建议设为1"
    }


def check_log_file_size(v: str, context: dict) -> dict:
    """检查日志文件大小"""
    buffer_pool = context.get("innodb_buffer_pool_size", 8 * 1024**3)
    ideal = buffer_pool * 0.25
    score = 100 if int(v) >= ideal * 0.8 else 60
    return {
        "score": score,
        "suggestion": f"当前: {int(v)/1024**3:.2f}GB, 建议设置为Buffer Pool({buffer_pool/1024**3:.1f}GB)的25%"
    }


def check_slow_query_log(v: str, context: dict) -> dict:
    """检查慢查询日志开关"""
    score = 100 if v.upper() == "ON" else 30
    return {
        "score": score,
        "suggestion": "建议开启慢查询日志以便监控性能"
    }


def check_long_query_time(v: str, context: dict) -> dict:
    """检查慢查询阈值"""
    val = float(v)
    if val <= 3:
        score = 100
    elif val <= 5:
        score = 70
    else:
        score = 40
    return {
        "score": score,
        "suggestion": f"当前: {v}秒, 建议设置为1-3秒以便捕获更多慢查询"
    }


def check_lock_wait_timeout(v: str, context: dict) -> dict:
    """检查锁等待超时"""
    score = 100 if int(v) <= 50 else 80
    return {
        "score": score,
        "suggestion": f"当前: {v}秒, 建议根据业务特点调整，一般不超过120秒"
    }


def check_max_allowed_packet(v: str, context: dict) -> dict:
    """检查最大数据包"""
    size_mb = int(v) / 1024**2
    score = 100 if size_mb >= 16 else 60
    return {
        "score": score,
        "suggestion": f"当前: {size_mb:.1f}MB, 建议设置为16MB或更大"
    }


def check_tmp_table_size(v: str, context: dict) -> dict:
    """检查临时表大小"""
    heap_size = context.get("max_heap_table_size", 16 * 1024**2)
    score = 100 if int(v) == heap_size else 70
    return {
        "score": score,
        "suggestion": f"当前: {int(v)/1024**2:.1f}MB, 建议与max_heap_table_size保持一致"
    }


def check_wait_timeout(v: str, context: dict) -> dict:
    """检查连接超时时间"""
    hours = int(v) / 3600
    if hours <= 2:
        score = 100
    elif hours <= 8:
        score = 80
    else:
        score = 60
    return {
        "score": score,
        "suggestion": f"当前: {hours:.1f}小时, 建议降低到1-2小时释放空闲连接"
    }


def check_query_cache_type(v: str, context: dict) -> dict:
    """检查查询缓存类型"""
    version = context.get("version", "")
    if "8.0" in version or v.upper() == "OFF":
        score = 100
    else:
        score = 60
    if "8.0" in version:
        suggestion = "MySQL 8.0已废弃查询缓存，建议关闭"
    else:
        suggestion = "查询缓存效果有限，建议关闭"
    return {
        "score": score,
        "suggestion": suggestion
    }


# 参数优化规则库
PARAMETER_OPTIMIZATION_RULES: Dict[str, Dict[str, Any]] = {
    "innodb_buffer_pool_size": {
        "description": "InnoDB缓冲池大小",
        "unit": "字节",
        "recommend_rule": "建议设置为物理内存的70-80%",
        "check_function": check_buffer_pool_size,
        "safe_range": lambda context: (context.get("memory_gb", 8) * 0.5 * 1024**3, context.get("memory_gb", 8) * 0.85 * 1024**3),
    },

    "max_connections": {
        "description": "最大连接数",
        "unit": "个",
        "recommend_rule": "根据应用并发需求设置，一般500-1000",
        "check_function": check_max_connections,
        "safe_range": (100, 2000),
    },

    "innodb_flush_log_at_trx_commit": {
        "description": "事务日志刷盘策略",
        "recommend_rule": "高安全场景设为1，高性能场景可设为2",
        "check_function": check_flush_log_trx,
        "safe_values": ["1", "2"],
        "risk_levels": {"0": "高风险(可能丢失数据)", "1": "安全", "2": "较安全"},
    },

    "sync_binlog": {
        "description": "Binlog同步策略",
        "recommend_rule": "高安全场景设为1，高性能场景可设为0",
        "check_function": check_sync_binlog,
        "safe_values": ["1"],
        "risk_levels": {"0": "有风险(OS崩溃可能丢失数据)", "1": "安全"},
    },

    "innodb_log_file_size": {
        "description": "InnoDB日志文件大小",
        "unit": "字节",
        "recommend_rule": "建议设置为Buffer Pool的25%",
        "check_function": check_log_file_size,
        "safe_range": (256 * 1024**2, 4 * 1024**3),  # 256MB - 4GB
    },

    "slow_query_log": {
        "description": "慢查询日志开关",
        "recommend_rule": "建议开启",
        "check_function": check_slow_query_log,
        "safe_values": ["ON"],
    },

    "long_query_time": {
        "description": "慢查询阈值",
        "unit": "秒",
        "recommend_rule": "建议设置为1-3秒",
        "check_function": check_long_query_time,
        "safe_range": (0.1, 10.0),
    },

    "innodb_lock_wait_timeout": {
        "description": "锁等待超时",
        "unit": "秒",
        "recommend_rule": "默认50秒，可根据业务调整",
        "check_function": check_lock_wait_timeout,
        "safe_range": (10, 120),
    },

    "max_allowed_packet": {
        "description": "最大数据包",
        "unit": "字节",
        "recommend_rule": "建议16MB或更大",
        "check_function": check_max_allowed_packet,
        "safe_range": (4 * 1024**2, 64 * 1024**2),  # 4MB - 64MB
    },

    "tmp_table_size": {
        "description": "临时表大小",
        "unit": "字节",
        "recommend_rule": "建议与max_heap_table_size一致",
        "check_function": check_tmp_table_size,
        "safe_range": (16 * 1024**2, 256 * 1024**2),  # 16MB - 256MB
    },

    "wait_timeout": {
        "description": "连接超时时间",
        "unit": "秒",
        "recommend_rule": "建议适当降低，如8小时改为1-2小时",
        "check_function": check_wait_timeout,
        "safe_range": (3600, 28800),  # 1小时 - 8小时
    },

    "query_cache_type": {
        "description": "查询缓存类型(MySQL 5.7)",
        "recommend_rule": "MySQL 5.7可设为OFF，8.0已废弃",
        "check_function": check_query_cache_type,
        "safe_values": ["OFF"],
    },
}


class ParameterOptimizer:
    """参数优化分析器"""

    def __init__(self, mysql_client: MySQLClient, context: dict = None):
        """初始化优化器"""
        self.mysql_client = mysql_client
        self.context = context or {}

    def analyze_all_parameters(self) -> dict:
        """分析所有关键参数"""
        # 获取所有参数
        variables = self.mysql_client.get_system_variables()
        status = self.mysql_client.get_status_variables()

        # 增强上下文
        context = self._enhance_context(variables, status)

        # 分析结果
        results: Dict[str, Any] = {
            "instance": self.context.get("instance_name", "unknown"),
            "timestamp": context.get("timestamp"),
            "parameters": [],
            "overall_score": 0,
            "critical_params": [],
            "warnings": [],
            "suggestions": [],
        }

        total_score = 0
        analyzed_count = 0

        for param_name, rule in PARAMETER_OPTIMIZATION_RULES.items():
            if param_name in variables:
                value = variables[param_name]

                # 执行检查
                check_result = rule["check_function"](value, context)

                param_result = {
                    "name": param_name,
                    "current_value": value,
                    "description": rule.get("description", ""),
                    "recommend_rule": rule.get("recommend_rule", ""),
                    "unit": rule.get("unit", ""),
                    "score": check_result.get("score", 100),
                    "suggestion": check_result.get("suggestion", ""),
                    "safe_range": rule.get("safe_range", ""),
                }

                results["parameters"].append(param_result)
                total_score += param_result["score"]
                analyzed_count += 1

                # 汇总严重参数
                if param_result["score"] < 50:
                    results["critical_params"].append(param_name)
                    results["suggestions"].append(check_result["suggestion"])

                elif param_result["score"] < 80:
                    results["warnings"].append(f"{param_name}: {check_result.get('suggestion', '')}")

        # 计算总分
        results["overall_score"] = int(total_score / analyzed_count) if analyzed_count > 0 else 0

        return results

    def _enhance_context(self, variables: dict, status: dict) -> dict:
        """增强上下文信息"""
        context = self.context.copy()

        # 添加版本
        context["version"] = variables.get("version", "")

        # 计算Buffer Pool大小（GB）
        buffer_pool = int(variables.get("innodb_buffer_pool_size", 0))
        context["innodb_buffer_pool_size"] = buffer_pool
        context["buffer_pool_gb"] = buffer_pool / 1024**3

        # 从状态变量获取内存相关信息
        # 这里假设实例规格可以从外部获取，否则使用Buffer Pool推算
        if not context.get("memory_gb"):
            # 假设Buffer Pool是内存的75%
            context["memory_gb"] = buffer_pool / 1024**3 / 0.75 if buffer_pool > 0 else 8

        # 其他相关参数
        context["max_heap_table_size"] = int(variables.get("max_heap_table_size", 16 * 1024**2))

        # 时间戳
        context["timestamp"] = variables.get("timestamp", "")

        return context

    def generate_optimization_report(self) -> str:
        """生成优化报告"""
        results = self.analyze_all_parameters()

        report_lines = [
            "=" * 60,
            "MySQL参数优化分析报告",
            "=" * 60,
            f"\n实例: {results['instance']}",
            f"分析时间: {results.get('timestamp')}",
            f"整体优化分数: {results['overall_score']}/100",
            "\n" + "-" * 60,
            "关键参数分析结果:",
            "-" * 60,
        ]

        for param in results["parameters"]:
            status = "✓" if param["score"] >= 80 else "⚠" if param["score"] >= 50 else "✗"
            report_lines.append(f"\n[{status}] {param['name']} (分数: {param['score']})")
            report_lines.append(f"    当前值: {param['current_value']}")
            report_lines.append(f"    描述: {param['description']}")
            if param["suggestion"]:
                report_lines.append(f"    建议: {param['suggestion']}")

        if results["critical_params"]:
            report_lines.append("\n" + "-" * 60)
            report_lines.append("严重参数问题:")
            for param in results["critical_params"]:
                report_lines.append(f"  ✗ {param}")

        if results["suggestions"]:
            report_lines.append("\n" + "-" * 60)
            report_lines.append("优化建议:")
            for i, suggestion in enumerate(results["suggestions"], 1):
                report_lines.append(f"  {i}. {suggestion}")

        report_lines.append("\n" + "=" * 60)

        return "\n".join(report_lines)


@tool
def analyze_parameter_optimization(instance_name: str) -> str:
    """分析MySQL实例的参数配置并提供优化建议。

    自动检查关键参数配置，计算优化分数，提供具体优化建议。

    Args:
        instance_name: 实例名称或ID

    Returns:
        参数优化分析报告（JSON格式）
    """
    try:
        platform_client = get_platform_client()
        instance = platform_client.search_instance_by_name(instance_name)

        if not instance:
            platform_client.close()
            return f"错误: 未找到实例 '{instance_name}'"

        conn_config = platform_client.get_instance_connection(instance.id)
        platform_client.close()

        if not conn_config:
            return f"错误: 无法获取实例连接配置"

        mysql_client = MySQLClient(conn_config)

        # 构建上下文
        context = {
            "instance_name": instance_name,
            "memory_gb": instance.storage_size / 10 if instance.storage_size else None,  # 简化估算
        }

        optimizer = ParameterOptimizer(mysql_client, context)
        results = optimizer.analyze_all_parameters()

        mysql_client.close()

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"参数优化分析失败: {instance_name} - {e}")
        return f"错误: 参数优化分析失败 - {str(e)}"


@tool
def get_parameter_recommendations(instance_name: str, param_names: str = None) -> str:
    """获取MySQL参数的推荐配置。

    Args:
        instance_name: 实例名称
        param_names: 要分析的参数名（逗号分隔），为空则分析所有关键参数

    Returns:
        参数推荐配置报告
    """
    try:
        platform_client = get_platform_client()
        instance = platform_client.search_instance_by_name(instance_name)

        if not instance:
            platform_client.close()
            return json.dumps({"error": f"未找到实例 '{instance_name}'"}, ensure_ascii=False)

        conn_config = platform_client.get_instance_connection(instance.id)
        platform_client.close()

        mysql_client = MySQLClient(conn_config)
        variables = mysql_client.get_system_variables()
        mysql_client.close()

        # 解析要分析的参数
        params_to_analyze = []
        if param_names:
            params_to_analyze = [p.strip() for p in param_names.split(",")]
        else:
            params_to_analyze = list(PARAMETER_OPTIMIZATION_RULES.keys())

        # 获取推荐值
        recommendations = []
        for param_name in params_to_analyze:
            current_value = variables.get(param_name, "未设置")
            rule = PARAMETER_OPTIMIZATION_RULES.get(param_name, {})

            recommendation = {
                "name": param_name,
                "current_value": current_value,
                "description": rule.get("description", ""),
                "recommend_rule": rule.get("recommend_rule", ""),
                "safe_range": str(rule.get("safe_range", "")),
            }
            recommendations.append(recommendation)

        return json.dumps({
            "instance": instance_name,
            "recommendations": recommendations,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"错误: {str(e)}"