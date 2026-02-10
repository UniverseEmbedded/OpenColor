"""健康检查处理器 - 提供引擎状态查询功能

本模块提供引擎健康检查相关的API端点，用于：
- 返回引擎版本信息
- 声明引擎支持的功能列表
- 提供基本的存活检测接口
"""

from __future__ import annotations

from typing import Any, Dict


def handle_health_ping() -> Dict[str, Any]:
    """处理健康检查请求

    返回引擎的版本信息和所支持的功能列表

    返回:
        包含引擎版本和支持功能的字典
    """
    return {
        "version": "0.1.0",
        "capabilities": [
            "board.generate",
            "lut.extract_from_photo",
            "bitmap.export",
        ],
    }
