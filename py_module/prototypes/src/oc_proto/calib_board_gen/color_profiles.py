"""
颜色配置文件管理模块
支持默认配置、自定义配置文件和命令行覆盖
"""

from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import json


# 默认颜色配置
DEFAULT_COLOR_PROFILES: Dict[str, Dict[str, Any]] = {
    "rgb": {
        "name": "RGB三原色",
        "description": "红绿蓝三原色配置",
        "colors": {
            "Red": [255, 0, 0, 255],
            "Green": [0, 255, 0, 255],
            "Blue": [0, 0, 255, 255],
        },
        "marker_colors": {
            "TL": "Red",
            "TR": "Green",
            "BR": "Blue",
            "BL": "Red",
        }
    },
    "rybw": {
        "name": "RYBW四色",
        "description": "红黄蓝白四色配置（适合基础彩色打印）",
        "colors": {
            "Red": [255, 0, 0, 255],
            "Yellow": [255, 255, 0, 255],
            "Blue": [0, 0, 255, 255],
            "White": [255, 255, 255, 255],
        },
        "marker_colors": {
            "TL": "Blue",
            "TR": "Red",
            "BR": "Blue",
            "BL": "Yellow",
        }
    },
    "rgbw": {
        "name": "RGBW四色",
        "description": "红绿蓝白四色配置（光色混合）",
        "colors": {
            "Red": [255, 0, 0, 255],
            "Green": [0, 255, 0, 255],
            "Blue": [0, 0, 255, 255],
            "White": [255, 255, 255, 255],
        },
        "marker_colors": {
            "TL": "Blue",
            "TR": "Red",
            "BR": "Blue",
            "BL": "Green",
        }
    },
    "rgbwk": {
        "name": "RGBWK五色",
        "description": "红绿蓝白黑五色配置",
        "colors": {
            "Red": [255, 0, 0, 255],
            "Green": [0, 255, 0, 255],
            "Blue": [0, 0, 255, 255],
            "White": [255, 255, 255, 255],
            "Black": [0, 0, 0, 255],
        },
        "marker_colors": {
            "TL": "Blue",
            "TR": "Red",
            "BR": "Blue",
            "BL": "Green",
        }
    },
    "full_8": {
        "name": "完整8色",
        "description": "RGB-CYM-WK完整八色配置",
        "colors": {
            "Red": [255, 0, 0, 255],
            "Green": [0, 255, 0, 255],
            "Blue": [0, 0, 255, 255],
            "Cyan": [0, 255, 255, 255],
            "Yellow": [255, 255, 0, 255],
            "Magenta": [255, 0, 255, 255],
            "White": [255, 255, 255, 255],
            "Black": [0, 0, 0, 255],
        },
        "marker_colors": {
            "TL": "Blue",
            "TR": "Red",
            "BR": "Blue",
            "BL": "Yellow",
        }
    },
}


