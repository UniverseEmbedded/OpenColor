#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SVG -> 三角形网格 SVG 验证器

使用示例：
  pixi run python svg_mesh_verify.py --in test.svg --out test_tri.svg --tol 0.5
  pixi run python svg_mesh_verify.py --in test.svg --out test_tri_raster.svg --color-mode raster --raster-scale 4

注意：
- 这不是完整的 SVG2 渲染器，目标是"几何保真度"检查
- 最佳视觉匹配模式是：--color-mode paint（复制 <defs> 并重用填充字符串）
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, Optional, Tuple

import cairosvg
import numpy as np
from lxml import etree
from PIL import Image

from svg_mesh_verify_geom import parse_length, parse_number_list, _strip_ns


@dataclass
class ViewBox:
    """SVG 视口定义"""

    x: float
    y: float
    w: float
    h: float


def parse_viewbox(root: etree._Element) -> ViewBox:
    """解析 SVG 的 viewBox 属性"""
    vb = root.get("viewBox")
    if vb:
        nums = parse_number_list(vb)
        if len(nums) >= 4:
            return ViewBox(nums[0], nums[1], nums[2], nums[3])
    w = parse_length(root.get("width")) or 1000.0
    h = parse_length(root.get("height")) or 1000.0
    return ViewBox(0.0, 0.0, float(w), float(h))


def render_svg_to_image(svg_bytes: bytes, vb: ViewBox, scale: float) -> Image.Image:
    """将 SVG 渲染为图像"""
    out_w = max(1, int(math.ceil(vb.w * scale)))
    out_h = max(1, int(math.ceil(vb.h * scale)))
    png_bytes = cairosvg.svg2png(
        bytestring=svg_bytes, output_width=out_w, output_height=out_h
    )
    img = Image.open(BytesIO(png_bytes)).convert("RGBA")
    return img


def composite_rgba_to_rgb(
    arr_rgba_u8: np.ndarray, bg_rgb_u8: Tuple[int, int, int]
) -> np.ndarray:
    """将 RGBA 图像合成到指定背景色上，返回 RGB"""
    rgb = arr_rgba_u8[..., :3].astype(np.float32)
    a = arr_rgba_u8[..., 3:4].astype(np.float32) / 255.0
    bg = np.array(bg_rgb_u8, dtype=np.float32).reshape(1, 1, 3)
    out = rgb * a + bg * (1.0 - a)
    return out


def premultiply_rgba(arr_rgba_u8: np.ndarray) -> np.ndarray:
    """预乘 Alpha 通道"""
    rgb = arr_rgba_u8[..., :3].astype(np.float32)
    a = arr_rgba_u8[..., 3:4].astype(np.float32) / 255.0
    premul = rgb * a
    out = np.concatenate([premul, arr_rgba_u8[..., 3:4].astype(np.float32)], axis=-1)
    return out


def compare_images(
    img_a: Image.Image, img_b: Image.Image, bg: str, diff_max: float, diff_gamma: float
) -> Tuple[Image.Image, Dict[str, float]]:
    """比较两幅图像，返回差异图和指标"""
    if img_a.size != img_b.size:
        raise ValueError(f"两张图尺寸不一致：{img_a.size} vs {img_b.size}")
    if diff_max <= 0:
        raise ValueError(f"diff-max 必须 > 0，当前为 {diff_max}")
    if diff_gamma <= 0:
        raise ValueError(f"diff-gamma 必须 > 0，当前为 {diff_gamma}")

    a = np.array(img_a.convert("RGBA"), dtype=np.uint8)
    b = np.array(img_b.convert("RGBA"), dtype=np.uint8)

    if bg == "white":
        aa = composite_rgba_to_rgb(a, (255, 255, 255))
        bb = composite_rgba_to_rgb(b, (255, 255, 255))
        diff = aa - bb
        mse = float(np.mean((diff / 255.0) ** 2))
        mag = np.sqrt(np.sum(diff**2, axis=-1)) / (math.sqrt(3.0) * 255.0)
    elif bg == "black":
        aa = composite_rgba_to_rgb(a, (0, 0, 0))
        bb = composite_rgba_to_rgb(b, (0, 0, 0))
        diff = aa - bb
        mse = float(np.mean((diff / 255.0) ** 2))
        mag = np.sqrt(np.sum(diff**2, axis=-1)) / (math.sqrt(3.0) * 255.0)
    elif bg == "transparent":
        aa = premultiply_rgba(a)
        bb = premultiply_rgba(b)
        diff = aa - bb
        mse = float(np.mean((diff / 255.0) ** 2))
        mag = np.sqrt(np.sum(diff**2, axis=-1)) / (math.sqrt(4.0) * 255.0)
    else:
        raise ValueError(f"未知背景模式：{bg}")

    rmse = float(math.sqrt(mse))
    mae = float(np.mean(np.abs(diff) / 255.0))
    p95 = float(np.quantile(mag, 0.95))
    maxv = float(np.max(mag))
    psnr = float(20.0 * math.log10(1.0 / max(rmse, 1e-12)))

    norm = np.clip(mag / float(diff_max), 0.0, 1.0)
    norm = norm ** (1.0 / float(diff_gamma))
    intensity = (1.0 - norm) * 255.0
    diff_img = Image.fromarray(intensity.astype(np.uint8))

    metrics = {
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "psnr": psnr,
        "p95": p95,
        "max": maxv,
        "width": float(img_a.size[0]),
        "height": float(img_a.size[1]),
    }
    return diff_img, metrics


