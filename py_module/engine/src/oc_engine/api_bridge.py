from __future__ import annotations

import sys
from typing import Any, Dict

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

from oc_engine.handlers.bitmap import handle_bitmap_export
from oc_engine.handlers.board import (
    handle_board_generate,
    handle_board_export_from_spec,
    handle_quick_calib_card_generate,
    handle_board_preview,
)
from oc_engine.handlers.dataset import (
    handle_dataset_create,
    handle_dataset_add_observation,
    handle_dataset_aggregate,
)
from oc_engine.handlers.health import handle_health_ping
from oc_engine.handlers.lut import handle_lut_extract, handle_lut_detect
from oc_engine.handlers.svg import handle_svg_export
from oc_engine.jobs import JobManager, _now_ms
from oc_engine.schema import (
    BitmapExportParams,
    BoardExportParams,
    BoardGenerateParams,
    BoardPreviewParams,
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


def _default_out_dir(method: str, params: Dict[str, Any] | None = None) -> str:
    from oc_core_02.core.app_paths import default_out_dir

    # 从参数中获取工作区路径
    workspace_path = None
    if params:
        workspace_path = params.get("workspace_path") or params.get("workspacePath")

    return str(default_out_dir(method, workspace_path))


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
        logger.error("Python错误: 方法 {} 调用失败: {}", method, e)
        # 返回标准的 JSON-RPC 错误格式，或者自定义错误格式
        # 这里为了简单，返回一个包含 error 字段的 JSON
        return json.dumps({"error": str(e)})


def dispatch_request(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    PyO3 入口函数。
    接收方法名和参数字典，返回结果字典或抛出异常。
    """

    # 1. 简单的同步方法
    if method == "ping":
        return {"result": ping()}

    if method == "health.ping":
        return handle_health_ping()

    if method == "job.cancel":
        job_id = params.get("job_id")
        if not job_id:
            raise ValueError("缺少 job_id 参数")
        cancelled = _JOB_MGR.cancel_job(job_id)
        return {"cancelled": cancelled}

    if method == "board.preview":
        # 同步预览方法，不需要创建任务
        try:
            validated_params = BoardPreviewParams.model_validate(params).model_dump()
            return handle_board_preview(validated_params)
        except Exception as e:
            logger.error("Python错误: 方法 {} 预览生成失败: {}", method, e)
            raise ValueError(f"预览生成失败: {e}")

    if method == "rts.predict":
        # RTS颜色预测 - 同步方法
        try:
            from oc_engine.handlers.board import _predict_color_with_rts

            recipe = params.get("recipe", [])
            profile_id = params.get("profile_id", "")

            if not recipe:
                raise ValueError("缺少recipe参数")
            if not profile_id:
                raise ValueError("缺少profile_id参数")

            target_rgb = _predict_color_with_rts(recipe, profile_id)
            return {"rgb": target_rgb}
        except Exception as e:
            logger.error("Python错误: 方法 {} RTS预测失败: {}", method, e)
            raise ValueError(f"RTS预测失败: {e}")

    if method == "board.generate":
        # 同步生成方法，直接返回结果
        try:
            from oc_engine.jobs import Job
            validated_params = BoardGenerateParams.model_validate(params).model_dump()
            
            # 处理输出目录 - 支持workspace_path和时间戳
            out_dir = params.get("out_dir")
            if not out_dir:
                workspace_path = params.get("workspace_path")
                timestamp = params.get("timestamp")
                if workspace_path and timestamp:
                    # 使用工作区路径 + 时间戳子文件夹
                    from pathlib import Path
                    out_dir = str(Path(workspace_path) / "01_board_gen" / timestamp)
                else:
                    out_dir = _default_out_dir(method, params)
            
            job = Job(job_id=f"sync_{_now_ms()}", out_dir=out_dir)
            
            def _progress(p: float, stage: str, message: str) -> None:
                print(f"[进度] {p:.2%} - {stage}: {message}", file=sys.stderr)
            
            result = handle_board_generate(job, validated_params, _progress)
            
            # 添加boards信息到结果
            from pathlib import Path
            spec_path = result.get("board_spec_path", "")
            if spec_path:
                # 从spec_path推断board信息
                spec_file = Path(spec_path)
                if spec_file.exists():
                    try:
                        spec_content = spec_file.read_text(encoding="utf-8")
                        spec_data = json.loads(spec_content)
                        rows = spec_data.get("rows", validated_params.get("rows", 26))
                        cols = spec_data.get("cols", validated_params.get("cols", 26))
                        data_cells = spec_data.get("data_cells", validated_params.get("data_cells", 24))
                        result["boards"] = [{
                            "path": spec_path,
                            "name": spec_file.stem,
                            "rows": rows,
                            "cols": cols,
                            "modifiedAt": timestamp or str(_now_ms()),
                            "dataRows": data_cells,
                            "dataCols": data_cells,
                            "cellSizeMm": validated_params.get("cell_size_mm", 4.0),
                            "layerHeightMm": validated_params.get("layer_height_mm", 0.12),
                            "layers": validated_params.get("n_layers", 5),
                        }]
                    except Exception:
                        pass
            
            return result
        except Exception as e:
            # 打印完整stacktrace到stderr，便于调试
            import traceback
            print(f"[Python错误] 方法 {method} 生成失败:", file=sys.stderr)
            traceback.print_exc()
            raise ValueError(f"生成失败: {e}")

    # 2. 复杂的异步任务
    handlers = {
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
            out_dir = params.get("out_dir") or _default_out_dir(method, params)
            job = _JOB_MGR.create_job(out_dir)

            # 异步执行
            _JOB_MGR.run_async(job, lambda j, p: handler_func(j, validated_params, p))

            # 立即返回任务信息
            return {"job_id": job.job_id, "out_dir": job.out_dir}
        except Exception as e:
            # 打印完整stacktrace到stderr，便于调试
            import traceback
            print(f"[Python错误] 方法 {method} 任务启动失败:", file=sys.stderr)
            traceback.print_exc()
            raise ValueError(f"任务启动失败: {e}")

    raise ValueError(f"未知方法: {method}")
