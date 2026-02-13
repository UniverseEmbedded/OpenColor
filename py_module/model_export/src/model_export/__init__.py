from __future__ import annotations

"""
模型导出模块。
提供将网格数据导出为 3MF 格式的功能，支持标准 3MF 和 Bambu Studio 3MF 项目。

⚠️ 警告:
    Bambu Studio 3MF 导出功能 (generate_bambu_project_from_template) 目前处于 Alpha 阶段，
    已弃用，无法正常使用。该功能基于当前版本的Bambu Studio源码实现，可能随时失效。
    建议使用标准 3MF 导出功能 (export_standard_3mf)。
"""

from .standard_3mf import export_standard_3mf
from .types import MeshData, SlotColor, DEFAULT_SLOT_COLORS, rgba_to_hex


__all__ = [
    "export_standard_3mf",
    "MeshData",
    "SlotColor",
    "DEFAULT_SLOT_COLORS",
    "rgba_to_hex",
]