def sample_rgba_bilinear(
    img: Image.Image, x: float, y: float
) -> Tuple[float, float, float, float]:
    """双线性插值采样 RGBA 值"""
    w, h = img.size
    x = max(0.0, min(x, w - 1.001))
    y = max(0.0, min(y, h - 1.001))
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = min(x0 + 1, w - 1)
    y1 = min(y0 + 1, h - 1)
    dx = x - x0
    dy = y - y0
    p00 = np.array(img.getpixel((x0, y0)), dtype=float)
    p10 = np.array(img.getpixel((x1, y0)), dtype=float)
    p01 = np.array(img.getpixel((x0, y1)), dtype=float)
    p11 = np.array(img.getpixel((x1, y1)), dtype=float)
    p0 = p00 * (1 - dx) + p10 * dx
    p1 = p01 * (1 - dx) + p11 * dx
    p = p0 * (1 - dy) + p1 * dy
    return float(p[0]), float(p[1]), float(p[2]), float(p[3])


def fmt_float(x: float) -> str:
    """格式化浮点数为简洁字符串"""
    return f"{x:.4f}".rstrip("0").rstrip(".")


def tri_to_pathd(
    a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]
) -> str:
    """将三角形转换为 SVG path 数据字符串"""
    return f"M {fmt_float(a[0])} {fmt_float(a[1])} L {fmt_float(b[0])} {fmt_float(b[1])} L {fmt_float(c[0])} {fmt_float(c[1])} Z"


def make_svg_root_like(original_root: etree._Element, vb: ViewBox) -> etree._Element:
    """创建与原始 SVG 相似的根元素"""
    nsmap = original_root.nsmap.copy() if original_root.nsmap else {}
    if None not in nsmap:
        nsmap[None] = "http://www.w3.org/2000/svg"
    out = etree.Element("svg", nsmap=nsmap)
    for k in ("width", "height"):
        if original_root.get(k) is not None:
            out.set(k, original_root.get(k))
    out.set("viewBox", f"{vb.x} {vb.y} {vb.w} {vb.h}")
    return out


def copy_defs(original_root: etree._Element, out_root: etree._Element):
    """复制 SVG 的 defs 定义到新根元素"""
    for el in original_root.iter():
        if _strip_ns(el.tag) == "defs":
            out_root.append(etree.fromstring(etree.tostring(el)))
            break


def set_opacity_attrs(
    el: etree._Element,
    opacity: Optional[str],
    fill_opacity: Optional[str],
    stroke_opacity: Optional[str],
):
    """设置元素的透明度属性"""
    if opacity and opacity.strip() not in ("", "1", "1.0"):
        el.set("opacity", opacity.strip())
    if fill_opacity and fill_opacity.strip() not in ("", "1", "1.0"):
        el.set("fill-opacity", fill_opacity.strip())
    if stroke_opacity and stroke_opacity.strip() not in ("", "1", "1.0"):
        el.set("stroke-opacity", stroke_opacity.strip())
