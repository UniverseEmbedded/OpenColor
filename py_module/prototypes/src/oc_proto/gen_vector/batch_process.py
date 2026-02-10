"""批量矢量化 - 处理gen_masks/out中的所有掩码结果

用法:
    pixi run python -m oc_proto.gen_vector.batch_process
"""

import sys
import traceback
from pathlib import Path

from loguru import logger as _logger
_logger.remove()
_logger.add(sys.stderr, format="<level>{message}</level>", level="INFO", colorize=True)

from oc_core_02.utils.logger import get_logger
from oc_proto.gen_vector.main import run as run_vector

logger = get_logger(__name__)


def main():
    # gen_masks 输出目录
    gen_masks_out_dir = Path("D:/pama1234/pfp/p-2026-01/OpenColor-05/py_module/prototypes/src/oc_proto/gen_masks/out")

    if not gen_masks_out_dir.exists():
        logger.error(f"gen_masks 输出目录不存在: {gen_masks_out_dir}")
        return

    # 查找所有有效的掩码运行子目录
    def _is_valid_mask_run_dir(d: Path) -> bool:
        """检查目录是否是有效的 gen_masks 输出目录"""
        manifest_path = d / "mask_manifest.json"
        masks_dir = d / "02_masks"
        return manifest_path.exists() and masks_dir.exists() and masks_dir.is_dir()

    run_dirs = [d for d in gen_masks_out_dir.iterdir() if d.is_dir() and _is_valid_mask_run_dir(d)]

    if not run_dirs:
        logger.error(f"在 {gen_masks_out_dir} 中未找到有效的掩码运行目录")
        return

    logger.info(f"找到 {len(run_dirs)} 个需要处理的运行目录:")
    for run_dir in sorted(run_dirs):
        logger.info(f"  - {run_dir.name}")

    # 处理每个运行目录
    success_count = 0
    fail_count = 0

    for run_dir in sorted(run_dirs):
        run_id = run_dir.name
        logger.info(f"\n{'='*70}")
        logger.info(f"开始处理: {run_id}")
        logger.info(f"{'='*70}")

        try:
            run_vector(
                mask_input_dir=str(run_dir),
                resample=True,
                impl="cpp",
                progress=True,
                jobs=0,  # 自动
                union_jobs=0,  # 自动
                preview_4x=False,
                vector_backend="cv2",
                cv2_simplify_mm=0.05,
                cv2_min_area_px=4,
                reconcile=True,
                reconcile_scale=2,
                reconcile_cv2_simplify_mm=0.05,
                svg_simplify_level=3,
            )
            logger.info(f"[gen_vector] 处理完成: {run_id}")
            success_count += 1
        except Exception as e:
            logger.error(f"[gen_vector] 处理失败: {run_id}, 错误: {e}")
            traceback.print_exc()
            fail_count += 1

    # 汇总报告
    logger.info(f"\n{'='*70}")
    logger.info(f"批量处理完成!")
    logger.info(f"{'='*70}")
    logger.info(f"成功={success_count}, 失败={fail_count}")
    logger.info(f"{'='*70}")


if __name__ == "__main__":
    main()
