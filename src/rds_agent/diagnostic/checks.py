"""诊断检查项实现 - 各类健康检查的具体实现。"""

import json
from datetime import datetime
from typing import Optional

from rds_agent.diagnostic.state import (
    CheckItem,
    CheckCategory,
    HealthStatus,
)
from rds_agent.data import get_platform_client, InstanceInfo
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.utils.logger import get_logger

logger = get_logger("checks")


class BaseCheck:
    """检查项基类"""

    name: str = ""
    category: CheckCategory = CheckCategory.INSTANCE_STATUS
    description: str = ""

    def __init__(self, mysql_client: MySQLClient, instance_info: Optional[InstanceInfo] = None):
        self.mysql_client = mysql_client
        self.instance_info = instance_info
        self.threshold = None

    def set_threshold(self, threshold: any) -> None:
        """设置阈值"""
        self.threshold = threshold

    def run(self) -> CheckItem:
        """执行检查"""
        raise NotImplementedError


class InstanceRunningCheck(BaseCheck):
    """实例运行状态检查"""

    name = "instance_running"
    category = CheckCategory.INSTANCE_STATUS
    description = "检查MySQL实例是否正常运行"

    def run(self) -> CheckItem:
        try:
            version = self.mysql_client.get_version()
            if version:
                return CheckItem(
                    name=self.name,
                    category=self.category,
                    status=HealthStatus.HEALTHY,
                    score=100,
                    value="running",
                    message=f"实例正常运行，版本: {version}",
                    details={"version": version},
                )
            else:
                return CheckItem(
                    name=self.name,
                    category=self.category,
                    status=HealthStatus.CRITICAL,
                    score=0,
                    value="not_running",
                    message="实例无法连接",
                )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.CRITICAL,
                score=0,
                value="error",
                message=f"检查失败: {str(e)}",
            )


