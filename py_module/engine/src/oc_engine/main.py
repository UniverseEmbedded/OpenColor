from __future__ import annotations

import os
import sys
from typing import Any, Dict


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Python engine starting...", file=sys.stderr)
sys.stderr.flush()

from oc_engine.handlers.health import handle_health_ping
from oc_engine.handlers.board import (
    handle_board_generate,
    handle_board_export_from_spec,
    handle_quick_calib_card_generate,
)
from oc_engine.handlers.lut import handle_lut_extract, handle_lut_detect
from oc_engine.handlers.bitmap import handle_bitmap_export
from oc_engine.handlers.svg import handle_svg_export
from oc_engine.handlers.dataset import (
    handle_dataset_create,
    handle_dataset_add_observation,
    handle_dataset_aggregate,
)
from oc_engine.jobs import JobManager
from oc_engine.protocol import make_response, parse_json_line, write_json_line
from oc_engine.schema import (
    BitmapExportParams,
    BoardExportParams,
    BoardGenerateParams,
    DatasetAddObservationParams,
    DatasetAggregateParams,
    DatasetCreateParams,
    JsonRpcRequest,
    LutDetectParams,
    LutExtractParams,
    McrtValidateParams,
    SvgExportParams,
)


def _default_out_dir(method: str) -> str:
    """集中式路径策略（开发 vs 打包）"""
    from oc_core_02.core.app_paths import default_out_dir

    return str(default_out_dir(method))


def _dispatch(job_mgr: JobManager, req_dict: Dict[str, Any]) -> None:
    """分发处理 JSON-RPC 请求"""
    try:
        req = JsonRpcRequest.model_validate(req_dict)
    except Exception as e:
        id_ = req_dict.get("id") if isinstance(req_dict, dict) else ""
        write_json_line(
            {
                "jsonrpc": "2.0",
                "id": id_ or "",
                "error": {"code": "E_BAD_REQUEST", "message": f"请求格式不正确: {e}"},
            }
        )
        return

    id_ = req.id
    method = req.method
    params = req.params

    if method == "health.ping":
        result = handle_health_ping()
        write_json_line(make_response(str(id_), result))
        return

    if method == "job.cancel":
        job_id = params.get("job_id")
        if not job_id:
            write_json_line(
                {
                    "jsonrpc": "2.0",
                    "id": str(id_),
                    "error": {"code": "E_BAD_PARAMS", "message": "缺少 job_id 参数"},
                }
            )
            return
        cancelled = job_mgr.cancel_job(job_id)
        write_json_line(make_response(str(id_), {"cancelled": cancelled}))
        return

    out_dir = params.get("out_dir") or _default_out_dir(method)
    job = job_mgr.create_job(out_dir)

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
            validated_params = param_model.model_validate(params).model_dump()
            job_mgr.run_async(job, lambda j, p: handler_func(j, validated_params, p))
            write_json_line(
                make_response(str(id_), {"job_id": job.job_id, "out_dir": job.out_dir})
            )
        except Exception as e:
            write_json_line(
                {
                    "jsonrpc": "2.0",
                    "id": str(id_),
                    "error": {"code": "E_BAD_PARAMS", "message": f"参数校验失败: {e}"},
                }
            )
        return

    write_json_line(
        {
            "jsonrpc": "2.0",
            "id": str(id_),
            "error": {"code": "E_METHOD", "message": "未知方法"},
        }
    )


def main() -> None:
    """主函数：启动引擎并处理标准输入"""
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    job_mgr = JobManager()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = parse_json_line(line)
        if req is None:
            continue
        try:
            _dispatch(job_mgr, req)
        except Exception as e:
            sys.stderr.write(f"[错误] 引擎处理异常: {e}\n")
            sys.stderr.flush()
            id_ = req.get("id") if isinstance(req, dict) else ""
            write_json_line(
                {
                    "jsonrpc": "2.0",
                    "id": id_ or "",
                    "error": {"code": "E_INTERNAL", "message": "引擎内部错误"},
                }
            )


if __name__ == "__main__":
    main()
