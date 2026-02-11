"""
校准板生成主模块
生成任意颜色数量的校准板规格文件和3MF打印文件

使用示例:
    # 使用默认8色配置
    pixi run p2-calib-board-gen
    
    # 使用4色配置
    pixi run p2-calib-board-gen --profile rybw
    
    # 使用自定义配置文件
    pixi run p2-calib-board-gen --config my_colors.json
    
    # 命令行直接指定颜色
    pixi run p2-calib-board-gen --colors "Red:255,0,0" "Green:0,255,0" "Blue:0,0,255"
"""

import argparse
import sys
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

from oc_proto.calib_board_gen import generate_8color_board as g8b
from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager, 
    create_profile_from_args,
    ColorProfile,
)

from oc_core_02.utils.manifest import write_manifest
from oc_core_02.utils.paths import ensure_data, get_out_dir

try:
    from oc_core_02.core.model_analysis import analyze_3mf_lib3mf
except Exception as e:
    analyze_3mf_lib3mf = None
    logger.warning(f"[警告] 无法加载 3MF 分析工具，将跳过导出后分析: {e}")
    import traceback

    traceback.print_exc()

VERSION = "calib_board_gen"


def run(
    num_boards: int = 8, 
    shrink: float = 0.0, 
    include_apriltag: bool = False, 
    include_side_triangles: bool = False,
    profile: ColorProfile = None,
    profile_id: str = "full_8",
):
    """
    运行校准板生成
    
    参数:
        num_boards: 生成的板子数量
        shrink: 格子缩进量
        include_apriltag: 是否包含AprilTag
        include_side_triangles: 是否包含侧边三角形
        profile: 颜色配置对象（优先使用）
        profile_id: 配置ID（当profile为None时使用）
    """
    # 获取颜色配置
    if profile is None:
        manager = get_profile_manager()
        profile = manager.get_profile(profile_id)
    
    num_colors = profile.num_colors
    
    # 准备目录
    prototype_dir = Path(__file__).resolve().parent
    ensure_data(prototype_dir, [])
    out_dir = get_out_dir(prototype_dir)
    
    logger.info(f"开始生成 {num_boards} 个 {num_colors} 色校准板 到 {out_dir}...")
    logger.info(f"配置名称: {profile.name}")
    logger.info(f"使用的颜色: {', '.join(profile.color_names)}")
    
    def generate_to_out(
        num_boards, 
        shrink, 
        output_dir, 
        include_apriltag, 
        include_side_triangles, 
        profile
    ):
        num_cells = g8b.DATA_ROWS * g8b.DATA_COLS
        total_cells_needed = num_cells * num_boards
        recipes = g8b.build_recipe_pool(
            layers=g8b.DEFAULT_LAYERS, 
            n_colors=profile.num_colors, 
            target_count=total_cells_needed
        )

        outputs = []
        for b_idx in range(num_boards):
            board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
            name = f"{profile.num_colors}-Color Board {board_char}"
            start_idx = b_idx * num_cells
            recs = recipes[start_idx : start_idx + num_cells]
            
            spec = g8b.build_board_spec(name, recs, g8b.DEFAULT_GROUP_ID, b_idx, profile=profile)
            spec_path = output_dir / f"{name.replace(' ', '_')}_board_spec.json"
            spec.save(spec_path)
            outputs.append(str(spec_path.relative_to(output_dir)))

            meshes_by_slot = g8b.spec_to_meshes(
                spec,
                shrink=shrink,
                include_apriltag=bool(include_apriltag),
                include_side_triangles=bool(include_side_triangles),
                profile=profile,
            )
            out_3mf = g8b.export_standard_3mf(output_dir, spec, meshes_by_slot, profile=profile)
            outputs.append(str(out_3mf.relative_to(output_dir)))
            logger.info(f"[OK] {name}: 3mf={out_3mf.name}")

            if analyze_3mf_lib3mf is not None:
                try:
                    analyze_3mf_lib3mf(Path(out_3mf))
                except Exception as e:
                    logger.error(f"[错误] 3MF导出后分析失败: {e}")
                    import traceback

                    traceback.print_exc()
                    raise
        
        return outputs, recipes

    output_files, all_recipes = generate_to_out(
        num_boards,
        shrink,
        out_dir,
        include_apriltag=bool(include_apriltag),
        include_side_triangles=bool(include_side_triangles),
        profile=profile,
    )
    
    # 写入 Manifest
    write_manifest(
        output_dir=out_dir,
        version=VERSION,
        inputs=[],
        outputs=output_files,
        params={
            "num_boards": num_boards,
            "shrink": shrink,
            "include_apriltag": bool(include_apriltag),
            "include_side_triangles": bool(include_side_triangles),
            "profile_name": profile.name,
            "num_colors": num_colors,
            "color_names": profile.color_names,
            "layers": g8b.DEFAULT_LAYERS,
            "cell_size": g8b.DEFAULT_CELL_SIZE
        }
    )
    
    # 输出文件位置提示
    logger.info("=" * 60)
    logger.info(f"生成完成！共 {num_boards} 个 {num_colors} 色校准板")
    logger.info(f"配置: {profile.name}")
    logger.info(f"输出目录: {out_dir.absolute()}")
    logger.info(f"可用的3MF打印文件:")
    for b_idx in range(num_boards):
        board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
        name = f"{num_colors}-Color_Board_{board_char}.3mf"
        file_path = out_dir / name
        if file_path.exists():
            logger.info(f"  - {name}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="OpenColor 校准板生成（支持任意颜色数量）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认8色配置
  pixi run p2-calib-board-gen
  
  # 使用4色RYBW配置
  pixi run p2-calib-board-gen --profile rybw
  
  # 使用自定义配置文件
  pixi run p2-calib-board-gen --config my_printer.json
  
  # 命令行直接指定3种颜色
  pixi run p2-calib-board-gen --colors "Red:255,0,0" "Green:0,255,0" "Blue:0,0,255"
  
  # 生成2个校准板
  pixi run p2-calib-board-gen --num_boards 2 --profile rgb
        """
    )
    parser.add_argument("--num_boards", type=int, default=8, help="生成的板子数量（默认8）")
    parser.add_argument("--shrink", type=float, default=0.0, help="格子缩进量（默认0.0）")
    parser.add_argument("--include_apriltag", action="store_true", help="启用色盘两侧的AprilTag")
    parser.add_argument("--include_side_triangles", action="store_true", help="启用色盘两侧白色三角形")
    
    # 颜色配置选项（互斥）
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument(
        "--profile", 
        type=str, 
        default="full_8",
        help="颜色配置名称（默认full_8）。可用: rgb, rybw, rgbw, rgbwk, full_8"
    )
    color_group.add_argument(
        "--config", 
        type=str, 
        help="自定义配置文件路径（JSON格式）"
    )
    color_group.add_argument(
        "--colors", 
        nargs="+", 
        help="自定义颜色列表（格式: 名称:R,G,B,A 或 名称:R,G,B）"
    )
    
    # 列出可用配置的选项
    parser.add_argument("--list-profiles", action="store_true", help="列出所有可用颜色配置")
    
    args = parser.parse_args()
    
    # 列出配置并退出
    if args.list_profiles:
        manager = get_profile_manager()
        print("可用颜色配置:")
        for profile_id, info in manager.get_profile_info().items():
            print(f"  {profile_id}: {info}")
        sys.exit(0)
    
    # 获取颜色配置
    profile = None
    
    if args.config:
        # 从配置文件加载
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            sys.exit(1)
        manager = get_profile_manager()
        loaded_id = manager.load_from_file(config_path)
        profile = manager.get_profile(loaded_id)
        logger.info(f"已从配置文件加载: {config_path}")
        
    elif args.colors:
        # 从命令行参数创建
        try:
            profile = create_profile_from_args(args.colors)
            logger.info(f"已从命令行创建自定义配置: {profile.num_colors}色")
        except ValueError as e:
            logger.error(f"颜色参数错误: {e}")
            sys.exit(1)
    
    # 运行生成
    run(
        num_boards=args.num_boards,
        shrink=args.shrink,
        include_apriltag=bool(args.include_apriltag),
        include_side_triangles=bool(args.include_side_triangles),
        profile=profile,
        profile_id=args.profile if profile is None else None,
    )


if __name__ == "__main__":
    main()
