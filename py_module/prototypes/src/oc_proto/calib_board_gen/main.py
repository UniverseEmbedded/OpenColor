"""
校准板生成主模块
生成8色校准板的规格文件和3MF打印文件
"""

import argparse
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

from oc_proto.calib_board_gen import generate_8color_board as g8b

from oc_core_02.utils.manifest import write_manifest
# 2. 从 common 导入工具
from oc_core_02.utils.paths import ensure_data, get_out_dir

try:
    from oc_core_02.core.model_analysis import analyze_3mf_lib3mf
except Exception as e:
    analyze_3mf_lib3mf = None
    logger.warning(f"[警告] 无法加载 3MF 分析工具，将跳过导出后分析: {e}")
    import traceback

    traceback.print_exc()

VERSION = "calib_board_gen"

def run(num_boards=8, shrink=0.0, include_apriltag=False, include_side_triangles=False):
    # 准备目录
    prototype_dir = Path(__file__).resolve().parent
    ensure_data(prototype_dir, [])
    out_dir = get_out_dir(prototype_dir)
    
    # 我们不再修改 g8b.ROOT_DIR，而是直接调用其核心函数并指定输出路径
    # 如果核心函数不支持输出路径，我们在这里实现一个适配版本
    
    def generate_to_out(num_boards, shrink, output_dir, include_apriltag, include_side_triangles):
        # 这里的逻辑是从 g8b.generate_8color_boards 适配而来的，但显式指定 output_dir
        num_cells = g8b.DATA_ROWS * g8b.DATA_COLS
        total_cells_needed = num_cells * num_boards
        recipes = g8b.build_recipe_pool(layers=g8b.DEFAULT_LAYERS, n_colors=8, target_count=total_cells_needed)

        outputs = []
        for b_idx in range(num_boards):
            board_char = chr(65 + b_idx) if b_idx < 26 else str(b_idx)
            name = f"8-Color Board {board_char}"
            start_idx = b_idx * num_cells
            recs = recipes[start_idx : start_idx + num_cells]
            
            spec = g8b.build_board_spec(name, recs, g8b.DEFAULT_GROUP_ID, b_idx)
            spec_path = output_dir / f"{name.replace(' ', '_')}_board_spec.json"
            spec.save(spec_path)
            outputs.append(str(spec_path.relative_to(output_dir)))

            meshes_by_slot = g8b.spec_to_meshes(
                spec,
                shrink=shrink,
                include_apriltag=bool(include_apriltag),
                include_side_triangles=bool(include_side_triangles),
            )
            out_3mf = g8b.export_standard_3mf(output_dir, spec, meshes_by_slot)
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

    logger.info(f"开始生成 {num_boards} 个校准板 到 {out_dir}...")
    output_files, all_recipes = generate_to_out(
        num_boards,
        shrink,
        out_dir,
        include_apriltag=bool(include_apriltag),
        include_side_triangles=bool(include_side_triangles),
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
            "layers": g8b.DEFAULT_LAYERS,
            "cell_size": g8b.DEFAULT_CELL_SIZE
        }
    )
    logger.info("生成完成。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenColor 校准板生成原型")
    parser.add_argument("--num_boards", type=int, default=8, help="生成的板子数量")
    parser.add_argument("--shrink", type=float, default=0.0, help="格子缩进量")
    parser.add_argument("--include_apriltag", action="store_true", help="启用色盘两侧的AprilTag")
    parser.add_argument("--include_side_triangles", action="store_true", help="启用色盘两侧白色三角形")
    args = parser.parse_args()
    
    run(
        num_boards=args.num_boards,
        shrink=args.shrink,
        include_apriltag=bool(args.include_apriltag),
        include_side_triangles=bool(args.include_side_triangles),
    )
