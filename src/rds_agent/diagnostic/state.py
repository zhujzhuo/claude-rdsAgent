"""诊断Agent状态定义。"""

from enum import Enum
from typing import Annotated, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class DiagnosticType(str, Enum):
    """诊断类型"""

    FULL_INSPECTION = "full_inspection"  # 完整实例巡检
    PERFORMANCE_DIAG = "performance_diag"  # 性能诊断
    CONNECTION_DIAG = "connection_diag"  # 连接诊断
    STORAGE_DIAG = "storage_diag"  # 存储诊断
    PARAMETER_DIAG = "parameter_diag"  # 参数诊断
    SECURITY_DIAG = "security_diag"  # 安全诊断
    LOG_DIAG = "log_diag"  # 日志诊断
    QUICK_CHECK = "quick_check"  # 快速检查


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"  # 健康
    WARNING = "warning"  # 警告
    CRITICAL = "critical"  # 严重
    UNKNOWN = "unknown"  # 未知


class CheckCategory(str, Enum):
    """检查类别"""

    INSTANCE_STATUS = "instance_status"  # 实例状态
    RESOURCE_USAGE = "resource_usage"  # 资源使用
    CONNECTION_SESSION = "connection_session"  # 连接与会话
    PERFORMANCE_METRICS = "performance_metrics"  # 性能指标
    STORAGE_ENGINE = "storage_engine"  # 存储引擎
    LOG_MONITOR = "log_monitor"  # 日志与监控
    BACKUP_RECOVERY = "backup_recovery"  # 备份与恢复
    HIGH_AVAILABILITY = "high_availability"  # 高可用与容灾
    SECURITY_CONFIG = "security_config"  # 安全配置
    SCHEMA_OBJECT = "schema_object"  # Schema与对象


class CheckItem(BaseModel):
    """检查项"""

    name: str = Field(..., description="检查项名称")
    category: CheckCategory = Field(..., description="检查类别")
    status: HealthStatus = Field(default=HealthStatus.UNKNOWN, description="健康状态")
    score: int = Field(default=0, ge=0, le=100, description="健康分数(0-100)")
    value: Any = Field(default=None, description="检测值")
    threshold: Any = Field(default=None, description="阈值")
    message: str = Field(default="", description="检测结果描述")
    suggestion: str = Field(default="", description="优化建议")
    details: dict = Field(default_factory=dict, description="详细信息")


class DiagnosticResult(BaseModel):
    """诊断结果"""

    instance_name: str = Field(..., description="实例名称")
    diagnostic_type: DiagnosticType = Field(..., description="诊断类型")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    overall_status: HealthStatus = Field(default=HealthStatus.UNKNOWN, description="整体状态")
    overall_score: int = Field(default=0, ge=0, le=100, description="整体分数")
    check_items: list[CheckItem] = Field(default_factory=list, description="检查项列表")
    summary: str = Field(default="", description="诊断摘要")
    critical_issues: list[str] = Field(default_factory=list, description="严重问题")
    warnings: list[str] = Field(default_factory=list, description="警告")
    suggestions: list[str] = Field(default_factory=list, description="优化建议")
    metadata: dict = Field(default_factory=dict, description="元数据")


class DiagnosticState(TypedDict):
    """诊断Agent状态"""

    # 目标实例
    target_instance: str

    # 诊断类型
    diagnostic_type: DiagnosticType

    # 当前检查阶段
    current_phase: str

    # 检查项结果
    check_results: list[CheckItem]

    # 诊断结果
    diagnostic_result: Optional[DiagnosticResult]

    # 进度百分比
    progress: int

    # 错误信息
    error: Optional[str]

    # 上下文信息
    context: dict


class InspectionTemplate(BaseModel):
    """巡检模板"""

    name: str = Field(..., description="模板名称")
    description: str = Field(default="", description="模板描述")
    categories: list[CheckCategory] = Field(default_factory=list, description="检查类别")
    check_items: list[str] = Field(default_factory=list, description="检查项列表")
    thresholds: dict = Field(default_factory=dict, description="阈值配置")


# 预定义巡检模板
DEFAULT_INSPECTION_TEMPLATE = InspectionTemplate(
    name="标准MySQL实例巡检",
    description="完整的MySQL实例健康检查模板",
    categories=[
        CheckCategory.INSTANCE_STATUS,
        CheckCategory.RESOURCE_USAGE,
        CheckCategory.CONNECTION_SESSION,
        CheckCategory.PERFORMANCE_METRICS,
        CheckCategory.STORAGE_ENGINE,
        CheckCategory.LOG_MONITOR,
        CheckCategory.SECURITY_CONFIG,
    ],
    check_items=[
        # 实例状态
        "instance_running",
        "uptime_check",
        # 资源使用
        "cpu_usage",
        "memory_usage",
        "disk_usage",
        # 连接与会话
        "connection_count",
        "active_sessions",
        "lock_wait",
        # 性能指标
        "qps_check",
        "buffer_pool_hit_rate",
        "slow_query_count",
        # 存储引擎
        "storage_capacity",
        "table_count",
        "fragmentation",
        # 日志与监控
        "error_log_check",
        "slow_log_enabled",
        # 安全配置
        "user_privileges",
        "password_policy",
    ],
    thresholds={
        "connection_usage_max": 80,
        "buffer_pool_hit_rate_min": 95,
        "slow_query_time_max": 10,
        "disk_usage_max": 85,
        "fragmentation_size_max": 100,
    }
)

QUICK_CHECK_TEMPLATE = InspectionTemplate(
    name="快速健康检查",
    description="快速检查关键指标",
    categories=[
        CheckCategory.INSTANCE_STATUS,
        CheckCategory.RESOURCE_USAGE,
        CheckCategory.PERFORMANCE_METRICS,
    ],
    check_items=[
        "instance_running",
        "connection_count",
        "buffer_pool_hit_rate",
        "slow_query_count",
    ],
    thresholds={
        "connection_usage_max": 80,
        "buffer_pool_hit_rate_min": 95,
    }
)