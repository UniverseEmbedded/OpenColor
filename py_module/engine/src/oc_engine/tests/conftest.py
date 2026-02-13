"""
pytest 配置文件

提供测试所需的fixtures和配置
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_board_spec() -> dict:
    """提供标准测试用的色盘规格数据

    Returns:
        包含8色配置的规格文件字典
    """
    slot_names = [
        "White", "Black", "Red", "Green",
        "Blue", "Cyan", "Magenta", "Yellow"
    ]
    cell_map = {}
    n_layers = 5
    idx = 0

    for r in range(1, 5):  # 4x4数据区域
        for c in range(1, 5):
            cell_map[f"{r},{c}"] = {
                "recipe_index": idx,
                "layers": [idx % 8] * n_layers,
                "slot_names": slot_names,
            }
            idx += 1

    return {
        "name": "Sample_Test_Board",
        "rows": 6,
        "cols": 6,
        "cell_size_mm": 4.0,
        "cell_map": cell_map,
        "markers": {
            "TL": [0, 0],
            "TR": [5, 0],
            "BR": [5, 5],
            "BL": [0, 5],
        },
    }


@pytest.fixture
def sample_spec_file(tmp_path: Path, sample_board_spec: dict) -> Path:
    """创建临时规格文件

    Args:
        tmp_path: pytest提供的临时路径
        sample_board_spec: 规格数据

    Returns:
        规格文件路径
    """
    spec_path = tmp_path / "sample_board_spec.json"
    spec_path.write_text(json.dumps(sample_board_spec), encoding="utf-8")
    return spec_path


@pytest.fixture
def color_profiles() -> dict:
    """提供测试用的颜色配置

    Returns:
        不同颜色数量的配置字典
    """
    return {
        "3color": ["Red", "Green", "Blue"],
        "4color": ["Red", "Green", "Blue", "White"],
        "5color": ["Red", "Green", "Blue", "White", "Black"],
        "8color": [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ],
    }
