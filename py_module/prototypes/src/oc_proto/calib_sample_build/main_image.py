"""样本构建模块 - 图像处理和规格解析

本模块提供图像变换、规格文件解析等功能
"""

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from oc_core_02.utils.paths import get_out_dir, PROJECT_ROOT
from oc_calib.spec_adapter import SpecAdapter, extract_layer_sequence

from .main_utils import (
    _apply_rotation,
    _perspective_warp_bgr,
    _score_warped_corners,
    _choose_inset_mode,
    parse_roi,
)


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _load_json(path: Path) -> dict:
    """加载JSON文件"""
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _resolve_warped_image_path(
    board_dir: Path, photos_root: Path, cache_dir: Path, *, rows: int, cols: int
) -> Path | None:
    """解析变换后的图像路径"""
    warped = board_dir / "board_warped.png"
    if warped.exists():
        return warped

    warp_json = board_dir / "warp.json"
    if not warp_json.exists():
        return None

    board_name = board_dir.name
    if not board_name.startswith("Board_"):
        return None
    suffix = board_name.removeprefix("Board_")
    if not suffix:
        return None
    raw_img = photos_root / f"{suffix}.png"
    if not raw_img.exists():
        raw_img = photos_root / f"{suffix}.jpg"
    if not raw_img.exists():
        return None

    warp = _load_json(warp_json)
    points = warp.get("points")
    if not (
        isinstance(points, list)
        and len(points) == 4
        and all(isinstance(p, list) and len(p) == 2 for p in points)
    ):
        logger.error(f"[错误] warp.json 格式不正确: {warp_json}")
        return None

    dst_size = int(warp.get("dst_size") or 1000)
    rotation_count = int(warp.get("rotation_count") or 0) % 4
    point_order = str(warp.get("point_order") or "TL_TR_BR_BL")
    if point_order != "TL_TR_BR_BL":
        logger.warning(
            f"[警告] 暂未实现 point_order={point_order}，将按 TL_TR_BR_BL 处理: {warp_json}"
        )

    img_bgr = cv2.imread(str(raw_img), cv2.IMREAD_COLOR)
    if img_bgr is None:
        logger.error(f"[错误] 无法读取原始照片: {raw_img}")
        return None

    inset_mode = warp.get("inset_mode")
    if isinstance(inset_mode, bool):
        use_inset = inset_mode
    else:
        if rows == 17 and cols == 17:
            use_inset = _choose_inset_mode(
                img_bgr,
                points,
                dst_size=dst_size,
                rotation_count=rotation_count,
                rows=rows,
                cols=cols,
            )
            logger.info(
                f"[信息] 自动判定 inset_mode={use_inset} (rows={rows}, cols={cols})"
            )
        else:
            use_inset = False

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_warped = (
        cache_dir
        / f"{board_dir.name}_board_warped_dst{dst_size}_rot{rotation_count}_inset{int(use_inset)}_r{rows}c{cols}.png"
    )
    if (
        out_warped.exists()
        and out_warped.stat().st_mtime >= warp_json.stat().st_mtime
        and out_warped.stat().st_mtime >= raw_img.stat().st_mtime
    ):
        return out_warped

    warped_bgr = _perspective_warp_bgr(
        img_bgr, points, dst_size, inset_mode=use_inset, rows=rows, cols=cols
    )
    warped_bgr = _apply_rotation(warped_bgr, rotation_count)

    try:
        cv2.imwrite(str(out_warped), warped_bgr)
    except Exception as e:
        logger.error(f"[错误] 写入失败: {out_warped} ({e})")
        return None

    logger.info(
        f"[信息] 已从 {raw_img.name}+warp.json 生成输入: {out_warped} (inset_mode={use_inset}, rotation_count={rotation_count})"
    )
    return out_warped


def _resolve_board_spec_path(board_dir: Path) -> Path | None:
    """解析色盘规格文件路径"""
    spec_existing = board_dir / "board_spec.json"
    if spec_existing.exists():
        return spec_existing

    manifest_path = board_dir / "manifest.json"
    spec_name = None
    if manifest_path.exists():
        try:
            m = _load_json(manifest_path)
            spec_name = (m.get("params") or {}).get("spec")
        except Exception as e:
            logger.error(
                f"[警告] 读取 manifest.json 失败，将回退到按目录名推断 spec: {manifest_path} ({e})"
            )

    if not spec_name and board_dir.name.startswith("Board_"):
        suffix = board_dir.name.removeprefix("Board_")
        if suffix:
            spec_name = f"8-Color Board {suffix}"

    if not spec_name:
        return None

    spec_id = str(spec_name).replace(" ", "_")
    gen_dir = Path(__file__).resolve().parent.parent / "calib_board_gen"
    src = gen_dir / "out" / f"{spec_id}_board_spec.json"
    if not src.exists():
        logger.info(
            f"[信息] 未找到规格文件: {src}，正在尝试通过 calib_board_gen 生成..."
        )
        try:
            subprocess.run(
                [sys.executable, "-m", "oc_proto.calib_board_gen.main"], check=True
            )
        except Exception as e:
            logger.error(f"[错误] 生成规格文件失败: {e}")
            return None

    if not src.exists():
        return None

    return src


def ensure_board_spec(target_spec: Path):
    """确保色盘规格文件存在，必要时生成它"""
    if target_spec.exists():
        return True

    prototype_dir = Path(__file__).resolve().parent
    gen_dir = prototype_dir.parent / "calib_board_gen"
    gen_out_spec = gen_dir / "out" / target_spec.name

    if not gen_out_spec.exists():
        logger.info(f"[信息] 未找到规格文件: {gen_out_spec}，正在尝试生成...")
        try:
            cmd = [sys.executable, "-m", "oc_proto.calib_board_gen.main"]
            subprocess.run(cmd, check=True)
            logger.info("生成成功。")
        except Exception as e:
            logger.error(f"[错误] 生成规格文件失败: {e}")
            return False

    if gen_out_spec.exists():
        target_spec.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(gen_out_spec, target_spec)
        logger.info(f"[信息] 已同步规格文件: {target_spec}")
        return True

    return False


def find_latest_patched(edit_module_dir: Path) -> Path | None:
    """尝试定位最新的 observation_patched.json 文件"""
    out_dir = edit_module_dir / "out"
    if not out_dir.exists():
        return None
    candidates = list(out_dir.rglob("observation_patched.json"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]
