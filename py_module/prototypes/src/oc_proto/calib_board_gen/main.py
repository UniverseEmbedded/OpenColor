"""
校准板生成主模块
生成多色校准板规格文件和3MF打印文件

使用示例:
    pixi run p2-calib-board-gen

    # 生成2个校准板
    pixi run p2-calib-board-gen --num_boards 2

    # 使用4色配置
    pixi run p2-calib-board-gen --profile rybw

    # 使用自定义配置文件
    pixi run p2-calib-board-gen --profile-file my_colors.json
"""

import argparse
import sys
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

from oc_proto.calib_board_gen import generate_board as gen_bd
from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager,
    ColorProfile,
    parse_color_argument,
    create_profile_from_args,
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


def get_default_border_color(profile: ColorProfile) -> str:
    """
    根据颜色配置获取默认边框颜色

    参数:
        profile: 颜色配置

    返回:
        边框颜色名称
    """
    n_colors = profile.num_colors
    slot_names = profile.color_names

    # 3色配置用Green，其它用White
    if n_colors == 3 and "Green" in slot_names:
        return "Green"
    elif "White" in slot_names:
        return "White"
    else:
        return slot_names[0] if slot_names else None


def run(
    num_boards: int = 8,
    shrink: float = 0.0,
    profile: ColorProfile = None,
    layer_height_mm: float = None,
    cell_size_mm: float = None,
    data_rows: int = None,
    data_cols: int = None,
):
    """
    运行校准板生成

    参数:
        num_boards: 生成的板子数量
        shrink: 格子缩进量
        profile: 颜色配置，默认为8色配置
        layer_height_mm: 层高（毫米），默认使用 generate_board.DEFAULT_LAYER_HEIGHT
        cell_size_mm: 格子尺寸（毫米），默认使用 generate_board.DEFAULT_CELL_SIZE
        data_rows: 数据区域行数，默认使用 generate_board.DATA_ROWS
        data_cols: 数据区域列数，默认使用 generate_board.DATA_COLS
    """
    # 使用默认8色配置
    if profile is None:
        manager = get_profile_manager()
        profile = manager.get_profile("full_8")

    n_colors = profile.num_colors
    slot_names = profile.color_names
    slot_colors = {name: profile.get_color_rgba(name) for name in slot_names}
    marker_colors = profile.marker_colors
    default_border_color = get_default_border_color(profile)

    # 准备目录
    prototype_dir = Path(__file__).resolve().parent
    ensure_data(prototype_dir, [])
    out_dir = get_out_dir(prototype_dir)

    # 使用默认层高如果未指定
    if layer_height_mm is None:
        layer_height_mm = gen_bd.DEFAULT_LAYER_HEIGHT

    # 使用默认格子尺寸如果未指定
    if cell_size_mm is None:
        cell_size_mm = gen_bd.DEFAULT_CELL_SIZE

    # 使用默认行列数如果未指定
    if data_rows is None:
        data_rows = gen_bd.DATA_ROWS
    if data_cols is None:
        data_cols = gen_bd.DATA_COLS

    logger.info(f"开始生成 {num_boards} 个 {n_colors} 色校准板 到 {out_dir}...")
    logger.info(f"颜色配置: {profile.name} ({', '.join(slot_names)})")
    logger.info(f"层高: {layer_height_mm}mm")
    logger.info(f"格子尺寸: {cell_size_mm}mm")
    logger.info(f"数据区域: {data_rows}行 x {data_cols}列")

    def generate_to_out(
        num_boards,
        shrink,
        output_dir,
        layer_height_mm,
        cell_size_mm,
        data_rows,
        data_cols,
    ):
        num_cells = data_rows * data_cols
        total_cells_needed = num_cells * num_boards
        recipes = gen_bd.build_recipe_pool(
            layers=gen_bd.DEFAULT_LAYERS,
            n_colors=n_colors,
            target_count=total_cells_needed,
        )

        outputs = []
        for b_idx in range(num_boards):
            board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
            name = f"{n_colors}-Color Board {board_char}"
            start_idx = b_idx * num_cells
            end_idx = start_idx + num_cells

            # 如果起始位置已超出配方池范围，停止生成更多板子
            if start_idx >= len(recipes):
                logger.info(f"配方池已耗尽，停止生成后续板子（已生成 {b_idx} 个板子）")
                break

            # 如果结束位置超出配方池范围，只使用剩余配方
            if end_idx > len(recipes):
                recs = recipes[start_idx:]
            else:
                recs = recipes[start_idx:end_idx]

            spec = gen_bd.build_board_spec(
                name, recs, gen_bd.DEFAULT_GROUP_ID, b_idx, slot_names=slot_names, layer_height_mm=layer_height_mm, cell_size_mm=cell_size_mm, data_rows=data_rows, data_cols=data_cols
            )
            spec_path = output_dir / f"{name.replace(' ', '_')}_board_spec.json"
            spec.save(spec_path)
            outputs.append(str(spec_path.relative_to(output_dir)))

            meshes_by_slot = gen_bd.spec_to_meshes(
                spec,
                shrink=shrink,
                slot_names=slot_names,
                marker_colors=marker_colors,
                default_border_color=default_border_color,
                cell_size_mm=cell_size_mm,
            )
            out_3mf = gen_bd.export_standard_3mf(
                output_dir, spec, meshes_by_slot,
                slot_names=slot_names,
                slot_colors=slot_colors,
            )
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
        layer_height_mm=layer_height_mm,
        cell_size_mm=cell_size_mm,
        data_rows=data_rows,
        data_cols=data_cols,
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
            "num_colors": n_colors,
            "color_names": slot_names,
            "color_profile": profile.name,
            "layers": gen_bd.DEFAULT_LAYERS,
            "cell_size": cell_size_mm,
            "layer_height_mm": layer_height_mm,
        },
    )

    # 输出文件位置提示
    logger.info("=" * 60)
    logger.info(f"生成完成！共 {num_boards} 个 {n_colors} 色校准板")
    logger.info(f"输出目录: {out_dir.absolute()}")
    logger.info(f"可用的3MF打印文件:")
    for b_idx in range(num_boards):
        board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
        name = f"{n_colors}-Color_Board_{board_char}.3mf"
        file_path = out_dir / name
        if file_path.exists():
            logger.info(f"  - {name}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description=f"OpenColor 多色校准板生成 (支持3-8色)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置生成8色校准板
  pixi run p2-calib-board-gen

  # 生成2个校准板
  pixi run p2-calib-board-gen --num_boards 2

  # 使用4色配置(Red, Yellow, Blue, White)
  pixi run p2-calib-board-gen --profile rybw

  # 使用3色配置(Red, Green, Blue)
  pixi run p2-calib-board-gen --profile rgb

  # 从配置文件加载自定义颜色
  pixi run p2-calib-board-gen --profile-file my_colors.json

  # 命令行指定颜色
  pixi run p2-calib-board-gen --colors "Red:255,0,0" "Green:0,255,0" "Blue:0,0,255"

可用预设配置:
  rgb      - RGB三原色(3色)
  rybw     - RYBW四色(4色)
  rgbw     - RGBW四色(4色)
  rgbwk    - RGBWK五色(5色)
  full_8   - 完整8色(8色，默认)
        """,
    )
    parser.add_argument(
        "--num_boards", type=int, default=8, help="生成的板子数量（默认8）"
    )
    parser.add_argument(
        "--shrink", type=float, default=0.0, help="格子缩进量（默认0.0）"
    )
    parser.add_argument(
        "--profile", type=str, default="full_8",
        help="使用预设颜色配置（默认full_8，可选：rgb, rybw, rgbw, rgbwk, full_8）"
    )
    parser.add_argument(
        "--profile-file", type=str, default=None,
        help="从JSON文件加载自定义颜色配置"
    )
    parser.add_argument(
        "--colors", type=str, nargs="+", default=None,
        help="命令行指定颜色，格式：'名称:R,G,B,A' 或 '名称:R,G,B'"
    )
    parser.add_argument(
        "--layer-height", type=float, default=None,
        help=f"层高（毫米，默认 {gen_bd.DEFAULT_LAYER_HEIGHT}）"
    )
    parser.add_argument(
        "--cell-size", type=float, default=None,
        help=f"格子尺寸（毫米，默认 {gen_bd.DEFAULT_CELL_SIZE}）"
    )
    parser.add_argument(
        "--rows", type=int, default=None,
        help=f"数据区域行数（默认 {gen_bd.DATA_ROWS}）"
    )
    parser.add_argument(
        "--cols", type=int, default=None,
        help=f"数据区域列数（默认 {gen_bd.DATA_COLS}）"
    )

    args = parser.parse_args()

    # 获取颜色配置
    profile = None

    if args.colors:
        # 从命令行参数创建配置
        try:
            profile = create_profile_from_args(args.colors, profile_name="Custom")
            logger.info(f"使用命令行指定的颜色: {profile.color_names}")
        except Exception as e:
            logger.error(f"[错误] 解析颜色参数失败: {e}")
            sys.exit(1)
    elif args.profile_file:
        # 从文件加载配置
        try:
            manager = get_profile_manager()
            profile_id = manager.load_from_file(Path(args.profile_file))
            profile = manager.get_profile(profile_id)
            logger.info(f"从文件加载配置: {args.profile_file} -> {profile.name}")
        except Exception as e:
            logger.error(f"[错误] 加载配置文件失败: {e}")
            sys.exit(1)
    else:
        # 使用预设配置
        try:
            manager = get_profile_manager()
            profile = manager.get_profile(args.profile)
            logger.info(f"使用预设配置: {profile.name}")
        except Exception as e:
            logger.error(f"[错误] 未知配置 '{args.profile}': {e}")
            logger.info(f"可用配置: {', '.join(get_profile_manager().list_profiles())}")
            sys.exit(1)

    # 运行生成
    run(
        num_boards=args.num_boards,
        shrink=args.shrink,
        profile=profile,
        layer_height_mm=args.layer_height,
        cell_size_mm=args.cell_size,
        data_rows=args.rows,
        data_cols=args.cols,
    )


if __name__ == "__main__":
    main()
