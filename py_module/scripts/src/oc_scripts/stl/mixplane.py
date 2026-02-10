#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mixplane.py - 平面离散层叠混合卡片（4个STL）

两种模式：
1) 组合：所有 (a,b,c,d) 非负整数且 a+b+c+d=层数
   数量 = C(层数+3,3)。当层数=5时 -> 56个瓦片。
   瓦片内堆叠顺序固定：A(底部)->B->C->D(顶部)

2) 序列：所有长度为'层数'的{A,B,C,D}序列
   数量 = 4^层数。当层数=5时 -> 1024个瓦片。
   瓦片内堆叠顺序遵循序列 底部->顶部

瓦片是连续的（无间隙）

输出：
  outdir/<name>_A.stl ... <name>_D.stl

依赖：numpy, trimesh
"""

from __future__ import annotations

import argparse
import json
import math
import os
from typing import List, Tuple

import numpy as np
import trimesh



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def add_mesh_accum(verts_acc: List[np.ndarray], faces_acc: List[np.ndarray], v: np.ndarray, f: np.ndarray) -> None:
    if len(v) == 0 or len(f) == 0:
        return
    offset = 0
    if verts_acc:
        offset = sum(len(x) for x in verts_acc)
    verts_acc.append(v)
    faces_acc.append(f + offset)


def prism(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Tuple[np.ndarray, np.ndarray]:
    v = np.array(
        [
            [x0, y0, z0],
            [x1, y0, z0],
            [x1, y1, z0],
            [x0, y1, z0],
            [x0, y0, z1],
            [x1, y0, z1],
            [x1, y1, z1],
            [x0, y1, z1],
        ],
        dtype=float,
    )
    f = np.array(
        [
            [0, 1, 2], [0, 2, 3],  # 底面
            [4, 6, 5], [4, 7, 6],  # 顶面
            [0, 4, 5], [0, 5, 1],  # y0
            [1, 5, 6], [1, 6, 2],  # x1
            [2, 6, 7], [2, 7, 3],  # y1
            [3, 7, 4], [3, 4, 0],  # x0
        ],
        dtype=np.int64,
    )
    return v, f


def compositions_4(n: int) -> List[Tuple[int, int, int, int]]:
    """所有非负整数元组 (a,b,c,d) 满足 a+b+c+d=n"""
    n = int(n)
    out: List[Tuple[int, int, int, int]] = []
    for a in range(n, -1, -1):
        for b in range(n - a, -1, -1):
            for c in range(n - a - b, -1, -1):
                d = n - a - b - c
                out.append((a, b, c, d))
    return out


def sequence_index_to_digits(base: int, length: int, idx: int) -> List[int]:
    """
    idx 在 [0, base^length) 范围内
    返回字典序的数字（长度）（最高位在前）
    数字在 [0..base-1] 范围内
    """
    digits = [0] * length
    x = idx
    for pos in range(length - 1, -1, -1):
        digits[pos] = x % base
        x //= base
    return digits


def main() -> None:
    ap = argparse.ArgumentParser(description="生成离散层叠平面混合卡片（4个STL）")
    ap.add_argument("--outdir", default="out_stl", help="输出目录")
    ap.add_argument("--name", default="mixplane", help="STL文件基础名称")

    ap.add_argument("--mode", choices=["composition", "sequence"], default="composition", help="混合枚举模式")
    ap.add_argument("--layers", type=int, default=5, help="每瓦片总离散层数（如5）")
    ap.add_argument("--layer-height", type=float, default=0.08, help="每离散层高度（毫米）（第一层除外）")
    ap.add_argument("--first-layer-height", type=float, default=0.12, help="第一层高度（毫米）（风险：可能隐藏薄细节）")
    ap.add_argument("--view", default="top", choices=["top", "bottom"])
    ap.add_argument("--backing", default="white", choices=["white", "black"])

    ap.add_argument("--tile", type=float, default=10.0, help="瓦片尺寸（毫米）。瓦片连续无间隙")
    ap.add_argument("--nx", type=int, default=0, help="每行瓦片数。0 = 自动（近似方形）")

    ap.add_argument("--material-names", default="A,B,C,D", help="逗号分隔的4个STL后缀名称")
    ap.add_argument("--validate", action="store_true", help="运行trimesh清理（较慢）")
    ap.add_argument("--export-metadata", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    mat_names = [x.strip() for x in args.material_names.split(",")]
    if len(mat_names) != 4:
        raise ValueError("--material-names 必须是恰好4个名称，如 A,B,C,D")

    L = max(1, int(args.layers))
    h = float(args.layer_height)
    h0 = float(args.first_layer_height)
    if h <= 0 or h0 <= 0:
        raise ValueError("层高度必须 > 0")

    layer_heights = [h0] + [h] * (L - 1)

    tile = float(args.tile)
    if tile <= 0:
        raise ValueError("--tile 必须 > 0")

    if args.mode == "composition":
        combos = compositions_4(L)
        total = len(combos)  # C(L+3,3)
    else:
        total = 4 ** L

    # nx 自动：目标接近方形网格
    if int(args.nx) <= 0:
        nx = int(math.ceil(math.sqrt(total)))
    else:
        nx = int(args.nx)
    nx = max(1, nx)
    ny = int(math.ceil(total / nx))

    total_thickness = sum(layer_heights)

    # 将整个卡片居中于原点
    size_x = nx * tile
    size_y = ny * tile
    x0_card = -size_x / 2.0
    y0_card = -size_y / 2.0

    all_verts: List[List[np.ndarray]] = [[], [], [], []]
    all_faces: List[List[np.ndarray]] = [[], [], [], []]

    tiles_meta = []

    if args.mode == "composition":
        for idx, (a, b, c, d) in enumerate(combos):
            ix = idx % nx
            iy = idx // nx

            x0 = x0_card + ix * tile
            x1 = x0 + tile
            y0 = y0_card + iy * tile
            y1 = y0 + tile

            counts = [int(a), int(b), int(c), int(d)]
            seq_digits: List[int] = []
            for mi in range(4):
                seq_digits.extend([mi] * int(counts[mi]))
            if len(seq_digits) != L:
                raise RuntimeError("内部错误：组合之和不等于层数")

            z = 0.0
            last_mi = None
            z0 = 0.0
            for layer_i, mi in enumerate(seq_digits):
                if last_mi is None:
                    last_mi = mi
                    z0 = 0.0

                z += float(layer_heights[layer_i])
                if layer_i == L - 1 or seq_digits[layer_i + 1] != mi:
                    v, f = prism(x0, x1, y0, y1, z0, z)
                    add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
                    z0 = z
                    last_mi = None

            tiles_meta.append(
                {
                    "tile_id": int(idx),
                    "ix": int(ix),
                    "iy": int(iy),
                    "counts": {mat_names[i]: int(counts[i]) for i in range(4)},
                    "seq": [mat_names[i] for i in seq_digits],
                    "heights_mm": [float(x) for x in layer_heights],
                    "view": str(args.view),
                    "backing": str(args.backing),
                }
            )
    else:
        # 序列模式：每层L选择一个材料；顺序重要
        for idx in range(total):
            ix = idx % nx
            iy = idx // nx

            x0 = x0_card + ix * tile
            x1 = x0 + tile
            y0 = y0_card + iy * tile
            y1 = y0 + tile

            seq_digits = sequence_index_to_digits(base=4, length=L, idx=idx)  # 每个在 0..3
            z = 0.0
            last_mi = None
            z0 = 0.0
            for layer_i, mi in enumerate(seq_digits):
                if last_mi is None:
                    last_mi = mi
                    z0 = z

                z += float(layer_heights[layer_i])
                if layer_i == L - 1 or seq_digits[layer_i + 1] != mi:
                    v, f = prism(x0, x1, y0, y1, z0, z)
                    add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
                    z0 = z
                    last_mi = None

            tiles_meta.append(
                {
                    "tile_id": int(idx),
                    "ix": int(ix),
                    "iy": int(iy),
                    "seq": [mat_names[i] for i in seq_digits],
                    "heights_mm": [float(x) for x in layer_heights],
                    "view": str(args.view),
                    "backing": str(args.backing),
                }
            )

    for mi in range(4):
        if not all_verts[mi]:
            logger.warning(f"[警告] 材料 {mat_names[mi]} 为空；跳过。")
            continue
        V = np.vstack(all_verts[mi])
        F = np.vstack(all_faces[mi])
        mesh = trimesh.Trimesh(vertices=V, faces=F, process=False)
        if args.validate:
            mesh.remove_duplicate_faces()
            mesh.remove_degenerate_faces()
            mesh.merge_vertices()
            mesh.fix_normals()
        outpath = os.path.join(args.outdir, f"{args.name}_{mat_names[mi]}.stl")
        mesh.export(outpath)
        logger.info(f"[OK] 已写入: {outpath} (顶点={len(mesh.vertices)}, 面={len(mesh.faces)})")

    if args.export_metadata:
        meta = {
            "schema_version": 1,
            "script": os.path.basename(__file__),
            "params": {
                "mode": str(args.mode),
                "layers": int(L),
                "first_layer_height_mm": float(h0),
                "layer_height_mm": float(h),
                "tile_mm": float(tile),
                "grid_nx": int(nx),
                "grid_ny": int(ny),
                "view": str(args.view),
                "backing": str(args.backing),
                "material_names": list(mat_names),
            },
            "tiles": tiles_meta,
        }
        meta_path = os.path.join(args.outdir, f"{args.name}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        logger.info(f"元数据: 已写入 {meta_path}")

    logger.info("\n摘要:")
    logger.info(f"  模式={args.mode}")
    logger.info(f"  层数={L}, 第一层高度={h0} 毫米, 层高度={h} 毫米, 瓦片厚度={total_thickness} 毫米")
    if args.mode == "composition":
        logger.info(f"  瓦片数 = C(层数+3,3) = {total}")
        logger.info("  每瓦片堆叠顺序: A(底部)->B->C->D(顶部)")
    else:
        logger.info(f"  瓦片数 = 4^层数 = {total}")
        logger.info("  每瓦片堆叠顺序遵循序列 底部->顶部")
    logger.info(f"  网格 = {nx} x {ny}, 瓦片 = {tile} 毫米, 无间隙")


if __name__ == "__main__":
    main()
