"""RDS Agent - MySQL数据库智能问答和运维助手。"""

__version__ = "0.1.0"

from rds_agent.utils.config import settings
from rds_agent.utils.logger import logger, get_logger

__all__ = ["__version__", "settings", "logger", "get_logger"]