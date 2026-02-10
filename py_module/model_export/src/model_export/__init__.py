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


def generate_bambu_project_from_template(*args, **kwargs):
    """
    从模板生成 Bambu Studio 3MF 项目（已弃用）
    
    ⚠️ 警告：此函数已弃用，无法正常使用。
    建议使用 export_standard_3mf 进行标准 3MF 导出。
    """
    import warnings

    warnings.warn(
        "bambu_3mf 模块处于 Alpha 阶段，已弃用，无法正常使用。"
        "建议使用 export_standard_3mf 进行标准 3MF 导出。",
        DeprecationWarning,
        stacklevel=2,
    )
    from .bambu_3mf.template import generate_bambu_project_from_template as _impl

    return _impl(*args, **kwargs)

__all__ = [
    "export_standard_3mf",
    "generate_bambu_project_from_template",
    "MeshData",
    "SlotColor",
    "DEFAULT_SLOT_COLORS",
    "rgba_to_hex",
]
