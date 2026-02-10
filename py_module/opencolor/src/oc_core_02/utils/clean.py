"""
清理工具模块
用于清理原型模块生成的中间产物(out和data目录)
"""

import shutil
from pathlib import Path



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def clean_module(module_path: Path):
    """
    清理单个模块的中间产物 (out 和 data 目录)
    
    参数:
        module_path: 模块目录路径
    """
    for folder_name in ["out", "data"]:
        folder = module_path / folder_name
        if folder.exists() and folder.is_dir():
            logger.info(f"正在清理: {folder}")
            try:
                shutil.rmtree(folder)
            except Exception as e:
                logger.error(f"清理失败 {folder}: {e}")

def get_prototypes_dir():
    """
    获取原型模块根目录
    
    返回:
        原型模块根目录的Path对象
    """
    return Path(__file__).resolve().parents[1]

def clean_calibration():
    """
    清理校准线路的中间产物
    
    清理以下模块的out和data目录:
    - calib_board_gen: 校准板生成
    - calib_photo_warp: 照片畸变校正
    - calib_sample_build: 样本构建
    - calib_color_model_fit: 颜色模型拟合
    """
    logger.info("=== 开始清理校准线路中间产物 ===")
    root = get_prototypes_dir()
    modules = [
        "calib_board_gen",
        "calib_photo_warp",
        "calib_sample_build",
        "calib_color_model_fit"
    ]
    for m in modules:
        clean_module(root / m)
    logger.info("=== 校准线路清理完成 ===\n")

def clean_generation():
    """
    清理生成线路的中间产物
    
    清理以下模块的out和data目录:
    - gen_masks: 掩码生成
    - gen_vector: 矢量生成
    """
    logger.info("=== 开始清理生成线路中间产物 ===")
    root = get_prototypes_dir()
    modules = [
        "gen_masks",
        "gen_vector"
    ]
    for m in modules:
        clean_module(root / m)
    logger.info("=== 生成线路清理完成 ===\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="清理 OpenColor 原型中间产物")
    parser.add_argument("--type", choices=["calib", "gen", "all"], default="all", help="清理类型")
    args = parser.parse_args()

    if args.type in ["calib", "all"]:
        clean_calibration()
    if args.type in ["gen", "all"]:
        clean_generation()
