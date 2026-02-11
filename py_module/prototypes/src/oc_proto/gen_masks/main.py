"""gen_masks - 掩码生成主模块

本模块提供从输入图像生成打印掩码的完整流程，包括：
- 图像预处理（超分辨率、引导滤波、锐化）
- 颜色求解优化
- 多图层联合优化
- 后处理（卷积、引导滤波、岛屿抑制）
- 可视化和统计输出
"""

import argparse
import sys
from typing import Dict, Optional

from loguru import logger as _logger

from oc_core_02.utils.logger import get_logger

# 首先配置简洁的日志格式
_logger.remove()
_logger.add(sys.stderr, format="<level>{message}</level>", level="INFO", colorize=True)

logger = get_logger(__name__)

VERSION = "gen_masks"


def run(
    image_path: str | None = None,
    *,
    layer0_bias_enabled: bool = True,
    superres_enabled: bool = True,
    superres_scale: int = 2,
    sharpening_enabled: bool = False,
    sharpening_strength: float = 1.5,
    postprocess_mode: str = "joint",
    output_dir: Optional[str] = None,
    board_mm: float = 60.0,
    layer_height_mm: float = 0.12,
    # 首层贴近原图优化参数
    first_print_layer_bias_enabled: bool = False,
    first_print_layer_bias_slack_de76: float = 0.3,
    # 联合优化参数
    joint_l0_enabled: bool = False,
    joint_l0_use_icm: bool = True,  # 使用ICM顺序更新模式
    joint_l0_passes: int = 1,
    joint_l0_lambda_smooth: float = 0.05,
    joint_l0_color_weight: float = 3.0,
    joint_l0_slack_de76: float = 0.15,
    joint_l0_edge_beta: float = 0.0,
    joint_l0_max_candidates: int = 0,
    joint_l0_proposal_radius: int = 4,
    joint_l0_proposal_eps: float = 0.001,
    joint_l0_proposal_min_soft_margin: float = 0.02,
    joint_l0_proposal_despeckle_iters: int = 1,
    joint_l0_mix_sigma: float = 2.5,
    joint_l0_mix_weight: float = 6.0,
    joint_l0_mix_max_increase_de76: float = 0.0,
    joint_l0_mix_base_slack_de76: float = 0.0,
    joint_l0_island_weight: float = 0.35,
    joint_l0_island_alpha: float = 1.0,
    joint_l0_remove_islands_max_area_px: int = 0,
    joint_l0_remove_islands_connectivity: int = 8,
    joint_l0_remove_islands_passes: int = 1,
    # 结构保护参数
    joint_l0_structure_protect: bool = True,
    joint_l0_structure_protect_strength: float = 0.8,
    # 后处理参数
    postprocess_conv_kernel: int = 3,
    postprocess_conv_passes: int = 1,
    postprocess_conv_min_majority_frac: float = 0.52,
    postprocess_conv_min_vote_margin: int = 2,
    postprocess_guided_radius: int = 4,
    postprocess_guided_eps: float = 0.001,
    postprocess_guided_passes: int = 1,
    postprocess_guided_min_soft_margin: float = 0.02,
    postprocess_guided_despeckle_iters: int = 1,
    postprocess_island_min_area_px: int = 4,
    postprocess_island_max_gap_px: int = 0,
    postprocess_island_connectivity: int = 8,
    postprocess_island_passes: int = 1,
) -> Dict:
    from .main_runner import run as _run_impl

    kwargs = locals().copy()
    kwargs.pop("_run_impl", None)
    return _run_impl(**kwargs)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description=f"{VERSION} - 掩码生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m oc_proto.gen_masks.main
  python -m oc_proto.gen_masks.main D:\\data\\image.png
  python -m oc_proto.gen_masks.main --image-path D:\\data\\image.png
  python -m oc_proto.gen_masks.main --joint-l0-enabled --joint-l0-passes 2
        """,
    )

    parser.add_argument("image", nargs="?", help="输入图像路径(留空使用默认龙娘.png)")
    parser.add_argument(
        "--image-path",
        dest="image_path",
        type=str,
        default=None,
        help="输入图像路径(优先级高于位置参数)",
    )
    parser.add_argument(
        "--output-dir", "-o", help="输出目录(会在其下创建 <文件名>_<hash6> 子目录)"
    )
    parser.add_argument(
        "--layer0-bias-off", action="store_true", help="关闭首层颜色偏向"
    )
    parser.add_argument("--superres-off", action="store_true", help="关闭超分辨率")
    parser.add_argument("--scale", type=int, default=2, help="超分辨率缩放倍数")
    parser.add_argument("--sharpen", action="store_true", help="启用锐化")
    parser.add_argument("--sharpen-strength", type=float, default=1.5, help="锐化强度")
    parser.add_argument(
        "--postprocess",
        default="joint",
        choices=["none", "conv", "guided", "joint", "island"],
        help="后处理模式",
    )
    parser.add_argument(
        "--board-mm", type=float, default=60.0, help="物理尺寸(mm)，用于下游矢量化"
    )
    parser.add_argument(
        "--layer-height-mm", type=float, default=0.12, help="层高(mm)，用于下游导出"
    )

    # 首层贴近原图优化参数
    parser.add_argument(
        "--first-print-layer-bias", action="store_true", help="启用首层贴近原图优化"
    )
    parser.add_argument(
        "--first-print-layer-bias-slack",
        type=float,
        default=0.3,
        help="首层贴近原图优化松弛量",
    )

    # 联合优化参数（默认关闭；需要时手动打开）
    parser.add_argument(
        "--joint-l0-enabled", action="store_true", help="启用首层联合优化"
    )
    parser.add_argument(
        "--joint-l0-use-icm",
        action="store_true",
        default=True,
        help="使用ICM顺序更新模式（默认启用）",
    )
    parser.add_argument(
        "--joint-l0-use-batch", action="store_true", help="使用批量更新模式（旧版）"
    )
    parser.add_argument(
        "--joint-l0-passes", type=int, default=1, help="首层联合优化迭代次数"
    )
    parser.add_argument(
        "--joint-l0-lambda-smooth", type=float, default=0.05, help="平滑度权重"
    )
    parser.add_argument(
        "--joint-l0-color-weight", type=float, default=3.0, help="色准权重"
    )
    parser.add_argument(
        "--joint-l0-slack-de76", type=float, default=0.15, help="色差松弛量"
    )
    parser.add_argument(
        "--joint-l0-edge-beta", type=float, default=0.0, help="边缘保护系数"
    )
    parser.add_argument(
        "--joint-l0-max-candidates", type=int, default=0, help="最大候选像素数"
    )
    parser.add_argument(
        "--joint-l0-proposal-radius", type=int, default=4, help="提案生成引导滤波半径"
    )
    parser.add_argument(
        "--joint-l0-proposal-eps", type=float, default=0.001, help="提案生成引导滤波eps"
    )
    parser.add_argument(
        "--joint-l0-proposal-min-soft-margin",
        type=float,
        default=0.02,
        help="提案生成最小软边距",
    )
    parser.add_argument(
        "--joint-l0-proposal-despeckle-iters",
        type=int,
        default=1,
        help="提案生成去噪迭代次数",
    )
    parser.add_argument(
        "--joint-l0-mix-sigma", type=float, default=2.5, help="混色评估高斯核sigma"
    )
    parser.add_argument(
        "--joint-l0-mix-weight", type=float, default=6.0, help="混色差权重"
    )
    parser.add_argument(
        "--joint-l0-mix-max-increase-de76",
        type=float,
        default=0.0,
        help="混色差最大增加量",
    )
    parser.add_argument(
        "--joint-l0-mix-base-slack-de76",
        type=float,
        default=0.0,
        help="混色差基线松弛量",
    )
    parser.add_argument(
        "--joint-l0-island-weight", type=float, default=0.35, help="小色块权重"
    )
    parser.add_argument(
        "--joint-l0-island-alpha", type=float, default=1.0, help="小色块面积指数"
    )
    parser.add_argument(
        "--joint-l0-remove-islands-max-area-px",
        type=int,
        default=0,
        help="剔除小连通域最大面积",
    )
    parser.add_argument(
        "--joint-l0-remove-islands-connectivity",
        type=int,
        default=8,
        help="剔除小连通域连通性",
    )
    parser.add_argument(
        "--joint-l0-remove-islands-passes",
        type=int,
        default=1,
        help="剔除小连通域迭代次数",
    )
    # 结构保护参数
    parser.add_argument(
        "--joint-l0-structure-protect",
        action="store_true",
        default=True,
        help="启用结构保护（默认启用）",
    )
    parser.add_argument(
        "--joint-l0-structure-protect-off", action="store_true", help="关闭结构保护"
    )
    parser.add_argument(
        "--joint-l0-structure-protect-strength",
        type=float,
        default=0.8,
        help="结构保护强度(0-1)",
    )

    # 后处理参数
    parser.add_argument(
        "--postprocess-conv-kernel", type=int, default=3, help="卷积平滑核大小"
    )
    parser.add_argument(
        "--postprocess-conv-passes", type=int, default=1, help="卷积平滑迭代次数"
    )
    parser.add_argument(
        "--postprocess-conv-min-majority-frac",
        type=float,
        default=0.52,
        help="卷积平滑最小多数比例",
    )
    parser.add_argument(
        "--postprocess-conv-min-vote-margin",
        type=int,
        default=2,
        help="卷积平滑最小投票边距",
    )
    parser.add_argument(
        "--postprocess-guided-radius", type=int, default=4, help="引导滤波半径"
    )
    parser.add_argument(
        "--postprocess-guided-eps", type=float, default=0.001, help="引导滤波eps"
    )
    parser.add_argument(
        "--postprocess-guided-passes", type=int, default=1, help="引导滤波迭代次数"
    )
    parser.add_argument(
        "--postprocess-guided-min-soft-margin",
        type=float,
        default=0.02,
        help="引导滤波最小软边距",
    )
    parser.add_argument(
        "--postprocess-guided-despeckle-iters",
        type=int,
        default=1,
        help="引导滤波去噪迭代次数",
    )
    parser.add_argument(
        "--postprocess-island-min-area-px", type=int, default=4, help="小色块最小面积"
    )
    parser.add_argument(
        "--postprocess-island-max-gap-px", type=int, default=0, help="小空洞最大面积"
    )
    parser.add_argument(
        "--postprocess-island-connectivity", type=int, default=8, help="岛屿抑制连通性"
    )
    parser.add_argument(
        "--postprocess-island-passes", type=int, default=1, help="岛屿抑制迭代次数"
    )

    args = parser.parse_args()

    chosen_image = args.image_path if args.image_path else args.image

    result = run(
        image_path=chosen_image,
        layer0_bias_enabled=(not bool(args.layer0_bias_off)),
        superres_enabled=(not bool(args.superres_off)),
        superres_scale=args.scale,
        sharpening_enabled=args.sharpen,
        sharpening_strength=args.sharpen_strength,
        postprocess_mode=args.postprocess,
        output_dir=args.output_dir,
        board_mm=args.board_mm,
        layer_height_mm=args.layer_height_mm,
        first_print_layer_bias_enabled=args.first_print_layer_bias,
        first_print_layer_bias_slack_de76=args.first_print_layer_bias_slack,
        joint_l0_enabled=args.joint_l0_enabled,
        joint_l0_use_icm=(args.joint_l0_use_icm and not args.joint_l0_use_batch),
        joint_l0_passes=args.joint_l0_passes,
        joint_l0_lambda_smooth=args.joint_l0_lambda_smooth,
        joint_l0_color_weight=args.joint_l0_color_weight,
        joint_l0_slack_de76=args.joint_l0_slack_de76,
        joint_l0_edge_beta=args.joint_l0_edge_beta,
        joint_l0_max_candidates=args.joint_l0_max_candidates,
        joint_l0_proposal_radius=args.joint_l0_proposal_radius,
        joint_l0_proposal_eps=args.joint_l0_proposal_eps,
        joint_l0_proposal_min_soft_margin=args.joint_l0_proposal_min_soft_margin,
        joint_l0_proposal_despeckle_iters=args.joint_l0_proposal_despeckle_iters,
        joint_l0_mix_sigma=args.joint_l0_mix_sigma,
        joint_l0_mix_weight=args.joint_l0_mix_weight,
        joint_l0_mix_max_increase_de76=args.joint_l0_mix_max_increase_de76,
        joint_l0_mix_base_slack_de76=args.joint_l0_mix_base_slack_de76,
        joint_l0_island_weight=args.joint_l0_island_weight,
        joint_l0_island_alpha=args.joint_l0_island_alpha,
        joint_l0_remove_islands_max_area_px=args.joint_l0_remove_islands_max_area_px,
        joint_l0_remove_islands_connectivity=args.joint_l0_remove_islands_connectivity,
        joint_l0_remove_islands_passes=args.joint_l0_remove_islands_passes,
        joint_l0_structure_protect=(
            args.joint_l0_structure_protect and not args.joint_l0_structure_protect_off
        ),
        joint_l0_structure_protect_strength=args.joint_l0_structure_protect_strength,
        postprocess_conv_kernel=args.postprocess_conv_kernel,
        postprocess_conv_passes=args.postprocess_conv_passes,
        postprocess_conv_min_majority_frac=args.postprocess_conv_min_majority_frac,
        postprocess_conv_min_vote_margin=args.postprocess_conv_min_vote_margin,
        postprocess_guided_radius=args.postprocess_guided_radius,
        postprocess_guided_eps=args.postprocess_guided_eps,
        postprocess_guided_passes=args.postprocess_guided_passes,
        postprocess_guided_min_soft_margin=args.postprocess_guided_min_soft_margin,
        postprocess_guided_despeckle_iters=args.postprocess_guided_despeckle_iters,
        postprocess_island_min_area_px=args.postprocess_island_min_area_px,
        postprocess_island_max_gap_px=args.postprocess_island_max_gap_px,
        postprocess_island_connectivity=args.postprocess_island_connectivity,
        postprocess_island_passes=args.postprocess_island_passes,
    )

    if "error" in result:
        logger.error(f"[错误] 处理失败: {result['error']}")
        import sys

        sys.exit(1)
    else:
        logger.info(f"[完成] 输出目录: {result['output_dir']}")


if __name__ == "__main__":
    main()
