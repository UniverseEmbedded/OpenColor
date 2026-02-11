"""
数据集IO模块
加载和处理数据集文件，提供Cell和Dataset数据类
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class Cell:
    row: int
    col: int
    enabled: bool
    recipe: dict[str, float]
    measured_rgb: np.ndarray  # uint8 RGB
    target_rgb: np.ndarray | None
    layer_names: list[str] = None
    palette_id: str = "unknown"


@dataclass
class Dataset:
    rows: int
    cols: int
    spec_path: Path | None
    cells: list[Cell]
    palette_id: str = "unknown"
    # 黑白校准参数
    black_offset: float = 0.0  # 黑场偏移量（0-255范围）
    white_offset: float = 0.0  # 白场偏移量（0-255范围）


def apply_bw_calibration_forward(
    rgb: np.ndarray, black_offset: float, white_offset: float
) -> np.ndarray:
    """
    应用黑白校准的正向映射（输入前）

    将原始RGB值映射到模型输入空间：
    - 黑色的0映射到black_offset
    - 白色的255映射到(255 - white_offset)

    Args:
        rgb: 原始RGB值 (0-255范围)
        black_offset: 黑场偏移量（例如32表示黑色映射到32）
        white_offset: 白场偏移量（例如32表示白色映射到223）

    Returns:
        映射后的RGB值
    """
    if black_offset == 0 and white_offset == 0:
        return rgb

    rgb_float = rgb.astype(np.float32)
    # 线性映射：将[0, 255]映射到[black_offset, 255-white_offset]
    scale = (255.0 - white_offset - black_offset) / 255.0
    mapped = rgb_float * scale + black_offset
    return np.clip(mapped, 0, 255).astype(rgb.dtype)


def apply_bw_calibration_inverse(
    rgb: np.ndarray, black_offset: float, white_offset: float
) -> np.ndarray:
    """
    应用黑白校准的逆向映射（输出后）

    将模型输出映射回原始RGB空间：
    - 将[black_offset, 255-white_offset]映射回[0, 255]

    Args:
        rgb: 模型输出的RGB值 (0-255范围)
        black_offset: 黑场偏移量
        white_offset: 白场偏移量

    Returns:
        逆向映射后的RGB值
    """
    if black_offset == 0 and white_offset == 0:
        return rgb

    rgb_float = rgb.astype(np.float32)
    # 逆向线性映射
    scale = 255.0 / (255.0 - white_offset - black_offset)
    mapped = (rgb_float - black_offset) * scale
    return np.clip(mapped, 0, 255).astype(rgb.dtype)


def load_dataset(
    path: Path,
    palette_id: str | None = None,
    black_offset: float = 0.0,
    white_offset: float = 0.0,
    apply_calibration: bool = True,
) -> Dataset:
    """
    加载数据集

    Args:
        path: 数据集文件路径
        palette_id: 色盘ID（可选）
        black_offset: 黑场偏移量（0-255范围）
        white_offset: 白场偏移量（0-255范围）
        apply_calibration: 是否应用黑白校准映射
    """
    ds = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    rows = int(ds.get("rows", 0))
    cols = int(ds.get("cols", 0))
    spec_path = Path(ds["spec_path"]) if ds.get("spec_path") else None

    # 优先使用传入的 palette_id，否则从 json 中读取，最后默认为 unknown
    ds_palette_id = palette_id or ds.get("palette_id") or "unknown"

    cells_in: list[dict[str, Any]] = ds.get("cells", [])

    cells: list[Cell] = []
    for c in cells_in:
        try:
            row = int(c.get("row"))
            col = int(c.get("col"))
        except Exception:
            continue
        enabled = bool(c.get("enabled", True))
        rec: dict[str, float] = {}
        raw_rec = c.get("recipe") or {}
        if isinstance(raw_rec, dict):
            for k, v in raw_rec.items():
                try:
                    rec[str(k)] = float(v)
                except Exception:
                    continue
        measured = np.array(c.get("measured_rgb", [0, 0, 0]), dtype=np.uint8)

        # 应用黑白校准正向映射（输入前）
        if apply_calibration and (black_offset > 0 or white_offset > 0):
            measured = apply_bw_calibration_forward(
                measured, black_offset, white_offset
            )

        tgt = c.get("target_rgb")
        target = None
        if (
            isinstance(tgt, (list, tuple))
            and len(tgt) == 3
            and all(t is not None for t in tgt)
        ):
            try:
                target = np.array(tgt, dtype=np.uint8)
                # 对target也应用相同的校准
                if apply_calibration and (black_offset > 0 or white_offset > 0):
                    target = apply_bw_calibration_forward(
                        target, black_offset, white_offset
                    )
            except Exception:
                target = None

        layer_names = c.get("layer_names")
        if not isinstance(layer_names, list):
            layer_names = []

        # cell 的 palette_id 优先使用 cell 自身的，否则使用 dataset 的
        c_palette_id = c.get("palette_id") or ds_palette_id

        cells.append(
            Cell(
                row=row,
                col=col,
                enabled=enabled,
                recipe=rec,
                measured_rgb=measured,
                target_rgb=target,
                layer_names=layer_names,
                palette_id=c_palette_id,
            )
        )

    return Dataset(
        rows=rows,
        cols=cols,
        spec_path=spec_path,
        cells=cells,
        palette_id=ds_palette_id,
        black_offset=black_offset,
        white_offset=white_offset,
    )


def infer_material_keys(cells: list[Cell]) -> list[str]:
    mats: set[str] = set()
    for c in cells:
        for k, v in c.recipe.items():
            # only numeric
            try:
                float(v)
            except Exception:
                continue
            mats.add(k)
    return sorted(mats)


def build_features(cells: list[Cell], material_keys: list[str]) -> np.ndarray:
    """X features: raw amounts + a few simple aggregates."""
    X = np.zeros((len(cells), len(material_keys) + 3), dtype=np.float32)
    # columns: [mat0..matN-1, sum, max, nnz]
    for i, c in enumerate(cells):
        vals = []
        for j, k in enumerate(material_keys):
            v = float(c.recipe.get(k, 0.0))
            X[i, j] = v
            vals.append(v)
        s = float(sum(vals))
        mx = float(max(vals) if vals else 0.0)
        nnz = float(sum(1 for v in vals if abs(v) > 1e-9))
        X[i, len(material_keys) + 0] = s
        X[i, len(material_keys) + 1] = mx
        X[i, len(material_keys) + 2] = nnz
    return X


def filter_training_cells(ds: Dataset) -> list[Cell]:
    """Use enabled cells with non-empty recipe."""
    out: list[Cell] = []
    for c in ds.cells:
        if not c.enabled:
            continue
        if not c.recipe:
            continue
        out.append(c)
    return out
