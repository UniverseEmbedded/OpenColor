"""
API桥接层测试 - 测试board相关API的通路

测试范围：
1. board.preview API接口
2. board.generate API接口（基础验证）
3. 前后端数据格式兼容性
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestBoardPreviewAPI:
    """测试board.preview API接口"""

    def _create_test_spec(self, slot_names: list[str], rows: int = 6, cols: int = 6) -> dict:
        """创建测试用的规格文件数据"""
        cell_map = {}
        n_layers = 5
        idx = 0

        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                cell_map[f"{r},{c}"] = {
                    "recipe_index": idx,
                    "layers": [idx % len(slot_names)] * n_layers,
                    "slot_names": slot_names,
                }
                idx += 1

        return {
            "name": "Test_Board_API",
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

    def test_api_board_preview_8color(self, tmp_path: Path) -> None:
        """测试8色配置的board.preview API

        验证：通过API调用能正确获取8色色盘的预览数据
        """
        # 创建测试规格文件
        slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]
        spec = self._create_test_spec(slot_names, rows=6, cols=6)
        spec_path = tmp_path / "test_api_8color_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 构建API请求
        req = {
            "jsonrpc": "2.0",
            "id": "test_preview_8color",
            "method": "board.preview",
            "params": {
                "profile_id": "full_8",
                "spec_path": str(spec_path),
            },
        }

        # 启动引擎子进程
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "oc_engine.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parents[2]),
            text=True,
        )

        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            # 等待响应
            deadline = time.time() + 10
            response = None

            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    payload = json.loads(line)
                    # 查找对应的响应
                    if payload.get("id") == "test_preview_8color":
                        response = payload
                        break
                    # 或者查找事件响应
                    if payload.get("event") == "job.done":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            # 验证响应
            assert response is not None, "未收到API响应"

            # 检查是否有错误
            if "error" in response:
                error_msg = response["error"].get("message", "未知错误")
                pytest.fail(f"API返回错误: {error_msg}")

            # 验证结果结构
            result = response.get("result", {})
            assert "cells" in result, "响应缺少cells字段"
            assert len(result["cells"]) > 0, "cells为空"

            # 验证每个cell的结构
            for cell in result["cells"]:
                assert "row" in cell, "cell缺少row字段"
                assert "col" in cell, "cell缺少col字段"
                assert "target_rgb" in cell, "cell缺少target_rgb字段"
                assert "recipe" in cell, "cell缺少recipe字段"

        finally:
            proc.kill()

    def test_api_board_preview_different_profile(self, tmp_path: Path) -> None:
        """测试规格文件与profile配置不同时的API行为

        验证：规格文件使用8色，但profile_id传入3色配置时，
              应该优先使用规格文件的slot_names（修复的bug）
        """
        # 规格文件使用8色
        spec_slot_names = [
            "White", "Black", "Red", "Green",
            "Blue", "Cyan", "Magenta", "Yellow"
        ]
        spec = self._create_test_spec(spec_slot_names, rows=6, cols=6)
        spec_path = tmp_path / "test_api_mismatch_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        # 但使用3色的profile_id调用
        req = {
            "jsonrpc": "2.0",
            "id": "test_preview_mismatch",
            "method": "board.preview",
            "params": {
                "profile_id": "rgb",  # 3色配置
                "spec_path": str(spec_path),
            },
        }

        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "oc_engine.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parents[2]),
            text=True,
        )

        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            deadline = time.time() + 10
            response = None

            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    payload = json.loads(line)
                    if payload.get("id") == "test_preview_mismatch":
                        response = payload
                        break
                    if payload.get("event") == "job.done":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            # 应该成功响应（使用规格文件的8色，而不是profile的3色）
            assert response is not None, "未收到API响应"

            if "error" in response:
                error_msg = response["error"].get("message", "未知错误")
                # 如果报错，应该是其他原因，而不是配方索引越界
                assert "配方索引超出范围" not in error_msg, \
                    f"修复的bug仍然出现: {error_msg}"

            result = response.get("result", {})
            assert "cells" in result, "响应缺少cells字段"

        finally:
            proc.kill()

    def test_api_board_preview_error_handling(self, tmp_path: Path) -> None:
        """测试API错误处理

        验证：传入不存在的spec_path时，API返回正确的错误信息
        """
        req = {
            "jsonrpc": "2.0",
            "id": "test_preview_error",
            "method": "board.preview",
            "params": {
                "profile_id": "full_8",
                "spec_path": "/nonexistent/path/spec.json",
            },
        }

        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "oc_engine.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parents[2]),
            text=True,
        )

        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            deadline = time.time() + 10
            response = None

            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    payload = json.loads(line)
                    if payload.get("id") == "test_preview_error":
                        response = payload
                        break
                    if payload.get("event") == "job.error":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            # 应该返回错误响应
            assert response is not None, "未收到API响应"
            assert "error" in response or response.get("event") == "job.error", \
                "应该返回错误，但收到了成功响应"

        finally:
            proc.kill()


class TestBoardGenerateAPI:
    """测试board.generate API接口（基础验证）"""

    def test_api_board_generate_basic(self, tmp_path: Path) -> None:
        """测试board.generate API的基础调用

        验证：能成功提交生成请求并收到job.accepted事件
        """
        req = {
            "jsonrpc": "2.0",
            "id": "test_generate_basic",
            "method": "board.generate",
            "params": {
                "materials": [
                    {"name": "Red", "r": 255, "g": 0, "b": 0},
                    {"name": "Green", "r": 0, "g": 255, "b": 0},
                    {"name": "Blue", "r": 0, "g": 0, "b": 255},
                ],
                "dataRows": 4,
                "dataCols": 4,
                "rows": 6,
                "cols": 6,
                "layers": 5,
                "cellSizeMm": 4.0,
                "layerHeightMm": 0.12,
                "shrink": 0.0,
                "export_formats": ["3mf"],
                "file_name": "Test_Board_API",
                "timestamp": "20250212_000000",
                "workspace_path": str(tmp_path),
            },
        }

        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "oc_engine.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parents[2]),
            text=True,
        )

        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            deadline = time.time() + 15
            accepted = False

            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    payload = json.loads(line)
                    # 检查是否收到job.accepted
                    if payload.get("event") == "job.accepted":
                        accepted = True
                        break
                    # 或者检查是否直接返回结果（同步执行）
                    if payload.get("id") == "test_generate_basic" and "result" in payload:
                        accepted = True
                        break
                    # 检查错误
                    if payload.get("event") == "job.error":
                        error_msg = payload.get("data", {}).get("message", "未知错误")
                        pytest.fail(f"生成任务失败: {error_msg}")
                except json.JSONDecodeError:
                    continue

            assert accepted, "未收到job.accepted事件或成功响应"

        finally:
            proc.kill()


class TestAPIResponseFormat:
    """测试API响应格式兼容性"""

    def test_jsonrpc_response_format(self, tmp_path: Path) -> None:
        """测试JSON-RPC 2.0响应格式

        验证：所有响应都符合JSON-RPC 2.0规范
        """
        slot_names = ["Red", "Green", "Blue"]
        spec = {
            "name": "Test_JSONRPC",
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
        spec_path = tmp_path / "test_jsonrpc_spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        req = {
            "jsonrpc": "2.0",
            "id": "test_jsonrpc_format",
            "method": "board.preview",
            "params": {
                "profile_id": "rgb",
                "spec_path": str(spec_path),
            },
        }

        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "oc_engine.main"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parents[2]),
            text=True,
        )

        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()

            deadline = time.time() + 10
            response = None

            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break

                try:
                    payload = json.loads(line)
                    if payload.get("id") == "test_jsonrpc_format":
                        response = payload
                        break
                    if payload.get("event") == "job.done":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            assert response is not None, "未收到响应"

            # 验证JSON-RPC格式
            if "jsonrpc" in response:
                assert response["jsonrpc"] == "2.0", "jsonrpc字段应为2.0"
                assert "id" in response, "响应应包含id字段"
                assert response["id"] == "test_jsonrpc_format", "id应匹配请求"

                # 成功响应应有result字段
                if "result" in response:
                    assert "error" not in response, "成功响应不应包含error字段"
                # 错误响应应有error字段
                elif "error" in response:
                    assert "result" not in response, "错误响应不应包含result字段"
                    assert "code" in response["error"], "error应包含code"
                    assert "message" in response["error"], "error应包含message"

        finally:
            proc.kill()
