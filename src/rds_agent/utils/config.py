"""配置管理模块，使用pydantic-settings管理环境变量。

支持 Django + Celery 架构配置，整合数据库和 Redis 配置。
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaSettings(BaseSettings):
    """Ollama模型配置"""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    host: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"
    embed_model: str = "nomic-embed-text"


class HermesSettings(BaseSettings):
    """Hermes Agent配置 (NousResearch Hermes Function Calling)"""

    model_config = SettingsConfigDict(env_prefix="HERMES_")

    # Hermes 模型选择: hermes2pro, hermes3
    model: str = "hermes3"
    # 是否启用 Hermes 作为默认 Agent
    enabled: bool = False
    # 最大工具调用迭代次数
    max_iterations: int = 10
    # 请求超时
    timeout: float = 60.0


class InstancePlatformSettings(BaseSettings):
    """实例管理平台配置"""

    model_config = SettingsConfigDict(env_prefix="INSTANCE_PLATFORM_")

    url: str = ""
    token: str = ""


class MySQLSettings(BaseSettings):
    """MySQL连接配置"""

    model_config = SettingsConfigDict(env_prefix="MYSQL_")

    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "mysql"


class DatabaseSettings(BaseSettings):
    """Django数据库配置 (用于 Celery/Django 架构)"""

    model_config = SettingsConfigDict(env_prefix="DB_")

    name: str = "rds_agent"
    user: str = "root"
    password: str = ""
    host: str = "localhost"
    port: int = 3306


class RedisSettings(BaseSettings):
    """Redis配置 (用于 Celery Broker)"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = "redis://localhost:6379/0"
    host: str = "localhost"
    port: int = 6379
    db: int = 0

    def get_broker_url(self) -> str:
        """获取 Celery Broker URL"""
        if self.url:
            return self.url
        return f"redis://{self.host}:{self.port}/{self.db}"


class DjangoSettings(BaseSettings):
    """Django框架配置"""

    model_config = SettingsConfigDict(env_prefix="DJANGO_")

    secret_key: str = "dev-secret-key-change-in-production-rds-agent"
    debug: bool = True
    allowed_hosts: str = "*"
    log_level: str = "INFO"


class CelerySettings(BaseSettings):
    """Celery任务调度配置"""

    model_config = SettingsConfigDict(env_prefix="CELERY_")

    worker_concurrency: int = 5
    task_time_limit: int = 3600  # 1 hour
    task_soft_time_limit: int = 3000  # 50 min
    worker_prefetch_multiplier: int = 1


class MonitorSettings(BaseSettings):
    """监控平台配置"""

    model_config = SettingsConfigDict(env_prefix="MONITOR_")

    api_url: str = ""


class VectorStoreSettings(BaseSettings):
    """向量知识库配置"""

    model_config = SettingsConfigDict(env_prefix="VECTOR_STORE_")

    path: str = "./data/vector_store"
    chroma_collection_name: str = "rds_knowledge"


class AgentSettings(BaseSettings):
    """Agent运行配置"""

    model_config = SettingsConfigDict(env_prefix="AGENT_")

    max_iterations: int = 10
    timeout_seconds: int = 60
    # Agent 类型: langgraph, hermes, auto (自动选择)
    type: str = "auto"


class RouterSettings(BaseSettings):
    """Router Agent 配置（双 Agent 自动选择）"""

    model_config = SettingsConfigDict(env_prefix="ROUTER_")

    # 是否启用自动选择模式
    auto_select: bool = True
    # Hermes 优先阈值（复杂度分数低于此值使用 Hermes）
    hermes_threshold: int = 30
    # Diagnostic 阈值（复杂度分数高于此值使用 Diagnostic）
    diagnostic_threshold: int = 70
    # 默认 Agent（当 auto_select=False 时）: langgraph, hermes, diagnostic
    default_agent: str = "auto"


class LogSettings(BaseSettings):
    """日志配置"""

    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = "INFO"
    file: str = "./logs/rds_agent.log"


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama: OllamaSettings = OllamaSettings()
    hermes: HermesSettings = HermesSettings()
    router: RouterSettings = RouterSettings()
    instance_platform: InstancePlatformSettings = InstancePlatformSettings()
    mysql: MySQLSettings = MySQLSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    django: DjangoSettings = DjangoSettings()
    celery: CelerySettings = CelerySettings()
    monitor: MonitorSettings = MonitorSettings()
    vector_store: VectorStoreSettings = VectorStoreSettings()
    agent: AgentSettings = AgentSettings()
    log: LogSettings = LogSettings()

    def get_django_database_config(self) -> dict:
        """获取 Django DATABASES 配置格式"""
        return {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": self.database.name,
                "USER": self.database.user,
                "PASSWORD": self.database.password,
                "HOST": self.database.host,
                "PORT": str(self.database.port),
                "OPTIONS": {
                    "charset": "utf8mb4",
                    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                },
            }
        }

    def get_celery_config(self) -> dict:
        """获取 Celery 配置"""
        return {
            "broker_url": self.redis.get_broker_url(),
            "result_backend": self.redis.get_broker_url().replace("/0", "/1"),
            "worker_concurrency": self.celery.worker_concurrency,
            "task_time_limit": self.celery.task_time_limit,
            "task_soft_time_limit": self.celery.task_soft_time_limit,
            "worker_prefetch_multiplier": self.celery.worker_prefetch_multiplier,
        }


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（缓存）"""
    return Settings()


def get_django_settings_dict() -> dict:
    """获取 Django settings.py 可用的配置字典"""
    settings = get_settings()
    return {
        "SECRET_KEY": settings.django.secret_key,
        "DEBUG": settings.django.debug,
        "ALLOWED_HOSTS": settings.django.allowed_hosts.split(","),
        "DATABASES": settings.get_django_database_config(),
        "CELERY_BROKER_URL": settings.redis.get_broker_url(),
        "CELERY_RESULT_BACKEND": settings.redis.get_broker_url().replace("/0", "/1"),
        "OLLAMA_HOST": settings.ollama.host,
        "OLLAMA_MODEL": settings.ollama.model,
        "INSTANCE_PLATFORM_URL": settings.instance_platform.url,
        "INSTANCE_PLATFORM_TOKEN": settings.instance_platform.token,
    }


# 导出常用配置
settings = get_settings()