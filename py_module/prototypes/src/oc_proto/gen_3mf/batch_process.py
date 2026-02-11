"""批量3MF导出 - 处理gen_vector/out中的所有矢量化结果"""

from pathlib import Path

from oc_core_02.utils.logger import get_logger
from oc_core_02.utils.paths import get_out_dir
from oc_proto.gen_3mf.main import run as run_3mf

logger = get_logger(__name__)


def main():
    # gen_vector 输出目录
    gen_vector_out_dir = Path(
        "D:/pama1234/pfp/p-2026-01/OpenColor-05/py_module/prototypes/src/oc_proto/gen_vector/out"
    )

    if not gen_vector_out_dir.exists():
        logger.error("gen_vector 输出目录不存在: {}", gen_vector_out_dir)
        return

    # 查找所有有效的矢量运行子目录
    def _is_valid_vector_run_dir(d: Path) -> bool:
        """检查目录是否是有效的 gen_vector 输出目录"""
        # 检查是否有 manifest.json 或 vtracer_manifest.json
        manifest_exists = (d / "manifest.json").exists() or (
            d / "vtracer_manifest.json"
        ).exists()
        polys_dir = d / "04_polys"
        return manifest_exists and polys_dir.exists() and polys_dir.is_dir()

    run_dirs = [
        d
        for d in gen_vector_out_dir.iterdir()
        if d.is_dir() and _is_valid_vector_run_dir(d)
    ]

    if not run_dirs:
        logger.error("在 {} 中未找到有效的矢量运行目录", gen_vector_out_dir)
        return

    logger.info("找到 {} 个需要处理的运行目录:", len(run_dirs))
    for run_dir in sorted(run_dirs):
        logger.info("  - {}", run_dir.name)

    # 处理每个运行目录
    success_count = 0
    fail_count = 0
    skip_count = 0

    prototype_dir = Path(__file__).resolve().parent
    out_dir_base = get_out_dir(prototype_dir)

    for run_dir in sorted(run_dirs):
        run_id = run_dir.name
        logger.info("\n{}", "=" * 70)
        logger.info("开始处理: {}", run_id)
        logger.info("{}", "=" * 70)

        out_3mf = (out_dir_base / run_id / "05_models" / "model_combined.3mf").resolve()
        if out_3mf.exists():
            logger.info("[gen_3mf] 已存在 3MF，跳过: {} -> {}", run_id, out_3mf)
            skip_count += 1
            continue

        try:
            run_3mf(
                poly_input_dir=str(run_dir),
                use_cpp=True,
                progress=True,
                jobs=0,  # 自动
                repair=True,
                simplify=True,
                voxel_repair=False,
                export_stl=True,
                export_3mf=True,
                use_cpp_union=True,
            )
            logger.info("[gen_3mf] 处理完成: {}", run_id)
            success_count += 1
        except Exception as e:
            logger.error("[gen_3mf] 处理失败: {}, 错误: {}", run_id, e)
            fail_count += 1
            raise

    # 汇总报告
    logger.info("\n{}", "=" * 70)
    logger.info("批量处理完成!")
    logger.info("{}", "=" * 70)
    logger.info("成功={}, 失败={}", success_count, fail_count)
    logger.info("跳过={}", skip_count)
    logger.info("{}", "=" * 70)


if __name__ == "__main__":
    main()
