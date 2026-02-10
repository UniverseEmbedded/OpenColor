from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any

from .board_spec import BoardSpec
from .observation import Observation


@dataclass
class CalibrationDataset:
    """汇总数据集 (Calibration Dataset)"""
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    boards: Dict[str, BoardSpec] = field(default_factory=dict) # board_id -> BoardSpec
    observations: List[Observation] = field(default_factory=list)
    
    # 汇总后的结果: cell_id -> {mean_rgb, median_rgb, std_rgb, count, ...}
    # 注意：这里的 cell_id 需要能够区分不同板子的相同 recipe，或者合并相同 recipe 的不同 cell
    # 简单起见，这里存储按 recipe 汇总的结果，或者按 cell_id 存储
    aggregated_results: Dict[str, Any] = field(default_factory=dict)

    def add_board(self, board: BoardSpec):
        self.boards[board.board_id] = board

    def add_observation(self, obs: Observation):
        self.observations.append(obs)

    def to_json(self) -> str:
        # 自定义序列化，因为 boards 和 observations 可能是对象
        data = {
            "dataset_id": self.dataset_id,
            "boards": {bid: b.__dict__ for bid, b in self.boards.items()},
            "observations": [o.__dict__ for o in self.observations],
            "aggregated_results": self.aggregated_results
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def save(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "calibration_dataset.json", 'w', encoding='utf-8') as f:
            f.write(self.to_json())
            
        # 还可以保存一个 summary.md
        self.generate_summary(output_dir / "dataset_summary.md")

    def generate_summary(self, path: Path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Calibration Dataset Summary\n\n")
            f.write(f"- Dataset ID: {self.dataset_id}\n")
            f.write(f"- Number of Boards: {len(self.boards)}\n")
            f.write(f"- Number of Observations: {len(self.observations)}\n\n")
            
            f.write(f"## Boards\n")
            for bid, b in self.boards.items():
                f.write(f"- {b.name} ({bid}): {b.rows}x{b.cols}\n")
            
            f.write(f"\n## Observations\n")
            for i, obs in enumerate(self.observations):
                f.write(f"{i+1}. Board: {obs.board_id}, Photo: {obs.photo_path}, Cells measured: {len(obs.cell_measurements)}\n")
