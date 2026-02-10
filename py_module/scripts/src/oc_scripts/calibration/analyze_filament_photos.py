#!/usr/bin/env python3
"""分析耗材卷轴特写照片（自然光）并推测PLA光学先验参数

功能（MVP）：
- 从每张照片稳健地采样代表性颜色（中色调像素的中位数，遮罩高光）
- 使用白色照片作为白平衡参考
- 为OpenColor类混合模型估计几个"光学先验"参数：
  - base_reflect_rgb（白平衡后的sRGB）
  - k_rgb（有效每通道衰减系数，mm^-1），使用简单的Beer-Lambert代理
  - haze（散射/白度代理）
  - specular_fraction（样本光泽度）

这不是物理真值校准。它是一个实用的初始化器/先验生成器。

用法：
  python analyze_filament_photos.py --white 白色.png --red 红色.png --green 绿色.png --blue 蓝色.png \
    --out filament_profiles.json

可选参数：
  --t0 0.2   # 将反射率转换为k_rgb时使用的有效厚度（mm）
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def srgb_to_linear(u: np.ndarray) -> np.ndarray:
    """近似sRGB -> 线性RGB转换"""
    u = np.clip(u, 0.0, 1.0)
    a = 0.055
    return np.where(u <= 0.04045, u / 12.92, ((u + a) / (1 + a)) ** 2.4)


def linear_to_srgb(u: np.ndarray) -> np.ndarray:
    """近似线性RGB -> sRGB转换"""
    u = np.clip(u, 0.0, 1.0)
    a = 0.055
    return np.where(u <= 0.0031308, 12.92 * u, (1 + a) * (u ** (1 / 2.4)) - a)


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """rgb: (...,3) 范围[0,1] -> hsv (...,3) 范围[0,1]"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.max(rgb, axis=-1)
    mn = np.min(rgb, axis=-1)
    diff = mx - mn

    h = np.zeros_like(mx)
    s = np.zeros_like(mx)
    v = mx

    # 饱和度
    s = np.where(mx == 0, 0, diff / (mx + 1e-12))

    # 色相
    mask = diff > 1e-12
    # 避免除零
    rc = (mx - r) / (diff + 1e-12)
    gc = (mx - g) / (diff + 1e-12)
    bc = (mx - b) / (diff + 1e-12)

    h = np.where((mask) & (r == mx), (bc - gc), h)
    h = np.where((mask) & (g == mx), 2.0 + (rc - bc), h)
    h = np.where((mask) & (b == mx), 4.0 + (gc - rc), h)
    h = (h / 6.0) % 1.0

    return np.stack([h, s, v], axis=-1)


@dataclass
class SampleStats:
    """样本统计信息"""
    rgb_srgb_median: np.ndarray  # 3
    rgb_lin_median: np.ndarray   # 3
    hsv_median: np.ndarray       # 3
    specular_fraction: float     # 高光比例
    used_fraction: float         # 使用的像素比例


def load_image(path: Path) -> np.ndarray:
    """加载图像并归一化到[0,1]范围"""
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(np.float32) / 255.0
    return arr


def robust_sample(arr_srgb: np.ndarray, for_white: bool = False) -> SampleStats:
    """返回稳健的中位数颜色，遮罩阴影和高光条纹"""
    hsv = rgb_to_hsv(arr_srgb)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    # 基础遮罩：保留中色调（避免深阴影+过曝高光）
    if for_white:
        m = (v > 0.35) & (v < 0.92)
    else:
        m = (v > 0.20) & (v < 0.92)

    # 移除可能的高光条纹：高V值且低S值（偏白条纹）
    m &= ~((v > 0.85) & (s < 0.25))

    # 如果像素仍然太少（例如非常光滑的表面），稍微放宽条件
    used = float(np.mean(m))
    if used < 0.05:
        m = (v > 0.15) & (v < 0.95)
        m &= ~((v > 0.88) & (s < 0.22))
        used = float(np.mean(m))

    # 高光比例指示器（未遮罩）：
    spec = float(np.mean((v > 0.90) & (s < 0.20)))

    pix = arr_srgb[m]
    if pix.size == 0:
        # 回退到整图中位数
        pix = arr_srgb.reshape(-1, 3)
        used = 1.0

    rgb_med = np.median(pix, axis=0)
    rgb_lin_med = np.median(srgb_to_linear(pix), axis=0)
    hsv_med = np.median(rgb_to_hsv(pix), axis=0)

    return SampleStats(
        rgb_srgb_median=rgb_med,
        rgb_lin_median=rgb_lin_med,
        hsv_median=hsv_med,
        specular_fraction=spec,
        used_fraction=used,
    )


def white_balance_gain(white_rgb_srgb: np.ndarray) -> np.ndarray:
    """计算每通道增益，使采样的白色变为中性灰"""
    w = np.clip(white_rgb_srgb, 1e-4, 1.0)
    gray = float(np.mean(w))
    gain = gray / w
    # 防止极端增益
    gain = np.clip(gain, 0.5, 2.0)
    return gain


