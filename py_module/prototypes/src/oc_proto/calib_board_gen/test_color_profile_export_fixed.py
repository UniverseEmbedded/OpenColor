"""
颜色配置验证脚本 - 修复版本
修复颜色映射问题，正确使用 ColorProfile 的颜色名
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "src"))

import numpy as np
from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager,
    ColorProfile,
)
from oc_proto.calib_board_gen.generate_board import (
    build_recipe_pool,
    build_board_spec,
    spec_to_meshes,
    export_standard_3mf,
    _build_core_volumes,
    _volume_to_core_mesh,
    DEFAULT_LAYERS,
    DATA_ROWS,
    DATA_COLS,
    SLOT_NAMES_8,
    COLOR_SYSTEM_8,
    CORE_SIZE,
    CELL_SIZE_MM,
    DEFAULT_LAYER_HEIGHT,
)
from oc_core_02.core.mesh_export import VoxelGrid, voxel_grid_to_mesh
from oc_core_02.utils.paths import ensure_data, get_out_dir
from oc_core_02.utils.logger import get_logger
import trimesh

logger = get_logger(__name__)


def _build_core_volumes_fixed(spec, profile: ColorProfile) -> dict:
    """
    修复版本：使用 ColorProfile 的颜色名映射
    """
    slot_names = profile.color_names
    n_colors = profile.num_colors
    
    # 初始化体素数据字典，使用实际的颜色名
    volumes = {}
    for name in slot_names:
        volumes[name] = np.zeros((DEFAULT_LAYERS, CORE_SIZE, CORE_SIZE), dtype=bool)
    
    # 处理标记区域的颜色（使用 profile 中的标记颜色配置）
    marker_colors = profile.marker_colors
    
    # 边框默认颜色：3色配置用Green，其他用White
    if n_colors == 3 and "Green" in slot_names:
        default_border_color = "Green"
    elif "White" in slot_names:
        default_border_color = "White"
    else:
        default_border_color = slot_names[0] if slot_names else None
    
    for r_cell in range(CORE_SIZE):
        for c_cell in range(CORE_SIZE):
            cell_data = spec.cell_map.get(f"{r_cell},{c_cell}")
            if cell_data:
                # 处理数据区域的格子
                layers = cell_data["layers"]
                for z, color_idx in enumerate(layers):
                    # 使用 profile 的颜色名映射
                    if color_idx < n_colors:
                        color_name = slot_names[int(color_idx)]
                        if color_name in volumes:
                            volumes[color_name][z, r_cell, c_cell] = True
            else:
                # 处理标记区域的格子（边框）
                # 默认使用第一个颜色作为边框颜色
                color_name = default_border_color
                
                # 检查是否是4个角点，使用特定标记颜色
                for m_name, (mc, mr) in spec.markers.items():
                    if r_cell == mr and c_cell == mc:
                        marker_color = marker_colors.get(m_name)
                        if marker_color and marker_color in volumes:
                            color_name = marker_color
                        break
                
                if color_name and color_name in volumes:
                    volumes[color_name][:, r_cell, c_cell] = True
    
    return volumes


def spec_to_meshes_fixed(spec, profile: ColorProfile, shrink: float = 0.0):
    """
    修复版本：使用 ColorProfile 的颜色配置生成网格
    """
    from oc_proto.calib_board_gen.generate_board import (
        _analyze_mesh_basic,
        _union_meshes,
    )
    
    slot_names = profile.color_names
    voxel_size = (CELL_SIZE_MM, CELL_SIZE_MM, DEFAULT_LAYER_HEIGHT)
    
    # 使用修复后的体素构建函数
    core_volumes = _build_core_volumes_fixed(spec, profile)
    
    meshes_by_slot = {name: [] for name in slot_names}
    
    for slot_name in slot_names:
        vol = core_volumes.get(slot_name)
        if vol is not None and np.any(vol):
            m = _volume_to_core_mesh(vol, voxel_size, shrink, slot_name)
            info = _analyze_mesh_basic(m, f"{profile.num_colors}色板/{slot_name}/体素网格(已并集)")
            if int(info.get("non_manifold_edges", 0)) > 0 or int(info.get("boundary_edges", 0)) > 0:
                logger.warning(f"体素网格质量警告(slot={slot_name}): 非流形边={info.get('non_manifold_edges')} 边界边={info.get('boundary_edges')}")
                # 尝试修复
                try:
                    import trimesh.repair
                    m_copy = m.copy()
                    trimesh.repair.fill_holes(m_copy)
                    info_after = _analyze_mesh_basic(m_copy, f"{profile.num_colors}色板/{slot_name}/修复后")
                    if int(info_after.get("boundary_edges", 0)) == 0:
                        m = m_copy
                        logger.info(f"  修复成功")
                except Exception as e:
                    logger.warning(f"  修复失败: {e}")
            meshes_by_slot[slot_name].append(m)
    
    # 合并每个颜色的所有网格
    merged = {}
    for slot_name in slot_names:
        merged_mesh = _union_meshes(meshes_by_slot[slot_name], slot_name)
        if merged_mesh.faces is not None and len(merged_mesh.faces) > 0:
            info = _analyze_mesh_basic(merged_mesh, f"{profile.num_colors}色板/{slot_name}/合并后")
            if int(info.get("non_manifold_edges", 0)) > 0 or int(info.get("boundary_edges", 0)) > 0:
                logger.warning(f"合并后网格质量警告(slot={slot_name}): 非流形边={info.get('non_manifold_edges')} 边界边={info.get('boundary_edges')}")
        merged[slot_name] = merged_mesh
    
    return merged


def export_standard_3mf_fixed(out_dir, spec, meshes_by_slot, profile: ColorProfile):
    """
    修复版本：使用 ColorProfile 的颜色配置导出3MF
    """
    from model_export.standard_3mf import export_standard_3mf_from_meshes
    
    out_3mf = out_dir / f"{spec.name.replace(' ', '_')}.3mf"
    slot_names_used = []
    
    for slot_name in profile.color_names:
        tm_mesh = meshes_by_slot.get(slot_name)
        if tm_mesh is None:
            continue
        if tm_mesh.faces is None or len(tm_mesh.faces) == 0:
            continue
        slot_names_used.append(slot_name)
    
    # 使用 profile 的颜色定义
    slot_colors = {}
    for name in profile.color_names:
        rgba = profile.get_color_rgba(name)
        slot_colors[name] = rgba
    
    export_standard_3mf_from_meshes(
        out_3mf=out_3mf,
        meshes=meshes_by_slot,
        slot_names=slot_names_used,
        slot_colors=slot_colors,
    )
    return out_3mf


def export_with_profile_fixed(profile: ColorProfile, output_dir: Path, board_name: str = None):
    """
    使用修复后的函数导出3MF
    """
    n_colors = profile.num_colors
    num_cells = DATA_ROWS * DATA_COLS
    
    if board_name is None:
        board_name = f"{n_colors}Color_Test_Fixed"
    
    logger.info(f"使用配置 '{profile.name}' ({n_colors}色) 生成校准板...")
    
    # 步骤1: 生成配方池
    recipes = build_recipe_pool(
        layers=DEFAULT_LAYERS,
        n_colors=n_colors,
        target_count=num_cells,
    )
    logger.info(f"生成 {len(recipes)} 个配方")
    
    # 步骤2: 构建 BoardSpec
    spec = build_board_spec(
        board_name=board_name,
        recipes=recipes,
        group_id=0,
        plate_index=0,
    )
    logger.info(f"构建 BoardSpec: {spec.name}, {len(spec.cell_map)} 个格子")
    
    # 步骤3: 使用修复后的函数生成网格
    meshes_by_slot = spec_to_meshes_fixed(spec, profile, shrink=0.0)
    logger.info(f"生成网格: {len(meshes_by_slot)} 个颜色槽位")
    
    # 步骤4: 使用修复后的函数导出3MF
    out_3mf = export_standard_3mf_fixed(output_dir, spec, meshes_by_slot, profile)
    logger.info(f"导出3MF: {out_3mf}")
    
    return out_3mf, spec, recipes


def test_export_different_profiles_fixed():
    """测试修复后的导出功能"""
    
    # 准备输出目录
    prototype_dir = Path(__file__).resolve().parent
    ensure_data(prototype_dir, [])
    out_dir = get_out_dir(prototype_dir) / "color_profile_test_fixed"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("测试修复后的颜色配置3MF导出")
    logger.info(f"输出目录: {out_dir}")
    logger.info("=" * 60)
    
    manager = get_profile_manager()
    
    # 测试1: 8色配置
    logger.info("\n【测试1】8色配置（full_8）")
    profile_8 = manager.get_profile("full_8")
    try:
        out_3mf_8, spec_8, recipes_8 = export_with_profile_fixed(profile_8, out_dir, "Test_8Color_Fixed")
        logger.info(f"[成功] 8色配置导出完成: {out_3mf_8.name}")
    except Exception as e:
        logger.error(f"[失败] 8色配置导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试2: 4色配置（rybw）
    logger.info("\n【测试2】4色配置（rybw）")
    profile_4 = manager.get_profile("rybw")
    try:
        out_3mf_4, spec_4, recipes_4 = export_with_profile_fixed(profile_4, out_dir, "Test_4Color_Fixed")
        logger.info(f"[成功] 4色配置导出完成: {out_3mf_4.name}")
        
        # 验证颜色映射
        sample_cell = spec_4.cell_map.get("1,1")
        if sample_cell:
            layers = sample_cell["layers"]
            logger.info(f"  示例格子 1,1: 索引{layers}")
            logger.info(f"  正确映射应为: {[profile_4.color_names[i] for i in layers]}")
            
    except Exception as e:
        logger.error(f"[失败] 4色配置导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试3: 3色配置（rgb）
    logger.info("\n【测试3】3色配置（rgb）")
    profile_3 = manager.get_profile("rgb")
    try:
        out_3mf_3, spec_3, recipes_3 = export_with_profile_fixed(profile_3, out_dir, "Test_3Color_Fixed")
        logger.info(f"[成功] 3色配置导出完成: {out_3mf_3.name}")
        
        # 验证颜色映射
        sample_cell = spec_3.cell_map.get("1,1")
        if sample_cell:
            layers = sample_cell["layers"]
            logger.info(f"  示例格子 1,1: 索引{layers}")
            logger.info(f"  正确映射应为: {[profile_3.color_names[i] for i in layers]}")
            
    except Exception as e:
        logger.error(f"[失败] 3色配置导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n" + "=" * 60)
    logger.info("修复版导出测试完成")
    logger.info("=" * 60)
    logger.info(f"输出文件位置: {out_dir}")
    logger.info("\n请检查3MF文件中的颜色是否正确:")
    logger.info("- 8色配置: White, Red, Yellow, Blue, Green, Cyan, Magenta, Black")
    logger.info("- 4色配置: Red, Yellow, Blue, White")
    logger.info("- 3色配置: Red, Green, Blue")


def main():
    test_export_different_profiles_fixed()


if __name__ == "__main__":
    main()
