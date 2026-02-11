#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# forward_mc.py
# 基于物理的 FDM 层叠颜色前向模型（顺序敏感）
# 使用蒙特卡洛辐射传输，包含吸收、散射和菲涅尔界面
#
# 输出白光照明下的每通道（R,G,B）反射率和透射率
# 然后结合可选的背板反射率得到观测颜色
#
# 示例（命令行）：
#   python forward_mc.py --seq G-R-W-W-W --heights 0.12,0.08,0.08,0.08,0.08 --view bottom --samples 200000
#
# 库调用方式：
#   from forward_mc import forward_rgb
#   rgb = forward_rgb(seq="W-G-W-R-W", heights=[0.08]*5, view="top", samples=200000, backing=(1,1,1))

from __future__ import annotations

import argparse
import json
import math
import random
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# -----------------------------
# 颜色空间辅助函数
# -----------------------------


def srgb_to_linear01(x: float) -> float:
    """将 sRGB 值转换为线性 0-1 范围。"""
    if x <= 0.04045:
        return x / 12.92
    return ((x + 0.055) / 1.055) ** 2.4


def linear01_to_srgb(x: float) -> float:
    """将线性 0-1 值转换为 sRGB。"""
    x = max(0.0, min(1.0, x))
    if x <= 0.0031308:
        return 12.92 * x
    return 1.055 * (x ** (1.0 / 2.4)) - 0.055


