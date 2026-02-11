"""SDF数据准备模块 - 提供像素匹配和体积生成功能"""

from typing import Dict

import numpy as np
from PIL import Image

from oc_core_02.core.bitmap_pipeline import (
    BitmapParams,
    _mask_transparency_and_bg,
    _flatten_lut,
    match_pixels_to_lut,
    _precompute_base_m_digits,
)
from oc_core_02.core.color_systems import ColorSystem
from .sdf_types import SDFParams


def prepare_data(
    pil: Image.Image, params: BitmapParams, sdf_params: SDFParams, lut_path: str
) -> Dict:
    """准备匹配后的像素数据和预览

    Args:
        pil: 输入RGBA图像
        params: 位图参数
        sdf_params: SDF参数
        lut_path: LUT文件路径

    Returns:
        包含匹配数据的字典
    """
    grid_scale = max(1, int(getattr(sdf_params, "grid_scale", 1)))
    rgba = np.array(pil, dtype=np.uint8)

    target_w_px = max(1, int(round(params.target_width_mm / params.nozzle_width_mm)))
    aspect = rgba.shape[0] / float(rgba.shape[1])
    target_h_px = max(1, int(round(target_w_px * aspect)))

    match_w_px = max(1, int(target_w_px * grid_scale))
    match_h_px = max(1, int(target_h_px * grid_scale))

    rgba_match = np.array(
        pil.resize((match_w_px, match_h_px), resample=Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )
    mask_match = _mask_transparency_and_bg(
        rgba_match, params.alpha_threshold, params.auto_bg_remove, params.bg_tol
    )

    lut = np.load(lut_path)
    lut_flat = _flatten_lut(lut)
    rgb_match = rgba_match[..., :3].astype(np.float32)

    ys, xs = np.where(mask_match)
    if ys.size == 0:
        raise ValueError("No non-transparent pixels after masking.")

    pix = rgb_match[ys, xs]
    idxs = match_pixels_to_lut(pix, lut_flat)

    # 预览图数据
    matched_rgb_hi = np.zeros_like(rgb_match, dtype=np.uint8)
    matched_rgb_hi[ys, xs] = np.clip(lut_flat[idxs], 0, 255).astype(np.uint8)

    matched_rgb = np.array(
        Image.fromarray(matched_rgb_hi, mode="RGB").resize(
            (target_w_px, target_h_px), resample=Image.Resampling.NEAREST
        ),
        dtype=np.uint8,
    )
    mask = (
        np.array(
            Image.fromarray(mask_match.astype(np.uint8) * 255, mode="L").resize(
                (target_w_px, target_h_px), resample=Image.Resampling.NEAREST
            ),
            dtype=np.uint8,
        )
        > 0
    )

    return {
        "grid_scale": grid_scale,
        "target_w_px": target_w_px,
        "target_h_px": target_h_px,
        "match_w_px": match_w_px,
        "match_h_px": match_h_px,
        "mask_match": mask_match,
        "ys": ys,
        "xs": xs,
        "idxs": idxs,
        "matched_rgb": matched_rgb,
        "mask": mask,
    }


def generate_layer_volumes(
    params: BitmapParams,
    cs: ColorSystem,
    ys,
    xs,
    idxs,
    match_h_px,
    match_w_px,
    recipe_digits=None,
) -> Dict[str, np.ndarray]:
    """生成每一层每个 slot 的布尔体积

    Args:
        params: 位图参数
        cs: 颜色系统
        ys: Y坐标数组
        xs: X坐标数组
        idxs: 颜色索引数组
        match_h_px: 匹配高度(像素)
        match_w_px: 匹配宽度(像素)
        recipe_digits: 预计算的配方数字(可选)

    Returns:
        每个slot的体积字典 {slot_name: (n_layers, h, w) bool array}
    """
    m = len(cs.slot_names)
    if recipe_digits is not None:
        digits = recipe_digits
    else:
        digits = _precompute_base_m_digits(params.n_layers, m)

    volumes: Dict[str, np.ndarray] = {
        name: np.zeros((params.n_layers, match_h_px, match_w_px), dtype=bool)
        for name in cs.slot_names
    }

    for k in range(ys.size):
        y, x = int(ys[k]), int(xs[k])
        d = digits[int(idxs[k])]
        for z in range(params.n_layers):
            volumes[cs.slot_names[int(d[z])]][z, y, x] = True

    return volumes
