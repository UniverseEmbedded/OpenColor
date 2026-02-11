import shutil
import tempfile
from pathlib import Path

import numpy as np

from oc_core_02.core.color_systems import ALL_SYSTEMS
from oc_core_02.core.mcrt_engine import OpticalProps


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _tmpdir() -> Path:
    """创建临时目录"""
    return Path(tempfile.mkdtemp(prefix="lumenboard_"))


def _zip_dir(dir_path: Path, zip_base_name: str) -> Path:
    """将目录压缩为zip文件"""
    zip_path = dir_path.parent / f"{zip_base_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(dir_path))
    return zip_path


# 从 forward_mc.py 整理的基础材料参数 (RGB 简化版)
DEFAULT_OPTICAL_DATA = {
    "White": {
        "mu_a": [0.10, 0.10, 0.10],
        "mu_s": [6.0, 6.0, 6.0],
        "g": 0.85,
        "n": 1.50,
    },
    "Red": {"mu_a": [0.35, 2.2, 2.6], "mu_s": [3.0, 3.0, 3.0], "g": 0.85, "n": 1.50},
    "Yellow": {
        "mu_a": [0.45, 0.45, 2.4],
        "mu_s": [3.0, 3.0, 3.0],
        "g": 0.85,
        "n": 1.50,
    },
    "Blue": {"mu_a": [2.6, 2.2, 0.35], "mu_s": [3.0, 3.0, 3.0], "g": 0.85, "n": 1.50},
    "Green": {"mu_a": [2.2, 0.35, 2.2], "mu_s": [3.0, 3.0, 3.0], "g": 0.85, "n": 1.50},
    "Cyan": {"mu_a": [2.4, 0.50, 0.50], "mu_s": [3.0, 3.0, 3.0], "g": 0.85, "n": 1.50},
    "Magenta": {
        "mu_a": [0.50, 2.4, 0.50],
        "mu_s": [3.0, 3.0, 3.0],
        "g": 0.85,
        "n": 1.50,
    },
    "Black": {"mu_a": [8.0, 8.0, 8.0], "mu_s": [2.0, 2.0, 2.0], "g": 0.80, "n": 1.50},
}


def get_material_props(name: str, bins: int = 31) -> OpticalProps:
    data = DEFAULT_OPTICAL_DATA.get(name, DEFAULT_OPTICAL_DATA["White"])
    # 将 RGB 扩展到 spectral bins
    # 这里做一个非常简化的插值：前 1/3 是 B, 中间 1/3 是 G, 后 1/3 是 R
    mu_a = np.zeros(bins)
    mu_s = np.zeros(bins)
    rgb_a = data["mu_a"]  # [R, G, B]
    rgb_s = data["mu_s"]

    # 粗略映射: bins 从 400nm(B) 到 700nm(R)
    mu_a[: bins // 3] = rgb_a[2]
    mu_a[bins // 3 : 2 * bins // 3] = rgb_a[1]
    mu_a[2 * bins // 3 :] = rgb_a[0]

    mu_s[: bins // 3] = rgb_s[2]
    mu_s[bins // 3 : 2 * bins // 3] = rgb_s[1]
    mu_s[2 * bins // 3 :] = rgb_s[0]

    return OpticalProps(mu_a=mu_a, mu_s=mu_s, g=data["g"], n=data["n"])


def _build_material_props(board_spec, color_system_name: str):
    idx_to_name = {}
    max_idx = -1
    if board_spec is not None:
        for recipe in board_spec.cell_map.values():
            layers = recipe.get("layers")
            slot_names = recipe.get("slot_names")
            if not layers or not slot_names:
                continue
            max_idx = max(max_idx, max(layers))
            for i, idx in enumerate(layers):
                if i >= len(slot_names):
                    continue
                name = slot_names[i]
                if idx not in idx_to_name:
                    idx_to_name[idx] = name
                elif idx_to_name[idx] != name:
                    logger.error(
                        f"[错误] BoardSpec 材料索引冲突：{idx} -> {idx_to_name[idx]} / {name}"
                    )

    if max_idx >= 0:
        slot_names = []
        mat_props = []
        for idx in range(max_idx + 1):
            name = idx_to_name.get(idx, "White")
            slot_names.append(name)
            mat_props.append(get_material_props(name))
        return mat_props, slot_names

    if color_system_name in ALL_SYSTEMS:
        cs = ALL_SYSTEMS[color_system_name]
        return [get_material_props(name) for name in cs.slot_names], cs.slot_names

    return None, None
