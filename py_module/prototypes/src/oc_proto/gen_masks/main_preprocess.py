"""gen_masks - 图像预处理和模型加载模块

本模块提供图像预处理、模型搜索和加载功能
"""

import json
import traceback
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image

from oc_core_02.core.bitmap_pipeline import BitmapParams, _mask_transparency_and_bg
from oc_core_02.core.color_systems import ColorSystem
from oc_xgb.model_io import load_model
from oc_core_02.utils.paths import RESOURCES, get_out_dir, make_out_subdir_name_for_file

from .main_utils import _choose_preview_output_size, _clear_dir_keep_root
from .filters import apply_sharpening, _gaussian_blur_masked_rgb_u8



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _load_model_and_setup(
    src_path: Path,
    out_dir_base: Path,
    output_dir: Optional[str],
    run_id: str,
) -> tuple[Path, Path, Dict, ColorSystem, int, BitmapParams]:
    """加载模型并设置输出目录
    
    Returns:
        out_run_dir: 输出目录
        model_dir: 模型目录
        model: 模型对象
        cs: 颜色系统
        n_layers: 层数
        params: 位图参数
    """
    # 设置输出目录
    out_run_dir = out_dir_base / run_id
    if output_dir is not None:
        out_run_dir = Path(output_dir).resolve() / run_id

    try:
        out_run_dir.mkdir(parents=True, exist_ok=True)
        _clear_dir_keep_root(out_run_dir)
    except PermissionError as e:
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_run_dir = out_dir_base / f"{run_id}_run_{ts}"
        logger.warning(f"[警告] 输出目录被占用，无法清理旧文件，将改为写入新目录: {out_run_dir}，原因={e}")
        out_run_dir.mkdir(parents=True, exist_ok=True)
        _clear_dir_keep_root(out_run_dir)

    # 搜索模型目录
    prototype_dir = Path(__file__).resolve().parent
    calib_rts_root = (Path(__file__).resolve().parent.parent / "calib_color_rts" / "out").resolve()
    calib_old_root = (prototype_dir.parent.parent / "oc_prototypes_02" / "calib_color_model_fit_01").resolve()
    
    candidates: list[tuple[int, int, float, Path]] = []
    
    # 在新版 calib_color_rts 中搜索
    if calib_rts_root.exists():
        # 查找 color_model.json + phys_gpr_model.npz (GPR模型)
        for meta_path in calib_rts_root.rglob("color_model.json"):
            model_dir = meta_path.parent
            npz_path = model_dir / "phys_gpr_model.npz"
            if not npz_path.exists():
                continue
            try:
                mtime = float(meta_path.stat().st_mtime)
            except Exception:
                mtime = 0.0
            p = str(model_dir).lower()
            prefer_four_flux = 1 if "four_flux" in p else 0
            prefer_vulkan = 1 if "vulkan" in p else 0
            candidates.append((prefer_four_flux, prefer_vulkan, mtime, model_dir))
        
        # 查找 rts_model.json (RTS模型)
        for meta_path in calib_rts_root.rglob("rts_model.json"):
            model_dir = meta_path.parent
            try:
                mtime = float(meta_path.stat().st_mtime)
            except Exception:
                mtime = 0.0
            p = str(model_dir).lower()
            prefer_rts = 2  # RTS模型优先级最高
            prefer_vulkan = 1 if "vulkan" in p else 0
            candidates.append((prefer_rts, prefer_vulkan, mtime, model_dir))
    
    # 在旧版 calib_color_model_fit_01 中搜索
    if calib_old_root.exists():
        for meta_path in calib_old_root.rglob("color_model.json"):
            model_dir = meta_path.parent
            npz_path = model_dir / "phys_gpr_model.npz"
            if not npz_path.exists():
                continue
            try:
                mtime = float(meta_path.stat().st_mtime)
            except Exception:
                mtime = 0.0
            p = str(model_dir).lower()
            prefer_four_flux = 1 if "four_flux" in p else 0
            prefer_vulkan = 1 if "vulkan" in p else 0
            # 旧版优先级较低
            candidates.append((prefer_four_flux - 2, prefer_vulkan, mtime, model_dir))

    if not candidates:
        raise FileNotFoundError(f"在目录中未找到可用模型: {calib_rts_root} 或 {calib_old_root}")
    candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    model_dir = candidates[0][3]
    logger.info(f"[信息] 使用模型目录: {model_dir}")

    # 加载模型
    model = load_model(model_dir)
    cs = ColorSystem.from_material_keys(name="DynamicModelSystem", keys=model.optical.material_keys)
    n_layers = int(model.optical.n_layers)

    # 设置位图参数
    params = BitmapParams()
    params.n_layers = n_layers
    params.layer_height_mm = 0.12
    params.target_width_mm = 60.0
    params.nozzle_width_mm = 60.0 / 1920.0
    params.auto_bg_remove = False

    return out_run_dir, model_dir, model, cs, n_layers, params


