from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Any


@dataclass
class Observation:
    """单张照片的分析结果 (Observation)"""

    board_id: str  # 指向 BoardSpec
    photo_id: str
    photo_path: str

    # 用户手调的四角点 (归一化或像素坐标，取决于实现，LBT 目前是像素坐标)
    warp_corners: List[Tuple[float, float]]

    # 算法参数 (zoom, barrel, offset 等)
    warp_params: Dict[str, Any] = field(default_factory=dict)

    # cell_id -> {rgb: [r,g,b], lab: [l,a,b], confidence: 0..1, quality_flags: []}
    cell_measurements: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 诊断信息
    diagnostics: Dict[str, str] = field(
        default_factory=dict
    )  # warp_img_path, overlay_img_path 等

    timestamp: float = field(default_factory=lambda: 0.0)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> Observation:
        d = json.loads(data)
        return cls(**d)

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
