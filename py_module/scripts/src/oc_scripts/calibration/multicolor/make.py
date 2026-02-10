#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""生成多材料校准板（STLs + 配方 JSON）

设计意图
-------------
此脚本生成一个或多个可打印的校准板。

每个校准板由 N 个独立的 STL 文件（每种材料一个）加上一个 JSON 清单组成，
清单描述了每个色块的层配方。该清单用于模型拟合（光学/经验参数或小型本地 ML 模型），
而非运行时数据库查询。

主要特性：
- 支持任意数量的材料（>=4 种）
- 支持完全枚举（序列/组合）和优先排序，将"重要"的色块放在前面的板上
- 首层高度和后续层高度可配置（默认：0.12mm + 0.08mm）
- 配方包含打印序列和观察序列（用于打印前翻转板子拍照）
"""

from __future__ import annotations

import argparse
import json
import math
import os
from typing import Dict, Iterable, List

import numpy as np
import trimesh

from .geom import (
    add_bottom_stripes,
    add_border_rings_for_layer,
    add_first_layer_border_segments,
    add_mesh_accum,
    prism,
    row_stripe_material_index,
)
from .seq import (
    compositions_k,
    interleave_from_counts,
    prioritized_sequences,
    sequence_index_to_digits,
)
from .utils import clean_mesh, parse_materials



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def add_tile(
    all_verts: List[List[np.ndarray]],
    all_faces: List[List[np.ndarray]],
    tiles_meta: List[Dict],
    *,
    tile_id: int,
    seq_digits: List[int],
    ix: int,
    iy: int,
    plate_index: int,
    x0_card: float,
    y0_card: float,
    pitch: float,
    tile_mm: float,
    bottom_stripes_enabled: bool,
    K: int,
    heights_mm: List[float],
    L: int,
    mats: List[str],
    flip_after_print: bool,
) -> None:
    """添加一个色块瓦片到网格中。

    Args:
        all_verts: 每种材料的顶点列表
        all_faces: 每种材料的面片列表
        tiles_meta: 色块元数据列表
        tile_id: 色块唯一标识
        seq_digits: 层序列的数字表示
        ix, iy: 网格中的行列索引
        plate_index: 板子索引
        x0_card, y0_card: 板子起始坐标
        pitch: 瓦片间距
        tile_mm: 瓦片尺寸（毫米）
        bottom_stripes_enabled: 是否启用底层条纹连接
        K: 材料种类数
        heights_mm: 每层高度列表
        L: 总层数
        mats: 材料名称列表
        flip_after_print: 打印后是否翻转
    """
    x0 = x0_card + ix * pitch
    x1 = x0 + tile_mm
    y0 = y0_card + iy * pitch
    y1 = y0 + tile_mm

    # 启用底层条纹时强制执行连接
    seq_digits_eff = list(seq_digits)
    if bottom_stripes_enabled:
        seq_digits_eff[0] = row_stripe_material_index(iy, K)

    # 构建网格部分：将连续相同材料的层合并为单个棱柱
    if bottom_stripes_enabled and L >= 2:
        z = float(heights_mm[0])
        last_mi = None
        z0 = z
        for li in range(1, L):
            mi = int(seq_digits_eff[li])
            if last_mi is None:
                last_mi = mi
                z0 = z
            z += float(heights_mm[li])
            if li == L - 1 or int(seq_digits_eff[li + 1]) != mi:
                v, f = prism(x0, x1, y0, y1, z0, z)
                add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
                z0 = z
                last_mi = None
    else:
        z = 0.0
        last_mi = None
        z0 = 0.0
        for li, mi in enumerate(seq_digits_eff):
            mi = int(mi)
            if last_mi is None:
                last_mi = mi
                z0 = z

            z += float(heights_mm[li])
            if li == L - 1 or int(seq_digits_eff[li + 1]) != mi:
                v, f = prism(x0, x1, y0, y1, z0, z)
                add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
                z0 = z
                last_mi = None

    seq_print = [mats[i] for i in seq_digits_eff]
    seq_view = list(reversed(seq_print)) if flip_after_print else list(seq_print)

    tiles_meta.append(
        {
            "tile_id": int(tile_id),
            "plate_index": int(plate_index),
            "ix": int(ix),
            "iy": int(iy),
            "rect_mm": {"x": float(x0), "y": float(y0), "w": float(tile_mm), "h": float(tile_mm)},
            "print_sequence": seq_print,
            "view_sequence": seq_view,
            "heights_mm": [float(x) for x in heights_mm],
        }
    )


def main() -> None:
    """主函数：解析命令行参数并生成多材料校准板"""
    ap = argparse.ArgumentParser(
        description="生成多材料校准板（STLs + 配方 JSON）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # 几何/布局参数
    ap.add_argument("--outdir", default="out_calibration_board", help="输出目录")
    ap.add_argument("--name", default="calib_board", help="输出文件基础名称")

    # A1 mini (180x180 打印床) 的实用默认值是 18x18 瓦片，8mm = 144mm
    # 为擦拭/Prime塔留出空间
    ap.add_argument("--board-mm", type=float, default=144.0, help="整板宽度/高度（正方形）")
    ap.add_argument("--tile-mm", type=float, default=8.0, help="色块尺寸（正方形）")
    ap.add_argument("--nx", type=int, default=0, help="每行瓦片数（0 = board-mm/tile-mm）")
    ap.add_argument("--ny", type=int, default=0, help="每列瓦片数（0 = board-mm/tile-mm）")
    ap.add_argument("--center", action="store_true", help="将板子中心置于原点（默认：左下角在 0,0）")

    ap.add_argument("--border-mm", type=float, default=3.0, help="外边框宽度（毫米），设为0禁用")
    ap.add_argument("--border-rings", type=int, default=4, help="首层以上用于边框的同心回形环数量")
    ap.add_argument("--no-bottom-stripes", action="store_true", help="禁用底层连接条纹，恢复为每瓦片首层")

    # 层叠参数
    ap.add_argument("--layers", type=int, default=5, help="每个色块的总离散层数")
    ap.add_argument("--first-layer-height", type=float, default=0.12, help="首层厚度（毫米）")
    ap.add_argument("--layer-height", type=float, default=0.08, help="后续层厚度（毫米）")
    ap.add_argument(
        "--flip-after-print",
        action="store_true",
        default=True,
        help="配方包含 view_sequence = reversed(print_sequence)，用于打印后翻转",
    )

    # 材料/枚举模式
    ap.add_argument(
        "--materials",
        default="R,G,B,W",
        help="逗号分隔的材料名称（>=4个）。每个名称对应一个输出 STL 后缀",
    )

    ap.add_argument(
        "--mode",
        choices=["sequence", "composition"],
        default="sequence",
        help=(
            "枚举模式：'sequence' 枚举完整层序列（K^L）；"
            "'composition' 枚举数量组合（C(L+K-1,K-1)）然后构建每层序列"
        ),
    )

    ap.add_argument(
        "--ordering",
        choices=["prioritized", "numeric"],
        default="prioritized",
        help=(
            "mode=sequence 时：'prioritized' 将更有信息量的色块（单色、单异、混合对等）"
            "优先放在前面的板上，然后回退到数字枚举。"
            "'numeric' 使用简单的 K 进制计数"
        ),
    )

    ap.add_argument(
        "--composition-order",
        choices=["interleave", "stacked"],
        default="interleave",
        help="mode=composition 时：通过交错（推荐）或堆叠 mats[0]..mats[K-1] 构建层序列",
    )

    ap.add_argument(
        "--goal",
        default="all",
        help=(
            "生成多少配方空间。原型推荐：'all'（自动拆分到所需板数）。"
            "其他形式：'first'（一块板，最重要的色块优先）、'budget:<Ntiles>'（总共生成 Ntiles 个）、"
            "或 'plates:<N>'（正好生成 N 块板；主要用于调试）"
        ),
    )

    ap.add_argument(
        "--max-plates",
        type=int,
        default=50,
        help=(
            "goal=all 时的安全上限。如果完整枚举需要超过此数量的板，脚本将中止并给出指导。"
            "如确实需要更多，可增加此值，或优先使用 mode=composition（空间小得多）"
        ),
    )

    ap.add_argument(
        "--gap-mm",
        type=float,
        default=0.0,
        help="瓦片间可选间隙（毫米）。对摄影有用；会减少有效填充面积",
    )

    ap.add_argument(
        "--max-tiles",
        type=int,
        default=0,
        help="硬上限，限制生成的色块数量（0 = 使用完整网格 nx*ny）",
    )

    ap.add_argument("--validate", action="store_true", help="运行 trimesh 清理（较慢但更安全）")

    args = ap.parse_args()

    mats = parse_materials(args.materials)
    K = len(mats)

    board_mm = float(args.board_mm)
    tile_mm = float(args.tile_mm)
    if board_mm <= 0 or tile_mm <= 0:
        raise ValueError("--board-mm 和 --tile-mm 必须大于 0")

    # 确定网格
    if args.nx > 0:
        nx = int(args.nx)
    else:
        nx = int(round(board_mm / tile_mm))
    if args.ny > 0:
        ny = int(args.ny)
    else:
        ny = int(round(board_mm / tile_mm))

    if nx <= 0 or ny <= 0:
        raise ValueError("nx/ny 必须大于 0")

    # 如 board 和 nx 不匹配，是否重新计算 tile？保持 tile 不变；在元数据中警告
    grid_w = nx * tile_mm
    grid_h = ny * tile_mm

    L = int(max(1, args.layers))
    h0 = float(args.first_layer_height)
    h = float(args.layer_height)
    if h0 <= 0 or h <= 0:
        raise ValueError("层高度必须大于 0")

    heights_mm: List[float] = [h0] + [h] * (L - 1)

    # 瓦片间距（瓦片 + 可选间隙）
    gap = float(args.gap_mm)
    pitch = tile_mm + gap
    grid_w = nx * pitch - gap
    grid_h = ny * pitch - gap

    # 每板容量
    grid_cap_plate = nx * ny

    # 总配方空间大小（sequence 模式下可能非常大）
    if args.mode == "composition":
        total_space = int(math.comb(L + K - 1, K - 1))
    else:
        total_space = int(K**L)

    # 解析 goal -> 生成多少瓦片，拆分到多少板
    goal_raw = str(args.goal).strip().lower()
    tiles_wanted: int
    plates_wanted: int

    def ceil_div(a: int, b: int) -> int:
        return (a + b - 1) // b

    if goal_raw == "all":
        tiles_wanted = total_space
        plates_wanted = ceil_div(tiles_wanted, grid_cap_plate)
        if plates_wanted > int(max(1, args.max_plates)):
            raise ValueError(
                f"goal=all 需要 {plates_wanted} 块板（{tiles_wanted} 个瓦片），网格 {nx}x{ny}={grid_cap_plate} 瓦片/板。"
                f"超过 --max-plates={args.max_plates}。\n"
                f"建议：使用 --mode composition（空间小得多），或 --goal budget:<Ntiles>，或增加 --max-plates"
            )
    elif goal_raw == "first":
        plates_wanted = 1
        tiles_wanted = min(total_space, grid_cap_plate)
    elif goal_raw.startswith("budget:"):
        n = int(goal_raw.split(":", 1)[1])
        if n <= 0:
            raise ValueError("budget 必须大于 0")
        tiles_wanted = min(total_space, n)
        plates_wanted = ceil_div(tiles_wanted, grid_cap_plate)
    elif goal_raw.startswith("plates:"):
        n = int(goal_raw.split(":", 1)[1])
        if n <= 0:
            raise ValueError("plates 必须大于 0")
        plates_wanted = n
        tiles_wanted = min(total_space, plates_wanted * grid_cap_plate)
    else:
        raise ValueError(
            "无效的 --goal。使用以下之一：all | first | budget:<Ntiles> | plates:<N>"
        )

    # 可选硬上限（调试用）。最后应用此上限
    if int(args.max_tiles) > 0:
        tiles_wanted = min(tiles_wanted, int(args.max_tiles))
        plates_wanted = max(1, ceil_div(tiles_wanted, grid_cap_plate))

    total_tiles = int(max(0, tiles_wanted))
    plates_to_generate = int(max(0, plates_wanted))

    # 放置位置
    if args.center:
        x0_card = -grid_w / 2.0
        y0_card = -grid_h / 2.0
    else:
        x0_card = 0.0
        y0_card = 0.0

    # 构建序列/组合源，但不物化巨大列表
    if args.mode == "composition":
        combos_all = compositions_k(L, K, limit=total_tiles)
        seq_source: Iterable[List[int]]
        if args.composition_order == "stacked":
            def _stacked():
                for counts in combos_all:
                    seq: List[int] = []
                    for mi in range(K):
                        seq.extend([mi] * int(counts[mi]))
                    yield seq

            seq_source = _stacked()
        else:
            def _interleave():
                for counts in combos_all:
                    yield interleave_from_counts(counts)

            seq_source = _interleave()
    else:
        if args.ordering == "prioritized":
            seq_source = prioritized_sequences(K, L, max_items=total_tiles)
        else:
            def _numeric():
                for idx in range(total_tiles):
                    yield sequence_index_to_digits(base=K, length=L, idx=idx, lsb_first=True)

            seq_source = _numeric()

    os.makedirs(args.outdir, exist_ok=True)

    # 逐板生成
    global_tile_id = 0
    plates_meta: List[Dict] = []

    seq_iter = iter(seq_source)
    for plate_index in range(int(max(1, plates_to_generate))):
        remaining = total_tiles - global_tile_id
        if remaining <= 0:
            break

        plate_tiles = min(grid_cap_plate, remaining)
        # 每板使用新的累加器
        all_verts: List[List[np.ndarray]] = [[] for _ in range(K)]
        all_faces: List[List[np.ndarray]] = [[] for _ in range(K)]
        tiles_meta: List[Dict] = []


        # ------------------------------------------------------------------
        # 稳健的附着特性
        # 1) 底层连接条纹，避免孤立岛屿
        # 2) 外边框：首层匹配相邻条纹颜色，
        #    上层使用同心回形环"缝合"材料
        # ------------------------------------------------------------------
        border_mm = float(args.border_mm)
        bottom_stripes_enabled = not bool(args.no_bottom_stripes)
        x0_inner = x0_card
        x1_inner = x0_card + grid_w
        y0_inner = y0_card
        y1_inner = y0_card + grid_h

        # 累积层 Z 范围
        z_edges = [0.0]
        for hh in heights_mm:
            z_edges.append(z_edges[-1] + float(hh))

        if bottom_stripes_enabled:
            add_bottom_stripes(
                all_verts,
                all_faces,
                mats_count=K,
                x0_inner=x0_inner,
                x1_inner=x1_inner,
                y0_inner=y0_inner,
                y1_inner=y1_inner,
                pitch=pitch,
                tile_mm=tile_mm,
                gap=gap,
                ny=ny,
                z0=z_edges[0],
                z1=z_edges[1],
            )

        if border_mm > 0:
            # 首层边框：匹配相邻底层条纹材料
            add_first_layer_border_segments(
                all_verts,
                all_faces,
                mats_count=K,
                border_mm=border_mm,
                x0_inner=x0_inner,
                x1_inner=x1_inner,
                y0_inner=y0_inner,
                y1_inner=y1_inner,
                pitch=pitch,
                tile_mm=tile_mm,
                gap=gap,
                ny=ny,
                z0=z_edges[0],
                z1=z_edges[1],
            )

            # 上层边框：循环材料的同心环
            for li in range(1, L):
                add_border_rings_for_layer(
                    all_verts,
                    all_faces,
                    mats_count=K,
                    layer_index=li,
                    border_mm=border_mm,
                    rings=int(args.border_rings),
                    x0_inner=x0_inner,
                    x1_inner=x1_inner,
                    y0_inner=y0_inner,
                    y1_inner=y1_inner,
                    z0=z_edges[li],
                    z1=z_edges[li + 1],
                )

        for local_id in range(plate_tiles):
            ix = local_id % nx
            iy = local_id // nx
            if iy >= ny:
                break
            try:
                seq_digits = next(seq_iter)
            except StopIteration:
                break
            add_tile(
                all_verts,
                all_faces,
                tiles_meta,
                tile_id=global_tile_id,
                seq_digits=seq_digits,
                ix=ix,
                iy=iy,
                plate_index=plate_index,
                x0_card=x0_card,
                y0_card=y0_card,
                pitch=pitch,
                tile_mm=tile_mm,
                bottom_stripes_enabled=bottom_stripes_enabled,
                K=K,
                heights_mm=heights_mm,
                L=L,
                mats=mats,
                flip_after_print=bool(args.flip_after_print),
            )
            global_tile_id += 1

        # 导出此板的 STL
        stl_paths: Dict[str, str] = {}
        for mi, mat_name in enumerate(mats):
            if not all_verts[mi]:
                continue
            V = np.vstack(all_verts[mi])
            F = np.vstack(all_faces[mi])
            mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
            if args.validate:
                mesh = clean_mesh(mesh)
            outpath = os.path.join(args.outdir, f"{args.name}_p{plate_index+1:02d}_{mat_name}.stl")
            mesh.export(outpath)
            stl_paths[mat_name] = os.path.abspath(outpath)
            logger.info(f"[OK] 已写入: {outpath}  (顶点={len(mesh.vertices)}, 面片={len(mesh.faces)})")

        meta = {
            "schema_version": 2,
            "script": os.path.basename(__file__),
            "plate_index": int(plate_index),
            "plate_count": int(max(1, plates_to_generate)),
            "params": {
                "goal": str(args.goal),
                "total_space": int(total_space),
                "tiles_wanted": int(total_tiles),
                "tiles_per_plate": int(grid_cap_plate),
                "mode": str(args.mode),
                "ordering": str(args.ordering),
                "composition_order": str(args.composition_order),
                "materials": list(mats),
                "layers": int(L),
                "first_layer_height_mm": float(h0),
                "layer_height_mm": float(h),
                "flip_after_print": bool(args.flip_after_print),
                "tile_mm": float(tile_mm),
                "gap_mm": float(gap),
                "pitch_mm": float(pitch),
                "board_mm_target": float(board_mm),
                "grid_nx": int(nx),
                "grid_ny": int(ny),
                "grid_mm": {"w": float(grid_w), "h": float(grid_h)},
                "center": bool(args.center),
                "max_tiles_total": int(total_tiles),
                "max_plates": int(args.max_plates),
                "border_mm": float(args.border_mm),
                "border_rings": int(args.border_rings),
                "bottom_stripes": bool(not args.no_bottom_stripes),
            },
            "stl": stl_paths,
            "tiles": tiles_meta,
        }

        meta_path = os.path.join(args.outdir, f"{args.name}_p{plate_index+1:02d}_recipes.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] 已写入: {meta_path}")

        plates_meta.append(
            {
                "plate_index": int(plate_index),
                "recipes_json": os.path.abspath(meta_path),
                "stl": stl_paths,
                "tile_count": len(tiles_meta),
            }
        )

    # 写入运行摘要 JSON（生成多块板时有用）
    run_meta = {
        "schema_version": 1,
        "script": os.path.basename(__file__),
        "name": str(args.name),
        "outdir": os.path.abspath(args.outdir),
        "plates": plates_meta,
        "totals": {
            "materials": int(K),
            "plates_generated": int(len(plates_meta)),
            "tiles_generated": int(global_tile_id),
        },
    }
    run_meta_path = os.path.join(args.outdir, f"{args.name}_run.json")
    with open(run_meta_path, "w", encoding="utf-8") as f:
        json.dump(run_meta, f, ensure_ascii=False, indent=2)
    logger.info(f"[OK] 已写入: {run_meta_path}")

    logger.info("\n摘要:")
    logger.info(f"  材料数={K} ({', '.join(mats)})")
    logger.info(f"  模式={args.mode}  排序={args.ordering}  板数={len(plates_meta)}")
    logger.info(f"  网格={nx}x{ny}  瓦片={tile_mm}mm  间隙={gap}mm  网格尺寸={grid_w:.2f}x{grid_h:.2f}mm")
    logger.info(f"  层数={L}  高度=[{h0}] + [{h}]*(L-1)  总厚度={sum(heights_mm):.3f}mm")
    logger.info(f"  生成瓦片数={global_tile_id}")


if __name__ == "__main__":
    main()