def _preprocess_image(
    src_path: Path,
    input_dir: Path,
    superres_enabled: bool = True,
    superres_scale: int = 2,
    sharpening_enabled: bool = False,
    sharpening_strength: float = 1.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    """预处理图像
    
    Returns:
        rgb_u8: RGB图像
        a_u8: Alpha通道
        mask_match: 掩码
        h: 高度
        w: 宽度
    """
    try:
        pil = Image.open(str(src_path)).convert("RGBA")
    except Exception as e:
        logger.error(f"[错误] 打开输入图像失败: {e}")
        traceback.print_exc()
        raise

    logger.info("[信息] 应用镜像翻转（底面打印模式）")
    pil = pil.transpose(Image.FLIP_LEFT_RIGHT)

    if superres_enabled:
        sr_scale = max(1, int(superres_scale))
        orig_w, orig_h = pil.size
        base_max_dim = max(1, int(1920 // sr_scale))
        base_out_w, base_out_h = _choose_preview_output_size(orig_w, orig_h, max_dim=base_max_dim)
        target_w_px, target_h_px = int(base_out_w * sr_scale), int(base_out_h * sr_scale)
        logger.info(f"[预处理] 应用超分辨率: {orig_w}x{orig_h} -> {target_w_px}x{target_h_px} (倍率={sr_scale}x)")
        rgba_base = np.array(pil.resize((base_out_w, base_out_h), resample=Image.Resampling.BILINEAR), dtype=np.uint8)
        rgb_u8 = rgba_base[..., :3]
        a_u8 = rgba_base[..., 3]
        rgb_u8 = cv2.resize(rgb_u8, (target_w_px, target_h_px), interpolation=cv2.INTER_LANCZOS4)
        a_u8 = cv2.resize(a_u8, (target_w_px, target_h_px), interpolation=cv2.INTER_NEAREST)
    else:
        rgba_u8 = np.array(pil, dtype=np.uint8)
        rgb_u8 = rgba_u8[..., :3]
        a_u8 = rgba_u8[..., 3]

    if sharpening_enabled:
        logger.info(f"[预处理] 应用锐化 (强度={float(sharpening_strength)})")
        rgb_u8 = apply_sharpening(rgb_u8, float(sharpening_strength))

    rgba_match = np.zeros((int(rgb_u8.shape[0]), int(rgb_u8.shape[1]), 4), dtype=np.uint8)
    rgba_match[..., :3] = rgb_u8
    rgba_match[..., 3] = a_u8

    preprocessed_path = str((input_dir / "preprocessed.png").resolve())
    Image.fromarray(rgba_match).save(preprocessed_path)

    h, w = int(rgba_match.shape[0]), int(rgba_match.shape[1])
    logger.info(f"[信息] 预处理后尺寸: {w}x{h}")

    # 备份输入图像（统一使用PNG格式以支持RGBA）
    try:
        backup_path = input_dir / f"{src_path.stem}_source.png"
        Image.open(str(src_path)).convert("RGBA").save(backup_path)
    except Exception as e:
        logger.error(f"[错误] 备份输入图像失败: {e}")
        traceback.print_exc()
        raise

    # 生成掩码
    params = BitmapParams()
    params.n_layers = 1
    params.layer_height_mm = 0.12
    params.target_width_mm = 60.0
    params.nozzle_width_mm = 60.0 / float(max(1, w))
    params.auto_bg_remove = False

    mask_match = _mask_transparency_and_bg(rgba_match, params.alpha_threshold, params.auto_bg_remove, params.bg_tol)

    try:
        Image.fromarray(rgb_u8).save(input_dir / "01_upscaled_lanczos4.png")
    except Exception as e:
        logger.error(f"[错误] 写出预处理图失败: {e}")
        traceback.print_exc()
        raise

    try:
        rgb_guided = _gaussian_blur_masked_rgb_u8(rgb_u8, mask_match, sigma=0.8)
        Image.fromarray(rgb_guided).save(input_dir / "02_guided_filtered_upscaled.png")
    except Exception as e:
        logger.error(f"[错误] 写出引导滤波预处理图失败: {e}")
        traceback.print_exc()
        raise

    return rgb_u8, a_u8, mask_match, h, w
