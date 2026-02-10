"""体素修复模块 - 提供基于体素的网格修复功能"""

from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from oc_core_02.core.mesh_export import VoxelGrid, voxel_grid_to_mesh
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _build_voxel_mesh_from_rasters(
    poly_dir: Path,
    slot_name: str,
    n_layers: int,
    board_mm: float,
    layer_height_mm: float,
) -> trimesh.Trimesh | None:
    """
    从栅格图构建体素网格
    
    读取多层栅格图像，将其转换为3D体素体积，然后生成网格模型
    
    参数:
        poly_dir: 包含栅格图像的目录路径
        slot_name: 槽位名称，用于匹配文件名
        n_layers: 层数
        board_mm: 板的物理尺寸（毫米）
        layer_height_mm: 每层高度（毫米）
        
    返回:
        trimesh.Trimesh对象或None（如果构建失败）
    """
    masks = []
    w = None
    h = None
    for z in range(int(n_layers)):
        # 优先尝试4x放大版本的栅格图
        p4 = poly_dir / f"L{z:02d}_{slot_name}_poly_raster_4x.png"
        p1 = poly_dir / f"L{z:02d}_{slot_name}_poly_raster.png"
        p = p4 if p4.exists() else (p1 if p1.exists() else None)
        if p is None:
            logger.warning(f"[警告] 无法进行体素修复：缺少栅格图: layer={z}, slot={slot_name}")
            return None

        im = Image.open(p).convert("L")
        arr = np.asarray(im, dtype=np.uint8)
        if arr.ndim != 2:
            logger.warning(f"[警告] 无法进行体素修复：栅格图维度异常: layer={z}, slot={slot_name}, shape={arr.shape}")
            return None
        if w is None:
            h, w = int(arr.shape[0]), int(arr.shape[1])
        else:
            if int(arr.shape[0]) != int(h) or int(arr.shape[1]) != int(w):
                logger.warning(f"[警告] 无法进行体素修复：栅格图尺寸不一致: layer={z}, slot={slot_name}, "
                    f"expect=({h},{w}), got=({arr.shape[0]},{arr.shape[1]})"
                )
                return None
        masks.append(arr > 127)

    if not masks:
        return None

    # 将掩码堆叠为3D体积
    vol = np.stack(masks, axis=0).astype(np.uint8)
    # 计算体素尺寸
    sx = float(board_mm) / float(w)
    sy = float(board_mm) / float(h)
    grid = VoxelGrid(volume=vol, voxel_size=(sx, sy, float(layer_height_mm)))
    try:
        m = voxel_grid_to_mesh(grid, shrink=0.0, weld_vertices=True)
    except Exception as e:
        logger.error(f"[错误] 体素转网格失败: slot={slot_name}, 原因={e}")
        import traceback
        traceback.print_exc()
        return None
    return m