def rgb_lin_to_srgb255(rgb: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """将线性 RGB 转换为 sRGB 255 范围。"""
    return tuple(int(round(linear01_to_srgb(c) * 255.0)) for c in rgb)


# -----------------------------
# 物理：菲涅尔（非偏振）、HG 散射
# -----------------------------


def fresnel_R_unpolarized(n1: float, n2: float, cos_i: float) -> float:
    """
    计算非偏振光在界面上的菲涅尔反射率。

    Args:
        n1: 入射介质折射率
        n2: 透射介质折射率
        cos_i: 入射角余弦值，必须在 [0,1] 范围内

    Returns:
        反射率（0-1 范围），处理全内反射情况
    """
    cos_i = max(0.0, min(1.0, cos_i))
    # 斯涅尔定律：n1 sin_i = n2 sin_t
    sin_i2 = max(0.0, 1.0 - cos_i * cos_i)
    # 如果 n1 > n2，可能发生全内反射
    sin_t2 = (n1 / n2) ** 2 * sin_i2
    if sin_t2 >= 1.0:
        return 1.0
    cos_t = math.sqrt(max(0.0, 1.0 - sin_t2))
    rs = ((n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)) ** 2
    rp = ((n1 * cos_t - n2 * cos_i) / (n1 * cos_t + n2 * cos_i)) ** 2
    return 0.5 * (rs + rp)


def sample_hg_cos_theta(g: float, u: float) -> float:
    """
    从 Henyey-Greenstein 相函数采样 cos(theta)。

    Args:
        g: 各向异性参数，范围 [-1,1]
        u: [0,1) 范围内的均匀随机数

    Returns:
        散射角的余弦值
    """
    g = max(-0.999, min(0.999, g))
    if abs(g) < 1e-6:
        return 2.0 * u - 1.0
    # 逆 CDF 采样
    num = 1.0 - g * g
    denom = 1.0 - g + 2.0 * g * u
    return (1.0 + g * g - (num / denom) ** 2) / (2.0 * g)


# -----------------------------
# 层模型
# -----------------------------


@dataclass
class OpticalProps:
    """材料光学属性数据类。

    Attributes:
        mu_a: 每通道吸收系数（1/mm）
        mu_s: 每通道散射系数（1/mm）
        g: 散射各向异性参数
        n: 折射率
    """

    # 每通道系数，单位 1/mm
    mu_a: Tuple[float, float, float]  # 吸收系数
    mu_s: Tuple[float, float, float]  # 散射系数
    g: float  # 各向异性参数
    n: float  # 折射率


# 默认材料光学参数（占位符，后续替换为拟合值）
# 直觉说明：
# - W（白色）：低吸收，高散射（乳白色）
# - T（透明）：极低吸收，低散射（透明）
# - K（黑色）：所有通道高吸收
# - R/G/B：其他通道高吸收 + 中等散射
DEFAULT_MATERIALS: Dict[str, OpticalProps] = {
    "W": OpticalProps(mu_a=(0.10, 0.10, 0.10), mu_s=(6.0, 6.0, 6.0), g=0.85, n=1.50),
    "T": OpticalProps(mu_a=(0.01, 0.01, 0.01), mu_s=(0.4, 0.4, 0.4), g=0.80, n=1.50),
    "K": OpticalProps(mu_a=(8.0, 8.0, 8.0), mu_s=(2.0, 2.0, 2.0), g=0.80, n=1.50),
    "R": OpticalProps(mu_a=(0.35, 2.2, 2.6), mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "G": OpticalProps(mu_a=(2.2, 0.35, 2.2), mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "B": OpticalProps(mu_a=(2.6, 2.2, 0.35), mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    # 可选扩展颜色
    "C": OpticalProps(mu_a=(2.4, 0.50, 0.50), mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "Y": OpticalProps(mu_a=(0.45, 0.45, 2.4), mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
    "M": OpticalProps(mu_a=(0.50, 2.4, 0.50), mu_s=(3.0, 3.0, 3.0), g=0.85, n=1.50),
}


def _default_materials_path() -> str:
    """获取默认材料配置文件路径。"""
    # 当前文件: py_module/scripts/src/oc_scripts/planning/
    # data/materials.json 在 repo 根目录下的 data 文件夹
    from pathlib import Path

    root = Path(__file__).resolve().parents[5]
    return str(root / "data" / "materials.json")


def load_materials_json(path: str) -> Dict[str, OpticalProps]:
    """从 JSON 文件加载材料光学参数。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mats = data.get("materials") or {}
    out: Dict[str, OpticalProps] = {}
    for k, v in mats.items():
        k2 = str(k).upper()
        out[k2] = OpticalProps(
            mu_a=tuple(map(float, v["mu_a"])),
            mu_s=tuple(map(float, v["mu_s"])),
            g=float(v.get("g", 0.85)),
            n=float(v.get("n", 1.50)),
        )
    return out


def cumulative_bounds(heights: Sequence[float]) -> List[float]:
    """计算层边界的累积高度。"""
    z = 0.0
    b = [0.0]
    for h in heights:
        z += float(h)
        b.append(z)
    return b  # 长度 L+1


def layer_index_at_z(bounds: Sequence[float], z: float) -> int:
    """根据 z 坐标确定所在层索引。"""
    # z 在 [0, total] 范围内
    # bounds 是有序的
    # 对于小 L，线性扫描即可；如需优化可用二分查找
    for i in range(len(bounds) - 1):
        if bounds[i] <= z < bounds[i + 1]:
            return i
    return len(bounds) - 2  # 如果 z == total


# -----------------------------
# 层状平板中的蒙特卡洛传输（1D 几何，3D 方向）
# -----------------------------


@dataclass
class MCResult:
    """蒙特卡洛模拟结果。

    Attributes:
        R: 每通道反射率 (0..1)
        T: 每通道透射率 (0..1)
    """

    R: Tuple[float, float, float]  # 每通道反射率
    T: Tuple[float, float, float]  # 每通道透射率


def _mc_one_channel(
    seq: Sequence[str],
    heights: Sequence[float],
    mats: Dict[str, OpticalProps],
    channel: int,
    view: str,
    samples: int,
    seed: int,
    air_n: float = 1.0,
    collimated_normal: bool = True,
    max_scatter_events: int = 2000,
) -> Tuple[float, float]:
    """
    对单一波长通道计算 (R, T)。

    Args:
        seq: 材料序列
        heights: 每层高度
        mats: 材料光学参数字典
        channel: 通道索引（0=R, 1=G, 2=B）
        view: 观察方向，"top" 表示从 z=0 入射向 +z 方向，"bottom" 表示从 z=total 入射向 -z 方向
        samples: 蒙特卡洛光子数
        seed: 随机种子
        air_n: 空气折射率
        collimated_normal: 是否使用准直入射
        max_scatter_events: 最大散射事件数

    Returns:
        (反射率, 透射率)
    """
    rng = random.Random(seed + 10007 * channel)

    # 如果从底部观察，通过镜像反转坐标系
    if view.lower() == "bottom":
        seq_eff = list(reversed(seq))
        heights_eff = list(reversed(heights))
    else:
        seq_eff = list(seq)
        heights_eff = list(heights)

    bounds = cumulative_bounds(heights_eff)
    total = bounds[-1]

    # 为简化，假设所有层具有相同的折射率（类似 PLA）
    # 但按层保留该参数
    # 菲涅尔界面只在空气/塑料和塑料/空气处计算
    # 相同折射率之间的内部界面不重要；如果后续设置不同折射率，
    # 可以在跨越层边界时添加内部菲涅尔检查

    # 预取每层的系数
    mu_a = [mats[t].mu_a[channel] for t in seq_eff]
    mu_s = [mats[t].mu_s[channel] for t in seq_eff]
    g = [mats[t].g for t in seq_eff]
    n_layer = [mats[t].n for t in seq_eff]
    # 假设内部折射率为常数 = n_layer[0] 用于外部菲涅尔计算
    # 如果需要变化的折射率，需要在每个边界计算菲涅尔；可行但更复杂
    n_in = float(np.median(n_layer)) if n_layer else 1.5

    R_count = 0.0
    T_count = 0.0

    for _ in range(samples):
        # 光子在入射表面启动
        z = 0.0
        # 方向余弦 mu = cos(theta) 相对于 +z（向下进入平板）
        mu = (
            1.0 if collimated_normal else math.sqrt(rng.random())
        )  # 如果是漫射则余弦加权
        # phi 在 1D 边界测试中不需要；只在散射后更新 mu 时需要

        # 入射处空气->塑料的菲涅尔反射
        Rf = fresnel_R_unpolarized(air_n, n_in, abs(mu))
        if rng.random() < Rf:
            # 镜面反射回空气
            R_count += 1.0
            continue

        # 光子进入
        # 折射后方向改变；为简化保持 mu 相同
        # 如果需要严格的斯涅尔方向，实现：
        # sin_t = n1/n2 * sin_i, 从 cos_t 得到；更新 mu = cos_t
        # 在小角度和准直入射的实际情况下，影响很小

        # 传输直到吸收或退出
        scatter_events = 0
        alive = True

        while alive and scatter_events < max_scatter_events:
            li = layer_index_at_z(bounds, z)
            mua = mu_a[li]
            mus = mu_s[li]
            mut = mua + mus
            if mut <= 1e-12:
                # 穿过该层的弹道传输：跳到下一个边界
                # 根据方向 mu 确定下一个边界
                if mu > 0:
                    next_z = bounds[li + 1]
                else:
                    next_z = bounds[li]
                z = next_z
            else:
                # 采样自由程
                s = -math.log(max(1e-12, rng.random())) / mut
                # z 方向步进
                dz = s * mu
                z_new = z + dz

                # 边界穿越处理：不能"传送"跨越多个边界
                # 裁剪到最近边界并继续剩余距离
                # 在层叠打印中 L 很小；循环裁剪即可
                while True:
                    if mu > 0:
                        # 向 +z 移动，下一个边界是当前层的顶部
                        b = bounds[li + 1]
                        if z_new < b + 1e-12:
                            # 未穿越边界
                            z = z_new
                            break
                        # 穿越边界
                        # 消耗到边界的距离
                        # （忽略部分吸收，因为我们使用基于交互的吸收）
                        z = b
                        li += 1
                        if z >= total - 1e-12:
                            # 从底部退出（塑料 -> 空气）
                            # 塑料->空气的菲涅尔反射
                            Rb = fresnel_R_unpolarized(n_in, air_n, abs(mu))
                            if rng.random() < Rb:
                                # 反射回平板
                                mu = -mu
                                z = total - 1e-9
                                break
                            T_count += 1.0
                            alive = False
                            break
                        # 通过"继续"剩余距离重新计算 z_new
                        # 我们用相同的 z_new 近似剩余距离；它已经包含了它
                        # 但必须更新层索引并继续；对于小 L 这是可接受的
                        # 在更严格的实现中，你需要跟踪剩余距离
                        z_new = z + 1e-9  # 轻微推入下一层
                        li = layer_index_at_z(bounds, z_new)
                        # 继续循环检查进一步穿越（罕见）
                        continue
                    else:
                        # 向 -z 移动，下一个边界是当前层的底部
                        b = bounds[li]
                        if z_new > b - 1e-12:
                            z = z_new
                            break
                        z = b
                        li -= 1
                        if z <= 0.0 + 1e-12:
                            # 从顶部退出（塑料 -> 空气）
                            Rt = fresnel_R_unpolarized(n_in, air_n, abs(mu))
                            if rng.random() < Rt:
                                mu = -mu
                                z = 1e-9
                                break
                            R_count += 1.0
                            alive = False
                            break
                        z_new = z - 1e-9
                        li = layer_index_at_z(bounds, z_new)
                        continue

            if not alive:
                break

            # 如果到达这里，我们在当前层有一个交互
            # 吸收或散射：
            li = layer_index_at_z(bounds, min(max(z, 0.0), total - 1e-9))
            mua = mu_a[li]
            mus = mu_s[li]
            mut = mua + mus
            if mut <= 1e-12:
                continue

            # 吸收概率
            if rng.random() < (mua / mut):
                alive = False
                break

            # 散射
            scatter_events += 1
            # 使用 HG 更新方向：相对于当前方向采样 cos(theta)
            ct = sample_hg_cos_theta(g[li], rng.random())
            # 我们只关心新的 mu（相对于 +z 的余弦）
            # 在 3D 中，mu' = mu*ct + sqrt(1-mu^2)*sqrt(1-ct^2)*cos(phi)
            phi = 2.0 * math.pi * rng.random()
            st = math.sqrt(max(0.0, 1.0 - ct * ct))
            smu = math.sqrt(max(0.0, 1.0 - mu * mu))
            mu = mu * ct + smu * st * math.cos(phi)
            # 限制数值漂移
            mu = max(-1.0, min(1.0, mu))

        # 如果超过最大散射事件数，视为吸收（罕见）
        # 不计数

    R = R_count / samples
    T = T_count / samples
    # 能量守恒：A = 1 - R - T
    return (R, T)


def forward_reflect_transmit(
    seq: Sequence[str],
    heights: Sequence[float],
    materials: Optional[Dict[str, OpticalProps]] = None,
    view: str = "top",
    samples: int = 200000,
    seed: int = 0,
) -> MCResult:
    """计算材料堆叠的前向反射和透射。

    Args:
        seq: 材料序列
        heights: 每层高度
        materials: 材料光学参数字典，默认使用 DEFAULT_MATERIALS
        view: 观察方向，"top" 或 "bottom"
        samples: 蒙特卡洛光子数
        seed: 随机种子

    Returns:
        MCResult 包含每通道反射率和透射率
    """
    mats = materials or DEFAULT_MATERIALS

    # 验证材料标识
    for t in seq:
        if t not in mats:
            raise ValueError(f"未知材料标识 {t}。已知材料: {sorted(mats.keys())}")

    if len(seq) != len(heights):
        raise ValueError("seq 和 heights 长度必须相同")

    # 三个通道 R,G,B
    Rvals = []
    Tvals = []
    for ch in range(3):
        Rch, Tch = _mc_one_channel(
            seq=seq,
            heights=heights,
            mats=mats,
            channel=ch,
            view=view,
            samples=samples,
            seed=seed,
        )
        Rvals.append(Rch)
        Tvals.append(Tch)
    return MCResult(R=tuple(Rvals), T=tuple(Tvals))


def observed_rgb_under_backing(
    R: Tuple[float, float, float],
    T: Tuple[float, float, float],
    backing_reflectance: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Tuple[float, float, float]:
    """
    计算背板上平板的标准合成颜色。

    公式：观测值 ≈ R + T * 背板反射率

    假设背板是从同一侧照明的朗伯反射器，
    忽略平板/背板之间的多次反射。可以按需扩展。

    Args:
        R: 反射率三元组
        T: 透射率三元组
        backing_reflectance: 背板反射率

    Returns:
        观测 RGB 值
    """
    return (
        max(0.0, min(1.0, R[0] + T[0] * backing_reflectance[0])),
        max(0.0, min(1.0, R[1] + T[1] * backing_reflectance[1])),
        max(0.0, min(1.0, R[2] + T[2] * backing_reflectance[2])),
    )


# -----------------------------
# 命令行接口
# -----------------------------


def parse_seq(s: str) -> List[str]:
    """解析材料序列字符串。"""
    s = s.strip()
    if "-" in s:
        return [x.strip().upper() for x in s.split("-") if x.strip()]
    return [c.upper() for c in s if not c.isspace()]


def parse_heights(s: str) -> List[float]:
    """解析高度字符串。"""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [float(p) for p in parts]


def main():
    """主函数：解析命令行参数并运行蒙特卡洛模拟。"""
    ap = argparse.ArgumentParser(description="基于物理的层叠堆栈前向模型（蒙特卡洛）")
    ap.add_argument("--seq", required=True, help="序列，如 W-G-W-R-W 或 WGW RW")
    ap.add_argument(
        "--heights",
        required=True,
        help="逗号分隔的高度（mm），如 0.12,0.08,0.08,0.08,0.08",
    )
    ap.add_argument(
        "--view", default="top", choices=["top", "bottom"], help="照明+观察侧"
    )
    ap.add_argument("--samples", type=int, default=200000, help="每通道蒙特卡洛光子数")
    ap.add_argument(
        "--samples-preview", type=int, default=None, help="低采样快速模式用于实时预览"
    )
    ap.add_argument("--seed", type=int, default=0, help="随机种子")
    ap.add_argument(
        "--backing",
        default="white",
        choices=["white", "black"],
        help="观测颜色的背板反射率",
    )
    ap.add_argument("--materials-json", default=None, help="materials.json 路径")
    args = ap.parse_args()

    seq = parse_seq(args.seq)
    heights = parse_heights(args.heights)

    mats_path = args.materials_json or _default_materials_path()
    if not os.path.exists(mats_path):
        raise SystemExit(f"未找到 materials.json: {mats_path}")
    mats = load_materials_json(mats_path)

    if args.samples_preview is not None:
        args.samples = int(args.samples_preview)

    res = forward_reflect_transmit(
        seq=seq,
        heights=heights,
        materials=mats,
        view=args.view,
        samples=args.samples,
        seed=args.seed,
    )

    backing = (1.0, 1.0, 1.0) if args.backing == "white" else (0.0, 0.0, 0.0)
    obs = observed_rgb_under_backing(res.R, res.T, backing_reflectance=backing)

    logger.info(f"seq={seq}")
    logger.info(f"heights_mm={heights} total={sum(heights):.3f}")
    logger.info(f"view={args.view} samples={args.samples} seed={args.seed}")
    logger.info(
        f"反射率 R={res.R}  透射率 T={res.T}  吸收率 A={(1 - res.R[0] - res.T[0], 1 - res.R[1] - res.T[1], 1 - res.R[2] - res.T[2])}"
    )
    logger.info(f"在 {args.backing} 背板上的观测值（线性）={obs}")
    logger.info(f"观测 sRGB={rgb_lin_to_srgb255(obs)}")


if __name__ == "__main__":
    main()