class UptimeCheck(BaseCheck):
    """运行时间检查"""

    name = "uptime_check"
    category = CheckCategory.INSTANCE_STATUS
    description = "检查MySQL运行时间"

    def run(self) -> CheckItem:
        try:
            status = self.mysql_client.get_status_variables()
            uptime = int(status.get("Uptime", 0))

            uptime_hours = uptime / 3600
            uptime_days = uptime_hours / 24

            # 运行时间越长越好（稳定）
            if uptime_days > 30:
                score = 100
                status_val = HealthStatus.HEALTHY
            elif uptime_days > 7:
                score = 90
                status_val = HealthStatus.HEALTHY
            elif uptime_hours > 24:
                score = 70
                status_val = HealthStatus.WARNING
                message = "实例近期有重启，请确认是否计划内维护"
            else:
                score = 50
                status_val = HealthStatus.WARNING
                message = "实例刚刚重启，请关注稳定性"

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value=uptime,
                message=message or f"运行时间: {uptime_days:.1f}天",
                details={"uptime_seconds": uptime, "uptime_days": round(uptime_days, 2)},
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class ConnectionCountCheck(BaseCheck):
    """连接数检查"""

    name = "connection_count"
    category = CheckCategory.CONNECTION_SESSION
    description = "检查连接数使用情况"

    def run(self) -> CheckItem:
        try:
            conn_status = self.mysql_client.get_connection_status()
            usage_ratio = conn_status.connection_usage_ratio

            threshold = self.threshold or 80

            if usage_ratio > threshold:
                status_val = HealthStatus.CRITICAL
                score = int(100 - usage_ratio)
                suggestion = "连接数过高，建议增大max_connections或检查应用连接池配置"
            elif usage_ratio > threshold * 0.7:
                status_val = HealthStatus.WARNING
                score = int(100 - usage_ratio + 20)
                suggestion = "连接数偏高，建议关注连接趋势"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "current": conn_status.current_connections,
                    "max": conn_status.max_connections,
                    "usage_ratio": usage_ratio,
                },
                threshold=threshold,
                message=f"连接数: {conn_status.current_connections}/{conn_status.max_connections} ({usage_ratio}%)",
                suggestion=suggestion,
                details={
                    "active_connections": conn_status.active_connections,
                    "idle_connections": conn_status.idle_connections,
                },
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class ActiveSessionsCheck(BaseCheck):
    """活跃会话检查"""

    name = "active_sessions"
    category = CheckCategory.CONNECTION_SESSION
    description = "检查活跃会话和长时间运行查询"

    def run(self) -> CheckItem:
        try:
            processlist = self.mysql_client.get_processlist()

            active_queries = [p for p in processlist if p.get("Command") == "Query"]
            long_running = [p for p in active_queries if p.get("Time", 0) > 60]

            if len(long_running) > 5:
                status_val = HealthStatus.CRITICAL
                score = 30
                suggestion = f"发现{len(long_running)}个长时间运行查询(>60秒)，建议检查并处理"
            elif len(long_running) > 0:
                status_val = HealthStatus.WARNING
                score = 60
                suggestion = f"发现{len(long_running)}个长时间运行查询，建议关注"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "total_processes": len(processlist),
                    "active_queries": len(active_queries),
                    "long_running": len(long_running),
                },
                message=f"活跃查询: {len(active_queries)}, 长时间运行: {len(long_running)}",
                suggestion=suggestion,
                details={"long_running_queries": [
                    {"id": p.get("Id"), "time": p.get("Time"), "sql": p.get("Info", "")[:50]}
                    for p in long_running[:5]
                ]},
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class LockWaitCheck(BaseCheck):
    """锁等待检查"""

    name = "lock_wait"
    category = CheckCategory.CONNECTION_SESSION
    description = "检查锁等待情况"

    def run(self) -> CheckItem:
        try:
            lock_info = self.mysql_client.get_lock_info()
            processlist = self.mysql_client.get_processlist()

            locked_processes = [
                p for p in processlist
                if p.get("State") and "lock" in p.get("State", "").lower()
            ]

            if len(lock_info) > 3 or len(locked_processes) > 5:
                status_val = HealthStatus.CRITICAL
                score = 20
                suggestion = "存在严重锁等待，建议检查事务逻辑或kill阻塞进程"
            elif len(lock_info) > 0 or len(locked_processes) > 0:
                status_val = HealthStatus.WARNING
                score = 50
                suggestion = "存在锁等待，建议关注"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "lock_waits": len(lock_info),
                    "locked_processes": len(locked_processes),
                },
                message=f"锁等待: {len(lock_info)}, 锁阻塞进程: {len(locked_processes)}",
                suggestion=suggestion,
                details={"lock_details": lock_info[:3]},
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class BufferPoolHitRateCheck(BaseCheck):
    """Buffer Pool命中率检查"""

    name = "buffer_pool_hit_rate"
    category = CheckCategory.PERFORMANCE_METRICS
    description = "检查InnoDB Buffer Pool命中率"

    def run(self) -> CheckItem:
        try:
            metrics = self.mysql_client.get_performance_metrics()
            hit_rate = metrics.buffer_pool_hit_rate

            threshold = self.threshold or 95

            if hit_rate < threshold:
                status_val = HealthStatus.CRITICAL
                score = int(hit_rate)
                suggestion = f"Buffer Pool命中率过低({hit_rate}%)，建议增大innodb_buffer_pool_size"
            elif hit_rate < threshold + 2:
                status_val = HealthStatus.WARNING
                score = int(hit_rate)
                suggestion = "Buffer Pool命中率偏低，建议关注"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value=hit_rate,
                threshold=threshold,
                message=f"Buffer Pool命中率: {hit_rate}%",
                suggestion=suggestion,
                details={
                    "qps": metrics.qps,
                    "tps": metrics.tps,
                },
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class SlowQueryCountCheck(BaseCheck):
    """慢查询数量检查"""

    name = "slow_query_count"
    category = CheckCategory.PERFORMANCE_METRICS
    description = "检查慢查询情况"

    def run(self) -> CheckItem:
        try:
            # 获取慢查询（阈值1秒）
            slow_queries = self.mysql_client.get_slow_queries(limit=20, min_time=1.0)

            # 获取慢查询日志状态
            variables = self.mysql_client.get_system_variables()
            slow_log_enabled = variables.get("slow_query_log", "OFF").upper() == "ON"
            long_query_time = float(variables.get("long_query_time", "10"))

            threshold = self.threshold or 10

            if len(slow_queries) > threshold:
                status_val = HealthStatus.CRITICAL
                score = int(100 - len(slow_queries) * 2)
                suggestion = f"发现{len(slow_queries)}个慢查询模式，建议逐个分析和优化"
            elif len(slow_queries) > threshold / 2:
                status_val = HealthStatus.WARNING
                score = int(100 - len(slow_queries))
                suggestion = f"发现{len(slow_queries)}个慢查询模式，建议关注"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            if not slow_log_enabled:
                suggestion += "\n建议开启慢查询日志以便持续监控"

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value=len(slow_queries),
                threshold=threshold,
                message=f"慢查询模式: {len(slow_queries)}, 日志状态: {slow_log_enabled}",
                suggestion=suggestion,
                details={
                    "slow_log_enabled": slow_log_enabled,
                    "long_query_time": long_query_time,
                    "top_slow_queries": [
                        {"sql": sq.sql_text[:100], "time": sq.query_time}
                        for sq in slow_queries[:5]
                    ],
                },
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class QPSCheck(BaseCheck):
    """QPS检查"""

    name = "qps_check"
    category = CheckCategory.PERFORMANCE_METRICS
    description = "检查QPS水平"

    def run(self) -> CheckItem:
        try:
            metrics = self.mysql_client.get_performance_metrics()
            qps = metrics.qps

            # 根据规格判断QPS是否合理（这里用通用标准）
            # 实际应根据实例规格调整
            if self.instance_info and self.instance_info.spec:
                # 可以根据规格设置预期QPS范围
                pass

            # QPS检查主要是记录和趋势分析
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.HEALTHY,
                score=100,
                value=qps,
                message=f"当前QPS: {qps}",
                details={
                    "tps": metrics.tps,
                    "thread_running": metrics.thread_running,
                },
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class StorageCapacityCheck(BaseCheck):
    """存储容量检查"""

    name = "storage_capacity"
    category = CheckCategory.STORAGE_ENGINE
    description = "检查存储空间使用情况"

    def run(self) -> CheckItem:
        try:
            storage = self.mysql_client.get_storage_usage()

            # 如果有实例信息，获取配额
            total_quota = None
            if self.instance_info and self.instance_info.storage_size:
                total_quota = self.instance_info.storage_size
                usage_ratio = storage.used_size_gb / total_quota * 100
            else:
                usage_ratio = 0
                total_quota = "未知"

            threshold = self.threshold or 85

            if total_quota != "未知" and usage_ratio > threshold:
                status_val = HealthStatus.CRITICAL
                score = int(100 - usage_ratio)
                suggestion = f"存储使用率过高({usage_ratio:.1f}%)，建议扩容或清理数据"
            elif total_quota != "未知" and usage_ratio > threshold * 0.7:
                status_val = HealthStatus.WARNING
                score = int(100 - usage_ratio + 20)
                suggestion = "存储使用率偏高，建议关注增长趋势"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "used_gb": storage.used_size_gb,
                    "quota_gb": total_quota,
                    "usage_ratio": usage_ratio if total_quota != "未知" else None,
                },
                threshold=threshold,
                message=f"已用空间: {storage.used_size_gb}GB, 表数量: {storage.table_count}",
                suggestion=suggestion,
                details={
                    "database_count": storage.database_count,
                    "largest_tables": storage.largest_tables[:5],
                },
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class FragmentationCheck(BaseCheck):
    """碎片检查"""

    name = "fragmentation"
    category = CheckCategory.STORAGE_ENGINE
    description = "检查表碎片情况"

    def run(self) -> CheckItem:
        try:
            table_stats = self.mysql_client.get_table_stats()

            threshold = self.threshold or 100  # MB

            fragmented_tables = [
                ts for ts in table_stats
                if ts.data_free_mb > threshold
            ]

            total_fragmentation = sum(ts.data_free_mb for ts in table_stats)

            if len(fragmented_tables) > 10:
                status_val = HealthStatus.CRITICAL
                score = 20
                suggestion = f"发现{len(fragmented_tables)}个高碎片表，建议执行OPTIMIZE TABLE"
            elif len(fragmented_tables) > 3:
                status_val = HealthStatus.WARNING
                score = 50
                suggestion = f"发现{len(fragmented_tables)}个碎片表，建议优化"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "fragmented_tables": len(fragmented_tables),
                    "total_fragmentation_mb": total_fragmentation,
                },
                threshold=threshold,
                message=f"碎片表: {len(fragmented_tables)}, 总碎片: {total_fragmentation:.1f}MB",
                suggestion=suggestion,
                details={"fragmented_tables": [
                    {"schema": ts.schema_name, "table": ts.table_name, "fragmentation_mb": ts.data_free_mb}
                    for ts in fragmented_tables[:10]
                ]},
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class SlowLogEnabledCheck(BaseCheck):
    """慢查询日志开启检查"""

    name = "slow_log_enabled"
    category = CheckCategory.LOG_MONITOR
    description = "检查慢查询日志配置"

    def run(self) -> CheckItem:
        try:
            variables = self.mysql_client.get_system_variables()
            slow_log_enabled = variables.get("slow_query_log", "OFF").upper() == "ON"
            long_query_time = float(variables.get("long_query_time", "10"))

            if not slow_log_enabled:
                status_val = HealthStatus.WARNING
                score = 50
                suggestion = "建议开启慢查询日志以监控性能问题"
            elif long_query_time > 5:
                status_val = HealthStatus.WARNING
                score = 70
                suggestion = f"慢查询阈值较高({long_query_time}秒)，建议降低到1-3秒"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "enabled": slow_log_enabled,
                    "threshold": long_query_time,
                },
                message=f"慢查询日志: {slow_log_enabled}, 阈值: {long_query_time}秒",
                suggestion=suggestion,
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class ErrorLogCheck(BaseCheck):
    """错误日志检查"""

    name = "error_log_check"
    category = CheckCategory.LOG_MONITOR
    description = "检查是否有错误日志"

    def run(self) -> CheckItem:
        try:
            variables = self.mysql_client.get_system_variables()
            log_error = variables.get("log_error", "")

            # 获取状态变量中的错误计数
            status_vars = self.mysql_client.get_status_variables()
            errors = int(status_vars.get("Connection_errors_total", 0))

            # 这个检查主要是确认错误日志配置
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.HEALTHY if log_error else HealthStatus.WARNING,
                score=100 if log_error else 50,
                value=log_error or "未配置",
                message=f"错误日志路径: {log_error or '未配置'}, 连接错误数: {errors}",
                suggestion="建议配置错误日志" if not log_error else "",
                details={"connection_errors": errors},
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


