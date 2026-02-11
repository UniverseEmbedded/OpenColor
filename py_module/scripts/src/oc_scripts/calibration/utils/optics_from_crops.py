#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""从裁剪照片估算简单光学参数

OpenColor材料配置文件的启发式引导程序

输入
  包含JPG文件的目录。文件名可以是中文（如 红色反光.jpg）或
  编码为 #U7ea2#U8272#U53cd#U5149.jpg

假设
  - 反光: 顶部区域是A4纸参考；下方是材料表面
  - 透光: 底部区域是未覆盖的屏幕渐变（参考）；上方是材料

输出
  - optics_estimates.json
  - debug_overlays/*.jpg 带有检测到的边界和采样带

注意
  这不是最终物理模型。它是一个实用的初始化器：
    reflectance_rgb: 相对于纸张的漫反射估算
    transmittance_rgb: 相对于未覆盖屏幕的每通道透射比估算
    haze: 透射中的对比度损失估算
    specular: 反射中的高光比例
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Tuple, List

import cv2
import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# ---------------------------- 文件名辅助函数 ----------------------------

_U_RE = re.compile(r"#U([0-9a-fA-F]{4,6})")


def decode_u_filename(name: str) -> str:
    """解码如 #U7ea2#U8272#U53cd#U5149.jpg -> 红色反光.jpg 的名称"""

    def repl(m: re.Match) -> str:
        code = int(m.group(1), 16)
        return chr(code)

    return _U_RE.sub(repl, name)


def guess_color_mode(filename: str) -> Tuple[str, str]:
    """返回 (颜色, 模式) 其中模式在 {反光, 透光} 中（如果可能）"""
    base = Path(filename).name
    base = decode_u_filename(base)
    base_noext = os.path.splitext(base)[0]

    mode = None
    for m in ("反光", "透光"):
        if m in base_noext:
            mode = m
            break
    if mode is None:
        raise ValueError(f"无法从文件名确定模式: {filename}")

    color = base_noext.replace(mode, "")
    color = color.strip(" _-\t")
    return color, mode


# ---------------------------- 颜色空间辅助函数 ----------------------------


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """x 在 [0,1] 范围内"""
    x = np.clip(x, 0.0, 1.0)
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    a = 0.055
    return np.where(x <= 0.0031308, x * 12.92, (1 + a) * (x ** (1 / 2.4)) - a)


# ---------------------------- 核心估算器 ----------------------------


def find_boundary_row(img_bgr: np.ndarray) -> int:
    """通过逐行特征变化检测主导水平边界"""
    h, w = img_bgr.shape[:2]

    # 使用饱和度和明度作为鲁棒的边界线索
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1].astype(np.float32)
    v = hsv[:, :, 2].astype(np.float32)

    # 聚焦中心列以避免边缘暗角
    x0 = int(w * 0.1)
    x1 = int(w * 0.9)
    s_row = np.mean(s[:, x0:x1], axis=1)
    v_row = np.mean(v[:, x0:x1], axis=1)

    # 平滑
    k = max(5, (h // 80) | 1)
    s_row = cv2.GaussianBlur(s_row.reshape(-1, 1), (1, k), 0).reshape(-1)
    v_row = cv2.GaussianBlur(v_row.reshape(-1, 1), (1, k), 0).reshape(-1)

    # 导数幅度
    ds = np.abs(np.diff(s_row, prepend=s_row[0]))
    dv = np.abs(np.diff(v_row, prepend=v_row[0]))
    score = ds + 0.5 * dv

    # 忽略极端区域
    y0 = int(h * 0.08)
    y1 = int(h * 0.92)
    y = int(y0 + np.argmax(score[y0:y1]))
    return y


def robust_band_stats(img_bgr: np.ndarray, y0: int, y1: int) -> Dict[str, np.ndarray]:
    """返回带区 [y0,y1) 的鲁棒中位数统计"""
    band = img_bgr[y0:y1, :, :]
    rgb = band[:, :, ::-1].astype(np.float32) / 255.0
    rgb_lin = srgb_to_linear(rgb)

    med = np.median(rgb_lin.reshape(-1, 3), axis=0)
    mean = np.mean(rgb_lin.reshape(-1, 3), axis=0)

    # 用于对比度的亮度
    luma = (
        0.2126 * rgb_lin[:, :, 0]
        + 0.7152 * rgb_lin[:, :, 1]
        + 0.0722 * rgb_lin[:, :, 2]
    )
    luma_row = np.mean(luma, axis=1)
    return {
        "median_lin": med,
        "mean_lin": mean,
        "luma_row": luma_row,
    }


def estimate_reflect(img_bgr: np.ndarray) -> Dict:
    h, w = img_bgr.shape[:2]
    yb = find_boundary_row(img_bgr)

    # 带边距的带区
    margin = int(h * 0.03)
    ref_y0 = int(h * 0.03)
    ref_y1 = max(ref_y0 + 5, yb - margin)
    mat_y0 = min(h - 5, yb + margin)
    mat_y1 = int(h * 0.97)

    ref = robust_band_stats(img_bgr, ref_y0, ref_y1)
    mat = robust_band_stats(img_bgr, mat_y0, mat_y1)

    # 相对于纸张的反射率估算
    eps = 1e-6
    refl = np.clip(mat["median_lin"] / (ref["median_lin"] + eps), 0.0, 1.5)

    # 粗略镜面：材料带中明亮低饱和度像素的比例
    band = img_bgr[mat_y0:mat_y1, :, :]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    spec = float(np.mean((v > 0.92) & (s < 0.35)))

    return {
        "boundary_y": int(yb),
        "ref_band": [int(ref_y0), int(ref_y1)],
        "mat_band": [int(mat_y0), int(mat_y1)],
        "paper_median_lin": ref["median_lin"].tolist(),
        "mat_median_lin": mat["median_lin"].tolist(),
        "reflectance_rgb_lin": refl.tolist(),
        "specular": spec,
    }


def estimate_transmit(img_bgr: np.ndarray) -> Dict:
    h, w = img_bgr.shape[:2]
    yb = find_boundary_row(img_bgr)

    margin = int(h * 0.03)
    cov_y0 = int(h * 0.03)
    cov_y1 = max(cov_y0 + 5, yb - margin)
    ref_y0 = min(h - 5, yb + margin)
    ref_y1 = int(h * 0.97)

    # 每列中位数以适应渐变
    cov = img_bgr[cov_y0:cov_y1, :, ::-1].astype(np.float32) / 255.0
    ref = img_bgr[ref_y0:ref_y1, :, ::-1].astype(np.float32) / 255.0
    cov_lin = srgb_to_linear(cov)
    ref_lin = srgb_to_linear(ref)

    cov_med_x = np.median(cov_lin, axis=0)  # 形状 w x 3
    ref_med_x = np.median(ref_lin, axis=0)

    # 避免接近黑色的参考列
    ref_luma = (
        0.2126 * ref_med_x[:, 0] + 0.7152 * ref_med_x[:, 1] + 0.0722 * ref_med_x[:, 2]
    )
    mask = ref_luma > np.percentile(ref_luma, 20)  # 忽略最暗的20%

    eps = 1e-6
    ratio_x = cov_med_x / (ref_med_x + eps)
    ratio_x = np.clip(ratio_x, 0.0, 2.0)

    if np.sum(mask) < max(20, w * 0.1):
        mask = ref_luma > np.percentile(ref_luma, 5)

    t_rgb = np.median(ratio_x[mask], axis=0)

    # 雾度：X轴上亮度信号的对比度降低
    cov_luma_x = (
        0.2126 * cov_med_x[:, 0] + 0.7152 * cov_med_x[:, 1] + 0.0722 * cov_med_x[:, 2]
    )
    ref_luma_x = ref_luma

    # 归一化使其尺度不变
    def norm_sig(sig: np.ndarray) -> np.ndarray:
        s = sig[mask].astype(np.float32)
        s = s - np.median(s)
        denom = np.percentile(np.abs(s), 90) + 1e-6
        return s / denom

    cov_n = norm_sig(cov_luma_x)
    ref_n = norm_sig(ref_luma_x)

    std_ratio = float(np.std(cov_n) / (np.std(ref_n) + 1e-6))
    haze = float(np.clip(1.0 - std_ratio, 0.0, 1.0))

    return {
        "boundary_y": int(yb),
        "covered_band": [int(cov_y0), int(cov_y1)],
        "ref_band": [int(ref_y0), int(ref_y1)],
        "transmittance_rgb_lin": t_rgb.tolist(),
        "haze": haze,
    }


def draw_debug_overlay(img_bgr: np.ndarray, info: Dict, mode: str) -> np.ndarray:
    out = img_bgr.copy()
    h, w = out.shape[:2]

    yb = int(info.get("boundary_y", h // 2))
    cv2.line(out, (0, yb), (w - 1, yb), (0, 255, 255), 3)

    if mode == "反光":
        ref0, ref1 = info["ref_band"]
        mat0, mat1 = info["mat_band"]
        cv2.rectangle(out, (0, ref0), (w - 1, ref1), (255, 0, 0), 2)
        cv2.rectangle(out, (0, mat0), (w - 1, mat1), (0, 255, 0), 2)
        cv2.putText(
            out,
            "纸张参考",
            (10, min(ref1 - 10, h - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
        )
        cv2.putText(
            out,
            "材料",
            (10, min(mat1 - 10, h - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
    else:
        cov0, cov1 = info["covered_band"]
        ref0, ref1 = info["ref_band"]
        cv2.rectangle(out, (0, cov0), (w - 1, cov1), (0, 255, 0), 2)
        cv2.rectangle(out, (0, ref0), (w - 1, ref1), (255, 0, 0), 2)
        cv2.putText(
            out,
            "覆盖区",
            (10, min(cov1 - 10, h - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            out,
            "屏幕参考",
            (10, min(ref1 - 10, h - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2,
        )

    return out


# ---------------------------- 命令行接口 ----------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", required=True, help="包含裁剪JPG的文件夹")
    ap.add_argument("--out_dir", required=True, help="输出文件夹")
    ap.add_argument("--write_overlays", action="store_true", help="写入调试叠加图像")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir = out_dir / "debug_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        [p for p in in_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg")]
    )
    if not files:
        raise SystemExit(f"在 {in_dir} 中未找到JPG文件")

    # 按材料收集
    by_color: Dict[str, Dict[str, Dict]] = {}
    by_color_paths: Dict[str, Dict[str, Path]] = {}

    for p in files:
        color, mode = guess_color_mode(p.name)
        by_color_paths.setdefault(color, {})[mode] = p

    for color, modes in by_color_paths.items():
        entry: Dict[str, Dict] = {}

        # 反射
        if "反光" in modes:
            img = cv2.imread(str(modes["反光"]))
            if img is None:
                raise RuntimeError(f"读取失败 {modes['反光']}")
            info = estimate_reflect(img)
            entry["reflect"] = info
            if args.write_overlays:
                over = draw_debug_overlay(img, info, "反光")
                cv2.imwrite(str(overlay_dir / f"{color}_反光_overlay.jpg"), over)

        # 透射
        if "透光" in modes:
            img = cv2.imread(str(modes["透光"]))
            if img is None:
                raise RuntimeError(f"读取失败 {modes['透光']}")
            info = estimate_transmit(img)
            entry["transmit"] = info
            if args.write_overlays:
                over = draw_debug_overlay(img, info, "透光")
                cv2.imwrite(str(overlay_dir / f"{color}_透光_overlay.jpg"), over)

        # 合并为OpenColorCore的紧凑配置文件
        profile = {
            "name": color,
            "reflectance_rgb_lin": entry.get("reflect", {}).get("reflectance_rgb_lin"),
            "transmittance_rgb_lin": entry.get("transmit", {}).get(
                "transmittance_rgb_lin"
            ),
            "haze": entry.get("transmit", {}).get("haze"),
            "specular": entry.get("reflect", {}).get("specular"),
        }
        entry["profile_guess"] = profile

        by_color[color] = entry

    # 写入输出
    out_json = out_dir / "optics_estimates.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(by_color, f, ensure_ascii=False, indent=2)

    # 同时写入扁平化JSON以便轻松导入
    flat = {color: data["profile_guess"] for color, data in by_color.items()}
    with (out_dir / "profiles_flat.json").open("w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)

    logger.info(f"已写入 {out_json}")


if __name__ == "__main__":
    main()
