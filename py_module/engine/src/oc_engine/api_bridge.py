from __future__ import annotations

import sys
from typing import Any, Dict

from oc_engine.handlers.bitmap import handle_bitmap_export
from oc_engine.handlers.board import (
    handle_board_generate,
    handle_board_export_from_spec,
    handle_quick_calib_card_generate,
)
from oc_engine.handlers.dataset import (
    handle_dataset_create,
    handle_dataset_add_observation,
    handle_dataset_aggregate,
)
from oc_engine.handlers.health import handle_health_ping
from oc_engine.handlers.lut import handle_lut_extract, handle_lut_detect
from oc_engine.handlers.svg import handle_svg_export
from oc_engine.jobs import JobManager
from oc_engine.schema import (
    BitmapExportParams,
    BoardExportParams,
    BoardGenerateParams,
    DatasetAddObservationParams,
    DatasetAggregateParams,
    DatasetCreateParams,
    LutDetectParams,
    LutExtractParams,
    McrtValidateParams,
    SvgExportParams,
)

# 在模块级别持有 JobManager 实例，保证状态跨调用持久
_JOB_MGR = JobManager()


def _default_out_dir(method: str) -> str:
    from oc_core_02.core.app_paths import default_out_dir

    return str(default_out_dir(method))


import json
from typing import Callable, Optional
import oc_engine.protocol as protocol

_CALLBACK: Optional[Callable[[str], None]] = None
_LOG_CALLBACK: Optional[Callable[[str, str], None]] = None
_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr


def ping() -> str:
    """
    检查 Python 引擎和原型模块是否正常工作。
    """
    res = "pong from oc_engine (Python)"

    # 检查 oc_proto 原型模块
    try:
        import oc_proto

        res += " | oc_proto 模块加载成功"

        # 检查关键子模块
        submodules = [
            "gen_masks",
            "gen_vector",
            "gen_3mf",
            "calib_color_rts",
            "calib_sample_build",
            "calib_board_gen",
        ]
        available = []
        for mod in submodules:
            try:
                __import__(f"oc_proto.{mod}")
                available.append(mod)
            except Exception:
                pass
        res += f" (子模块: {', '.join(available) if available else '无'})"
    except Exception as e:
        res += f" | [错误] 无法加载 oc_proto: {e}"

    return res


def register_callback(
    callback: Callable[[str], None],
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> None:
    global _CALLBACK, _LOG_CALLBACK
    _CALLBACK = callback
    _LOG_CALLBACK = log_callback

    if log_callback:
        sys.stdout = _LogStream("stdout", log_callback, _ORIGINAL_STDOUT)
        sys.stderr = _LogStream("stderr", log_callback, _ORIGINAL_STDERR)


class _LogStream:
    def __init__(
        self, name: str, callback: Callable[[str, str], None], fallback
    ) -> None:
        self.name = name
        self.callback = callback
        self.fallback = fallback

    def write(self, data: str):
        if data.strip():
            self.callback(self.name, data)
        try:
            self.fallback.write(data)
            self.fallback.flush()
        except Exception as e:
            if self.name == "stdout":
                sys.__stdout__.write(f"[错误] 写入原始 stdout 失败: {e}\n")
                sys.__stdout__.flush()
            else:
                sys.__stderr__.write(f"[错误] 写入原始 stderr 失败: {e}\n")
                sys.__stderr__.flush()

    def flush(self):
        try:
            self.fallback.flush()
        except Exception as e:
            if self.name == "stdout":
                sys.__stdout__.write(f"[错误] 刷新原始 stdout 失败: {e}\n")
                sys.__stdout__.flush()
            else:
                sys.__stderr__.write(f"[错误] 刷新原始 stderr 失败: {e}\n")
                sys.__stderr__.flush()


# Monkey patch protocol.write_json_line to intercept events
_original_write = protocol.write_json_line


def _intercept_write(data: Dict[str, Any]) -> None:
    if _CALLBACK:
        try:
            _CALLBACK(json.dumps(data))
        except Exception:
            # Fallback to original write if callback fails
            _original_write(data)
    else:
        _original_write(data)


protocol.write_json_line = _intercept_write


def dispatch_json(method: str, params_json: str) -> str:
    """
    接收 JSON 字符串参数，返回 JSON 字符串结果。
    方便 Rust 端通过 PyO3 调用，无需处理复杂的类型转换。
    """
    try:
        params = json.loads(params_json)
        result = dispatch_request(method, params)
        return json.dumps(result)
    except Exception as e:
        # 返回标准的 JSON-RPC 错误格式，或者自定义错误格式
        # 这里为了简单，返回一个包含 error 字段的 JSON
        return json.dumps({"error": str(e)})


def dispatch_request(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    PyO3 入口函数。
    接收方法名和参数字典，返回结果字典或抛出异常。
    """

    # 1. 简单的同步方法
    if method == "health.ping":
        return handle_health_ping()

    if method == "job.cancel":
        job_id = params.get("job_id")
        if not job_id:
            raise ValueError("缺少 job_id 参数")
        cancelled = _JOB_MGR.cancel_job(job_id)
        return {"cancelled": cancelled}

    # 2. 复杂的异步任务
    handlers = {
        "board.generate": (handle_board_generate, BoardGenerateParams),
        "board.export_from_spec": (handle_board_export_from_spec, BoardExportParams),
        "quick_calib.generate_card": (
            handle_quick_calib_card_generate,
            BoardGenerateParams,
        ),
        "lut.extract_from_photo": (handle_lut_extract, LutExtractParams),
        "lut.detect_points": (handle_lut_detect, LutDetectParams),
        "dataset.create": (handle_dataset_create, DatasetCreateParams),
        "dataset.add_observation": (
            handle_dataset_add_observation,
            DatasetAddObservationParams,
        ),
        "dataset.aggregate": (handle_dataset_aggregate, DatasetAggregateParams),
        "bitmap.export": (handle_bitmap_export, BitmapExportParams),
        "svg.export": (handle_svg_export, SvgExportParams),
    }

    if method in handlers:
        handler_func, param_model = handlers[method]
        try:
            # 校验参数
            validated_params = param_model.model_validate(params).model_dump()

            # 创建并启动任务
            out_dir = params.get("out_dir") or _default_out_dir(method)
            job = _JOB_MGR.create_job(out_dir)

            # 异步执行
            _JOB_MGR.run_async(job, lambda j, p: handler_func(j, validated_params, p))

            # 立即返回任务信息
            return {"job_id": job.job_id, "out_dir": job.out_dir}
        except Exception as e:
            raise ValueError(f"任务启动失败: {e}")

    raise ValueError(f"未知方法: {method}")