def apply_gain(rgb: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """应用增益到RGB值"""
    return np.clip(rgb * gain, 0.0, 1.0)


def guess_haze_from_sat(sat: float) -> float:
    """启发式：较低饱和度通常表示较强散射/白度"""
    haze = 0.20 + 1.20 * (0.35 - sat)
    return float(np.clip(haze, 0.10, 0.65))


def guess_k_rgb(color_rgb: np.ndarray, white_rgb: np.ndarray, t0_mm: float) -> np.ndarray:
    """从相对反射率计算有效衰减代理（mm^-1）"""
    eps = 1e-3
    num = np.clip(color_rgb, eps, 1.0)
    den = np.clip(white_rgb, eps, 1.0)
    ratio = np.clip(num / den, eps, 1.0)
    k = -np.log(ratio) / max(t0_mm, 1e-6)
    k = np.maximum(k, 0.0)
    # 保持合理的上限，避免暗通道数值爆炸
    k = np.clip(k, 0.0, 20.0)
    return k


def to_hex(rgb: np.ndarray) -> str:
    """将RGB数组转换为十六进制颜色字符串"""
    rgb8 = (np.clip(rgb, 0, 1) * 255.0 + 0.5).astype(np.int32)
    return "#%02X%02X%02X" % (rgb8[0], rgb8[1], rgb8[2])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--white", required=True, help="白色耗材照片路径")
    ap.add_argument("--red", required=True, help="红色耗材照片路径")
    ap.add_argument("--green", required=True, help="绿色耗材照片路径")
    ap.add_argument("--blue", required=True, help="蓝色耗材照片路径")
    ap.add_argument("--t0", type=float, default=0.20, help="有效厚度（mm）")
    ap.add_argument("--out", default="filament_profiles.json", help="输出JSON文件路径")
    args = ap.parse_args()

    paths = {
        "W": Path(args.white),
        "R": Path(args.red),
        "G": Path(args.green),
        "B": Path(args.blue),
    }

    # 加载并采样
    samples = {}
    for k, p in paths.items():
        arr = load_image(p)
        samples[k] = robust_sample(arr, for_white=(k == "W"))

    # 从白色样本进行白平衡
    wb_gain = white_balance_gain(samples["W"].rgb_srgb_median)

    # 白平衡后的中位数
    wb_rgb = {k: apply_gain(v.rgb_srgb_median, wb_gain) for k, v in samples.items()}

    white_wb = wb_rgb["W"]

    # 构建配置文件
    profiles = {}
    for k in ["W", "R", "G", "B"]:
        rgb = wb_rgb[k]
        hsv = rgb_to_hsv(rgb.reshape(1, 1, 3))[0, 0]
        haze = guess_haze_from_sat(float(hsv[1]))
        spec = float(samples[k].specular_fraction)
        k_rgb = guess_k_rgb(rgb, white_wb, args.t0)

        name = {"W": "white", "R": "red", "G": "green", "B": "blue"}[k]

        profiles[name] = {
            "assumptions": {
                "illuminant": "自然光，使用提供的白色照片进行白平衡",
                "t0_mm": args.t0,
                "model": "有效Beer-Lambert代理 + haze启发式（仅初始化器）",
            },
            "base_reflect_rgb_srgb": [float(x) for x in rgb.tolist()],
            "base_reflect_hex": to_hex(rgb),
            "hsv": {
                "h": float(hsv[0]),
                "s": float(hsv[1]),
                "v": float(hsv[2]),
            },
            "specular_fraction": spec,
            "used_pixel_fraction": float(samples[k].used_fraction),
            "optical_priors": {
                "n_550nm": 1.461,  # 常见PLA先验值
                "haze": haze,
                "k_rgb_mm-1": [float(x) for x in k_rgb.tolist()],
            },
            "notes": {
                "interpretation": {
                    "haze": "散射/白度代理：越高 => 越乳白/越不透明",
                    "k_rgb": "每通道衰减代理；作为先验使用，然后用打印/扫描结果精修",
                    "specular_fraction": "越高 => 表面越光泽（类似丝绸）；需要处理高光",
                }
            },
        }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印简洁的汇总表
    def fmt(v):
        return "[%.3f %.3f %.3f]" % (v[0], v[1], v[2])

    logger.info("白平衡增益 (R,G,B):", fmt(wb_gain))
    logger.info("有效 t0 (mm):", args.t0)
    logger.info("\n汇总（白平衡后中位数）:")
    logger.info("name   reflect_srgb           hex      haze  spec_frac  k_rgb(mm^-1)")
    for name in ["white", "red", "green", "blue"]:
        pr = profiles[name]
        rgb = np.array(pr["base_reflect_rgb_srgb"], dtype=float)
        haze = pr["optical_priors"]["haze"]
        spec = pr["specular_fraction"]
        k_rgb = pr["optical_priors"]["k_rgb_mm-1"]
        logger.info(f"{name:<6} {fmt(rgb):<22} {pr['base_reflect_hex']:<8} "
            f"{haze:>4.2f}   {spec:>6.3f}   "
            f"[{k_rgb[0]:.2f} {k_rgb[1]:.2f} {k_rgb[2]:.2f}]"
        )


if __name__ == "__main__":
    main()
