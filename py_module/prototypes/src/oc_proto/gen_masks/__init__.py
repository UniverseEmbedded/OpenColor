"""gen_masks - 掩码生成模块

本模块提供从输入图像生成打印掩码的完整流程。
"""

VERSION = "gen_masks"


def run(*args, **kwargs):
    from .main import run as _run

    return _run(*args, **kwargs)


def main(*args, **kwargs):
    from .main import main as _main

    return _main(*args, **kwargs)


from .filters import (
    apply_super_resolution_simple,
    apply_guided_filter_to_mask,
    apply_sharpening,
    _guided_filter_gray,
    _gaussian_blur_masked_rgb_u8,
)
from .joint_refinement import (
    joint_refinement,
    compute_boundary_mask,
    compute_perimeter_by_slot,
    compute_boundary_length,
    build_components_by_label,
    remove_small_components,
    despeckle_single_pixels,
    guided_filter,
)
from .island_suppress import (
    volumes_to_labels,
    labels_to_volumes,
    smooth_labels_by_convolution,
    smooth_labels_by_guided_filter,
    suppress_small_islands as suppress_small_islands_v2,
)
from .optimizer import (
    optimize_first_layer_color,
    _bias_first_print_layer_to_target,
    compute_color_distance,
    find_closest_palette_color,
    quantize_to_palette,
)
from .stats import (
    compute_layer_statistics,
    compute_perimeter_stats,
    compute_island_stats,
    suppress_small_islands,
    print_layer_stats,
    print_layer_perimeter_stats,
)
from .visualization import (
    _save_layer_total_contour_viz,
    _save_layer_solved_palette_viz,
    _analyze_solved_palette_vs_solver_input,
    create_layer_composite_visualization,
    create_difference_visualization,
)

__version__ = VERSION
__all__ = [
    # 主函数
    "run",
    "main",
    "VERSION",
    # 滤波
    "apply_super_resolution_simple",
    "apply_guided_filter_to_mask",
    "apply_sharpening",
    "_guided_filter_gray",
    "_gaussian_blur_masked_rgb_u8",
    # 优化
    "optimize_first_layer_color",
    "_bias_first_print_layer_to_target",
    "compute_color_distance",
    "find_closest_palette_color",
    "quantize_to_palette",
    # 联合优化
    "joint_refinement",
    "compute_boundary_mask",
    "compute_perimeter_by_slot",
    "compute_boundary_length",
    "build_components_by_label",
    "remove_small_components",
    "despeckle_single_pixels",
    "guided_filter",
    # 可视化
    "_save_layer_total_contour_viz",
    "_save_layer_solved_palette_viz",
    "_analyze_solved_palette_vs_solver_input",
    "create_layer_composite_visualization",
    "create_difference_visualization",
    # 统计
    "compute_layer_statistics",
    "compute_perimeter_stats",
    "compute_island_stats",
    "suppress_small_islands",
    "print_layer_stats",
    "print_layer_perimeter_stats",
    # 后处理
    "volumes_to_labels",
    "labels_to_volumes",
    "smooth_labels_by_convolution",
    "smooth_labels_by_guided_filter",
    "suppress_small_islands_v2",
]
