"""波点测试图生成模块 - 生成波点测试图并送入gen_masks管线处理

用于测试颜色求解器在不同颜色、不同饱和度/亮度、不同空间频率（波点大小）
以及波点偏移-重叠场景下的表现。

测试图结构:
- 区域A (主测试): 波点大小 × HSB颜色矩阵
  - 水平: 波点从小到大 (4px → 32px)
  - 垂直: HSB颜色轮转 + 饱和度/亮度变化
- 区域B (偏移-重叠测试): 不同颜色对的偏移重叠效果
  - 水平: 偏移量 0% → 100%
  - 垂直: 不同颜色组合 (互补/邻近/冷暖等)
"""

import json
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from oc_core_02.core.bitmap_pipeline import BitmapParams
from oc_core_02.core.color_systems import ColorSystem
from oc_sdf.sdf_data_prep import generate_layer_volumes
from oc_xgb.color_space import lab_to_rgb01, rgb01_to_lab
from oc_xgb.model_io import load_model
from oc_proto.gen_masks.solver_cpp_wrapper import CPP_AVAILABLE, create_solver


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def hsb_to_rgb(h: float, s: float, b: float) -> Tuple[int, int, int]:
    """将HSB颜色转换为RGB

    参数:
        h: 色相 0-360
        s: 饱和度 0-100
        b: 亮度 0-100

    返回:
        (R, G, B) 元组，每个值0-255
    """
    s = s / 100.0
    v = b / 100.0

    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    r = int((r + m) * 255)
    g = int((g + m) * 255)
    b_val = int((b + m) * 255)

    return (r, g, b_val)


def _rmtree_retry(p: Path, *, tries: int = 8, wait_s: float = 0.2) -> None:
    """带重试的目录删除"""
    for i in range(int(tries)):
        try:
            shutil.rmtree(p)
            return
        except PermissionError as e:
            if i >= int(tries) - 1:
                raise
            logger.error(
                f"警告: 删除目录失败(可能被占用)，将重试 {i + 1}/{tries}: {p}，原因={e}"
            )
            time.sleep(float(wait_s))


def _clear_dir_keep_root(d: Path) -> None:
    """清空目录但保留根目录"""
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        return
    for child in d.iterdir():
        if child.is_dir():
            _rmtree_retry(child)
        else:
            try:
                child.unlink()
            except PermissionError as e:
                logger.error(f"警告: 删除文件失败(可能被占用): {child}，原因={e}")
                raise


