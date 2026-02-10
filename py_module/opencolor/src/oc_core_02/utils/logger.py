"""日志配置模块 - 基于loguru的统一日志管理

使用示例:
    from oc_core_02.utils.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("应用启动")
    logger.debug("调试信息: {}", some_var)
    logger.warning("警告信息")
    logger.error("错误信息")
    logger.critical("严重错误")
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

__all__ = ["get_logger", "setup_logger", "logger"]


class LoggerConfig:
    """日志配置类"""
    
    # 详细格式（用于调试）
    DEFAULT_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 简洁格式（默认使用）
    SIMPLE_FORMAT = "<level>{message}</level>"
    
    def __init__(
        self,
        level: str = "INFO",
        log_dir: Optional[Path] = None,
        enable_file: bool = False,
        enable_console: bool = True,
        rotation: str = "10 MB",
        retention: str = "7 days",
        format_str: Optional[str] = None,
    ):
        self.level = level
        self.log_dir = log_dir
        self.enable_file = enable_file
        self.enable_console = enable_console
        self.rotation = rotation
        self.retention = retention
        self.format_str = format_str or self.SIMPLE_FORMAT


def setup_logger(config: Optional[LoggerConfig] = None) -> None:
    """配置全局日志记录器
    
    Args:
        config: 日志配置对象，如果为None则使用默认配置
    """
    if config is None:
        config = LoggerConfig()
    
    # 移除所有现有的处理器
    _logger.remove()
    
    # 添加控制台处理器
    if config.enable_console:
        _logger.add(
            sys.stderr,
            level=config.level,
            format=config.format_str,
            colorize=True,
            enqueue=True,
        )
    
    # 添加文件处理器
    if config.enable_file and config.log_dir:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = config.log_dir / "opencolor_{time:YYYY-MM-DD}.log"
        _logger.add(
            str(log_file),
            level=config.level,
            format=config.format_str,
            rotation=config.rotation,
            retention=config.retention,
            encoding="utf-8",
            enqueue=True,
        )


def get_logger(name: Optional[str] = None) -> "loguru.Logger":
    """获取一个命名日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        配置好的日志记录器
    """
    if name:
        return _logger.bind(name=name)
    return _logger


# 默认初始化（使用INFO级别）
# 在应用启动时可以调用 setup_logger() 进行自定义配置
logger = _logger
