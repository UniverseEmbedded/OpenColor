"""中断处理模块 - 提供信号处理和线程中断功能"""

import os
import signal
import threading
from concurrent.futures import FIRST_COMPLETED, wait

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

_INTERRUPTED = threading.Event()


def _install_interrupt_handlers() -> None:
    """安装中断信号处理器"""
    def _on_sigint(sig, frame):
        try:
            _INTERRUPTED.set()
            sig_name = getattr(sig, "name", None) or str(sig)
            logger.info(f"[报时] 收到中断信号 {sig_name}，正在退出...")
        except Exception as e:
            logger.error(f"[报时] 收到中断信号，正在退出...（报时失败: {e}）")

    try:
        signal.signal(signal.SIGINT, _on_sigint)
    except Exception as e:
        logger.error(f"[警告] 安装 SIGINT 处理器失败: {e}")

    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, _on_sigint)
        except Exception as e:
            logger.error(f"[警告] 安装 SIGBREAK 处理器失败: {e}")


def _hard_abort_if_interrupted(stage: str) -> None:
    """检查是否被中断，如果是则强制退出"""
    if _INTERRUPTED.is_set():
        _hard_exit_130(stage)


def _hard_exit_130(stage: str) -> None:
    """强制退出进程"""
    try:
        logger.info(f"[报时] 用户手动中断(Ctrl-C)，退出阶段: {stage}")
    except Exception as e:
        logger.error(f"[报时] 用户手动中断(Ctrl-C)，退出阶段: {stage}（报时失败: {e}）")
    os._exit(130)


def _collect_futures_interruptible(ex, futs: list, stage: str) -> list:
    """可中断的 future 收集"""
    results = []
    pending = set(futs)
    try:
        while pending:
            _hard_abort_if_interrupted(stage)
            done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            for fut in done:
                results.append(fut.result())
    except KeyboardInterrupt:
        _INTERRUPTED.set()
        logger.info(f"[报时] 收到 Ctrl-C，正在强制退出（{stage}）")
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        finally:
            _hard_exit_130(stage)
    return results