def _find_model_dir(calib_root: Path) -> Path:
    """查找模型目录"""
    candidates: list[tuple[int, float, Path]] = []
    for meta_path in calib_root.rglob("color_model.json"):
        model_dir = meta_path.parent
        npz_path = model_dir / "phys_gpr_model.npz"
        if not npz_path.exists():
            continue
        try:
            mtime = meta_path.stat().st_mtime
        except Exception as e:
            logger.warning(f"警告: 无法读取模型时间戳: {meta_path}，原因={e}")
            mtime = 0.0
        p = str(model_dir).lower()
        prefer_four_flux = 1 if "four_flux" in p else 0
        candidates.append((prefer_four_flux, mtime, model_dir))
    if not candidates:
        raise FileNotFoundError(f"在目录中未找到可用模型: {calib_root}")
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def draw_dot_pattern_base(
    width: int = 1024,
    height: int = 640,
) -> Tuple[np.ndarray, dict]:
    """绘制波点测试图基础版本

    返回:
        (rgba数组, 元数据字典)
    """
    # 创建白色背景
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    metadata = {
        "version": "dot_pattern_v1",
        "width": width,
        "height": height,
        "sections": {},
    }

    # ========== 区域A: 主测试区域 (波点大小 × HSB颜色) ==========
    # 布局: 6行 × 4档大小
    section_a_y = 0
    section_a_h = 480
    section_a_rows = 6
    section_a_cols = 4  # 4档大小

    # 波点大小配置
    dot_sizes = [4, 8, 16, 32]  # 小到大

    # 颜色行配置 (HSB)
    color_rows = [
        # (描述, 色相范围, 饱和度, 亮度)
        ("色相全饱和全亮", (0, 360), 100, 100),
        ("色相半饱和全亮", (0, 360), 50, 100),
        ("色相全饱和半亮", (0, 360), 100, 50),
        ("灰阶", None, 0, None),  # 特殊处理
        ("暖色调", (0, 60), 100, 100),  # 红到黄
        ("冷色调", (180, 240), 100, 100),  # 青到蓝
    ]

    row_height = section_a_h // section_a_rows
    col_width = width // section_a_cols

    metadata["sections"]["main_test"] = {
        "y_range": [section_a_y, section_a_y + section_a_h],
        "rows": [],
        "cols": [],
    }

    for row_idx, (desc, hue_range, sat, bri) in enumerate(color_rows):
        y_start = section_a_y + row_idx * row_height
        y_end = y_start + row_height

        row_info = {
            "index": row_idx,
            "description": desc,
            "y_range": [y_start, y_end],
            "cells": [],
        }

        for col_idx, dot_size in enumerate(dot_sizes):
            x_start = col_idx * col_width
            x_end = x_start + col_width

            # 绘制这一格的波点
            cell_info = _draw_dot_cell(
                draw,
                img,
                x_start,
                y_start,
                x_end,
                y_end,
                dot_size,
                hue_range,
                sat,
                bri,
                row_idx,
                col_idx,
            )
            row_info["cells"].append(cell_info)

        metadata["sections"]["main_test"]["rows"].append(row_info)

    # ========== 区域B: 偏移-重叠测试区域 ==========
    section_b_y = section_a_h
    section_b_h = height - section_a_h
    section_b_rows = 4

    # 颜色对配置
    color_pairs = [
        ("红+青(互补)", (255, 0, 0), (0, 255, 255)),
        ("红+黄(邻近)", (255, 0, 0), (255, 255, 0)),
        ("蓝+黄(冷暖)", (0, 0, 255), (255, 255, 0)),
        ("黑+白(极端)", (0, 0, 0), (255, 255, 255)),
    ]

    # 偏移量配置: 0%, 25%, 50%, 75%, 100%
    offsets_pct = [0, 25, 50, 75, 100]

    row_height_b = section_b_h // section_b_rows
    col_width_b = width // len(offsets_pct)

    metadata["sections"]["overlap_test"] = {
        "y_range": [section_b_y, section_b_y + section_b_h],
        "rows": [],
    }

    for row_idx, (desc, color_a, color_b) in enumerate(color_pairs):
        y_start = section_b_y + row_idx * row_height_b
        y_end = y_start + row_height_b

        row_info = {
            "index": row_idx,
            "description": desc,
            "color_a": color_a,
            "color_b": color_b,
            "y_range": [y_start, y_end],
            "cells": [],
        }

        for col_idx, offset_pct in enumerate(offsets_pct):
            x_start = col_idx * col_width_b
            x_end = x_start + col_width_b

            cell_info = _draw_overlap_cell(
                draw,
                img,
                x_start,
                y_start,
                x_end,
                y_end,
                color_a,
                color_b,
                offset_pct,
                row_idx,
                col_idx,
            )
            row_info["cells"].append(cell_info)

        metadata["sections"]["overlap_test"]["rows"].append(row_info)

    # 转换为numpy数组
    rgba_array = np.array(img)

    return rgba_array, metadata


