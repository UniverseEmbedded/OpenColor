"""
数据集IO模块(XGBoost版本)
加载calib_sample_build生成的dataset_cells.json文件
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Cell:
    """
    数据集单元格数据类
    
    属性:
        row: 行索引
        col: 列索引
        enabled: 是否启用
        has_recipe: 是否有配方
        recipe: 配方字典，键为颜色名称，值为用量比例
        measured_rgb: 测量得到的RGB值，None表示未测量
        target_rgb: 目标RGB值，None表示无目标
    """
    row: int
    col: int
    enabled: bool
    has_recipe: bool
    recipe: Dict[str, float]
    measured_rgb: Optional[Tuple[int, int, int]]
    target_rgb: Optional[Tuple[int, int, int]]


def _to_rgb_tuple(x: Any) -> Optional[Tuple[int, int, int]]:
    """
    将输入转换为RGB元组
    
    参数:
        x: 输入数据，可以是列表、元组或None
        
    返回:
        RGB元组(r, g, b)或None
    """
    if x is None:
        return None
    if isinstance(x, (list, tuple)) and len(x) == 3:
        try:
            r, g, b = int(x[0]), int(x[1]), int(x[2])
            return (r, g, b)
        except Exception:
            return None
    return None


def _to_recipe_dict(x: Any) -> Dict[str, float]:
    """
    将输入转换为配方字典
    
    参数:
        x: 输入数据，应为字典类型
        
    返回:
        键为字符串、值为浮点数的配方字典
    """
    if not isinstance(x, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in x.items():
        try:
            out[str(k)] = float(v)
        except Exception:
            continue
    return out


def load_dataset_cells(dataset_path: Path) -> List[Cell]:
    """
    加载由calib_sample_build生成的dataset_cells.json文件
    
    参数:
        dataset_path: dataset_cells.json文件的路径
        
    返回:
        Cell对象列表
        
    异常:
        ValueError: 当JSON文件中'cells'键对应的值不是列表时抛出
    """
    data = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    cells_in = data.get("cells", data.get("dataset_cells", data))
    if not isinstance(cells_in, list):
        raise ValueError("dataset_cells.json: expected a list under key 'cells'")
    cells: List[Cell] = []
    for c in cells_in:
        if not isinstance(c, dict):
            continue
        row = int(c.get("row", c.get("r", 0)))
        col = int(c.get("col", c.get("c", 0)))
        enabled = bool(c.get("enabled", False))
        has_recipe = bool(c.get("has_recipe", bool(c.get("recipe"))))
        recipe = _to_recipe_dict(c.get("recipe"))
        measured_rgb = _to_rgb_tuple(c.get("measured_rgb"))
        target_rgb = _to_rgb_tuple(c.get("target_rgb"))
        cells.append(Cell(row=row, col=col, enabled=enabled, has_recipe=has_recipe, recipe=recipe, measured_rgb=measured_rgb, target_rgb=target_rgb))
    return cells
