from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def get_app_root() -> Path:
    """获取应用程序根目录路径。

    - 开发环境：返回仓库根目录
    - 打包环境：返回 Tauri 资源目录（引擎侧边栏文件夹的父目录）
    """

    # PyInstaller 会设置 `sys.frozen` 为 True，且 `sys.executable` 指向侧边栏可执行文件
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        # 引擎被打包到 <resources>/engine/ 目录下，因此应用根目录是其父目录
        return exe_dir.parent

    # 开发环境：当前文件位于 <repo>/py_module/opencolor/src/oc_core/core/app_paths.py
    return Path(__file__).resolve().parents[5]


def get_user_documents_dir() -> Path:
    """获取用户文档目录下的 OpenColor 文件夹路径。"""
    if sys.platform == "win32":
        # Windows 系统: C:\Users\xxx\Documents\OpenColor
        import ctypes
        from ctypes import wintypes
        CSIDL_PERSONAL = 5  # 我的文档
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        base = Path(buf.value)
    else:
        # Linux/macOS 系统: ~/Documents/OpenColor
        base = Path.home() / "Documents"
    
    path = base / "OpenColor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_local_appdata_dir() -> Path:
    """获取用户本地应用数据目录下的 OpenColor 文件夹路径。"""
    if sys.platform == "win32":
        # Windows 系统: C:\Users\xxx\AppData\Local\OpenColor
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif sys.platform == "darwin":
        # macOS 系统: ~/Library/Application Support/OpenColor
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux 系统: ~/.local/share/OpenColor (或使用 XDG_DATA_HOME 环境变量)
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    
    path = base / "OpenColor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_path(*parts: str) -> Path:
    """获取 data/ 目录下指定文件的完整路径。"""

    return get_app_root().joinpath("data", *parts)


def default_out_dir(method: str) -> Path:
    """获取引擎作业的默认输出目录路径。

    对于特定的数据存档方法，使用用户文档目录作为输出位置。
    其他情况下默认输出到 <app_root>/out_engine 目录下。
    """
    
    # 根据方法名决定是否使用文档目录
    if method.startswith("quick_calib") or method in ["board.generate", "materials.archive"]:
        base = get_user_documents_dir()
        ts = time.strftime("%Y%m%d_%H%M%S")
        return base / method.replace(".", "_") / ts

    ts = time.strftime("%Y%m%d_%H%M%S")
    return get_app_root() / "out_engine" / method.replace(".", "_") / ts
