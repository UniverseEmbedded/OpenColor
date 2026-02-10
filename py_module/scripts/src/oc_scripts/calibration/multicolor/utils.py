#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import List
import trimesh

def clean_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """清理 Trimesh 网格，合并顶点、去除重复面和退化面、删除未引用顶点。"""
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    return mesh

def parse_materials(s: str) -> List[str]:
    """解析逗号分隔的耗材名称字符串，去重并保持原始顺序。
    
    要求至少提供 4 种不同的耗材名称，例如 "R,G,B,W"。
    """
    mats = [x.strip() for x in s.split(",") if x.strip()]
    if len(mats) < 4:
        raise ValueError("至少需要 4 种耗材，例如 R,G,B,W")
    # 去重并保持顺序
    seen = set()
    out = []
    for m in mats:
        if m in seen:
            continue
        seen.add(m)
        out.append(m)
    if len(out) < 4:
        raise ValueError("至少需要 4 种唯一的耗材名称")
    return out
