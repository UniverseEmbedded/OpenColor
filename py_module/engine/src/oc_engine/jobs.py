from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

from .protocol import (
    make_event_done,
    make_event_error,
    make_event_progress,
    write_json_line,
)


def _now_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


@dataclass
class Job:
    """任务类，表示一个异步任务"""

    job_id: str  # 任务唯一标识
    out_dir: str  # 输出目录
    cancelled: bool = field(default=False, init=False)  # 是否已取消


class JobManager:
    """任务管理器，用于创建、管理和执行异步任务"""

    def __init__(self) -> None:
        """初始化任务管理器"""
        self._lock = threading.Lock()  # 线程锁，用于保护共享数据
        self._seq = 0  # 任务序号计数器
        self._jobs: Dict[str, Job] = {}  # 任务字典，存储所有任务

    def create_job(self, out_dir: str) -> Job:
        """创建一个新任务"""
        with self._lock:
            self._seq += 1
            job_id = f"job_{_now_ms()}_{self._seq}"
            job = Job(job_id=job_id, out_dir=out_dir)
            self._jobs[job_id] = job
        return job

    def cancel_job(self, job_id: str) -> bool:
        """取消指定的任务。返回是否成功取消。"""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.cancelled = True
                return True
            return False

    def remove_job(self, job_id: str) -> None:
        """从管理器中移除任务。"""
        with self._lock:
            self._jobs.pop(job_id, None)

    def run_async(
        self,
        job: Job,
        handler: Callable[[Job, Callable[[float, str, str], None]], Dict[str, Any]],
    ) -> None:
        """异步执行任务"""

        def _task() -> None:
            try:
                # 定义进度回调函数
                def _progress(p: float, stage: str, message: str) -> None:
                    if job.cancelled:
                        raise InterruptedError("任务已被取消")
                    write_json_line(make_event_progress(job.job_id, p, stage, message))

                # 执行实际的任务处理函数
                result = handler(job, _progress)

                # 根据任务状态发送完成或取消事件
                if job.cancelled:
                    write_json_line(
                        make_event_error(job.job_id, "E_CANCELLED", "任务已被取消")
                    )
                else:
                    write_json_line(make_event_done(job.job_id, result))
            except InterruptedError:
                # 处理任务取消异常
                msg = "任务已被取消"
                write_json_line(make_event_error(job.job_id, "E_CANCELLED", msg))
                sys.stderr.write(f"[信息] {msg}: {job.job_id}\n")
                sys.stderr.flush()
            except Exception as e:
                # 处理任务执行异常
                msg = f"{e}"
                write_json_line(make_event_error(job.job_id, "E_JOB", msg))
                sys.stderr.write(f"[错误] 任务失败: {msg}\n")
                sys.stderr.flush()
            finally:
                # 任务结束后从管理器中移除
                self.remove_job(job.job_id)

        # 创建并启动后台线程执行任务
        t = threading.Thread(target=_task, daemon=True)
        t.start()
