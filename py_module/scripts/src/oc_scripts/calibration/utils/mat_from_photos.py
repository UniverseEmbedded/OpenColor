#!/usr/bin/env python3
"""calibrate_materials_from_photos.py

简化光学校准（MVP）
----------------------------------

目标：将4张在相同光照下拍摄的卷轴照片（W/R/G/B）转换为
可被OpenColor原型其余部分使用的`materials_calibrated.json`。

存在原因
~~~~~~~~~~~~~~~
我们无法从单张反射照片中恢复真实的物理光学参数。但我们可以构建一个有用的"经验先验"：

* 稳健地采样每种耗材的代表性sRGB值
* 使用白色耗材照片进行白平衡
* 推导每通道衰减代理（k_rgb）和雾度代理

这些是以下功能的良好初始化器：
* 规划器"快速"模型：`color_srgb`、`strength`
* forward_mc模型：`mu_a`、`mu_s`（粗略映射；稍后精修）

输出
~~~~~~~
* filament_profiles.json        （可调试的中间文件）
* materials_calibrated.json     （materials.json的直接替代品）

用法
~~~~~
python calibrate_materials_from_photos.py \
  --white "D:\\...\\白色.png" \
  --red   "D:\\...\\红色.png" \
  --green "D:\\...\\绿色.png" \
  --blue  "D:\\...\\蓝色.png"

然后使用以下命令运行任何生成器：
  --materials-json materials_calibrated.json

或者，由于planner.py在存在时优先使用materials_calibrated.json，
大多数脚本会自动选择它。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from PIL import Image

import analyze_filament_photos as afp



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _clamp(x: float, lo: float, hi: float) -> float:
    """将数值限制在指定范围内"""
    return max(lo, min(hi, x))


def _rgb01_to_rgb255(rgb01: np.ndarray) -> Tuple[int, int, int]:
    """将0-1范围的RGB转换为0-255范围的整数RGB"""
    v = np.clip(np.round(rgb01 * 255.0), 0, 255).astype(int)
    return (int(v[0]), int(v[1]), int(v[2]))


def _normalize_chroma(rgb01: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """归一化以保持色度；避免照片过暗

    对于彩色耗材，我们更关心色度而非曝光。
    将最大通道设为1.0（除非接近灰色）。
    """
    mx = float(np.max(rgb01))
    mn = float(np.min(rgb01))
    if mx < eps:
        return rgb01
    # 如果接近灰色，保持原样（白色将单独处理）
    if (mx - mn) < 0.02:
        return rgb01
    return np.clip(rgb01 / mx, 0.0, 1.0)


def _token_from_name(name: str) -> str:
    """将颜色名称转换为材料标识符"""
    name = name.lower().strip()
    return {
        "white": "W",
        "red": "R",
        "green": "G",
        "blue": "B",
    }[name]


def _estimate_strength(k_rgb: np.ndarray, haze: float) -> float:
    """将k/雾度代理映射到规划器strength初始化器

    Strength控制材料随层数堆叠达到不透明度的速度。
    这是启发式初始化器（非测量参数）。
    """
    k_max = float(np.max(k_rgb))
    # 基础1.5（类似透明），添加颜料衰减+雾度贡献
    s = 1.5 + 0.7 * k_max + 8.0 * max(0.0, haze - 0.10)
    return _clamp(s, 1.5, 14.0)


def _estimate_mu_s(haze: float) -> float:
    """将雾度代理映射到mu_s（1/mm）初始化器"""
    # 透明基线~0.4，典型彩色PLA~3，非常乳白/白色更高
    mu = 0.4 + 26.0 * haze
    return _clamp(mu, 0.4, 8.0)


def _estimate_mu_a_from_k(k_rgb: np.ndarray, low: float = 0.35, high: float = 2.6) -> Tuple[float, float, float]:
    """将k_rgb代理转换为相对mu_a RGB（1/mm）初始化器"""
    k = np.maximum(k_rgb.astype(float), 0.0)
    k0 = float(np.min(k))
    d = k - k0
    mx = float(np.max(d))
    if mx < 1e-6:
        return (low, low, low)
    scale = (high - low) / mx
    mu = low + d * scale
    return (float(mu[0]), float(mu[1]), float(mu[2]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--white", required=True, help="白色耗材照片")
    ap.add_argument("--red", required=True, help="红色耗材照片")
    ap.add_argument("--green", required=True, help="绿色耗材照片")
    ap.add_argument("--blue", required=True, help="蓝色耗材照片")
    ap.add_argument("--t0", type=float, default=0.2, help="k估计的有效厚度（mm）")
    ap.add_argument("--base-materials", default="materials.json", help="基础materials.json路径")
    ap.add_argument("--out-materials", default="materials_calibrated.json", help="输出材料json路径")
    ap.add_argument("--out-profiles", default="filament_profiles.json", help="输出配置文件json路径")
    args = ap.parse_args()

    # 加载基础材料
    base_path = Path(args.base_materials)
    if not base_path.exists():
        raise FileNotFoundError(f"基础材料文件未找到：{base_path}")
    base = json.loads(base_path.read_text(encoding="utf-8"))

    # 读取图像并采样颜色（复用analyze_filament_photos工具函数）
    photo_paths = {
        "white": Path(args.white),
        "red": Path(args.red),
        "green": Path(args.green),
        "blue": Path(args.blue),
    }
    samples: Dict[str, afp.SampleStats] = {}
    for name, p in photo_paths.items():
        img = Image.open(p).convert("RGB")
        arr = np.asarray(img).astype(np.float32) / 255.0
        samples[name] = afp.robust_sample(arr, for_white=(name == "white"))

    # 使用白色中位数进行白平衡增益（均衡各通道）
    w = np.array(samples["white"].rgb_srgb_median, dtype=float)
    w_mean = float(np.mean(w))
    gains = w_mean / (w + 1e-8)
    gains = np.clip(gains, 0.5, 2.0)

    def apply_wb(rgb01: np.ndarray) -> np.ndarray:
        """应用白平衡到RGB值"""
        return np.clip(rgb01 * gains, 0.0, 1.0)

    # k估计的分母
    w_wb = apply_wb(w)

    profiles_out: Dict[str, dict] = {}
    updates: Dict[str, dict] = {}

    t0 = float(args.t0)
    eps = 1e-3

    for name in ["white", "red", "green", "blue"]:
        rgb = np.array(samples[name].rgb_srgb_median, dtype=float)
        rgb_wb = apply_wb(rgb)
        hsv_wb = afp.rgb_to_hsv(rgb_wb[None, None, :])[0, 0, :]

        sat = float(hsv_wb[1])
        haze = float(np.clip(0.2 + 1.2 * (0.35 - sat), 0.10, 0.65))

        ratio = (rgb_wb + eps) / (w_wb + eps)
        k = -np.log(ratio) / max(t0, 1e-6)
        k = np.clip(k, 0.0, 40.0)

        # 归一化色度，使曝光不会使`color_srgb`变暗
        if name == "white":
            color01 = np.array([1.0, 1.0, 1.0], dtype=float)
        else:
            color01 = _normalize_chroma(rgb_wb)

        token = _token_from_name(name)

        strength = _estimate_strength(k, haze)
        mu_s = _estimate_mu_s(haze)

        if token == "W":
            # 保持稳健的白色基线
            mu_a = (0.1, 0.1, 0.1)
            g = float(base["materials"].get("W", {}).get("g", 0.85))
            n = float(base["materials"].get("W", {}).get("n", 1.50))
        else:
            mu_a = _estimate_mu_a_from_k(k)
            g = float(base["materials"].get(token, {}).get("g", 0.85))
            n = float(base["materials"].get(token, {}).get("n", 1.50))

        updates[token] = {
            "color_srgb": list(_rgb01_to_rgb255(color01)),
            "strength": float(strength),
            "mu_a": list(mu_a),
            "mu_s": [float(mu_s)] * 3,
            "g": float(g),
            "n": float(n),
        }

        profiles_out[name] = {
            "photo": str(photo_paths[name]),
            "median_rgb_srgb": [float(x) for x in rgb_wb],
            "median_hsv": [float(x) for x in hsv_wb],
            "used_pixel_fraction": float(samples[name].used_fraction),
            "specular_fraction": float(samples[name].specular_fraction),
            "white_balance_gain": [float(x) for x in gains],
            "optical_priors": {
                "haze": float(haze),
                "k_rgb_mm-1": [float(x) for x in k],
                "strength": float(strength),
                "mu_a": list(mu_a),
                "mu_s": [float(mu_s)] * 3,
            },
        }

    # 将更新合并到基础材料
    out = dict(base)
    out_mats = dict(out.get("materials", {}))
    for token, v in updates.items():
        if token not in out_mats:
            out_mats[token] = {"name": token}
        out_mats[token] = {**out_mats[token], **v}
    out["materials"] = out_mats

    # 写入输出
    Path(args.out_profiles).write_text(json.dumps(profiles_out, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_materials).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("完成")
    logger.info("  已写入：", args.out_profiles)
    logger.info("  已写入：", args.out_materials)
    logger.info("  白平衡增益 (R,G,B)：", np.array2string(gains, precision=3))


if __name__ == "__main__":
    main()
