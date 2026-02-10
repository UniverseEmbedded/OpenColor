from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class AprilTagSpec:
    tag_id: int
    size_mm: float
    board_corners_mm: List[List[float]]  # [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]

@dataclass
class BoardSpec:
    """色盘定义（Board Specification）"""
    board_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unknown Board"
    rows: int = 34
    cols: int = 34
    cell_size_mm: float = 0.42
    border_mm: float = 0.0  # 暂时保留，可能由 layout 决定
    
    # AprilTag 配置
    apriltag: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "families": ["tag36h11"],
        "primary": None,
        "secondary": None,
    })
    
    # 关键点定义，例如四角点 {"TL": [0,0], "TR": [33,0], ...}
    markers: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        "TL": (0, 0),
        "TR": (33, 0),
        "BR": (33, 33),
        "BL": (0, 33)
    })
    
    # cell_id -> recipe_info (例如 {"layers": [0,1,2,3,0]})
    # 显式映射表，不依赖推导
    cell_map: Dict[str, Any] = field(default_factory=dict)
    
    # 打印配置信息
    print_profile: Dict[str, Any] = field(default_factory=dict)
    
    def cell_id_at(self, r: int, c: int) -> Optional[str]:
        """获取指定行列的 cell_id"""
        # 默认实现：如果 cell_map 里有 "r,c" 这种 key，则返回
        key = f"{r},{c}"
        if key in self.cell_map:
            return key
        return None

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> BoardSpec:
        d = json.loads(data)
        return cls(**d)

    def save(self, path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: Path) -> BoardSpec:
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())

def create_legacy_32x32_spec(color_system: str = "RYBW", n_layers: int = 5) -> BoardSpec:
    """创建一个兼容旧版 32x32 (total 34x34) 的 BoardSpec"""
    from oc_core_02.core.recipes import int_to_recipe
    
    spec = BoardSpec(
        name=f"Legacy 32x32 ({color_system}, {n_layers} layers)",
        rows=34,
        cols=34,
        cell_size_mm=0.42,
        markers={
            "TL": (0, 0),
            "TR": (33, 0),
            "BR": (33, 33),
            "BL": (0, 33)
        }
    )
    
    # 填充 32x32 数据区
    for r in range(1, 33):
        for c in range(1, 33):
            idx = (r - 1) * 32 + (c - 1)
            recipe = int_to_recipe(idx, n_layers)
            spec.cell_map[f"{r},{c}"] = {
                "recipe_index": idx,
                "layers": recipe.layers
            }
            
    return spec
