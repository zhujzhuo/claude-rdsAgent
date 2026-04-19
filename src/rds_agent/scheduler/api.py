"""巡检任务管理API - FastAPI接口。"""

from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from rds_agent.scheduler.executor import get_scheduler
from rds_agent.scheduler.alert_engine import get_alert_engine
from rds_agent.scheduler.history_store import get_history_store
from rds_agent.scheduler.notification import get_notification_manager
from rds_agent.scheduler.state import (
    InspectionTask,
    TaskExecution,
    AlertEvent,
    AlertRule,
    HealthHistory,
    TaskStatus,
    ScheduleType,
    TaskType,
    AlertLevel,
    NotificationChannel,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("scheduler_api")

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


# ============= 任务管理接口 =============

class TaskCreateRequest(BaseModel):
    """创建任务请求"""

    name: str
    description: str = ""
    target_instances: list[str]
    task_type: TaskType = TaskType.FULL_INSPECTION
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    alert_enabled: bool = True
    alert_levels: list[AlertLevel] = ["warning", "critical"]
    alert_channels: list[str] = []
    thresholds: dict = {}


class TaskUpdateRequest(BaseModel):
    """更新任务请求"""

    name: Optional[str] = None
    description: Optional[str] = None
    target_instances: Optional[list[str]] = None
    task_type: Optional[TaskType] = None
    schedule_type: Optional[ScheduleType] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    alert_enabled: Optional[bool] = None
    alert_levels: Optional[list[AlertLevel]] = None
    alert_channels: Optional[list[str]] = None
    thresholds: Optional[dict] = None
    status: Optional[TaskStatus] = None


@router.post("/tasks")
async def create_task(request: TaskCreateRequest):
    """创建巡检任务"""
    scheduler = get_scheduler()

    task = InspectionTask(
        name=request.name,
        description=request.description,
        target_instances=request.target_instances,
        task_type=request.task_type,
        schedule_type=request.schedule_type,
        cron_expression=request.cron_expression,
        interval_seconds=request.interval_seconds,
        scheduled_time=request.scheduled_time,
        alert_enabled=request.alert_enabled,
        alert_levels=request.alert_levels,
        alert_channels=request.alert_channels,
        thresholds=request.thresholds,
        status=TaskStatus.DISABLED,
    )

    task_id = scheduler.add_task(task)

    return {
        "task_id": task_id,
        "name": task.name,
        "status": task.status,
        "message": "任务创建成功，请启用任务以开始调度",
    }


@router.get("/tasks")
async def list_tasks():
    """列出所有任务"""
    scheduler = get_scheduler()
    tasks = scheduler.list_tasks()

    return {
        "total": len(tasks),
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "type": t.task_type,
                "status": t.status,
                "target_instances": t.target_instances,
                "schedule_type": t.schedule_type,
                "last_run": t.last_run_time.isoformat() if t.last_run_time else None,
                "next_run": t.next_run_time.isoformat() if t.next_run_time else None,
                "run_count": t.run_count,
            }
            for t in tasks
        ],
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    scheduler = get_scheduler()
    task = scheduler.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return task.model_dump()


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    """更新任务"""
    scheduler = get_scheduler()

    updates = request.model_dump(exclude_none=True)
    task = scheduler.update_task(task_id, updates)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task_id,
        "message": "任务更新成功",
        "task": task.model_dump(),
    }


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    scheduler = get_scheduler()

    if not scheduler.remove_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"task_id": task_id, "message": "任务删除成功"}


@router.post("/tasks/{task_id}/enable")
async def enable_task(task_id: str):
    """启用任务"""
    scheduler = get_scheduler()

    if not scheduler.enable_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"task_id": task_id, "status": "enabled", "message": "任务已启用"}


@router.post("/tasks/{task_id}/disable")
async def disable_task(task_id: str):
    """禁用任务"""
    scheduler = get_scheduler()

    if not scheduler.disable_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"task_id": task_id, "status": "disabled", "message": "任务已禁用"}


@router.post("/tasks/{task_id}/run")
async def run_task_now(task_id: str, background_tasks: BackgroundTasks):
    """立即执行任务"""
    scheduler = get_scheduler()
    task = scheduler.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 在后台执行
    background_tasks.add_task(scheduler.run_task_now, task_id)

    return {
        "task_id": task_id,
        "message": "任务已触发执行",
        "target_instances": task.target_instances,
    }


@router.get("/tasks/{task_id}/executions")
async def get_task_executions(task_id: str, limit: int = 10):
    """获取任务执行历史"""
    scheduler = get_scheduler()
    executions = scheduler.get_task_executions(task_id, limit)

    return {
        "task_id": task_id,
        "total": len(executions),
        "executions": [
            {
                "id": e.id,
                "instance": e.instance_name,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "status": e.status,
                "score": e.overall_score,
                "critical_count": e.critical_count,
                "warning_count": e.warning_count,
            }
            for e in executions
        ],
    }


# ============= 调度器状态接口 =============

@router.get("/status")
async def get_scheduler_status():
    """获取调度器状态"""
    scheduler = get_scheduler()
    status = scheduler.get_scheduler_status()

    return status


