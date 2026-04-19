"""巡检任务调度模块状态定义。"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScheduleType(str, Enum):
    """调度类型"""

    CRON = "cron"  # Cron表达式
    INTERVAL = "interval"  # 固定间隔
    ONCE = "once"  # 单次执行


class TaskStatus(str, Enum):
    """任务状态"""

    ENABLED = "enabled"  # 启用
    DISABLED = "disabled"  # 禁用
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 暂停


class TaskType(str, Enum):
    """任务类型"""

    FULL_INSPECTION = "full_inspection"  # 完整巡检
    QUICK_CHECK = "quick_check"  # 快速检查
    PERFORMANCE_DIAG = "performance_diag"  # 性能诊断
    CONNECTION_DIAG = "connection_diag"  # 连接诊断
    STORAGE_DIAG = "storage_diag"  # 存储诊断
    PARAMETER_DIAG = "parameter_diag"  # 参数诊断
    SECURITY_DIAG = "security_diag"  # 安全诊断


class AlertLevel(str, Enum):
    """告警级别"""

    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    CRITICAL = "critical"  # 严重
    EMERGENCY = "emergency"  # 紧急


class InspectionTask(BaseModel):
    """巡检任务定义"""

    id: Optional[str] = Field(default=None, description="任务ID")
    name: str = Field(..., description="任务名称")
    description: str = Field(default="", description="任务描述")

    # 目标实例
    target_instances: list[str] = Field(default_factory=list, description="目标实例列表")

    # 任务类型
    task_type: TaskType = Field(default=TaskType.FULL_INSPECTION, description="任务类型")

    # 调度配置
    schedule_type: ScheduleType = Field(default=ScheduleType.INTERVAL, description="调度类型")
    cron_expression: Optional[str] = Field(default=None, description="Cron表达式")
    interval_seconds: Optional[int] = Field(default=None, description="间隔秒数")
    scheduled_time: Optional[datetime] = Field(default=None, description="计划执行时间(单次)")

    # 状态
    status: TaskStatus = Field(default=TaskStatus.DISABLED, description="任务状态")

    # 告警配置
    alert_enabled: bool = Field(default=True, description="是否启用告警")
    alert_levels: list[AlertLevel] = Field(
        default_factory=lambda: [AlertLevel.WARNING, AlertLevel.CRITICAL],
        description="告警级别"
    )
    alert_channels: list[str] = Field(default_factory=list, description="告警渠道")

    # 配置
    thresholds: dict = Field(default_factory=dict, description="阈值配置")
    tags: dict = Field(default_factory=dict, description="标签")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    last_run_time: Optional[datetime] = Field(default=None, description="上次执行时间")
    next_run_time: Optional[datetime] = Field(default=None, description="下次执行时间")

    # 执行统计
    run_count: int = Field(default=0, description="执行次数")
    success_count: int = Field(default=0, description="成功次数")
    failure_count: int = Field(default=0, description="失败次数")


class TaskExecution(BaseModel):
    """任务执行记录"""

    id: Optional[str] = Field(default=None, description="执行ID")
    task_id: str = Field(..., description="任务ID")
    instance_name: str = Field(..., description="实例名称")

    # 执行信息
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration_seconds: Optional[float] = Field(default=None, description="执行时长(秒)")

    # 结果信息
    status: str = Field(default="running", description="执行状态")
    overall_score: Optional[int] = Field(default=None, description="健康分数")
    overall_status: Optional[str] = Field(default=None, description="健康状态")

    # 告警信息
    alerts_triggered: list[dict] = Field(default_factory=list, description="触发告警")
    critical_count: int = Field(default=0, description="严重问题数")
    warning_count: int = Field(default=0, description="警告数")

    # 结果路径
    report_path: Optional[str] = Field(default=None, description="报告路径")
    result_data: Optional[dict] = Field(default=None, description="结果数据")

    # 错误信息
    error_message: Optional[str] = Field(default=None, description="错误信息")


class AlertRule(BaseModel):
    """告警规则"""

    id: Optional[str] = Field(default=None, description="规则ID")
    name: str = Field(..., description="规则名称")
    description: str = Field(default="", description="规则描述")

    # 触发条件
    metric_name: str = Field(..., description="指标名称")
    operator: str = Field(default=">", description="比较运算符(>, <, >=, <=, ==, !=)")
    threshold: float = Field(..., description="阈值")
    duration_seconds: Optional[int] = Field(default=None, description="持续时间(秒)")

    # 告警级别
    level: AlertLevel = Field(default=AlertLevel.WARNING, description="告警级别")

    # 通知配置
    notification_channels: list[str] = Field(default_factory=list, description="通知渠道")
    notification_template: Optional[str] = Field(default=None, description="通知模板")

    # 抑制配置
    suppress_duration: int = Field(default=300, description="抑制时长(秒)")
    max_alerts_per_hour: int = Field(default=10, description="每小时最大告警数")

    # 状态
    enabled: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class AlertEvent(BaseModel):
    """告警事件"""

    id: Optional[str] = Field(default=None, description="告警ID")
    rule_id: str = Field(..., description="规则ID")
    instance_name: str = Field(..., description="实例名称")

    # 告警信息
    level: AlertLevel = Field(..., description="告警级别")
    title: str = Field(..., description="告警标题")
    message: str = Field(..., description="告警内容")
    metric_name: str = Field(..., description="指标名称")
    metric_value: float = Field(..., description="指标值")
    threshold: float = Field(..., description="阈值")

    # 时间信息
    triggered_at: datetime = Field(default_factory=datetime.now, description="触发时间")
    resolved_at: Optional[datetime] = Field(default=None, description="恢复时间")
    acknowledged_at: Optional[datetime] = Field(default=None, description="确认时间")

    # 状态
    status: str = Field(default="firing", description="状态(firing/resolved/acknowledged)")

    # 通知
    notification_sent: bool = Field(default=False, description="是否已发送通知")
    notification_channels: list[str] = Field(default_factory=list, description="已发送渠道")

    # 关联
    execution_id: Optional[str] = Field(default=None, description="关联执行ID")
    suggestion: Optional[str] = Field(default=None, description="处理建议")


class HealthHistory(BaseModel):
    """健康历史记录"""

    id: Optional[str] = Field(default=None, description="记录ID")
    instance_name: str = Field(..., description="实例名称")

    # 健康信息
    overall_score: int = Field(..., description="健康分数")
    overall_status: str = Field(..., description="健康状态")

    # 分类分数
    category_scores: dict = Field(default_factory=dict, description="分类分数")

    # 问题统计
    critical_count: int = Field(default=0, description="严重问题数")
    warning_count: int = Field(default=0, description="警告数")

    # 时间
    recorded_at: datetime = Field(default_factory=datetime.now, description="记录时间")
    execution_id: Optional[str] = Field(default=None, description="执行ID")

    # 趋势分析
    score_change: Optional[float] = Field(default=None, description="分数变化")
    trend: Optional[str] = Field(default=None, description="趋势(improving/stable/degrading)")


class NotificationChannel(BaseModel):
    """通知渠道配置"""

    id: Optional[str] = Field(default=None, description="渠道ID")
    name: str = Field(..., description="渠道名称")
    type: str = Field(..., description="渠道类型(dingtalk/email/wechat/webhook)")

    # 配置
    config: dict = Field(default_factory=dict, description="配置参数")
    enabled: bool = Field(default=True, description="是否启用")

    # 时间
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_used_at: Optional[datetime] = Field(default=None, description="上次使用时间")