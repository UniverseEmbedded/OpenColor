"""C++模块构建脚本 - 用于构建OpenColor C++扩展模块"""

from __future__ import annotations

import os
import subprocess
import shutil
import sys
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """执行命令并打印"""
    logger.info(f"[命令] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def main() -> None:
    """主函数 - 配置并构建C++模块"""
    # 定位项目根目录
    project_root = Path(__file__).resolve().parents[2]
    cpp_dir = project_root / "cpp_module"
    vcpkg_dir = cpp_dir / "vcpkg"
    build_dir = cpp_dir / "build"

    # 检查vcpkg是否存在，不存在则自动执行setup-cpp
    if not (vcpkg_dir / "vcpkg.exe").exists() and not (vcpkg_dir / "vcpkg").exists():
        logger.info(
            "[信息] 未检测到 vcpkg 可执行文件，正在自动运行：pixi run setup-cpp"
        )
        subprocess.run(["pixi", "run", "setup-cpp"], check=True)

    # 检查工具链文件
    toolchain = vcpkg_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
    if not toolchain.exists():
        raise FileNotFoundError("未找到 vcpkg.cmake，请确认 vcpkg 是否初始化成功")

    # 从环境变量获取配置
    generator = os.environ.get("CMAKE_GENERATOR", "Visual Studio 17 2022").strip()
    arch = os.environ.get("CMAKE_ARCH", "x64").strip()
    triplet = os.environ.get("VCPKG_TARGET_TRIPLET", "x64-windows").strip()
    config = os.environ.get("CMAKE_BUILD_TYPE", "Release").strip()

    # Python路径配置
    python_root = Path(sys.executable).resolve().parent
    python_include = python_root / "Include"
    python_library = (
        python_root
        / "libs"
        / f"python{sys.version_info.major}{sys.version_info.minor}.lib"
    )

    # 检查CMake缓存是否匹配当前目录
    cache_path = build_dir / "CMakeCache.txt"
    if cache_path.exists():
        cache_text = cache_path.read_text(encoding="utf-8", errors="ignore")
        marker = "CMAKE_HOME_DIRECTORY:INTERNAL="
        for line in cache_text.splitlines():
            if line.startswith(marker):
                cached_dir = line[len(marker) :].strip()
                if Path(cached_dir).resolve() != cpp_dir.resolve():
                    logger.info(
                        "[信息] 检测到旧的 CMake 缓存目录不匹配，将清理 build 目录"
                    )
                    shutil.rmtree(build_dir)
                break

    build_dir.mkdir(parents=True, exist_ok=True)

    # 运行CMake配置
    _run(
        [
            "cmake",
            "-S",
            str(cpp_dir),
            "-B",
            str(build_dir),
            "-G",
            generator,
            "-A",
            arch,
            f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
            f"-DVCPKG_TARGET_TRIPLET={triplet}",
            "-DVCPKG_DISABLE_FIND_PACKAGE_Python=ON",
            "-DVCPKG_DISABLE_FIND_PACKAGE_Python3=ON",
            "-DVCPKG_DISABLE_FIND_PACKAGE_PythonInterp=ON",
            f"-DPython_EXECUTABLE={sys.executable}",
            f"-DPython_ROOT_DIR={python_root}",
            "-DPython_FIND_STRATEGY=LOCATION",
            "-DPython_FIND_REGISTRY=NEVER",
            f"-DPython_INCLUDE_DIR={python_include}",
            f"-DPython_LIBRARY={python_library}",
            "-DVCPKG_FEATURE_FLAGS=manifests",
        ],
        cwd=cpp_dir,
    )

    # 运行构建
    _run(["cmake", "--build", str(build_dir), "--config", config], cwd=cpp_dir)

    # 检查主可执行文件
    exe = build_dir / config / "opencolor_cpp_module.exe"
    if exe.exists():
        logger.info(f"[完成] 构建成功：{exe}")
    else:
        logger.warning(
            "[警告] 未找到输出 exe（可能使用了不同的生成器/配置），请在 build 目录下查找"
        )

    # 复制Web探测程序到Tauri资源目录
    web_probe = build_dir / config / "opencolor_web_probe.exe"
    if web_probe.exists():
        tauri_cpp_dir = project_root / "web" / "src-tauri" / "resources" / "cpp"
        tauri_cpp_dir.mkdir(parents=True, exist_ok=True)
        target = tauri_cpp_dir / web_probe.name
        shutil.copy2(web_probe, target)
        logger.info(f"[完成] 已复制 C++ 探测程序到：{target}")
    else:
        logger.warning("[警告] 未找到 C++ 探测程序，可执行文件未复制到 Tauri 资源目录")


if __name__ == "__main__":
    main()
