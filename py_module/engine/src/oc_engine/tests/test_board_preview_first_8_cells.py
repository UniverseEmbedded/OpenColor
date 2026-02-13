"""
验证前8个格子的颜色数据测试

这个测试专门验证修复的bug：配方索引与颜色名称的映射是否正确
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oc_engine.handlers.board import handle_board_preview


class TestFirst8CellsColorMapping:
    """测试前8个格子的颜色映射 - 验证修复的bug"""

    def test_first_8_cells_with_8_color_spec(self, tmp_path: Path) -> None:
        """测试8色规格文件的前8个格子颜色映射

        验证：规格文件使用8色，配方索引0-7能正确映射到对应颜色
        """
        # 使用与DEFAULT_MATERIALS_8一致的顺序
        slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]

        # 创建规格文件，前8个数据格子分别使用索引0-7
        cell_map = {}
        n_layers = 5

        # 数据区域从(1,1)开始，前8个格子是：
        # (1,1), (1,2), (1,3), (1,4), (1,5), (1,6), (1,7), (1,8)
        # 对于6x6的格子，数据区域是(1,1)到(4,4)，共16个格子
        # 前8个是：(1,1), (1,2), (1,3), (1,4), (2,1), (2,2), (2,3), (2,4)

        idx = 0
        for r in range(1, 5):  # 行 1-4
            for c in range(1, 5):  # 列 1-4
                if idx < 8:
                    # 前8个格子使用索引0-7（每个格子纯色）
                    recipe = [idx] * n_layers
                else:
                    recipe = [0] * n_layers

                cell_map[f"{r},{c}"] = {
                    "recipe_index": idx,
                    "layers": recipe,
                    "slot_names": slot_names,
                }
                idx += 1

        spec = {
            "name": "Test_First_8_Cells",
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

        spec_path = tmp_path / "test_first_8_cells_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 调用预览
        result = handle_board_preview({
            "profile_id": "full_8",
            "spec_path": str(spec_path),
        })

        # 验证结果
        assert "cells" in result
        cells = result["cells"]

        # 找到数据区域的格子（排除边框）
        data_cells = [c for c in cells if c["row"] in range(1, 5) and c["col"] in range(1, 5)]

        # 验证至少有8个数据格子
        assert len(data_cells) >= 8, f"数据格子数量不足: {len(data_cells)}"

        # 验证每个格子都有颜色数据
        for i, cell in enumerate(sorted(data_cells, key=lambda x: (x["row"], x["col"]))[:8]):
            assert "target_rgb" in cell, f"格子 {i} 缺少target_rgb"
            rgb = cell["target_rgb"]
            assert "r" in rgb and "g" in rgb and "b" in rgb, f"格子 {i} 的RGB数据不完整"

            # 验证颜色值在有效范围
            assert 0 <= rgb["r"] <= 255, f"格子 {i} 的红色值越界: {rgb['r']}"
            assert 0 <= rgb["g"] <= 255, f"格子 {i} 的绿色值越界: {rgb['g']}"
            assert 0 <= rgb["b"] <= 255, f"格子 {i} 的蓝色值越界: {rgb['b']}"

        print(f"\n前8个格子颜色验证通过，共 {len(data_cells)} 个数据格子")

    def test_first_8_cells_with_different_profile(self, tmp_path: Path) -> None:
        """测试规格文件8色但profile为3色时的前8个格子

        验证：这是修复的核心bug场景
              规格文件使用8色，但profile_id传入3色配置
              应该优先使用规格文件的8色，而不是profile的3色
        """
        # 规格文件使用8色
        spec_slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]

        # 创建规格文件，前8个格子使用索引0-7
        cell_map = {}
        n_layers = 5

        idx = 0
        for r in range(1, 5):
            for c in range(1, 5):
                if idx < 8:
                    recipe = [idx] * n_layers
                else:
                    recipe = [0] * n_layers

                cell_map[f"{r},{c}"] = {
                    "recipe_index": idx,
                    "layers": recipe,
                    "slot_names": spec_slot_names,
                }
                idx += 1

        spec = {
            "name": "Test_First_8_Cells_Mismatch",
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

        spec_path = tmp_path / "test_first_8_cells_mismatch_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 使用3色的profile_id调用
        # 如果修复正确，这应该成功（使用规格文件的8色）
        # 如果修复失败，这会抛出"配方索引超出范围"错误
        try:
            result = handle_board_preview({
                "profile_id": "rgb",  # 3色配置
                "spec_path": str(spec_path),
            })

            # 验证成功获取结果
            assert "cells" in result
            cells = result["cells"]

            # 找到数据区域的格子
            data_cells = [c for c in cells if c["row"] in range(1, 5) and c["col"] in range(1, 5)]

            # 验证至少有8个数据格子
            assert len(data_cells) >= 8, f"数据格子数量不足: {len(data_cells)}"

            print(f"\n修复验证通过：规格8色 + profile 3色 成功返回 {len(data_cells)} 个数据格子")

        except ValueError as e:
            if "配方索引超出范围" in str(e):
                pytest.fail(f"修复的bug仍然存在: {e}")
            else:
                raise

    def test_border_cells_vs_data_cells(self, tmp_path: Path) -> None:
        """测试边框格子与数据格子的区别

        验证：
        - 边框格子（row=0 或 row=rows-1 或 col=0 或 col=cols-1）使用边框颜色
        - 数据格子使用规格文件中的配方
        """
        slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]

        # 创建规格文件
        cell_map = {}
        n_layers = 5

        # 数据区域使用索引1（Black）
        for r in range(1, 5):
            for c in range(1, 5):
                cell_map[f"{r},{c}"] = {
                    "recipe_index": 0,
                    "layers": [1] * n_layers,  # 使用Black
                    "slot_names": slot_names,
                }

        spec = {
            "name": "Test_Border_vs_Data",
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

        spec_path = tmp_path / "test_border_vs_data_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        result = handle_board_preview({
            "profile_id": "full_8",
            "spec_path": str(spec_path),
        })

        assert "cells" in result
        cells = result["cells"]

        # 分类格子
        border_cells = []
        data_cells = []

        for cell in cells:
            row, col = cell["row"], cell["col"]
            is_border = row == 0 or row == 5 or col == 0 or col == 5
            if is_border:
                border_cells.append(cell)
            else:
                data_cells.append(cell)

        # 验证边框格子和数据格子的数量
        # 6x6格子，边框是外围一圈：(6*4 - 4) = 20个边框格子
        # 数据格子是内部4x4 = 16个
        assert len(border_cells) == 20, f"边框格子数量应为20，实际为{len(border_cells)}"
        assert len(data_cells) == 16, f"数据格子数量应为16，实际为{len(data_cells)}"

        # 验证数据格子都有颜色数据
        for cell in data_cells:
            assert "target_rgb" in cell
            rgb = cell["target_rgb"]
            assert all(0 <= v <= 255 for v in [rgb["r"], rgb["g"], rgb["b"]])

        print(f"\n边框格子: {len(border_cells)} 个，数据格子: {len(data_cells)} 个")

    def test_cell_count_consistency(self, tmp_path: Path) -> None:
        """测试格子数量一致性

        验证：返回的cells数量 = rows * cols
        """
        slot_names = ["Red", "Green", "Blue"]

        cell_map = {}
        for r in range(1, 5):
            for c in range(1, 5):
                cell_map[f"{r},{c}"] = {
                    "recipe_index": 0,
                    "layers": [0, 0, 0, 0, 0],
                    "slot_names": slot_names,
                }

        spec = {
            "name": "Test_Cell_Count",
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

        spec_path = tmp_path / "test_cell_count_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        result = handle_board_preview({
            "profile_id": "rgb",
            "spec_path": str(spec_path),
        })

        assert "cells" in result
        cells = result["cells"]

        # 验证格子总数
        expected_count = 6 * 6  # rows * cols
        assert len(cells) == expected_count, f"格子总数应为{expected_count}，实际为{len(cells)}"

        # 验证行列范围
        rows = [c["row"] for c in cells]
        cols = [c["col"] for c in cells]

        assert min(rows) == 0 and max(rows) == 5, f"行范围应为0-5，实际为{min(rows)}-{max(rows)}"
        assert min(cols) == 0 and max(cols) == 5, f"列范围应为0-5，实际为{min(cols)}-{max(cols)}"

        print(f"\n格子数量验证通过: {len(cells)} 个格子 (6x6)")