# ============= 告警管理接口 =============

class AlertRuleRequest(BaseModel):
    """告警规则请求"""

    name: str
    description: str = ""
    metric_name: str
    operator: str = ">"
    threshold: float
    level: AlertLevel = AlertLevel.WARNING
    notification_channels: list[str] = []
    suppress_duration: int = 300
    max_alerts_per_hour: int = 10


@router.post("/alerts/rules")
async def create_alert_rule(request: AlertRuleRequest):
    """创建告警规则"""
    engine = get_alert_engine()

    rule = AlertRule(
        name=request.name,
        description=request.description,
        metric_name=request.metric_name,
        operator=request.operator,
        threshold=request.threshold,
        level=request.level,
        notification_channels=request.notification_channels,
        suppress_duration=request.suppress_duration,
        max_alerts_per_hour=request.max_alerts_per_hour,
    )

    rule_id = engine.add_rule(rule)

    return {"rule_id": rule_id, "message": "告警规则创建成功"}


@router.get("/alerts/rules")
async def list_alert_rules():
    """列出告警规则"""
    engine = get_alert_engine()
    rules = engine.list_rules()

    return {
        "total": len(rules),
        "rules": [r.model_dump() for r in rules],
    }


@router.get("/alerts/active")
async def get_active_alerts(instance: Optional[str] = None):
    """获取活跃告警"""
    engine = get_alert_engine()
    alerts = engine.get_active_alerts(instance)

    return {
        "total": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "instance": a.instance_name,
                "level": a.level,
                "title": a.title,
                "message": a.message,
                "triggered_at": a.triggered_at.isoformat(),
                "suggestion": a.suggestion,
            }
            for a in alerts
        ],
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """确认告警"""
    engine = get_alert_engine()

    if not engine.acknowledge_alert(alert_id):
        raise HTTPException(status_code=404, detail="告警不存在")

    return {"alert_id": alert_id, "status": "acknowledged"}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """恢复告警"""
    engine = get_alert_engine()

    if not engine.resolve_alert(alert_id):
        raise HTTPException(status_code=404, detail="告警不存在")

    return {"alert_id": alert_id, "status": "resolved"}


# ============= 健康历史接口 =============

@router.get("/history/{instance}")
async def get_health_history(instance: str, days: int = 7):
    """获取实例健康历史"""
    store = get_history_store()
    history = store.get_health_history(instance, days)

    return {
        "instance": instance,
        "days": days,
        "total": len(history),
        "history": [
            {
                "id": h.id,
                "score": h.overall_score,
                "status": h.overall_status,
                "critical": h.critical_count,
                "warning": h.warning_count,
                "recorded_at": h.recorded_at.isoformat(),
                "trend": h.trend,
                "score_change": h.score_change,
            }
            for h in history
        ],
    }


@router.get("/history/{instance}/trend")
async def get_health_trend(instance: str, days: int = 7):
    """获取健康趋势分析"""
    store = get_history_store()
    trend = store.get_health_trend(instance, days)

    return trend


@router.get("/history/trends")
async def get_all_trends(days: int = 7):
    """获取所有实例趋势"""
    store = get_history_store()
    trends = store.get_all_instances_trend(days)

    return {
        "total": len(trends),
        "trends": trends,
    }


@router.get("/history/{instance}/compare")
async def compare_health(instance: str, days: int = 7):
    """健康对比分析"""
    store = get_history_store()
    comparison = store.compare_health(instance, days)

    return comparison


# ============= 通知渠道接口 =============

class NotificationChannelRequest(BaseModel):
    """通知渠道请求"""

    name: str
    type: str
    config: dict
    enabled: bool = True


@router.post("/notifications/channels")
async def create_notification_channel(request: NotificationChannelRequest):
    """创建通知渠道"""
    manager = get_notification_manager()

    channel = NotificationChannel(
        name=request.name,
        type=request.type,
        config=request.config,
        enabled=request.enabled,
    )

    channel_id = manager.add_channel(channel)

    return {"channel_id": channel_id, "message": "通知渠道创建成功"}


@router.get("/notifications/channels")
async def list_notification_channels():
    """列出通知渠道"""
    manager = get_notification_manager()
    channels = manager.list_channels()

    return {
        "total": len(channels),
        "channels": [
            {
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "enabled": c.enabled,
                "last_used": c.last_used_at.isoformat() if c.last_used_at else None,
            }
            for c in channels
        ],
    }


def init_scheduler():
    """初始化调度器组件"""
    scheduler = get_scheduler()
    alert_engine = get_alert_engine()
    history_store = get_history_store()

    # 连接组件
    scheduler.set_alert_engine(alert_engine)
    scheduler.set_history_store(history_store)

    # 设置告警通知回调
    def alert_notification_callback(alert: AlertEvent, channels: list[str]):
        manager = get_notification_manager()
        manager.send_alert(alert, channels)

    alert_engine.set_notification_callback(alert_notification_callback)

    logger.info("调度器组件初始化完成")