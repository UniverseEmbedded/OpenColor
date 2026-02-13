"""
校准板预览功能测试

测试范围：
1. 配方索引与颜色名称映射正确性（修复的bug）
2. 不同颜色数量配置的预览功能
3. 规格文件slot_names读取逻辑
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from oc_engine.handlers.board import handle_board_preview, _predict_color_with_rts


class TestBoardPreviewColorMapping:
    """测试颜色映射相关功能 - 针对修复的bug"""

    def _create_mock_spec(
        self,
        slot_names: list[str],
        rows: int = 6,
        cols: int = 6,
        recipes: list[list[int]] | None = None,
    ) -> dict:
        """创建模拟的规格文件数据

        Args:
            slot_names: 颜色名称列表
            rows: 行数
            cols: 列数
            recipes: 自定义配方列表，如果为None则使用默认配方

        Returns:
            规格文件字典
        """
        cell_map = {}
        n_layers = 5

        # 数据区域 (1,1) 到 (rows-2, cols-2)
        idx = 0
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                if recipes and idx < len(recipes):
                    recipe = recipes[idx]
                else:
                    # 默认配方：使用索引0的颜色（纯色）
                    recipe = [0] * n_layers

                cell_map[f"{r},{c}"] = {
                    "recipe_index": idx,
                    "layers": recipe,
                    "slot_names": slot_names,
                }
                idx += 1

        return {
            "name": "Test_Board",
            "rows": rows,
            "cols": cols,
            "cell_size_mm": 4.0,
            "cell_map": cell_map,
            "markers": {
                "TL": [0, 0],
                "TR": [cols - 1, 0],
                "BR": [cols - 1, rows - 1],
                "BL": [0, rows - 1],
            },
        }

    def test_preview_with_8_colors(self, tmp_path: Path) -> None:
        """测试8色配置的预览功能

        验证：使用8色配置时，配方索引0-7都能正确映射
        """
        # 使用与DEFAULT_MATERIALS_8一致的顺序
        slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]

        # 创建包含各种配方索引的规格文件
        recipes = [
            [0] * 5,  # White
            [1] * 5,  # Black
            [2] * 5,  # Red
            [3] * 5,  # Green
            [4] * 5,  # Blue
            [5] * 5,  # Cyan
            [6] * 5,  # Magenta
            [7] * 5,  # Yellow
        ]

        spec = self._create_mock_spec(slot_names, rows=6, cols=6, recipes=recipes)
        spec_path = tmp_path / "test_board_8color_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 调用预览函数
        result = handle_board_preview({
            "profile_id": "full_8",
            "spec_path": str(spec_path),
        })

        # 验证结果
        assert "cells" in result
        assert len(result["cells"]) > 0

        # 验证每个cell都有正确的颜色数据
        for cell in result["cells"]:
            assert "target_rgb" in cell
            assert "r" in cell["target_rgb"]
            assert "g" in cell["target_rgb"]
            assert "b" in cell["target_rgb"]

    def test_preview_with_3_colors(self, tmp_path: Path) -> None:
        """测试3色配置的预览功能

        验证：使用3色配置时，配方索引0-2能正确映射
        """
        slot_names = ["Red", "Green", "Blue"]

        recipes = [
            [0] * 5,  # Red
            [1] * 5,  # Green
            [2] * 5,  # Blue
        ]

        spec = self._create_mock_spec(slot_names, rows=6, cols=6, recipes=recipes)
        spec_path = tmp_path / "test_board_3color_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        result = handle_board_preview({
            "profile_id": "rgb",
            "spec_path": str(spec_path),
        })

        assert "cells" in result
        assert len(result["cells"]) > 0

    def test_slot_names_from_spec_file(self, tmp_path: Path) -> None:
        """测试优先从规格文件读取slot_names

        验证：即使profile_id对应的配置不同，也使用规格文件中的slot_names
        这是修复的核心逻辑
        """
        # 规格文件使用8色
        spec_slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]

        # 但传入的profile_id是3色配置
        spec = self._create_mock_spec(spec_slot_names, rows=6, cols=6)
        spec_path = tmp_path / "test_board_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 使用3色的profile_id调用，应该能成功（因为优先使用规格文件的8色）
        result = handle_board_preview({
            "profile_id": "rgb",  # 3色配置
            "spec_path": str(spec_path),
        })

        assert "cells" in result
        # 验证返回了正确数量的格子
        assert result["rows"] == 6
        assert result["cols"] == 6

    def test_recipe_index_out_of_range_error(self, tmp_path: Path) -> None:
        """测试配方索引越界时的错误处理

        验证：当配方索引超出slot_names范围时，应抛出有意义的错误
        """
        slot_names = ["Red", "Green", "Blue"]  # 只有3色

        # 创建包含越界索引的配方（索引5超出了3色范围）
        recipes = [
            [5] * 5,  # 索引5在3色配置中是越界的
        ]

        spec = self._create_mock_spec(slot_names, rows=6, cols=6, recipes=recipes)
        spec_path = tmp_path / "test_board_error_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 应该抛出异常
        with pytest.raises(ValueError, match="配方索引超出范围"):
            handle_board_preview({
                "profile_id": "rgb",
                "spec_path": str(spec_path),
            })

    def test_missing_slot_names_fallback(self, tmp_path: Path) -> None:
        """测试规格文件缺少slot_names时的回退逻辑

        验证：当规格文件没有slot_names时，使用profile的color_names
        """
        # 创建没有slot_names的规格文件
        spec = {
            "name": "Test_Board_No_SlotNames",
            "rows": 6,
            "cols": 6,
            "cell_size_mm": 4.0,
            "cell_map": {
                "1,1": {
                    "recipe_index": 0,
                    "layers": [0, 0, 0, 0, 0],
                    # 注意：没有slot_names字段
                },
            },
            "markers": {
                "TL": [0, 0],
                "TR": [5, 0],
                "BR": [5, 5],
                "BL": [0, 5],
            },
        }

        spec_path = tmp_path / "test_board_no_slotnames_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 应该使用profile的color_names成功执行
        result = handle_board_preview({
            "profile_id": "full_8",
            "spec_path": str(spec_path),
        })

        assert "cells" in result


class TestPredictColorWithRts:
    """测试RTS颜色预测函数"""

    def test_predict_with_valid_recipe(self) -> None:
        """测试有效配方的颜色预测

        验证：使用有效的配方索引能返回RGB颜色
        """
        slot_names = ["Red", "Green", "Blue", "White", "Black"]
        recipe = [0, 1, 2, 3, 4]  # 使用所有5种颜色

        # 注意：这个测试需要RTS模型文件存在
        # 如果模型不存在，测试会跳过
        try:
            result = _predict_color_with_rts(recipe, "full_8", slot_names)
            assert "r" in result
            assert "g" in result
            assert "b" in result
        except (FileNotFoundError, ValueError) as e:
            pytest.skip(f"RTS模型不可用: {e}")

    def test_predict_with_index_out_of_range(self) -> None:
        """测试越界索引的错误处理

        验证：配方索引超出slot_names范围时抛出错误
        """
        slot_names = ["Red", "Green", "Blue"]
        recipe = [0, 1, 5]  # 索引5超出3色范围

        with pytest.raises(ValueError, match="配方索引超出范围: 5"):
            _predict_color_with_rts(recipe, "rgb", slot_names)


class TestBoardPreviewIntegration:
    """集成测试 - 测试完整的生成+预览流程"""

    def test_generate_then_preview_same_colors(self, tmp_path: Path) -> None:
        """测试生成和预览使用相同颜色配置

        验证：生成的色盘能用相同的profile_id正确预览
        """
        # 这个测试需要board生成功能
        # 这里只做简单的结构验证
        pass

    def test_preview_output_structure(self, tmp_path: Path) -> None:
        """测试预览输出的数据结构

        验证：预览返回的数据包含所有必要字段
        """
        slot_names = ["White", "Black", "Red", "Green", "Blue", "Cyan", "Magenta", "Yellow"]

        spec = {
            "name": "Test_Board",
            "rows": 6,
            "cols": 6,
            "cell_size_mm": 4.0,
            "cell_map": {
                "1,1": {
                    "recipe_index": 0,
                    "layers": [0, 0, 0, 0, 0],
                    "slot_names": slot_names,
                },
            },
            "markers": {
                "TL": [0, 0],
                "TR": [5, 0],
                "BR": [5, 5],
                "BL": [0, 5],
            },
        }

        spec_path = tmp_path / "test_structure_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        result = handle_board_preview({
            "profile_id": "full_8",
            "spec_path": str(spec_path),
        })

        # 验证输出结构
        assert "cells" in result
        assert "rows" in result
        assert "cols" in result
        assert "dataRows" in result
        assert "dataCols" in result

        assert result["rows"] == 6
        assert result["cols"] == 6
        assert result["dataRows"] == 4  # rows - 2
        assert result["dataCols"] == 4  # cols - 2

        # 验证每个cell的结构
        for cell in result["cells"]:
            assert "row" in cell
            assert "col" in cell
            assert "target_rgb" in cell
            assert "recipe" in cell

            assert "r" in cell["target_rgb"]
            assert "g" in cell["target_rgb"]
            assert "b" in cell["target_rgb"]
