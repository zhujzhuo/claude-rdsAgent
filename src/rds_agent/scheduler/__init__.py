"""调度器模块 - 自动化巡检任务管理 (Django + Celery)。"""

default_app_config = "scheduler.apps.SchedulerConfig"

# Django ORM models will be imported from scheduler.models
# Celery tasks will be imported from scheduler.tasks
# Services will be imported from scheduler.services

__all__ = [
    "default_app_config",
]