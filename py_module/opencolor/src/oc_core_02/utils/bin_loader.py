import os
import platform
import sys
from pathlib import Path
from typing import Optional

from oc_core_02.utils import get_logger

logger = get_logger(__name__)


def _find_module_in_dir(directory: Path, name: str) -> Optional[Path]:
    """在指定目录中查找 C++ 扩展模块，支持多种命名格式"""
    if not directory.exists():
        return None

    # Windows 上 .pyd 文件可能有版本后缀，如 opencolor_geometry.cp312-win_amd64.pyd
    if platform.system() == "Windows":
        # 首先尝试精确匹配
        exact = directory / f"{name}.pyd"
        if exact.exists():
            return exact
        # 然后尝试通配匹配
        for f in directory.glob(f"{name}*.pyd"):
            return f
    else:
        # Linux/Mac
        for ext in [".so", f"{name}.so"]:
            p = directory / f"{name}{ext}"
            if p.exists():
                return p
        # 尝试通配匹配
        for f in directory.glob(f"{name}*.so"):
            return f
    return None


def get_binary_path(name: str) -> Optional[Path]:
    """
    寻找 C++ 扩展二进制文件的路径。
    优先级：
    1. 环境变量 OC_BIN_DIR
    2. 当前文件同级的 bin/ 目录
    3. 项目根目录下的 cpp_module/build/Release (仅限开发模式)
    """
    # 1. 环境变量优先
    env_dir = os.environ.get("OC_BIN_DIR")
    if env_dir:
        p = _find_module_in_dir(Path(env_dir), name)
        if p:
            return p

    # 2. 核心库自带的 bin 目录
    current_bin = Path(__file__).resolve().parent.parent / "bin"
    p = _find_module_in_dir(current_bin, name)
    if p:
        return p

    # 3. 开发环境下的构建目录
    # 尝试寻找项目根目录或包含 cpp_module 的父目录
    root = Path(__file__).resolve()
    for parent in [root] + list(root.parents):
        cpp_root = parent / "cpp_module" / "build"
        if not cpp_root.exists():
            continue

        for config in ["Release", "Debug"]:
            build_dir = cpp_root / config
            p = _find_module_in_dir(build_dir, name)
            if p:
                return p

        p = _find_module_in_dir(cpp_root, name)
        if p:
            return p

    return None


def import_cpp_extension(name: str):
    """
    安全地导入 C++ 扩展。
    """
    bin_path = get_binary_path(name)
    if not bin_path:
        raise ImportError(f"找不到 C++ 扩展 {name}")

    bin_dir = str(bin_path.parent)
    if bin_dir not in sys.path:
        sys.path.insert(0, bin_dir)

    try:
        # 使用 __import__ 动态导入
        module = __import__(name)
        return module
    except ImportError as e:
        logger.error("导入 {} 失败 (路径: {}): {}", name, bin_path, e)
        raise
