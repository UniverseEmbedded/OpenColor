"""
颜色配置验证脚本 - 导出3MF版本
验证 ColorProfile 与 generate_board 的集成，并导出3MF文件供观察
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "src"))

from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager,
    ColorProfile,
)
from oc_proto.calib_board_gen.generate_board import (
    build_recipe_pool,
    build_board_spec,
    spec_to_meshes,
    export_standard_3mf,
    DEFAULT_LAYERS,
    DATA_ROWS,
    DATA_COLS,
    SLOT_NAMES_8,
    COLOR_SYSTEM_8,
)
from oc_core_02.utils.paths import ensure_data, get_out_dir
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def export_with_profile(profile: ColorProfile, output_dir: Path, board_name: str = None):
    """
    使用指定的颜色配置导出3MF文件
    
    参数:
        profile: 颜色配置
        output_dir: 输出目录
        board_name: 板子名称（默认为配置名）
    """
    n_colors = profile.num_colors
    num_cells = DATA_ROWS * DATA_COLS
    
    if board_name is None:
        board_name = f"{profile.num_colors}Color_Test"
    
    logger.info(f"使用配置 '{profile.name}' ({n_colors}色) 生成校准板...")
    
    # 步骤1: 生成配方池
    recipes = build_recipe_pool(
        layers=DEFAULT_LAYERS,
        n_colors=n_colors,
        target_count=num_cells,
    )
    logger.info(f"生成 {len(recipes)} 个配方")
    
    # 步骤2: 构建 BoardSpec（注意：当前使用硬编码 SLOT_NAMES_8）
    spec = build_board_spec(
        board_name=board_name,
        recipes=recipes,
        group_id=0,
        plate_index=0,
    )
    logger.info(f"构建 BoardSpec: {spec.name}, {len(spec.cell_map)} 个格子")
    
    # 步骤3: 转换为网格
    meshes_by_slot = spec_to_meshes(spec, shrink=0.0)
    logger.info(f"生成网格: {len(meshes_by_slot)} 个颜色槽位")
    
    # 步骤4: 导出3MF
    # 注意：export_standard_3mf 使用硬编码 COLOR_SYSTEM_8
    out_3mf = export_standard_3mf(output_dir, spec, meshes_by_slot)
    logger.info(f"导出3MF: {out_3mf}")
    
    return out_3mf, spec, recipes


def test_export_different_profiles():
    """测试导出不同颜色配置的3MF"""
    
    # 准备输出目录
    prototype_dir = Path(__file__).resolve().parent
    ensure_data(prototype_dir, [])
    out_dir = get_out_dir(prototype_dir) / "color_profile_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("测试导出不同颜色配置的3MF")
    logger.info(f"输出目录: {out_dir}")
    logger.info("=" * 60)
    
    manager = get_profile_manager()
    
    # 测试1: 8色配置（当前默认，应该正常）
    logger.info("\n【测试1】8色配置（full_8）")
    profile_8 = manager.get_profile("full_8")
    try:
        out_3mf_8, spec_8, recipes_8 = export_with_profile(profile_8, out_dir, "Test_8Color")
        logger.info(f"[成功] 8色配置导出完成: {out_3mf_8.name}")
        
        # 验证颜色映射
        sample_cell = spec_8.cell_map.get("1,1")
        if sample_cell:
            layers = sample_cell["layers"]
            slot_names = sample_cell["slot_names"]
            logger.info(f"  示例格子 1,1: 索引{layers} -> 名称{slot_names}")
            
    except Exception as e:
        logger.error(f"[失败] 8色配置导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试2: 4色配置（rybw）
    logger.info("\n【测试2】4色配置（rybw）")
    profile_4 = manager.get_profile("rybw")
    try:
        out_3mf_4, spec_4, recipes_4 = export_with_profile(profile_4, out_dir, "Test_4Color")
        logger.info(f"[成功] 4色配置导出完成: {out_3mf_4.name}")
        
        # 验证颜色映射
        sample_cell = spec_4.cell_map.get("1,1")
        if sample_cell:
            layers = sample_cell["layers"]
            slot_names = sample_cell["slot_names"]
            logger.info(f"  示例格子 1,1: 索引{layers} -> 名称{slot_names}")
            logger.info(f"  注意：索引对应的是 SLOT_NAMES_8，不是 rybw 的颜色顺序")
            logger.info(f"  SLOT_NAMES_8: {SLOT_NAMES_8[:4]}...")
            logger.info(f"  rybw 颜色: {profile_4.color_names}")
            
    except Exception as e:
        logger.error(f"[失败] 4色配置导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试3: 3色配置（rgb）
    logger.info("\n【测试3】3色配置（rgb）")
    profile_3 = manager.get_profile("rgb")
    try:
        out_3mf_3, spec_3, recipes_3 = export_with_profile(profile_3, out_dir, "Test_3Color")
        logger.info(f"[成功] 3色配置导出完成: {out_3mf_3.name}")
        
        # 验证颜色映射
        sample_cell = spec_3.cell_map.get("1,1")
        if sample_cell:
            layers = sample_cell["layers"]
            slot_names = sample_cell["slot_names"]
            logger.info(f"  示例格子 1,1: 索引{layers} -> 名称{slot_names}")
            
    except Exception as e:
        logger.error(f"[失败] 3色配置导出失败: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n" + "=" * 60)
    logger.info("导出测试完成")
    logger.info("=" * 60)
    logger.info(f"输出文件位置: {out_dir}")
    logger.info("\n请检查3MF文件中的颜色是否正确:")
    logger.info("- 8色配置: 应该显示 White, Red, Yellow, Blue, Green, Cyan, Magenta, Black")
    logger.info("- 4色配置: 当前会错误地映射到 SLOT_NAMES_8 的前4个颜色")
    logger.info("- 3色配置: 当前会错误地映射到 SLOT_NAMES_8 的前3个颜色")


def main():
    test_export_different_profiles()


if __name__ == "__main__":
    main()
