from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SDFParams:
    """SDF 算法特有参数（默认偏“稳”和“顺”，宁可略厚也不要空洞）。"""
    # SDF 平滑强度：相当于“扩散半径”。数值越大边界越顺，但也更容易吞掉细线。
    # 建议范围：1.2 ~ 2.0
    smooth_sigma: float = 1.5
    # 轮廓简化阈值（像素单位）。越大越省面、越容易损失细节。
    # 默认更保守，优先保留细节
    simplify_eps: float = 0.2
    # 清理阈值：过大会删掉细碎结构；默认尽量保留
    min_area: int = 1
    min_hole_area: int = 1
    open_radius: int = 0
    # 闭运算半径（像素）。过大会吞掉细节。默认关闭，通过 smooth_sigma 获得平滑边界。
    close_radius: int = 0
    # 轻微“膨胀”用来填补多边形化后的微小缝隙（单位：毫米）
    fill_gap_mm: float = 0.01

    # 在更高分辨率网格上计算 SDF/轮廓（缓解网格化/45°味道，并尽量保留细节）。
    # 1 = 与 nozzle 像素网格相同；推荐 2~4。
    grid_scale: int = 4

    contour_backend: str = "auto"
    vtracer_mode: str = "polygon"
    vtracer_filter_speckle: int = 4
    vtracer_segment_length: int = 4
    vtracer_corner_threshold: int = 60

    # vtracer 输入二值化阈值（当输入为浮点灰度 mask 时）
    vtracer_binarize_threshold: float = 0.5
    # vtracer 连接域过滤：移除面积小于该阈值(像素)的孤岛。0 表示自动推断。
    vtracer_min_component_area: int = 0
    # 是否执行后处理裁剪逻辑
    enable_clip_intersection: bool = True
    enable_gap_filling: bool = True
    enable_mutual_exclusion: bool = True
