"""日志工具模块。"""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from rds_agent.utils.config import settings


def setup_logging() -> logging.Logger:
    """设置日志配置"""
    logger = logging.getLogger("rds_agent")
    logger.setLevel(getattr(logging, settings.log.level.upper()))

    # 清除现有处理器
    logger.handlers.clear()

    # Rich控制台处理器（彩色输出）
    console = Console(stderr=True)
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=True,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
    )
    rich_handler.setLevel(logging.DEBUG)
    logger.addHandler(rich_handler)

    # 文件处理器（如果配置了日志文件）
    if settings.log.file:
        log_path = Path(settings.log.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


# 全局日志实例
logger = setup_logging()


def get_logger(name: str) -> logging.Logger:
    """获取子模块日志器"""
    return logging.getLogger(f"rds_agent.{name}")