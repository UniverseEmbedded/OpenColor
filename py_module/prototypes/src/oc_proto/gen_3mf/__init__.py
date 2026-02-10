"""gen_model_exporter - 模型导出模块

本模块提供从矢量多边形导出3D网格模型的功能。
"""

from .geometry_bridge import (
    _make_exclusive_by_layer_cpp,
    check_cpp_available,
    get_cpp_geometry,
)
from .interrupt_handler import (
    _install_interrupt_handlers,
    _collect_futures_interruptible,
    _hard_abort_if_interrupted,
)
from .main import run, main, VERSION
from model_export.mesh_utils import (
    _repair_mesh,
    _simplify_mesh,
    _extrude_2d_to_3d,
    _save_mesh,
    _check_mesh_quality,
)
from .voxel_repair import _build_voxel_mesh_from_rasters

__version__ = VERSION
__all__ = [
    # 主函数
    "run",
    "main",
    "VERSION",
    # 中断处理
    "_install_interrupt_handlers",
    "_collect_futures_interruptible",
    "_hard_abort_if_interrupted",
    # 几何桥接
    "_make_exclusive_by_layer_cpp",
    "check_cpp_available",
    "get_cpp_geometry",
    # 体素修复
    "_build_voxel_mesh_from_rasters",
    # 网格工具
    "_repair_mesh",
    "_simplify_mesh",
    "_extrude_2d_to_3d",
    "_save_mesh",
    "_check_mesh_quality",
]
