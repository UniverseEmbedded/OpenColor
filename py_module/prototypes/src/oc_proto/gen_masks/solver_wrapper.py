"""求解器包装模块 - 提供C++ Hill Climbing Solver的Python接口"""

import json
import os
import subprocess
import tempfile
from typing import Tuple, List, Dict

import numpy as np
from PIL import Image


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def solve_layer_colors_with_cpp(
    layer_idx: int,
    layer_mask_u8: np.ndarray,
    original_rgb: np.ndarray,
    candidate_colors: List[Tuple[int, int, int]],
    solver_path: str = "opencolor_solver",
    *,
    max_iterations: int = 1000,
    tolerance: float = 0.001,
    use_vulkan: bool = True,
) -> Tuple[List[Tuple[int, int, int]], Dict]:
    """
    使用C++ Hill Climbing Solver求解图层颜色

    Args:
        layer_idx: 图层索引
        layer_mask_u8: 图层掩码 (H, W) uint8
        original_rgb: 原始图像 (H, W, 3) uint8
        candidate_colors: 候选颜色列表
        solver_path: 求解器可执行文件路径
        max_iterations: 最大迭代次数
        tolerance: 收敛容差
        use_vulkan: 是否使用Vulkan加速

    Returns:
        (求解后的颜色列表, 统计信息字典)
    """
    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 保存输入数据
        mask_path = os.path.join(tmpdir, f"layer_{layer_idx}_mask.png")
        image_path = os.path.join(tmpdir, f"layer_{layer_idx}_image.png")
        config_path = os.path.join(tmpdir, f"layer_{layer_idx}_config.json")
        output_path = os.path.join(tmpdir, f"layer_{layer_idx}_output.json")

        # 保存掩码和图像
        Image.fromarray(layer_mask_u8).save(mask_path)
        Image.fromarray(original_rgb).save(image_path)

        # 创建配置文件
        config = {
            "layer_idx": layer_idx,
            "mask_path": mask_path,
            "image_path": image_path,
            "candidate_colors": candidate_colors,
            "max_iterations": max_iterations,
            "tolerance": tolerance,
            "use_vulkan": use_vulkan,
            "output_path": output_path,
        }

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        # 调用C++求解器
        try:
            result = subprocess.run(
                [solver_path, config_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )

            if result.returncode != 0:
                logger.error(f"[警告] 求解器返回错误码 {result.returncode}")
                logger.warning(f"[警告] stderr: {result.stderr}")
                return candidate_colors, {"error": result.stderr}

            # 读取输出
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    output = json.load(f)

                solved_colors = [tuple(c) for c in output.get("solved_colors", [])]
                stats = output.get("stats", {})

                return solved_colors, stats
            else:
                logger.warning(f"[警告] 求解器未生成输出文件")
                return candidate_colors, {"error": "No output file"}

        except subprocess.TimeoutExpired:
            logger.error(f"[错误] 求解器超时")
            return candidate_colors, {"error": "Timeout"}
        except Exception as e:
            logger.error(f"[错误] 调用求解器时发生异常: {e}")
            return candidate_colors, {"error": str(e)}


def solve_all_layers_with_cpp(
    layers_masks: List[np.ndarray],
    original_rgb: np.ndarray,
    layers_candidate_colors: List[List[Tuple[int, int, int]]],
    solver_path: str = "opencolor_solver",
    *,
    max_iterations: int = 1000,
    use_vulkan: bool = True,
) -> Tuple[List[List[Tuple[int, int, int]]], List[Dict]]:
    """
    求解所有图层的颜色

    Args:
        layers_masks: 图层掩码列表
        original_rgb: 原始图像
        layers_candidate_colors: 每层候选颜色列表
        solver_path: 求解器路径
        max_iterations: 最大迭代次数
        use_vulkan: 是否使用Vulkan加速

    Returns:
        (所有层的求解颜色, 所有层的统计信息)
    """
    all_solved_colors = []
    all_stats = []

    for i, (mask, candidates) in enumerate(zip(layers_masks, layers_candidate_colors)):
        logger.info(f"[求解器] 正在求解图层 {i}...")

        solved, stats = solve_layer_colors_with_cpp(
            i,
            mask,
            original_rgb,
            candidates,
            solver_path,
            max_iterations=max_iterations,
            use_vulkan=use_vulkan,
        )

        all_solved_colors.append(solved)
        all_stats.append(stats)

        if "error" not in stats:
            logger.info(f"[求解器] 图层 {i} 求解完成，得到 {len(solved)} 种颜色")

    return all_solved_colors, all_stats


def check_solver_available(solver_path: str = "opencolor_solver") -> bool:
    """
    检查求解器是否可用

    Args:
        solver_path: 求解器路径

    Returns:
        是否可用
    """
    try:
        result = subprocess.run(
            [solver_path, "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except:
        return False