def _draw_dot_cell(
    draw: ImageDraw.Draw,
    img: Image.Image,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    dot_size: int,
    hue_range: tuple | None,
    sat: int,
    bri: int,
    row_idx: int,
    col_idx: int,
) -> dict:
    """绘制单个波点单元格"""

    cell_w = x2 - x1
    cell_h = y2 - y1

    # 边距
    margin = 8
    draw_x1 = x1 + margin
    draw_y1 = y1 + margin
    draw_x2 = x2 - margin
    draw_y2 = y2 - margin

    # 绘制边框
    draw.rectangle([x1, y1, x2, y2], outline=(200, 200, 200, 255), width=1)

    if hue_range is None:
        # 灰阶行特殊处理
        return _draw_gray_dots(
            draw, draw_x1, draw_y1, draw_x2, draw_y2, dot_size, row_idx, col_idx
        )

    # 计算波点排列
    spacing = dot_size * 2  # 波点间距为直径的2倍

    # 在单元格内均匀分布波点
    avail_w = draw_x2 - draw_x1
    avail_h = draw_y2 - draw_y1

    n_dots_x = max(1, avail_w // spacing)
    n_dots_y = max(1, avail_h // spacing)

    # 计算起始位置以居中
    total_w = (n_dots_x - 1) * spacing + dot_size
    total_h = (n_dots_y - 1) * spacing + dot_size
    start_x = draw_x1 + (avail_w - total_w) // 2 + dot_size // 2
    start_y = draw_y1 + (avail_h - total_h) // 2 + dot_size // 2

    hue_start, hue_end = hue_range

    for iy in range(n_dots_y):
        for ix in range(n_dots_x):
            # 根据x位置计算色相
            if n_dots_x > 1:
                hue = hue_start + (hue_end - hue_start) * ix / (n_dots_x - 1)
            else:
                hue = hue_start

            # 确保色相在0-360范围内
            hue = hue % 360

            rgb = hsb_to_rgb(hue, sat, bri)

            cx = start_x + ix * spacing
            cy = start_y + iy * spacing

            draw.ellipse(
                [
                    cx - dot_size // 2,
                    cy - dot_size // 2,
                    cx + dot_size // 2,
                    cy + dot_size // 2,
                ],
                fill=rgb + (255,),
            )

    return {
        "row": row_idx,
        "col": col_idx,
        "dot_size": dot_size,
        "n_dots": [n_dots_x, n_dots_y],
        "hue_range": hue_range,
        "saturation": sat,
        "brightness": bri,
    }


def _draw_gray_dots(
    draw: ImageDraw.Draw,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    dot_size: int,
    row_idx: int,
    col_idx: int,
) -> dict:
    """绘制灰阶波点"""

    cell_w = x2 - x1
    cell_h = y2 - y1

    spacing = dot_size * 2
    avail_w = x2 - x1
    avail_h = y2 - y1

    n_dots_x = max(1, avail_w // spacing)
    n_dots_y = max(1, avail_h // spacing)

    total_w = (n_dots_x - 1) * spacing + dot_size
    total_h = (n_dots_y - 1) * spacing + dot_size
    start_x = x1 + (avail_w - total_w) // 2 + dot_size // 2
    start_y = y1 + (avail_h - total_h) // 2 + dot_size // 2

    for iy in range(n_dots_y):
        for ix in range(n_dots_x):
            # 灰阶从黑到白
            if n_dots_x > 1:
                gray_val = int(255 * ix / (n_dots_x - 1))
            else:
                gray_val = 128

            rgb = (gray_val, gray_val, gray_val)

            cx = start_x + ix * spacing
            cy = start_y + iy * spacing

            draw.ellipse(
                [
                    cx - dot_size // 2,
                    cy - dot_size // 2,
                    cx + dot_size // 2,
                    cy + dot_size // 2,
                ],
                fill=rgb + (255,),
            )

    return {
        "row": row_idx,
        "col": col_idx,
        "dot_size": dot_size,
        "n_dots": [n_dots_x, n_dots_y],
        "type": "gray_scale",
    }


def _draw_overlap_cell(
    draw: ImageDraw.Draw,
    img: Image.Image,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color_a: Tuple[int, int, int],
    color_b: Tuple[int, int, int],
    offset_pct: int,
    row_idx: int,
    col_idx: int,
) -> dict:
    """绘制偏移-重叠单元格"""

    cell_w = x2 - x1
    cell_h = y2 - y1

    # 边距
    margin = 10
    draw_x1 = x1 + margin
    draw_y1 = y1 + margin
    draw_x2 = x2 - margin
    draw_y2 = y2 - margin

    # 绘制边框
    draw.rectangle([x1, y1, x2, y2], outline=(180, 180, 180, 255), width=1)

    # 波点大小固定为24px
    dot_size = 24
    radius = dot_size // 2

    # 计算中心位置
    center_y = (draw_y1 + draw_y2) // 2

    # 可用宽度
    avail_w = draw_x2 - draw_x1

    # 计算偏移量
    # offset_pct=0: 完全重叠 (A和B在同一位置)
    # offset_pct=100: 刚好相切 (A和B边缘接触)
    max_offset = dot_size  # 直径
    offset_px = int(max_offset * offset_pct / 100)

    # 计算两个波点的位置 (水平排列，A在左，B向右偏移)
    center_x_a = draw_x1 + (avail_w - offset_px) // 2
    center_x_b = center_x_a + offset_px

    # 绘制波点A (底层/左侧)
    draw.ellipse(
        [
            center_x_a - radius,
            center_y - radius,
            center_x_a + radius,
            center_y + radius,
        ],
        fill=color_a + (255,),
    )

    # 绘制波点B (顶层/右侧，带偏移)
    draw.ellipse(
        [
            center_x_b - radius,
            center_y - radius,
            center_x_b + radius,
            center_y + radius,
        ],
        fill=color_b + (255,),
    )

    # 在角落标注偏移百分比
    label = f"{offset_pct}%"
    # 使用小矩形作为标签背景
    label_w = 28
    label_h = 14
    draw.rectangle(
        [x1 + 2, y1 + 2, x1 + 2 + label_w, y1 + 2 + label_h], fill=(255, 255, 255, 200)
    )

    return {
        "row": row_idx,
        "col": col_idx,
        "offset_percent": offset_pct,
        "offset_pixels": offset_px,
        "color_a": color_a,
        "color_b": color_b,
        "dot_size": dot_size,
    }


def run_gen_masks_pipeline(
    input_image_path: Path,
    out_dir: Path,
) -> None:
    """运行gen_masks管线处理测试图"""

    start_wall = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"开始时间: {start_wall}")

    # 定位模型目录
    prototype_dir = Path(__file__).resolve().parent
    calib_root = prototype_dir.parent / "calib_color_rts"
    model_dir = _find_model_dir(calib_root)
    logger.info(f"使用模型目录: {model_dir}")

    # 检查C++求解器可用性
    if not CPP_AVAILABLE:
        raise RuntimeError(
            "当前环境无法导入 opencolor_solver.pyd，无法按要求使用C++求解器"
        )

    # 加载模型和创建求解器
    model = load_model(model_dir)
    solver = create_solver(model, use_cpp=True, force_cpp=True)

    # 创建颜色系统
    cs = ColorSystem.from_material_keys(
        name="DynamicModelSystem",
        keys=model.optical.material_keys,
    )

    n_layers = int(model.optical.n_layers)
    if n_layers != 5:
        logger.warning(f"警告: 当前模型层数为 {n_layers}，不是 5。仍将按模型层数输出。")

    # 准备输出目录 - 只清空子目录，保留根目录中的文件
    out_dir.mkdir(parents=True, exist_ok=True)

    # 创建子目录（如果不存在）
    input_dir = out_dir / "00_input"
    preview_dir = out_dir / "01_preview"
    mask_dir = out_dir / "02_masks"
    layer_viz_dir = out_dir / "04_layer_solved_palette"
    for d in [input_dir, preview_dir, mask_dir, layer_viz_dir]:
        d.mkdir(parents=True, exist_ok=True)
        # 清空子目录内容
        _clear_dir_keep_root(d)

    # 设置位图参数
    params = BitmapParams()
    params.n_layers = n_layers
    params.auto_bg_remove = False

    # 加载输入图像
    input_img = Image.open(input_image_path)
    rgba_u8 = np.array(input_img)
    h, w = rgba_u8.shape[:2]

    # 复制输入图像到输出目录
    shutil.copy(input_image_path, input_dir / input_image_path.name)
    logger.info(f"已复制输入图像: {input_image_path.name} ({w}x{h})")

    # 准备像素数据
    rgb01 = rgba_u8[..., :3].astype(np.float32) / 255.0
    pix = rgb01.reshape(-1, 3)
    # 去重以加速求解
    unique_pix, inverse = np.unique(pix, axis=0, return_inverse=True)
    logger.info(
        f"待求解像素总数={int(pix.shape[0])}，唯一颜色数={int(unique_pix.shape[0])}"
    )

    # 求解最优配方
    logger.info("开始求解最优配方...")
    t0 = time.time()
    unique_recipe_indices_solved = solver.solve(unique_pix)
    t1 = time.time()
    logger.info(f"求解完成，用时 {t1 - t0:.3f} 秒")

    # 反转层序（从底层到顶层）
    unique_recipe_indices_print = unique_recipe_indices_solved[:, ::-1].copy()
    idxs = inverse
    recipe_digits = unique_recipe_indices_print

    # 生成正面预测预览图
    logger.info("生成叠色预测预览图(正面/反面)...")
    predicted_labs = solver._predict_batch(unique_recipe_indices_solved)
    predicted_rgbs = lab_to_rgb01(predicted_labs)
    full_predicted_rgbs = predicted_rgbs[inverse].reshape(h, w, 3)
    front_u8 = np.clip(full_predicted_rgbs * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(front_u8).save(preview_dir / "01_preview_predicted_front.png")
    Image.fromarray(front_u8).save(preview_dir / "01_preview_predicted.png")

    # 生成反面预测预览图
    predicted_labs_back = solver._predict_batch(unique_recipe_indices_print)
    predicted_rgbs_back = lab_to_rgb01(predicted_labs_back)
    full_back_rgbs = predicted_rgbs_back[inverse].reshape(h, w, 3)
    back_u8 = np.clip(full_back_rgbs * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(back_u8).save(preview_dir / "01_preview_predicted_back.png")
    Image.fromarray(back_u8).save(preview_dir / "01_preview_back_predicted.png")

    # 生成正反面差异符号可视化
    logger.info("生成正反面差异符号可视化...")
    diff = front_u8.astype(np.float32) - back_u8.astype(np.float32)
    mag = np.clip(np.abs(diff) * 2, 0, 255).astype(np.uint8)
    sign_viz = np.zeros((h, w, 3), dtype=np.uint8)
    # 计算每个像素的平均差异幅度
    mag_gray = np.mean(mag, axis=2)
    diff_gray = np.mean(diff, axis=2)
    pos = diff_gray > 2
    neg = diff_gray < -2
    sign_viz[pos, 0] = mag_gray[pos]  # 红色通道
    sign_viz[neg, 2] = mag_gray[neg]  # 蓝色通道
    Image.fromarray(sign_viz).save(preview_dir / "01_preview_front_vs_back_sign.png")

    # 生成误差热力图
    logger.info("生成误差热力图...")
    original_rgb01 = rgba_u8[..., :3].astype(np.float32) / 255.0
    predicted_rgb01 = full_predicted_rgbs

    # 计算DeltaE误差
    original_lab = rgb01_to_lab(original_rgb01.reshape(-1, 3)).reshape(h, w, 3)
    predicted_lab = rgb01_to_lab(predicted_rgb01.reshape(-1, 3)).reshape(h, w, 3)
    deltaE = np.linalg.norm(original_lab - predicted_lab, axis=2)

    # 归一化并应用颜色映射
    deltaE_norm = np.clip(deltaE / 10.0 * 255, 0, 255).astype(np.uint8)
    heatmap_bgr = cv2.applyColorMap(deltaE_norm, cv2.COLORMAP_JET)
    heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)
    Image.fromarray(heatmap_rgb).save(preview_dir / "01_error_heatmap_predicted.png")

    # 保存误差统计
    error_stats = {
        "mean_deltaE": float(np.mean(deltaE)),
        "max_deltaE": float(np.max(deltaE)),
        "min_deltaE": float(np.min(deltaE)),
        "std_deltaE": float(np.std(deltaE)),
        "percentile_95": float(np.percentile(deltaE, 95)),
        "percentile_99": float(np.percentile(deltaE, 99)),
    }
    with open(
        preview_dir / "01_error_stats_predicted.json", "w", encoding="utf-8"
    ) as f:
        json.dump(error_stats, f, indent=2, ensure_ascii=False)
    logger.error(
        f"误差统计: 平均DeltaE={error_stats['mean_deltaE']:.2f}, 最大={error_stats['max_deltaE']:.2f}"
    )

    # 生成每层调色板预览图
    rgb_lut = np.asarray(
        [cs.slot_preview_rgb[n] for n in cs.slot_names], dtype=np.uint8
    )
    logger.info("生成每层调色板预览图...")
    for z in range(n_layers):
        digits_z = (
            recipe_digits[idxs, int(z)].reshape(h, w).astype(np.int32, copy=False)
        )
        img = rgb_lut[digits_z]
        Image.fromarray(img).save(layer_viz_dir / f"L{z:02d}_solved_palette.png")

    # 生成体素体积数据
    ys, xs = np.indices((h, w))
    ys = ys.reshape(-1)
    xs = xs.reshape(-1)
    volumes = generate_layer_volumes(
        params, cs, ys, xs, idxs, h, w, recipe_digits=recipe_digits
    )
    full_mask = np.ones((h, w), dtype=bool)

    # 导出每层每色掩码
    logger.info("导出每层每色 mask...")
    mask_count = 0
    for z in range(n_layers):
        for slot_name in cs.slot_names:
            mask = volumes[slot_name][z]
            if int(np.count_nonzero(mask)) == 0:
                continue
            prefix = f"L{z:02d}_{slot_name}"
            Image.fromarray((mask.astype(np.uint8) * 255)).save(
                mask_dir / f"{prefix}_mask.png"
            )
            mask_count += 1

    Image.fromarray((full_mask.astype(np.uint8) * 255)).save(mask_dir / "full_mask.png")
    logger.info(f"共导出 {mask_count} 个掩码文件")

    # 生成 mask_manifest.json
    logger.info("生成 mask_manifest.json...")
    slot_preview_rgb = {}
    for i, name in enumerate(cs.slot_names):
        rgb = cs.slot_preview_rgb[name]
        slot_preview_rgb[name] = [int(rgb[0]), int(rgb[1]), int(rgb[2])]

    mask_manifest = {
        "version": "gen_masks",
        "image_name": input_image_path.name,
        "image_path": str(input_image_path),
        "pixel_w": w,
        "pixel_h": h,
        "board_mm": 60.0,
        "n_layers": n_layers,
        "layer_height_mm": 0.12,
        "slot_names": list(cs.slot_names),
        "slot_preview_rgb": slot_preview_rgb,
        "mask_postprocess": {
            "layer0_bias_enabled": False,
            "first_print_layer_bias_enabled": False,
            "first_print_layer_bias_slack_de76": 0.3,
            "joint_l0_enabled": False,
            "joint_l0_passes": 1,
            "joint_l0_lambda_smooth": 0.05,
            "joint_l0_color_weight": 3.0,
            "joint_l0_slack_de76": 0.15,
            "joint_l0_edge_beta": 0.0,
            "mode": "none",
            "postprocess_conv_kernel": 3,
        },
    }

    with open(out_dir / "mask_manifest.json", "w", encoding="utf-8") as f:
        json.dump(mask_manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"已生成 mask_manifest.json")

    logger.info(f"完成。输出目录: {out_dir}")


def main():
    """主函数"""
    # 生成波点测试图
    logger.info("=" * 60)
    logger.info("生成波点测试图...")
    logger.info("=" * 60)

    rgba_array, metadata = draw_dot_pattern_base(width=1024, height=640)

    # 保存测试图
    prototype_dir = Path(__file__).resolve().parent
    out_base = prototype_dir / "out"
    out_base.mkdir(parents=True, exist_ok=True)

    # 使用时间戳创建唯一目录
    timestamp = datetime.now().strftime("%m%d_%H%M%S")
    test_dir = out_base / f"波点_{timestamp}"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 保存图像
    test_image_path = test_dir / "dot_pattern_test.png"
    Image.fromarray(rgba_array).save(test_image_path)
    logger.info(f"测试图已保存: {test_image_path}")

    # 保存元数据
    metadata_path = test_dir / "test_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"元数据已保存: {metadata_path}")

    # 运行gen_masks管线
    logger.info("\n" + "=" * 60)
    logger.info("运行gen_masks管线...")
    logger.info("=" * 60)

    try:
        run_gen_masks_pipeline(test_image_path, test_dir)
    except Exception as e:
        logger.error(f"管线处理失败: {e}")
        traceback.print_exc()
        raise

    logger.info(f"\n全部完成！输出目录: {test_dir}")
    return test_dir


if __name__ == "__main__":
    try:
        output_dir = main()
        logger.info(f"\n最终输出: {output_dir}")
    except Exception as e:
        logger.error(f"执行失败: {e}")
        traceback.print_exc()
        raise
