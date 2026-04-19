"""
Scheduler Django App Configuration.
"""

from django.apps import AppConfig


class SchedulerConfig(AppConfig):
    """Configuration for the Scheduler app."""

    default_auto_field = "django.db.models.UUIDField"
    name = "scheduler"
    verbose_name = "巡检调度器"

    def ready(self):
        """Initialize app when Django starts."""
        # Import tasks to ensure they are registered with Celery
        try:
            import scheduler.tasks.inspection  # noqa
            import scheduler.tasks.notification  # noqa
        except ImportError:
            pass

        # Load configuration from utils/config.py
        try:
            from rds_agent.utils.config import get_settings
            settings = get_settings()

            # Store settings for access throughout the app
            from django.conf import settings as django_settings
            django_settings.RDS_AGENT_CONFIG = {
                "ollama_host": settings.ollama.host,
                "ollama_model": settings.ollama.model,
                "ollama_embed_model": settings.ollama.embed_model,
                "instance_platform_url": settings.instance_platform.url,
                "instance_platform_token": settings.instance_platform.token,
                "mysql_host": settings.mysql.host,
                "mysql_port": settings.mysql.port,
                "mysql_user": settings.mysql.user,
                "mysql_database": settings.mysql.database,
                "vector_store_path": settings.vector_store.path,
                "chroma_collection_name": settings.vector_store.chroma_collection_name,
                "agent_max_iterations": settings.agent.max_iterations,
                "agent_timeout_seconds": settings.agent.timeout_seconds,
            }
        except ImportError:
            pass