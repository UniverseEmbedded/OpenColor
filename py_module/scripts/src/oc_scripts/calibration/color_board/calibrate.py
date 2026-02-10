#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用于真实用户照片 + ROI裁剪的稳健校准板采样器。

主要升级：
- --roi x,y,w,h：模拟UI框选（检测前裁剪）
- 基于色度的四边形检测（不易被接缝欺骗）
- --quad-expand：将检测到的四边形向外扩展（修复"只向内收缩"问题）
- 网格细化升级：
  * 从梯度投影估计pitch_x/pitch_y（在预期附近的FFT峰值）
  * 使用估计的pitch细化dx/dy
  * 使用独立的scale_x/scale_y进行毫米到像素的映射，修复"左边对、右边漂移"问题
- 调试产物：
  * debug_mask/edges/quad
  * debug_proj_x/debug_proj_y（投影 + 估计的pitch）
- 仍支持：--corners / --use-image-corners / --rot90 / --flip-x / --flip-y

输出到 --outdir：
- debug/*（mask/edges/quad/projections）
- warped.png
- overlay.png
- samples_tiles.json
- report.json
- materials_calibrated_from_board.json（如果基础文件存在）
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np

from oc_scripts.calibration.color_board.calib_color import bgr_to_lab, deltaE76, linear01_to_srgb, srgb_to_linear01
from oc_scripts.calibration.color_board.calib_geom import (
    detect_board_quad_by_chroma,
    expand_quad,
    order_quad_points,
    parse_corners,
    warp_perspective,
)
from oc_scripts.calibration.calibrate_color_board_io import _read_image_unicode, _write_png
from oc_scripts.calibration.color_board.projection import (
    draw_projection_debug,
    estimate_pitch_fft,
    gradient_projections,
    refine_dxdy,
)



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# ---------------- 数据 ----------------

@dataclass
class TileSample:
    tile_id: int
    ix: int
    iy: int
    rect_mm: Dict[str, float]
    view_sequence: List[str]
    print_sequence: List[str]
    heights_mm: List[float]
    measured_srgb: List[int]
    measured_linear_rgb01: List[float]


# ---------------- 主程序 ----------------

def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--photo", required=True, help="校准板照片路径（jpg/png）")
    ap.add_argument("--recipes", required=True, help="*_recipes.json路径")
    ap.add_argument("--outdir", required=True, help="输出目录")

    ap.add_argument("--scale", type=float, default=10.0, help="扭曲目标的标称每毫米像素数（仅先验）。")
    ap.add_argument("--sample-frac", type=float, default=0.55, help="每色块的中心裁剪比例")
    ap.add_argument("--roi", default=None, help="输入上的可选裁剪ROI：'x,y,w,h'（UI框选）")
    ap.add_argument("--analyze", action="store_true", help="仅转储分析产物；不计算材料/报告。")

    ap.add_argument("--corners", default=None, help="手动角点：'x1,y1 x2,y2 x3,y3 x4,y4'，ROI坐标")
    ap.add_argument("--corners-are-ordered", action="store_true", help="将--corners视为TL TR BR BL。")
    ap.add_argument("--use-image-corners", action="store_true", help="跳过检测，使用ROI/完整图像角点。")
    ap.add_argument("--min-quad-area-frac", type=float, default=0.25, help="如果四边形太小则回退到完整角点。")
    ap.add_argument("--quad-expand", type=float, default=0.08, help="将检测到的四边形向外扩展此比例（0.0禁用）。")

    ap.add_argument("--rot90", type=int, default=0, choices=[0, 1, 2, 3], help="将扭曲图像顺时针旋转90° k次。")
    ap.add_argument("--flip-x", action="store_true", help="左右翻转扭曲图像。")
    ap.add_argument("--flip-y", action="store_true", help="上下翻转扭曲图像。")

    ap.add_argument("--no-border", action="store_true", help="将角点视为网格角点（忽略params.border_mm）。")

    ap.add_argument("--refine-steps", type=int, default=61, help="dx/dy细化的搜索步数。")
    ap.add_argument("--pitch-search-frac", type=float, default=0.35, help="FFT pitch搜索范围围绕预期（+/- 比例）。")
    ap.add_argument("--base-materials", default="materials_calibrated.json", help="如果存在则更新的基础材料json。")

    args = ap.parse_args()

    photo_path = Path(args.photo)
    recipes_path = Path(args.recipes)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    debug_dir = outdir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    recipes = json.loads(recipes_path.read_text(encoding="utf-8"))
    params = recipes.get("params", {})

    centered = bool(params.get("center", False))
    grid_nx = int(params.get("grid_nx", 0) or 0)
    grid_ny = int(params.get("grid_ny", 0) or 0)

    grid_w_mm = float(params.get("grid_mm", {}).get("w", 0.0))
    grid_h_mm = float(params.get("grid_mm", {}).get("h", 0.0))
    if grid_w_mm <= 0 or grid_h_mm <= 0:
        tiles0 = recipes["tiles"]
        maxx = max(t["rect_mm"]["x"] + t["rect_mm"]["w"] for t in tiles0)
        maxy = max(t["rect_mm"]["y"] + t["rect_mm"]["h"] for t in tiles0)
        grid_w_mm, grid_h_mm = float(maxx), float(maxy)

    border_mm = float(params.get("border_mm", 0.0))
    if args.no_border:
        border_mm = 0.0

    x0_card = -grid_w_mm / 2.0 if centered else 0.0
    y0_card = -grid_h_mm / 2.0 if centered else 0.0
    x_min = x0_card - border_mm
    y_min = y0_card - border_mm
    outer_w_mm = grid_w_mm + 2.0 * border_mm
    outer_h_mm = grid_h_mm + 2.0 * border_mm

    out_w_px = int(round(outer_w_mm * args.scale))
    out_h_px = int(round(outer_h_mm * args.scale))
    if out_w_px < 50 or out_h_px < 50:
        raise RuntimeError("扭曲尺寸太小；请检查--scale和板毫米参数。")

    img_full = _read_image_unicode(str(photo_path), flags=cv2.IMREAD_COLOR)

    # ROI裁剪（模拟UI框选）
    roi = None
    img = img_full
    if args.roi:
        x, y, w, h = [int(round(float(v))) for v in args.roi.split(",")]
        x = max(0, min(x, img_full.shape[1] - 1))
        y = max(0, min(y, img_full.shape[0] - 1))
        w = max(1, min(w, img_full.shape[1] - x))
        h = max(1, min(h, img_full.shape[0] - y))
        roi = (x, y, w, h)
        img = img_full[y:y + h, x:x + w].copy()

    img_h, img_w = img.shape[:2]

    def full_image_quad() -> np.ndarray:
        return np.array([[0, 0], [img_w - 1, 0], [img_w - 1, img_h - 1], [0, img_h - 1]], dtype=np.float32)

    # 选择四边形
    if args.corners:
        quad_raw = parse_corners(args.corners)
        quad = quad_raw.astype(np.float32) if args.corners_are_ordered else order_quad_points(quad_raw)
        vis = img.copy()
        cv2.polylines(vis, [quad.astype(np.int32)], True, (0, 255, 0), 3)
        _write_png(debug_dir / "debug_quad_manual.png", vis)
    elif args.use_image_corners:
        quad = full_image_quad()
    else:
        quad = detect_board_quad_by_chroma(img, debug_dir=debug_dir)
        quad_area = float(cv2.contourArea(quad.reshape(-1, 1, 2)))
        img_area = float(img_w * img_h)
        if img_area > 0 and quad_area / img_area < float(args.min_quad_area_frac):
            logger.warning(f"[警告] 检测到的四边形太小（面积比例={quad_area/img_area:.3f}），回退到ROI角点。")
            quad = full_image_quad()

    # 向外扩展四边形（修复仅向内收缩问题）
    quad = expand_quad(quad, float(args.quad_expand), img_w=img_w, img_h=img_h)

    vis2 = img.copy()
    cv2.polylines(vis2, [quad.astype(np.int32)], True, (0, 0, 255), 3)
    _write_png(debug_dir / "debug_quad_final.png", vis2)

    # 扭曲
    warped, _H = warp_perspective(img, quad, out_w_px, out_h_px)

    # 方向修正
    rot90 = int(args.rot90) % 4
    if rot90 == 1:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    elif rot90 == 2:
        warped = cv2.rotate(warped, cv2.ROTATE_180)
    elif rot90 == 3:
        warped = cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if args.flip_x:
        warped = cv2.flip(warped, 1)
    if args.flip_y:
        warped = cv2.flip(warped, 0)

    _write_png(outdir / "warped.png", warped)

    # 投影 + pitch估计
    col_sum, row_sum = gradient_projections(warped)

    tile_mm = float(params.get("tile_mm", 0.0) or 0.0)
    pitch_mm = float(params.get("pitch_mm", tile_mm) or tile_mm)
    if pitch_mm <= 0:
        pitch_mm = tile_mm if tile_mm > 0 else (grid_w_mm / max(grid_nx, 1))

    expected_pitch_px = float(pitch_mm * args.scale)

    pitch_x = estimate_pitch_fft(col_sum, expected_pitch_px, search_frac=float(args.pitch_search_frac))
    pitch_y = estimate_pitch_fft(row_sum, expected_pitch_px, search_frac=float(args.pitch_search_frac))

    draw_projection_debug(col_sum, pitch_x, debug_dir / "debug_proj_x.png", "col_sum")
    draw_projection_debug(row_sum, pitch_y, debug_dir / "debug_proj_y.png", "row_sum")

    # 细化dx/dy（使用估计的pitch）
    dx_ref, dy_ref, refine_score = 0.0, 0.0, 1.0
    if grid_nx > 0 and grid_ny > 0 and pitch_x > 5 and pitch_y > 5:
        dx_ref, dy_ref, refine_score = refine_dxdy(
            col_sum, row_sum, nx=grid_nx, ny=grid_ny, pitch_x=pitch_x, pitch_y=pitch_y, search_steps=int(args.refine_steps)
        )

    # 每轴毫米到像素的比例校正（这修复了左边对、右边漂移）
    scale_x = float(pitch_x / pitch_mm) if pitch_mm > 0 else float(args.scale)
    scale_y = float(pitch_y / pitch_mm) if pitch_mm > 0 else float(args.scale)

    if refine_score < 1.10:
        logger.warning(f"[警告] refine_score较低（{refine_score:.2f}）。可能是部分裁剪/严重模糊/布局不匹配。")

    # 叠加 + 采样
    out_h_px, out_w_px = warped.shape[:2]
    overlay = warped.copy()

    cv2.putText(
        overlay,
        f"rot90={rot90} flip_x={bool(args.flip_x)} flip_y={bool(args.flip_y)} center={centered} "
        f"pitch(px)=({pitch_x:.1f},{pitch_y:.1f}) scale(mm->px)=({scale_x:.2f},{scale_y:.2f}) "
        f"refine(dx,dy)=({dx_ref:.1f},{dy_ref:.1f}) score={refine_score:.2f}",
        (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    sample_frac = float(np.clip(args.sample_frac, 0.1, 0.95))
    tiles: List[TileSample] = []
    clipped_tiles = 0

    for t in recipes["tiles"]:
        rect = t["rect_mm"]

        # 使用校正的比例 + 细化的平移将板毫米映射到扭曲像素
        x_mm = float(rect["x"]) - x_min
        y_mm = float(rect["y"]) - y_min
        w_mm = float(rect["w"])
        h_mm = float(rect["h"])

        x0 = int(round(dx_ref + x_mm * scale_x))
        y0 = int(round(dy_ref + y_mm * scale_y))
        x1 = int(round(dx_ref + (x_mm + w_mm) * scale_x))
        y1 = int(round(dy_ref + (y_mm + h_mm) * scale_y))

        x0c, y0c = max(0, x0), max(0, y0)
        x1c, y1c = min(out_w_px, x1), min(out_h_px, y1)
        if x1c - x0c <= 2 or y1c - y0c <= 2:
            clipped_tiles += 1
            continue

        sw = int(round((x1c - x0c) * sample_frac))
        sh = int(round((y1c - y0c) * sample_frac))
        cx = (x0c + x1c) // 2
        cy = (y0c + y1c) // 2
        sx0 = max(0, cx - sw // 2)
        sy0 = max(0, cy - sh // 2)
        sx1 = min(out_w_px, sx0 + sw)
        sy1 = min(out_h_px, sy0 + sh)

        roi_img = warped[sy0:sy1, sx0:sx1, :]
        if roi_img.size == 0:
            clipped_tiles += 1
            continue

        roi_rgb = roi_img[..., ::-1].astype(np.float32) / 255.0
        med_rgb01 = np.median(roi_rgb.reshape(-1, 3), axis=0)
        med_lin01 = srgb_to_linear01(med_rgb01)
        med_srgb255 = (np.clip(med_rgb01, 0, 1) * 255.0 + 0.5).astype(np.uint8)

        tiles.append(
            TileSample(
                tile_id=int(t["tile_id"]),
                ix=int(t.get("ix", -1)),
                iy=int(t.get("iy", -1)),
                rect_mm=rect,
                view_sequence=list(t.get("view_sequence", [])),
                print_sequence=list(t.get("print_sequence", [])),
                heights_mm=list(t.get("heights_mm", [])),
                measured_srgb=[int(med_srgb255[0]), int(med_srgb255[1]), int(med_srgb255[2])],
                measured_linear_rgb01=[float(med_lin01[0]), float(med_lin01[1]), float(med_lin01[2])],
            )
        )

        cv2.rectangle(overlay, (x0c, y0c), (x1c, y1c), (0, 255, 0), 1)
        cv2.rectangle(overlay, (sx0, sy0), (sx1, sy1), (255, 255, 255), 1)

        if int(t.get("ix", -1)) == 0 and int(t.get("iy", -1)) == 0:
            cv2.putText(overlay, "(0,0)", (x0c + 2, y0c + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    _write_png(outdir / "overlay.png", overlay)

    # 始终保存样本（对下游有用）
    samples_out = {
        "photo": str(photo_path),
        "recipes": str(recipes_path),
        "roi": roi,
        "params": {
            "grid_w_mm": grid_w_mm,
            "grid_h_mm": grid_h_mm,
            "grid_nx": grid_nx,
            "grid_ny": grid_ny,
            "tile_mm": tile_mm,
            "pitch_mm": pitch_mm,
            "center": centered,
            "border_mm": border_mm,
            "scale_nominal_px_per_mm": float(args.scale),
            "pitch_est_px_x": float(pitch_x),
            "pitch_est_px_y": float(pitch_y),
            "scale_est_px_per_mm_x": float(scale_x),
            "scale_est_px_per_mm_y": float(scale_y),
            "refine_dx_px": float(dx_ref),
            "refine_dy_px": float(dy_ref),
            "refine_score": float(refine_score),
            "quad_expand": float(args.quad_expand),
        },
        "stats": {
            "tiles_total": int(len(recipes.get("tiles", []))),
            "tiles_sampled": int(len(tiles)),
            "tiles_clipped": int(clipped_tiles),
        },
        "tiles": [t.__dict__ for t in tiles],
    }
    (outdir / "samples_tiles.json").write_text(json.dumps(samples_out, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.analyze:
        logger.info("[成功] 分析完成。请查看：")
        logger.info(" -", outdir / "debug" / "debug_quad_final.png")
        logger.info(" -", outdir / "debug" / "debug_proj_x.png")
        logger.info(" -", outdir / "debug" / "debug_proj_y.png")
        logger.info(" -", outdir / "warped.png")
        logger.info(" -", outdir / "overlay.png")
        logger.info(" -", outdir / "samples_tiles.json")
        return

    # ---- v1 从纯色色块估计材料 ----
    materials = list(params.get("materials", []))
    if not materials:
        mats = set()
        for tt in tiles:
            mats.update(tt.view_sequence)
        materials = sorted(mats)

    mat_lin_colors: Dict[str, np.ndarray] = {}
    mat_srgb_colors: Dict[str, List[int]] = {}

    for m in materials:
        pure = [tt for tt in tiles if tt.view_sequence and all(x == m for x in tt.view_sequence)]
        if not pure:
            pure = [tt for tt in tiles if tt.print_sequence and all(x == m for x in tt.print_sequence)]
        if not pure:
            continue
        arr = np.array([tt.measured_linear_rgb01 for tt in pure], dtype=np.float32)
        med_lin = np.median(arr, axis=0)
        mat_lin_colors[m] = med_lin
        srgb01 = linear01_to_srgb(med_lin)
        srgb255 = (np.clip(srgb01, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        mat_srgb_colors[m] = [int(srgb255[0]), int(srgb255[1]), int(srgb255[2])]

    def srgb255_to_lab(srgb255: np.ndarray) -> np.ndarray:
        bgr = srgb255[..., ::-1].astype(np.uint8)
        return bgr_to_lab(bgr)

    tile_errors = []
    for tt in tiles:
        if not tt.view_sequence or not tt.heights_mm:
            continue
        if any(m not in mat_lin_colors for m in set(tt.view_sequence)):
            continue

        thick: Dict[str, float] = {m: 0.0 for m in mat_lin_colors.keys()}
        for m, h in zip(tt.view_sequence, tt.heights_mm):
            if m in thick:
                thick[m] += float(h)
        tot = sum(thick.values())
        if tot <= 0:
            continue

        pred_lin = np.zeros(3, dtype=np.float32)
        for m, th in thick.items():
            if th > 0:
                pred_lin += (th / tot) * mat_lin_colors[m]

        pred_srgb01 = linear01_to_srgb(pred_lin)
        pred_srgb255 = (np.clip(pred_srgb01, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        meas_srgb255 = np.array(tt.measured_srgb, dtype=np.uint8)

        lab_pred = srgb255_to_lab(pred_srgb255.reshape(1, 1, 3))[0, 0]
        lab_meas = srgb255_to_lab(meas_srgb255.reshape(1, 1, 3))[0, 0]
        de = deltaE76(lab_pred, lab_meas)

        tile_errors.append(
            {
                "tile_id": tt.tile_id,
                "ix": tt.ix,
                "iy": tt.iy,
                "deltaE76": de,
                "measured_srgb": tt.measured_srgb,
                "predicted_srgb": [int(pred_srgb255[0]), int(pred_srgb255[1]), int(pred_srgb255[2])],
            }
        )

    de_vals = [e["deltaE76"] for e in tile_errors]
    report = {
        "photo": str(photo_path),
        "recipes": str(recipes_path),
        "materials_estimated": {
            m: {
                "color_srgb": mat_srgb_colors[m],
                "color_linear_rgb01": [float(x) for x in mat_lin_colors[m]],
                "source": "median_of_pure_tiles",
            }
            for m in mat_lin_colors.keys()
        },
        "error_metric": {
            "name": "DeltaE76",
            "note": "测量值 vs 厚度加权线性混合基线。",
            "tile_count": len(de_vals),
            "mean": float(np.mean(de_vals)) if de_vals else None,
            "median": float(np.median(de_vals)) if de_vals else None,
            "p90": float(np.percentile(de_vals, 90)) if de_vals else None,
        },
        "tile_errors": tile_errors[:5000],
        "sampling_stats": samples_out["stats"],
        "refine": samples_out["params"],
    }
    (outdir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    base_path = Path(args.base_materials)
    updated_path = outdir / "materials_calibrated_from_board.json"
    if base_path.exists():
        base = json.loads(base_path.read_text(encoding="utf-8"))
        mats_obj = base.get("materials", {})
        for m, c in mat_srgb_colors.items():
            if m in mats_obj:
                mats_obj[m]["color_srgb"] = c
            else:
                mats_obj[m] = {"name": m, "color_srgb": c}
        base["materials"] = mats_obj
        updated_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("[成功] 已写入：")
    logger.info(" -", outdir / "debug")
    logger.info(" -", outdir / "warped.png")
    logger.info(" -", outdir / "overlay.png")
    logger.info(" -", outdir / "samples_tiles.json")
    logger.info(" -", outdir / "report.json")
    if updated_path.exists():
        logger.info(" -", updated_path)
    if mat_srgb_colors:
        logger.info("\n估计的材料颜色（sRGB 0-255）：")
        for m in materials:
            if m in mat_srgb_colors:
                logger.info(f"  {m}: {mat_srgb_colors[m]}")
    if de_vals:
        logger.info("\n基线误差（DeltaE76）：")
        logger.info(f"  色块数={len(de_vals)} 均值={np.mean(de_vals):.2f} 中位数={np.median(de_vals):.2f} p90={np.percentile(de_vals,90):.2f}")


if __name__ == "__main__":
    main()
