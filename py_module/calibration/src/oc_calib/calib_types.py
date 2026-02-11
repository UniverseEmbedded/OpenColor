from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Any


@dataclass
class Observation:
    """单张照片的分析结果 (Observation)"""

    board_id: str  # 指向 BoardSpec
    photo_id: str
    photo_path: str

    # 用户手调的四角点
    warp_corners: List[Tuple[float, float]]

    # 算法参数
    warp_params: Dict[str, Any] = field(default_factory=dict)

    # cell_id -> {rgb: [r,g,b], ...}
    cell_measurements: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 诊断信息
    diagnostics: Dict[str, str] = field(default_factory=dict)

    timestamp: float = field(default_factory=lambda: 0.0)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> Observation:
        d = json.loads(data)
        return cls(**d)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: Path) -> Observation:
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())
