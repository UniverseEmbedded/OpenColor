"""批量掩码生成 - 处理data/image中的所有图片

用法:
    pixi run python -m oc_proto.gen_masks.batch_process
"""

import sys
import traceback
from pathlib import Path

from loguru import logger as _logger
_logger.remove()
_logger.add(sys.stderr, format="<level>{message}</level>", level="INFO", colorize=True)

from oc_core_02.utils.logger import get_logger
from oc_proto.gen_masks.main import run

logger = get_logger(__name__)


def main():
    # 图片目录
    image_dir = Path("D:/pama1234/pfp/p-2026-01/OpenColor-05/data/image")

    if not image_dir.exists():
        logger.error(f"图片目录不存在: {image_dir}")
        return

    # 获取所有图片文件
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
    image_files = [
        f for f in image_dir.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    if not image_files:
        logger.error(f"在 {image_dir} 中未找到图片文件")
        return

    logger.info(f"找到 {len(image_files)} 个图片文件:")
    for img in sorted(image_files):
        logger.info(f"  - {img.name}")

    # 处理每个图片
    success_count = 0
    fail_count = 0

    for img_path in sorted(image_files):
        logger.info(f"\n{'='*70}")
        logger.info(f"开始处理: {img_path.name}")
        logger.info(f"{'='*70}")

        try:
            result = run(
                image_path=str(img_path),
                # 启用超分辨率
                superres_enabled=True,
                superres_scale=2,
                # 启用首层颜色偏向
                layer0_bias_enabled=True,
                # 后处理模式
                postprocess_mode="joint",
                # 物理尺寸参数
                board_mm=60.0,
                layer_height_mm=0.12,
            )

            if "error" in result:
                logger.error(f"处理失败: {result['error']}")
                fail_count += 1
            else:
                logger.info(f"处理完成，输出目录: {result['output_dir']}")
                success_count += 1

        except Exception as e:
            logger.error(f"处理异常: {e}")
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
