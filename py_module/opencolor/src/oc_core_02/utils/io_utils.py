"""
IO工具模块
提供文件哈希计算、日志设置、文件安全复制等通用IO功能
"""

import datetime
import hashlib
import logging
import shutil
import threading
import time
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _ts_now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_ts(msg: str) -> None:
    logger.info(f"{_ts_now_str()} {msg}", flush=True)


def start_heartbeat(name: str, interval_sec: float = 30.0, extra_info_fn=None):
    interval_sec = float(interval_sec)
    if interval_sec <= 0:
        interval_sec = 30.0

    start_t = time.perf_counter()
    stop_event = threading.Event()

    def _run() -> None:
        while True:
            if stop_event.wait(interval_sec):
                return
            dt = time.perf_counter() - start_t
            extra = ""
            if extra_info_fn is not None:
                try:
                    extra_raw = extra_info_fn()
                    if extra_raw:
                        extra = str(extra_raw)
                except Exception as e:
                    print_ts(f"[警告] 心跳附加信息获取失败: {e}")
                    import traceback

                    traceback.print_exc()
                    extra = ""
            print_ts(f"[报时] {name} 已运行 {dt:.1f}s{extra}")

    t = threading.Thread(target=_run, name=f"oc_heartbeat:{name}", daemon=True)
    t.start()
    return stop_event


def get_file_hash(filepath):
    """计算文件 SHA256"""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def setup_simple_logging(log_path):
    """设置简单的日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger()


def copy_file(src, dst):
    """安全复制文件并返回目标路径"""
    src = Path(src)
    dst = Path(dst)
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst
    return None
