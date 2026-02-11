from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Callable, List, Tuple

import cv2
import numpy as np

from oc_calib.calibration import (
    WarpParams,
    perspective_warp_bgr,
    render_grid_overlay_bgr,
    extract_lut_from_warped_bgr,
)
from oc_calib.calib_types import BoardSpec, Observation, create_legacy_32x32_spec
from oc_scripts.calibration.color_board.calib_geom import detect_board_quad_by_chroma
from ..jobs import Job


def _parse_points(raw: Any) -> List[Tuple[float, float]]:
    """解析角点坐标列表

    将输入的原始数据解析为包含4个角点坐标的列表

    参数:
        raw: 原始角点数据，应为包含4个点的列表

    返回:
        包含4个(x, y)元组的列表

    异常:
        ValueError: 角点数量不为4或格式不正确时抛出
    """
    pts = raw if isinstance(raw, list) else []
    if len(pts) != 4:
        raise ValueError("corner_points 需要 4 个点")
    out = []
    for p in pts:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("corner_points 格式不正确")
        out.append((float(p[0]), float(p[1])))
    return out


def _load_board_spec(params: Dict[str, Any]) -> BoardSpec:
    """从参数中加载色盘规格

    支持从 JSON 字符串、文件路径或 board_id 加载色盘规格

    参数:
        params: 包含色盘规格信息的参数字典

    返回:
        色盘规格对象

    异常:
        ValueError: 当指定了 board_id 但无法找到对应规格时抛出
    """
    board_spec_json = params.get("board_spec_json")
    board_spec_path = params.get("board_spec_path")
    board_id = params.get("board_id")

    if board_spec_json:
        if isinstance(board_spec_json, str):
            return BoardSpec.from_json(board_spec_json)
        return BoardSpec.from_json(json.dumps(board_spec_json, ensure_ascii=False))

    if board_spec_path:
        return BoardSpec.load(Path(str(board_spec_path)))

    if board_id:
        raise ValueError(
            "未找到指定 board_id，请传入 board_spec_json 或 board_spec_path"
        )

    return create_legacy_32x32_spec()


def handle_lut_detect(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理 LUT 检测：自动识别色盘角点

    通过颜色分析自动识别照片中色盘的四角位置

    参数:
        job: 任务对象
        params: 包含 photo_path（照片路径）的参数字典
        progress: 进度回调函数

    返回:
        包含识别到的角点坐标列表的字典

    异常:
        ValueError: 缺少 photo_path 或无法读取照片时抛出
        RuntimeError: 角点识别失败时抛出
    """
    photo_path = params.get("photo_path")
    if not photo_path:
        raise ValueError("缺少 photo_path")

    progress(0.2, "load", "读取照片")
    bgr = cv2.imread(str(photo_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("无法读取照片")

    progress(0.5, "detect", "自动识别角点")
    try:
        quad = detect_board_quad_by_chroma(bgr)
        pts = [[float(p[0]), float(p[1])] for p in quad.tolist()]
    except Exception as e:
        raise RuntimeError(f"自动角点识别失败: {e}")

    progress(1.0, "done", "识别完成")
    return {"corner_points": pts}


def handle_lut_extract(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理 LUT 提取：从照片中提取颜色查找表

    根据用户指定的四角坐标，对照片进行透视校正，
    然后从色盘各格中提取颜色数据，生成 LUT 和观测数据

    参数:
        job: 任务对象，包含输出目录等信息
        params: 包含照片路径、角点坐标、色盘规格等信息的参数字典
        progress: 进度回调函数

    返回:
        包含 LUT 文件路径、校正后图像路径、观测数据路径等的字典

    异常:
        ValueError: 缺少必要参数或参数格式不正确时抛出
    """
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    photo_path = params.get("photo_path")
    if not photo_path:
        raise ValueError("缺少 photo_path")

    corner_points = _parse_points(params.get("corner_points"))

    board_spec = _load_board_spec(params)
    if board_spec.rows != board_spec.cols:
        raise ValueError("当前采样仅支持正方形色盘规格")
    if board_spec.rows < 2:
        raise ValueError("色盘规格行列数不合法")

    total_cells = int(board_spec.rows)
    data_cells = max(1, total_cells - 2)
    border = 1 if total_cells >= 3 else 0

    wp = WarpParams(
        dst_size=int(params.get("dst_size", 1000)),
        total_cells=total_cells,
        zoom=float(params.get("zoom", 1.0)),
        barrel=float(params.get("barrel", 0.0)),
        offset_x=float(params.get("offset_x", 0.0)),
        offset_y=float(params.get("offset_y", 0.0)),
        auto_wb=bool(params.get("auto_wb", False)),
        vignette_fix=bool(params.get("vignette_fix", False)),
    )

    progress(0.1, "load", "读取照片")
    bgr = cv2.imread(str(photo_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("无法读取照片")

    progress(0.4, "warp", "透视校正")
    warped = perspective_warp_bgr(bgr, corner_points, wp)
    warped_path = out_dir / "board_warped.png"
    cv2.imwrite(str(warped_path), warped)

    progress(0.7, "lut", "提取 LUT")
    lut = extract_lut_from_warped_bgr(
        warped,
        total_cells=wp.total_cells,
        data_cells=data_cells,
        window_px=int(params.get("window_px", 8)),
    )
    lut_path = out_dir / "lut.npy"
    np.save(str(lut_path), lut)

    overlay = render_grid_overlay_bgr(warped, total_cells=wp.total_cells, line_step=1)
    overlay_path = out_dir / "board_overlay.png"
    cv2.imwrite(str(overlay_path), overlay)

    cell_measurements: Dict[str, Dict[str, Any]] = {}
    for r in range(data_cells):
        for c in range(data_cells):
            cell_r = r + border
            cell_c = c + border
            cell_id = f"{cell_r},{cell_c}"
            cell_measurements[cell_id] = {
                "rgb": lut[r, c].tolist(),
                "confidence": 1.0,
                "is_data": cell_id in board_spec.cell_map,
                "enabled": True,
                "error": 0.0,
                "recipe": board_spec.cell_map.get(cell_id),
            }

    obs = Observation(
        board_id=board_spec.board_id,
        photo_id=str(int(time.time())),
        photo_path=str(photo_path),
        warp_corners=corner_points,
        warp_params=wp.__dict__,
        cell_measurements=cell_measurements,
        diagnostics={
            "warped": str(warped_path),
            "overlay": str(overlay_path),
        },
        timestamp=time.time(),
    )
    obs_path = out_dir / f"observation_{obs.photo_id}.json"
    obs.save(obs_path)

    progress(1.0, "done", "完成")

    return {
        "out_dir": str(out_dir),
        "warped": str(warped_path),
        "overlay": str(overlay_path),
        "lut": str(lut_path),
        "observation": str(obs_path),
        "board_spec": {
            "board_id": board_spec.board_id,
            "name": board_spec.name,
            "rows": board_spec.rows,
            "cols": board_spec.cols,
        },
        "grid_shape": {
            "rows": total_cells,
            "cols": total_cells,
            "data_rows": data_cells,
            "data_cols": data_cells,
            "border": border,
        },
    }
