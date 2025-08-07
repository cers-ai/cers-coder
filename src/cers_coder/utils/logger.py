"""
日志配置工具
"""

import logging
import os
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False,
    format_string: Optional[str] = None
) -> None:
    """设置日志配置"""
    
    # 确定日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 创建日志目录
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # 使用默认日志文件
        log_dir = Path(os.getenv("LOG_DIR", "./logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "cers-coder.log"
    
    # 设置日志格式
    if format_string is None:
        if verbose:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        else:
            format_string = "%(asctime)s - %(levelname)s - %(message)s"
    
    # 配置根日志器
    logging.basicConfig(
        level=log_level,
        format=format_string,
        handlers=[
            # 文件处理器
            logging.FileHandler(log_file, encoding='utf-8'),
            # Rich控制台处理器
            RichHandler(
                rich_tracebacks=True,
                show_path=verbose,
                show_time=verbose
            )
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # 如果是调试模式，显示更多信息
    if verbose:
        logging.getLogger("cers_coder").setLevel(logging.DEBUG)
    
    logging.info(f"日志系统已初始化，级别: {level}, 文件: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(f"cers_coder.{name}")
