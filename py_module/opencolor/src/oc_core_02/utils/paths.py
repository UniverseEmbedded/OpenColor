"""
路径管理模块
定义项目根目录、测试资源路径
提供资源复制和输出目录管理功能
"""

import hashlib
import shutil
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 项目根目录 (OpenColor)
PROJECT_ROOT = Path(__file__).resolve().parents[5]

# 测试资源原始路径
RESOURCES = {
    "icon_svg": PROJECT_ROOT / "data" / "icon.svg",
    "img_sbare": PROJECT_ROOT / "data" / "image" / "sbare女装.png",
    "img_outline": PROJECT_ROOT / "data" / "image" / "描边龙娘.png",
    "img_particle": PROJECT_ROOT / "data" / "image" / "粒子生命概念图.png",
    "img_longyunqing": PROJECT_ROOT / "data" / "image" / "长云清.jpg",
    "img_dragon_girl": PROJECT_ROOT / "data" / "image" / "龙娘.png",
    "photo_01b": PROJECT_ROOT / "data" / "calibration" / "photos" / "01.jpg",
    "photo_01": PROJECT_ROOT / "cache" / "色盘" / "01.jpg",
    "photo_02": PROJECT_ROOT / "data" / "calibration" / "photos" / "02.jpg",
    "spec_b": PROJECT_ROOT
    / "out_calibration_board_8"
    / "8-Color_Board_B_board_spec.json",
    "spec_a": PROJECT_ROOT
    / "out_calibration_board_8"
    / "8-Color_Board_A_board_spec.json",
}


def ensure_data(prototype_dir, resource_keys):
    """
    确保原型目录下的 data/ 文件夹中包含指定的资源。
    """
    data_dir = Path(prototype_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    for key in resource_keys:
        if key in RESOURCES:
            src = RESOURCES[key]
            dst = data_dir / src.name
            # 如果是图片或 spec，且用户希望直接使用，我们可以在这里做特殊处理
            # 但为了保持兼容性，这里仍然保留复制逻辑，只是如果目标已存在且源更新了，则覆盖
            if src.exists():
                if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                    logger.info(f"复制/更新资源: {src} -> {dst}")
                    shutil.copy2(src, dst)
        else:
            logger.warning(f"警告: 未找到资源键 '{key}'")
    return data_dir


def get_out_dir(prototype_dir):
    """
    获取输出目录
    """
    out_dir = Path(prototype_dir) / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def calc_file_hash6(path: Path) -> str:
    """计算文件内容哈希(前6位)"""
    p = Path(path)
    h = hashlib.sha1()
    with open(p, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:6]


def make_out_subdir_name_for_file(path: Path) -> str:
    """使用文件名 + 6位hash 生成 out 子目录名"""
    p = Path(path)
    return f"{p.stem}_{calc_file_hash6(p)}"


def select_latest_subdir(
    base_dir: Path, *, required_relpaths: list[str] | None = None
) -> Path | None:
    """在 base_dir 下选择最近修改的子目录（可要求包含指定文件）"""
    d = Path(base_dir)
    if not d.exists():
        return None

    best: Path | None = None
    best_mtime = -1.0

    for child in d.iterdir():
        if not child.is_dir():
            continue

        if required_relpaths:
            ok = True
            for rp in required_relpaths:
                if not (child / rp).exists():
                    ok = False
                    break
            if not ok:
                continue

        try:
            mtime = float(child.stat().st_mtime)
        except OSError:
            continue

        if mtime > best_mtime:
            best = child
            best_mtime = mtime

    return best