class ColorProfile:
    """颜色配置类"""
    
    def __init__(self, name: str, colors: Dict[str, List[int]], marker_colors: Optional[Dict[str, str]] = None):
        """
        初始化颜色配置
        
        参数:
            name: 配置名称
            colors: 颜色字典 {名称: [R, G, B, A]}
            marker_colors: 标记颜色配置 {位置: 颜色名称}
        """
        self.name = name
        self.colors = colors
        self.color_names = list(colors.keys())
        self.num_colors = len(colors)
        
        # 如果没有指定标记颜色，使用默认逻辑
        if marker_colors is None:
            self.marker_colors = self._generate_default_markers()
        else:
            # 验证标记颜色是否都在颜色列表中
            for pos, color_name in marker_colors.items():
                if color_name not in self.color_names:
                    raise ValueError(f"标记颜色 '{color_name}' 不在颜色列表中")
            self.marker_colors = marker_colors
    
    def _generate_default_markers(self) -> Dict[str, str]:
        """生成默认标记颜色配置"""
        markers = {}
        positions = ["TL", "TR", "BR", "BL"]  # 左上、右上、右下、左下
        
        for i, pos in enumerate(positions):
            # 循环使用颜色列表中的颜色
            color_idx = i % self.num_colors
            markers[pos] = self.color_names[color_idx]
        
        return markers
    
    def get_color_rgba(self, color_name: str) -> Tuple[int, int, int, int]:
        """获取颜色的RGBA值"""
        if color_name not in self.colors:
            raise ValueError(f"未知颜色: {color_name}")
        rgba = self.colors[color_name]
        return tuple(rgba)  # type: ignore
    
    def get_color_index(self, color_name: str) -> int:
        """获取颜色在列表中的索引"""
        return self.color_names.index(color_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "colors": self.colors,
            "marker_colors": self.marker_colors,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorProfile":
        """从字典创建配置"""
        return cls(
            name=data.get("name", "Custom"),
            colors=data["colors"],
            marker_colors=data.get("marker_colors"),
        )


class ColorProfileManager:
    """颜色配置管理器"""
    
    def __init__(self):
        self.profiles: Dict[str, ColorProfile] = {}
        self._load_default_profiles()
    
    def _load_default_profiles(self):
        """加载默认配置"""
        for profile_id, profile_data in DEFAULT_COLOR_PROFILES.items():
            self.profiles[profile_id] = ColorProfile(
                name=profile_data["name"],
                colors=profile_data["colors"],
                marker_colors=profile_data.get("marker_colors"),
            )
    
    def get_profile(self, profile_id: str) -> ColorProfile:
        """获取指定配置"""
        if profile_id not in self.profiles:
            available = ", ".join(self.list_profiles())
            raise ValueError(f"未知配置: {profile_id}。可用配置: {available}")
        return self.profiles[profile_id]
    
    def list_profiles(self) -> List[str]:
        """列出所有可用配置ID"""
        return list(self.profiles.keys())
    
    def get_profile_info(self) -> Dict[str, str]:
        """获取所有配置的简要信息"""
        info = {}
        for profile_id, profile in self.profiles.items():
            default_data = DEFAULT_COLOR_PROFILES.get(profile_id, {})
            desc = default_data.get("description", f"{profile.num_colors}色配置")
            info[profile_id] = f"{profile.name} ({profile.num_colors}色) - {desc}"
        return info
    
    def load_from_file(self, filepath: Path) -> str:
        """
        从JSON文件加载配置
        
        参数:
            filepath: 配置文件路径
            
        返回:
            加载的配置ID
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 支持单个配置或配置集合
        if "colors" in data:
            # 单个配置
            profile_id = filepath.stem
            self.profiles[profile_id] = ColorProfile.from_dict(data)
            return profile_id
        else:
            # 配置集合
            loaded_ids = []
            for profile_id, profile_data in data.items():
                self.profiles[profile_id] = ColorProfile.from_dict(profile_data)
                loaded_ids.append(profile_id)
            return loaded_ids[0] if len(loaded_ids) == 1 else loaded_ids[0]
    
    def save_to_file(self, profile_id: str, filepath: Path):
        """保存配置到JSON文件"""
        profile = self.get_profile(profile_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
    
    def create_custom_profile(
        self,
        profile_id: str,
        colors: Dict[str, List[int]],
        name: Optional[str] = None,
        marker_colors: Optional[Dict[str, str]] = None,
    ) -> ColorProfile:
        """
        创建自定义配置
        
        参数:
            profile_id: 配置ID
            colors: 颜色字典 {名称: [R, G, B, A]}
            name: 配置显示名称
            marker_colors: 标记颜色配置
        """
        if len(colors) < 2:
            raise ValueError("至少需要2种颜色")
        
        profile = ColorProfile(
            name=name or f"自定义{len(colors)}色",
            colors=colors,
            marker_colors=marker_colors,
        )
        self.profiles[profile_id] = profile
        return profile


# 全局配置管理器实例
_profile_manager: Optional[ColorProfileManager] = None


def get_profile_manager() -> ColorProfileManager:
    """获取全局配置管理器"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ColorProfileManager()
    return _profile_manager


def parse_color_argument(color_str: str) -> Tuple[str, List[int]]:
    """
    解析命令行颜色参数
    
    格式: "名称:R,G,B,A" 或 "名称:R,G,B" (A默认为255)
    
    示例:
        "Red:255,0,0,255"
        "Blue:0,0,255"
    """
    if ":" not in color_str:
        raise ValueError(f"颜色格式错误: {color_str}，应为 '名称:R,G,B,A'")
    
    name, rgba_str = color_str.split(":", 1)
    name = name.strip()
    
    try:
        rgba = [int(x.strip()) for x in rgba_str.split(",")]
    except ValueError:
        raise ValueError(f"RGBA值格式错误: {rgba_str}")
    
    if len(rgba) == 3:
        rgba.append(255)  # 默认不透明
    elif len(rgba) != 4:
        raise ValueError(f"RGBA需要3或4个值，得到{len(rgba)}个")
    
    # 验证值范围
    for i, v in enumerate(rgba):
        if not (0 <= v <= 255):
            label = ["R", "G", "B", "A"][i]
            raise ValueError(f"{label}值必须在0-255之间，得到{v}")
    
    return name, rgba


def create_profile_from_args(color_args: List[str], profile_name: str = "Custom") -> ColorProfile:
    """
    从命令行参数创建配置
    
    参数:
        color_args: 颜色参数字符串列表
        profile_name: 配置名称
    """
    colors = {}
    for arg in color_args:
        name, rgba = parse_color_argument(arg)
        colors[name] = rgba
    
    return ColorProfile(name=profile_name, colors=colors)
