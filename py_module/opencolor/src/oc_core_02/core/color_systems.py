"""
颜色系统定义模块

定义校准板使用的多材料颜色系统，包括色盘配置、角标映射等
支持 RYBW、CMYW 等标准颜色系统
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class ColorSystem:
    """校准板和 LUT 映射流程使用的4材料颜色系统

    板几何结构：32x32 数据单元格，带1单元格边框（总计 34x34）

    角标颜色是 UI 提示，帮助用户一致地点击角落
    约定：
      - TL: 左上角 (top-left)
      - TR: 右上角 (top-right)
      - BR: 右下角 (bottom-right)
      - BL: 左下角 (bottom-left)

    `slot_names` 是预期的材料槽位顺序
    `slot_preview_rgb` 仅用于 UI 预览
    `corner_marker_by_corner` 将角落名称映射到材料槽位名称
    """

    name: str
    slot_names: List[str]
    slot_preview_rgb: Dict[str, RGB]
    corner_marker_by_corner: Dict[str, str]

    def validate(self) -> None:
        """验证颜色系统配置的完整性"""
        if len(self.slot_names) < 1:
            raise ValueError("至少需要一种材料")
        for s in self.slot_names:
            if s not in self.slot_preview_rgb:
                raise ValueError(f"槽位 '{s}' 缺少预览 RGB 值")
        for corner in ("TL", "TR", "BR", "BL"):
            if corner not in self.corner_marker_by_corner:
                raise ValueError(f"缺少角落 '{corner}' 的映射")
            slot = self.corner_marker_by_corner[corner]
            if slot not in self.slot_names:
                raise ValueError(f"角落 '{corner}' 指向未知的槽位 '{slot}'")

    @classmethod
    def from_material_keys(cls, name: str, keys: List[str]) -> ColorSystem:
        """从耗材名称列表动态构建 ColorSystem，自动匹配标准预览色"""
        preview = {
            k: STANDARD_FILAMENT_RGB.get(k.upper(), (128, 128, 128)) for k in keys
        }
        # 默认角标指向第一个耗材，确保通过验证
        corners = {c: keys[0] for c in ["TL", "TR", "BR", "BL"]} if keys else {}
        return cls(
            name=name,
            slot_names=keys,
            slot_preview_rgb=preview,
            corner_marker_by_corner=corners,
        )


STANDARD_FILAMENT_RGB: Dict[str, RGB] = {
    "BLACK": (30, 30, 30),
    "WHITE": (245, 245, 245),
    "RED": (220, 40, 40),
    "GREEN": (40, 200, 40),
    "BLUE": (40, 90, 220),
    "CYAN": (30, 180, 200),
    "MAGENTA": (200, 40, 170),
    "YELLOW": (235, 210, 30),
}


RYBW = ColorSystem(
    name="RYBW",
    slot_names=["White", "Red", "Yellow", "Blue"],
    slot_preview_rgb={
        "White": (245, 245, 245),
        "Red": (220, 40, 40),
        "Yellow": (235, 210, 30),
        "Blue": (40, 90, 220),
    },
    corner_marker_by_corner={
        "TL": "White",
        "TR": "Red",
        "BR": "Blue",
        "BL": "Yellow",
    },
)

CMYW = ColorSystem(
    name="CMYW",
    slot_names=["White", "Cyan", "Magenta", "Yellow"],
    slot_preview_rgb={
        "White": (245, 245, 245),
        "Cyan": (30, 180, 200),
        "Magenta": (200, 40, 170),
        "Yellow": (235, 210, 30),
    },
    corner_marker_by_corner={
        "TL": "White",
        "TR": "Cyan",
        "BR": "Magenta",
        "BL": "Yellow",
    },
)

ALL_SYSTEMS = {"RYBW": RYBW, "CMYW": CMYW}

RGB_CYM_WK = ColorSystem(
    name="RGB-CYM-WK",
    slot_names=["Red", "Green", "Blue", "Cyan", "Magenta", "Yellow", "White", "Black"],
    slot_preview_rgb={
        "Red": STANDARD_FILAMENT_RGB["RED"],
        "Green": STANDARD_FILAMENT_RGB["GREEN"],
        "Blue": STANDARD_FILAMENT_RGB["BLUE"],
        "Cyan": STANDARD_FILAMENT_RGB["CYAN"],
        "Magenta": STANDARD_FILAMENT_RGB["MAGENTA"],
        "Yellow": STANDARD_FILAMENT_RGB["YELLOW"],
        "White": STANDARD_FILAMENT_RGB["WHITE"],
        "Black": STANDARD_FILAMENT_RGB["BLACK"],
    },
    corner_marker_by_corner={
        "TL": "White",
        "TR": "Red",
        "BR": "Blue",
        "BL": "Yellow",
    },
)

ALL_SYSTEMS["RGB-CYM-WK"] = RGB_CYM_WK

for _cs in ALL_SYSTEMS.values():
    _cs.validate()