class UserPrivilegesCheck(BaseCheck):
    """用户权限检查"""

    name = "user_privileges"
    category = CheckCategory.SECURITY_CONFIG
    description = "检查用户权限配置"

    def run(self) -> CheckItem:
        try:
            # 查询用户列表
            users = self.mysql_client.execute_query(
                "SELECT user, host FROM mysql.user"
            )

            # 查询有超级权限的用户
            super_users = self.mysql_client.execute_query(
                "SELECT user, host FROM mysql.user WHERE Super_priv = 'Y'"
            )

            # 检查是否有无密码用户
            empty_password_users = self.mysql_client.execute_query(
                "SELECT user, host FROM mysql.user WHERE authentication_string = '' OR password IS NULL"
            )

            warnings = []
            if len(super_users) > 5:
                warnings.append(f"超级权限用户较多({len(super_users)}个)")

            if len(empty_password_users) > 0:
                warnings.append(f"存在无密码用户({len(empty_password_users)}个)")

            if warnings:
                status_val = HealthStatus.WARNING
                score = 60
                suggestion = "; ".join(warnings) + "，建议检查权限配置"
            else:
                status_val = HealthStatus.HEALTHY
                score = 100
                suggestion = ""

            return CheckItem(
                name=self.name,
                category=self.category,
                status=status_val,
                score=score,
                value={
                    "total_users": len(users),
                    "super_users": len(super_users),
                    "empty_password_users": len(empty_password_users),
                },
                message=f"用户数: {len(users)}, 超级权限: {len(super_users)}",
                suggestion=suggestion,
                details={
                    "super_users": [f"{u['user']}@{u['host']}" for u in super_users[:5]],
                    "empty_password_users": [f"{u['user']}@{u['host']}" for u in empty_password_users],
                },
            )
        except Exception as e:
            return CheckItem(
                name=self.name,
                category=self.category,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            )


# 检查项注册表
CHECK_REGISTRY = {
    "instance_running": InstanceRunningCheck,
    "uptime_check": UptimeCheck,
    "connection_count": ConnectionCountCheck,
    "active_sessions": ActiveSessionsCheck,
    "lock_wait": LockWaitCheck,
    "buffer_pool_hit_rate": BufferPoolHitRateCheck,
    "slow_query_count": SlowQueryCountCheck,
    "qps_check": QPSCheck,
    "storage_capacity": StorageCapacityCheck,
    "fragmentation": FragmentationCheck,
    "slow_log_enabled": SlowLogEnabledCheck,
    "error_log_check": ErrorLogCheck,
    "user_privileges": UserPrivilegesCheck,
}


def get_check_class(name: str) -> Optional[type]:
    """获取检查类"""
    return CHECK_REGISTRY.get(name)