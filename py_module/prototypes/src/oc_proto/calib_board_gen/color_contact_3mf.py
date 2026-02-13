from __future__ import annotations

import argparse
import colorsys
import json
import math
import os
import random
import subprocess
import traceback
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import trimesh
from tqdm import tqdm

from model_export.standard_3mf import export_standard_3mf_from_meshes
from model_export.types import apply_alpha_to_brightness
from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager,
    ColorProfile,
    parse_color_argument,
    create_profile_from_args,
)
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _gen_colors(n: int) -> List[Tuple[int, int, int]]:
    """生成指定数量的 HSV 色相分布的颜色列表。"""
    if n <= 0:
        raise SystemExit("颜色数量必须大于0")
    colors: List[Tuple[int, int, int]] = []
    if n == 1:
        return [(255, 0, 0)]
    for i in range(n):
        h = (i / n) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 1.0)
        colors.append((int(round(r * 255)), int(round(g * 255)), int(round(b * 255))))
    return colors


def _edges_for_grid(w: int, h: int) -> List[Tuple[int, int]]:
    """为指定尺寸的网格生成相邻单元格之间的边列表。"""
    edges: List[Tuple[int, int]] = []
    for y in range(h):
        row = y * w
        for x in range(w):
            idx = row + x
            if x + 1 < w:
                edges.append((idx, idx + 1))
            if y + 1 < h:
                edges.append((idx, idx + w))
    return edges


def _pair_count(n: int) -> int:
    """计算 n 个元素之间所有可能的配对数量。"""
    return n * (n - 1) // 2


def _lower_bound_tiles(n: int) -> int:
    """计算满足 n 种颜色两两接触所需的最小单元格数量下界。"""
    return int(math.ceil((n * (n - 1)) / 4.0))


def _grid_factors(v: int) -> List[Tuple[int, int]]:
    """获取指定单元格数量的所有可能网格尺寸（宽 x 高）组合。"""
    out: List[Tuple[int, int]] = []
    for h in range(1, int(math.sqrt(v)) + 1):
        if v % h == 0:
            w = v // h
            out.append((w, h))
            if w != h:
                out.append((h, w))
    out.sort(key=lambda x: (x[0] * x[1], x[0], x[1]))
    return out


def _score_grid(grid: Sequence[int], edges: Sequence[Tuple[int, int]]) -> int:
    """计算网格中相邻单元格之间不同颜色配对的数量。"""
    pairs = set()
    for a, b in edges:
        ca = grid[a]
        cb = grid[b]
        if ca == cb:
            continue
        if ca < cb:
            pairs.add((ca, cb))
        else:
            pairs.add((cb, ca))
    return len(pairs)


def _random_grid(n: int, v: int, rng: random.Random) -> List[int]:
    """生成包含 v 个单元格的随机颜色网格，每种颜色编号范围为 [0, n-1]。"""
    return [rng.randrange(n) for _ in range(v)]


