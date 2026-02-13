"""
API桥接层测试 - 测试ping API的通路

测试范围：
1. ping API接口（Web → Python 连通性测试）
2. health.ping API接口
3. 未知方法错误处理
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestPingAPI:
    """测试ping API接口 - WebUI调试页面使用的连通性测试"""

    def test_api_ping_basic(self) -> None:
        """测试ping API的基础调用

        验证：ping方法能正确返回pong响应，包含oc_engine和oc_proto模块状态
        """
        req = {
            "jsonrpc": "2.0",
            "id": "test_ping_basic",
            "method": "ping",
            "params": {},
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
                    if payload.get("id") == "test_ping_basic":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            # 验证响应
            assert response is not None, "未收到API响应"
            assert "error" not in response, f"API返回错误: {response.get('error', {})}"
            assert "result" in response, "响应缺少result字段"

            result = response["result"]
            assert "result" in result, "result字段应包含result子字段"
            
            # 验证返回内容包含预期信息
            ping_result = result["result"]
            assert "pong from oc_engine" in ping_result, "应包含oc_engine标识"
            assert "oc_proto 模块加载成功" in ping_result, "应包含oc_proto模块加载状态"

        finally:
            proc.kill()

    def test_api_health_ping(self) -> None:
        """测试health.ping API接口

        验证：health.ping方法能正确返回健康状态（版本和 capabilities）
        """
        req = {
            "jsonrpc": "2.0",
            "id": "test_health_ping",
            "method": "health.ping",
            "params": {},
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
                    if payload.get("id") == "test_health_ping":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            # 验证响应
            assert response is not None, "未收到API响应"
            assert "error" not in response, f"API返回错误: {response.get('error', {})}"
            assert "result" in response, "响应缺少result字段"

            result = response["result"]
            assert "version" in result, "应包含version字段"
            assert "capabilities" in result, "应包含capabilities字段"
            assert isinstance(result["capabilities"], list), "capabilities应为列表"

        finally:
            proc.kill()

    def test_api_unknown_method(self) -> None:
        """测试未知方法错误处理

        验证：调用不存在的方法时返回正确的错误信息
        """
        req = {
            "jsonrpc": "2.0",
            "id": "test_unknown_method",
            "method": "nonexistent.method",
            "params": {},
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
                    if payload.get("id") == "test_unknown_method":
                        response = payload
                        break
                except json.JSONDecodeError:
                    continue

            # 验证错误响应
            assert response is not None, "未收到API响应"
            assert "error" in response, "应返回错误响应"
            
            error = response["error"]
            assert "未知方法" in str(error) or "Unknown method" in str(error), \
                f"错误信息应包含'未知方法'，实际: {error}"

        finally:
            proc.kill()

    def test_api_ping_via_dispatch_json(self) -> None:
        """测试通过dispatch_json直接调用ping

        验证：dispatch_json函数能正确处理ping方法（模拟Rust端调用方式）
        """
        from oc_engine.api_bridge import dispatch_json

        result_json = dispatch_json("ping", "{}")
        result = json.loads(result_json)

        assert "error" not in result, f"不应返回错误: {result.get('error')}"
        assert "result" in result, "应包含result字段"
        
        ping_result = result["result"]
        assert "pong from oc_engine" in ping_result, "应包含oc_engine标识"

    def test_api_ping_via_dispatch_request(self) -> None:
        """测试通过dispatch_request直接调用ping

        验证：dispatch_request函数能正确处理ping方法
        """
        from oc_engine.api_bridge import dispatch_request

        result = dispatch_request("ping", {})

        assert "result" in result, "应包含result字段"
        ping_result = result["result"]
        assert "pong from oc_engine" in ping_result, "应包含oc_engine标识"
