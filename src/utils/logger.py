"""
日志模块 - 支持文件记录和GUI实时输出
"""
import logging
import queue
from datetime import datetime
from pathlib import Path
from typing import Optional


class GuiLogHandler(logging.Handler):
    """将日志消息放入队列，供GUI线程读取"""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                             datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.log_queue.put({
            "level": record.levelname,
            "message": msg,
            "timestamp": datetime.now(),
        })


def setup_logger(
    name: str = "bili_summarizer",
    log_queue: Optional[queue.Queue] = None,
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_queue: GUI日志队列（可选，用于实时显示）
        log_file: 日志文件路径（可选）
        level: 日志级别

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(console_handler)

    # GUI 输出
    if log_queue is not None:
        gui_handler = GuiLogHandler(log_queue)
        logger.addHandler(gui_handler)

    # 文件输出
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "bili_summarizer") -> logging.Logger:
    """获取已有的日志记录器"""
    return logging.getLogger(name)