def _search_layout(
    n: int,
    max_extra: int,
    tries: int,
    steps: int,
    seed: int,
) -> Tuple[List[int], int, int, int]:
    """使用爬山算法搜索满足所有颜色两两接触条件的最小网格布局。

    返回: (网格颜色列表, 宽度, 高度, 总单元格数)
    """
    if n <= 0:
        raise SystemExit("颜色数量必须大于0")
    if n == 1:
        return [0], 1, 1, 1

    target = _pair_count(n)
    v0 = _lower_bound_tiles(n)
    rng = random.Random(seed if seed != 0 else None)

    total_grids = sum(len(_grid_factors(v)) for v in range(v0, v0 + max_extra + 1))
    with tqdm(
        total=total_grids, desc="网格遍历", unit="种", dynamic_ncols=True
    ) as grid_bar:
        for v in range(v0, v0 + max_extra + 1):
            for w, h in _grid_factors(v):
                grid_bar.set_postfix_str(f"尺寸 {w}x{h} 块数 {v}")
                edges = _edges_for_grid(w, h)
                best_grid: List[int] = []
                best_score = -1
                with tqdm(
                    total=tries,
                    desc="随机尝试",
                    unit="次",
                    leave=False,
                    dynamic_ncols=True,
                ) as try_bar:
                    for _ in range(tries):
                        grid = _random_grid(n, v, rng)
                        score = _score_grid(grid, edges)
                        if score > best_score:
                            best_grid = list(grid)
                            best_score = score
                        if score == target:
                            return grid, w, h, v

                        with tqdm(
                            total=steps,
                            desc="微调搜索",
                            unit="步",
                            leave=False,
                            dynamic_ncols=True,
                            mininterval=0.5,
                        ) as step_bar:
                            step_count = 0
                            for _ in range(steps):
                                if score == target:
                                    return grid, w, h, v
                                if rng.random() < 0.5:
                                    i = rng.randrange(v)
                                    new_c = rng.randrange(n)
                                    if new_c != grid[i]:
                                        old = grid[i]
                                        grid[i] = new_c
                                        new_score = _score_grid(grid, edges)
                                        if new_score >= score:
                                            score = new_score
                                        else:
                                            grid[i] = old
                                else:
                                    i = rng.randrange(v)
                                    j = rng.randrange(v)
                                    if i != j:
                                        grid[i], grid[j] = grid[j], grid[i]
                                        new_score = _score_grid(grid, edges)
                                        if new_score >= score:
                                            score = new_score
                                        else:
                                            grid[i], grid[j] = grid[j], grid[i]
                                step_count += 1
                                if step_count % 50 == 0:
                                    step_bar.update(50)
                            if step_count % 50 != 0:
                                step_bar.update(step_count % 50)

                        if score > best_score:
                            best_grid = list(grid)
                            best_score = score
                        try_bar.update(1)
                grid_bar.update(1)
                if best_score == target:
                    return best_grid, w, h, v

    raise SystemExit("未能在限制范围内找到满足全部接触条件的最小布局")


def _search_layout_cpp(
    n: int,
    max_extra: int,
    tries: int,
    steps: int,
    seed: int,
) -> Tuple[List[int], int, int, int] | None:
    """调用 C++ 加速模块搜索颜色接触布局。

    返回: (网格颜色列表, 宽度, 高度, 总单元格数)，如果 C++ 模块不可用则返回 None
    """
    # 当前文件: py_module/prototypes/src/oc_proto/calib_board_gen/color_contact_3mf.py
    # parents[5] 是项目根目录
    root = Path(__file__).resolve().parents[5]
    config = os.environ.get("CMAKE_BUILD_TYPE", "").strip()
    configs = [config] if config else ["Release", "Debug"]
    exe = None
    for cfg in configs:
        candidate = (
            root / "cpp_module" / "build" / cfg / "opencolor_color_contact_search.exe"
        )
        if candidate.exists():
            exe = candidate
            break
    if exe is None:
        logger.info("未找到C++加速模块可执行文件")
        logger.info("请先运行：pixi run cpp-build")
        return None

    cmd = [
        str(exe),
        "--colors",
        str(n),
        "--max-extra",
        str(max_extra),
        "--tries",
        str(tries),
        "--steps",
        str(steps),
        "--seed",
        str(seed),
    ]
    logger.info("使用C++加速模块搜索布局")
    try:
        result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    except Exception as exc:
        logger.error("C++加速模块执行失败")
        logger.info(str(exc))
        logger.info("异常详情：")
        logger.info(traceback.format_exc())
        return None

    if result.returncode != 0:
        logger.error("C++加速模块返回错误")
        if result.stdout:
            logger.info("标准输出：")
            logger.info(result.stdout)
        if result.stderr:
            logger.error("错误输出：")
            logger.info(result.stderr)
        return None

    try:
        payload = json.loads(result.stdout.strip())
    except Exception as exc:
        logger.error("C++加速模块输出解析失败")
        logger.info(str(exc))
        logger.info("原始输出：")
        logger.info(result.stdout)
        return None

    grid = payload.get("grid")
    w = int(payload.get("w"))
    h = int(payload.get("h"))
    v = int(payload.get("v"))
    if not isinstance(grid, list):
        logger.info("C++加速模块输出缺少grid")
        return None
    return [int(x) for x in grid], w, h, v


