#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def add_mesh_accum(
    verts_acc: List[np.ndarray],
    faces_acc: List[np.ndarray],
    v: np.ndarray,
    f: np.ndarray,
) -> None:
    """累积添加网格数据，自动处理顶点偏移"""
    if v.size == 0 or f.size == 0:
        return
    offset = 0
    if verts_acc:
        offset = sum(len(x) for x in verts_acc)
    verts_acc.append(v)
    faces_acc.append(f + offset)


def prism(
    x0: float, x1: float, y0: float, y1: float, z0: float, z1: float
) -> Tuple[np.ndarray, np.ndarray]:
    """创建一个棱柱体（长方体）的顶点和面

    Args:
        x0, x1: X 轴范围
        y0, y1: Y 轴范围
        z0, z1: Z 轴范围

    Returns:
        (顶点数组, 面数组)
    """
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
            [0, 1, 2],
            [0, 2, 3],  # 底面
            [4, 6, 5],
            [4, 7, 6],  # 顶面
            [0, 4, 5],
            [0, 5, 1],  # 侧面
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ],
        dtype=np.int64,
    )
    return v, f


def row_stripe_material_index(iy: int, K: int) -> int:
    """根据行号计算条纹材料索引"""
    if K <= 0:
        return 0
    return int(iy) % int(K)


def add_border_ring(
    all_verts: List[List[np.ndarray]],
    all_faces: List[List[np.ndarray]],
    *,
    mat_index: int,
    x0o: float,
    x1o: float,
    y0o: float,
    y1o: float,
    x0i: float,
    x1i: float,
    y0i: float,
    y1i: float,
    z0: float,
    z1: float,
) -> None:
    """添加边框环状结构"""
    if y0i > y0o:
        v, f = prism(x0o, x1o, y0o, y0i, z0, z1)
        add_mesh_accum(all_verts[mat_index], all_faces[mat_index], v, f)
    if y1o > y1i:
        v, f = prism(x0o, x1o, y1i, y1o, z0, z1)
        add_mesh_accum(all_verts[mat_index], all_faces[mat_index], v, f)
    if x0i > x0o and y1i > y0i:
        v, f = prism(x0o, x0i, y0i, y1i, z0, z1)
        add_mesh_accum(all_verts[mat_index], all_faces[mat_index], v, f)
    if x1o > x1i and y1i > y0i:
        v, f = prism(x1i, x1o, y0i, y1i, z0, z1)
        add_mesh_accum(all_verts[mat_index], all_faces[mat_index], v, f)


def add_border_rings_for_layer(
    all_verts: List[List[np.ndarray]],
    all_faces: List[List[np.ndarray]],
    *,
    mats_count: int,
    layer_index: int,
    border_mm: float,
    rings: int,
    x0_inner: float,
    x1_inner: float,
    y0_inner: float,
    y1_inner: float,
    z0: float,
    z1: float,
) -> None:
    """为层添加多个边框环"""
    if border_mm <= 0:
        return
    rings = max(1, int(rings))
    ring_w = float(border_mm) / float(rings)

    for r in range(rings):
        x0o = x0_inner - border_mm + r * ring_w
        x1o = x1_inner + border_mm - r * ring_w
        y0o = y0_inner - border_mm + r * ring_w
        y1o = y1_inner + border_mm - r * ring_w
        x0i = x0o + ring_w
        x1i = x1o - ring_w
        y0i = y0o + ring_w
        y1i = y1o - ring_w
        if x1i <= x0i or y1i <= y0i:
            continue

        mi = (int(layer_index) + int(r)) % int(mats_count)
        add_border_ring(
            all_verts,
            all_faces,
            mat_index=mi,
            x0o=x0o,
            x1o=x1o,
            y0o=y0o,
            y1o=y1o,
            x0i=x0i,
            x1i=x1i,
            y0i=y0i,
            y1i=y1i,
            z0=z0,
            z1=z1,
        )


def add_first_layer_border_segments(
    all_verts: List[List[np.ndarray]],
    all_faces: List[List[np.ndarray]],
    *,
    mats_count: int,
    border_mm: float,
    x0_inner: float,
    x1_inner: float,
    y0_inner: float,
    y1_inner: float,
    pitch: float,
    tile_mm: float,
    gap: float,
    ny: int,
    z0: float,
    z1: float,
) -> None:
    """添加第一层边框分段"""
    if border_mm <= 0:
        return

    mi_bottom = row_stripe_material_index(0, mats_count)
    mi_top = row_stripe_material_index(max(0, ny - 1), mats_count)

    v, f = prism(
        x0_inner - border_mm,
        x1_inner + border_mm,
        y0_inner - border_mm,
        y0_inner,
        z0,
        z1,
    )
    add_mesh_accum(all_verts[mi_bottom], all_faces[mi_bottom], v, f)

    v, f = prism(
        x0_inner - border_mm,
        x1_inner + border_mm,
        y1_inner,
        y1_inner + border_mm,
        z0,
        z1,
    )
    add_mesh_accum(all_verts[mi_top], all_faces[mi_top], v, f)

    for iy in range(int(ny)):
        mi = row_stripe_material_index(iy, mats_count)
        y0 = y0_inner + iy * pitch
        y1 = y0 + tile_mm
        if iy < ny - 1:
            y1 = y0 + tile_mm + gap
        else:
            y1 = y1_inner

        v, f = prism(x0_inner - border_mm, x0_inner, y0, y1, z0, z1)
        add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
        v, f = prism(x1_inner, x1_inner + border_mm, y0, y1, z0, z1)
        add_mesh_accum(all_verts[mi], all_faces[mi], v, f)


def add_bottom_stripes(
    all_verts: List[List[np.ndarray]],
    all_faces: List[List[np.ndarray]],
    *,
    mats_count: int,
    x0_inner: float,
    x1_inner: float,
    y0_inner: float,
    y1_inner: float,
    pitch: float,
    tile_mm: float,
    gap: float,
    ny: int,
    z0: float,
    z1: float,
) -> None:
    """添加底部条纹"""
    for iy in range(int(ny)):
        mi = row_stripe_material_index(iy, mats_count)
        ys = y0_inner + iy * pitch
        if iy < ny - 1:
            ye = ys + tile_mm + gap
        else:
            ye = y1_inner
        if ye <= ys:
            continue
        v, f = prism(x0_inner, x1_inner, ys, ye, z0, z1)
        add_mesh_accum(all_verts[mi], all_faces[mi], v, f)