def _build_meshes(
    placements: Sequence[Tuple[int, float, float, int]],
    tile_mm: float,
    thickness_mm: float,
    color_count: int,
) -> dict[str, trimesh.Trimesh]:
    """根据放置位置构建多色网格字典。

    参数:
        placements: 放置位置列表 [(颜色索引, x, y, 单元格索引), ...]
        tile_mm: 正方形边长(mm)
        thickness_mm: 正方形厚度(mm)
        color_count: 颜色数量

    返回:
        按颜色索引分组的网格字典 {颜色索引字符串: trimesh.Trimesh}
    """
    base_tile = trimesh.creation.box(extents=(tile_mm, tile_mm, thickness_mm))
    if color_count <= 0:
        raise ValueError("颜色数量必须大于0")
    parts: List[List[trimesh.Trimesh]] = [[] for _ in range(int(color_count))]
    cz = thickness_mm / 2.0
    for color_index, x, y, _ in placements:
        if color_index < 0 or color_index >= color_count:
            continue
        tile = base_tile.copy()
        tile.apply_translation((x + tile_mm / 2.0, y + tile_mm / 2.0, cz))
        parts[color_index].append(tile)

    meshes: dict[str, trimesh.Trimesh] = {}
    for i, group in enumerate(parts):
        slot_name = f"Color_{i:02d}"
        if not group:
            # 创建占位网格
            mesh = trimesh.creation.box(extents=(0.01, 0.01, 0.01))
        else:
            mesh = trimesh.util.concatenate(group)
        meshes[slot_name] = mesh
    return meshes


def _export_standard_3mf(
    *,
    out_path: Path,
    colors: Sequence[Tuple[int, int, int, int]],
    placements: Sequence[Tuple[int, float, float, int]],
    tile_mm: float,
    thickness_mm: float,
) -> None:
    """导出标准3MF文件。

    重要：此函数必须使用 apply_alpha_to_brightness 处理颜色，
    以确保半透明颜色（如 Transparent）与纯色（如 White）在3MF中可区分。
    否则 Bambu Studio 等软件会将它们识别为同一种颜色。

    参数:
        out_path: 输出3MF文件路径
        colors: 颜色列表 [(R, G, B, A), ...]，包含Alpha通道
        placements: 放置位置列表 [(颜色索引, x, y, 单元格索引), ...]
        tile_mm: 正方形边长(mm)
        thickness_mm: 正方形厚度(mm)
    """
    color_count = len(colors)

    # 构建网格
    meshes = _build_meshes(placements, tile_mm, thickness_mm, color_count)

    # 准备颜色配置
    slot_names = [f"Color_{i:02d}" for i in range(color_count)]
    slot_colors = {}
    for i, rgba in enumerate(colors):
        slot_name = f"Color_{i:02d}"
        # 使用 apply_alpha_to_brightness 处理颜色，将Alpha编码到RGB亮度中
        # 这是必要的，否则半透明颜色（如White+128Alpha）会与纯色（White+255Alpha）
        # 在3MF中被识别为同一种颜色
        adjusted_rgba = apply_alpha_to_brightness(rgba)
        slot_colors[slot_name] = adjusted_rgba

    # 导出3MF
    export_standard_3mf_from_meshes(
        out_3mf=out_path,
        meshes=meshes,
        slot_names=slot_names,
        slot_colors=slot_colors,
    )
    logger.info(f"标准3MF输出完成：{out_path.resolve()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="生成颜色互相接触的正方形3MF")
    ap.add_argument(
        "--out",
        type=str,
        default="out_color_contact/color_contact_squares.3mf",
        help="输出3MF路径",
    )

    # 颜色配置选项（与main.py保持一致）
    color_group = ap.add_mutually_exclusive_group()
    color_group.add_argument(
        "--colors",
        type=str,
        nargs="+",
        default=None,
        help="命令行指定颜色，格式：'名称:R,G,B,A' 或 '名称:R,G,B'"
    )
    color_group.add_argument(
        "--profile",
        type=str,
        default=None,
        help="使用预设颜色配置（可选：rgb, rybw, rgbw, rgbwk, full_8）"
    )
    color_group.add_argument(
        "--profile-file",
        type=str,
        default=None,
        help="从JSON文件加载自定义颜色配置"
    )
    color_group.add_argument(
        "--color-count",
        type=int,
        default=None,
        help="自动生成指定数量的HSV分布颜色（传统方式）"
    )

    ap.add_argument("--tile-mm", type=float, default=10.0, help="正方形边长(mm)")
    ap.add_argument("--thickness-mm", type=float, default=1.0, help="正方形厚度(mm)")
    ap.add_argument(
        "--max-extra", type=int, default=8, help="在最小数量基础上允许额外增加的块数"
    )
    ap.add_argument("--tries", type=int, default=60, help="每个网格尺寸的随机尝试次数")
    ap.add_argument("--steps", type=int, default=8000, help="每次尝试的迭代步数")
    ap.add_argument("--seed", type=int, default=0, help="随机种子(0为自动)")
    ap.add_argument("--python", action="store_true", help="使用Python模式（默认使用C++模式，C++不可用时将报错）")
    args = ap.parse_args()

    if args.tile_mm <= 0 or args.thickness_mm <= 0:
        raise SystemExit("边长和厚度必须大于0")
    if args.max_extra < 0:
        raise SystemExit("max-extra 不能为负数")
    if args.tries <= 0 or args.steps <= 0:
        raise SystemExit("tries 和 steps 必须大于0")

    # 获取颜色配置
    profile = None

    if args.colors:
        # 从命令行参数创建配置
        try:
            profile = create_profile_from_args(args.colors, profile_name="Custom")
            logger.info(f"使用命令行指定的颜色: {profile.color_names}")
        except Exception as e:
            logger.error(f"解析颜色参数失败: {e}")
            raise SystemExit(1)
    elif args.profile_file:
        # 从文件加载配置
        try:
            manager = get_profile_manager()
            profile_id = manager.load_from_file(Path(args.profile_file))
            profile = manager.get_profile(profile_id)
            logger.info(f"从文件加载配置: {args.profile_file} -> {profile.name}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise SystemExit(1)
    elif args.profile:
        # 使用预设配置
        try:
            manager = get_profile_manager()
            profile = manager.get_profile(args.profile)
            logger.info(f"使用预设配置: {profile.name}")
        except Exception as e:
            logger.error(f"未知配置 '{args.profile}': {e}")
            manager = get_profile_manager()
            logger.info(f"可用配置: {', '.join(manager.list_profiles())}")
            raise SystemExit(1)
    elif args.color_count:
        # 使用传统方式：自动生成HSV颜色
        color_count = args.color_count
        colors = _gen_colors(color_count)
        logger.info(f"使用自动生成的 {color_count} 种HSV颜色")
    else:
        # 默认使用4色配置
        manager = get_profile_manager()
        profile = manager.get_profile("rybw")
        logger.info(f"使用默认配置: {profile.name}")

    # 从profile获取颜色，或者使用自动生成的颜色
    # 重要：必须保留完整的RGBA（包括Alpha通道），以便正确处理半透明颜色
    if profile is not None:
        color_count = profile.num_colors
        colors = []
        for name in profile.color_names:
            rgba = profile.get_color_rgba(name)
            # 保留完整的RGBA，包括Alpha通道
            # 这是必要的，因为 apply_alpha_to_brightness 需要Alpha来区分半透明和纯色
            colors.append(rgba)
        logger.info(f"颜色列表: {profile.color_names}")
    else:
        # 自动生成的颜色默认不透明（Alpha=255）
        colors = [(c[0], c[1], c[2], 255) for c in colors]
        logger.info(f"生成 {color_count} 种颜色的接触布局")

    # 搜索布局（默认使用C++模式，除非指定--python）
    grid = None
    w = h = v = 0

    if not args.python:
        # 默认使用C++模式
        cpp_result = _search_layout_cpp(
            color_count,
            int(args.max_extra),
            int(args.tries),
            int(args.steps),
            int(args.seed),
        )
        if cpp_result is not None:
            grid, w, h, v = cpp_result
        else:
            logger.error("C++加速模块不可用，请运行 'pixi run cpp-build' 编译")
            logger.error("或添加 --python 参数使用Python模式（较慢）")
            raise SystemExit(1)
    else:
        # 使用Python模式
        logger.info("使用Python模式搜索布局（较慢）")
        grid, w, h, v = _search_layout(
            color_count,
            int(args.max_extra),
            int(args.tries),
            int(args.steps),
            int(args.seed),
        )

    logger.info(f"找到布局：{w}x{h}, 共 {v} 块")

    placements = []
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            color_index = grid[idx]
            placements.append((color_index, x * args.tile_mm, y * args.tile_mm, idx))

    # 导出标准3MF
    out_path = Path(args.out)
    _export_standard_3mf(
        out_path=out_path,
        colors=colors,
        placements=placements,
        tile_mm=args.tile_mm,
        thickness_mm=args.thickness_mm,
    )

    logger.info("=" * 60)
    logger.info(f"生成完成！共 {color_count} 种颜色，{v} 个正方形")
    logger.info(f"输出文件: {out_path.absolute()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
