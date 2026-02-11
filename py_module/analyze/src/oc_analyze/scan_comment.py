"""注释覆盖率报告生成脚本 - 运行注释覆盖率分析工具

默认直接执行已编译的程序，使用 --build 参数触发编译
"""

from __future__ import annotations


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
import os
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """执行命令并打印"""
    logger.info(f"[命令] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _find_repo_root(start: Path) -> Path:
    """从起始路径向上查找仓库根目录

    通过查找 cpp_module 和 doc 目录来确定根目录
    """
    cur = start.resolve()
    for _ in range(10):
        if (cur / "cpp_module").exists() and (cur / "doc").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()


def _find_built_exe(build_dir: Path, config: str) -> Path:
    """在构建目录中查找已编译的可执行文件

    尝试多个可能的位置，包括子目录
    """
    candidates: list[Path] = []
    candidates.append(build_dir / config / "opencolor_comment_coverage_ts.exe")
    candidates.append(build_dir / "opencolor_comment_coverage_ts.exe")
    candidates.append(
        build_dir
        / "tools"
        / "comment_coverage_ts"
        / config
        / "opencolor_comment_coverage_ts.exe"
    )

    for c in candidates:
        if c.exists():
            return c

    for c in build_dir.rglob("opencolor_comment_coverage_ts.exe"):
        if c.is_file():
            return c

    raise FileNotFoundError("未找到 opencolor_comment_coverage_ts.exe，请检查构建输出")


def _build_cpp_tool(repo_root: Path) -> Path:
    """编译C++注释覆盖率分析工具"""
    cpp_dir = repo_root / "cpp_module"
    vcpkg_dir = cpp_dir / "vcpkg"

    # 检查vcpkg是否存在
    if not (vcpkg_dir / "vcpkg.exe").exists() and not (vcpkg_dir / "vcpkg").exists():
        raise RuntimeError("未检测到 vcpkg 可执行文件，请先运行：pixi run setup-cpp")

    # 检查工具链文件
    toolchain = vcpkg_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
    if not toolchain.exists():
        raise FileNotFoundError("未找到 vcpkg.cmake，请确认 vcpkg 是否初始化成功")

    # 从环境变量获取配置
    generator = os.environ.get("CMAKE_GENERATOR", "Visual Studio 17 2022").strip()
    arch = os.environ.get("CMAKE_ARCH", "x64").strip()
    triplet = os.environ.get("VCPKG_TARGET_TRIPLET", "x64-windows").strip()
    config = os.environ.get("CMAKE_BUILD_TYPE", "Release").strip()

    # 构建目录
    build_dir = cpp_dir / "build_comment_coverage"
    build_dir.mkdir(parents=True, exist_ok=True)

    # CMake配置参数
    cmake_args = [
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
        "-DVCPKG_FEATURE_FLAGS=manifests",
        "-DVCPKG_MANIFEST_FEATURES=dev-comment-coverage",
        "-DOPENCOLOR_BUILD_CORE=OFF",
        "-DOPENCOLOR_BUILD_DEV_TOOLS=ON",
    ]

    # 配置并构建
    logger.info("[信息] 开始编译C++工具...")
    _run(cmake_args, cwd=cpp_dir)
    _run(
        [
            "cmake",
            "--build",
            str(build_dir),
            "--config",
            config,
            "--target",
            "opencolor_comment_coverage_ts",
        ],
        cwd=cpp_dir,
    )

    # 查找可执行文件
    exe = _find_built_exe(build_dir, config)
    logger.info(f"[信息] 编译完成：{exe}")
    return exe


def main() -> None:
    """主函数 - 运行注释覆盖率分析工具"""
    # 定位仓库根目录
    repo_root = _find_repo_root(Path(__file__).resolve())
    cpp_dir = repo_root / "cpp_module"
    build_dir = cpp_dir / "build_comment_coverage"
    config = os.environ.get("CMAKE_BUILD_TYPE", "Release").strip()

    # 解析命令行参数
    raw_args = sys.argv[1:]
    need_build = False
    forward_args: list[str] = []

    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg == "--build":
            need_build = True
        elif arg == "--":
            # 剩余参数全部转发
            forward_args.extend(raw_args[i + 1 :])
            break
        else:
            forward_args.append(arg)
        i += 1

    # 如果需要编译，先执行编译
    if need_build:
        exe = _build_cpp_tool(repo_root)
    else:
        # 尝试查找已编译的可执行文件
        try:
            exe = _find_built_exe(build_dir, config)
            logger.info(f"[信息] 使用已编译的可执行文件：{exe}")
        except FileNotFoundError:
            logger.error("[错误] 未找到已编译的可执行文件")
            logger.info("[提示] 请先运行：python comment_coverage_report.py --build")
            sys.exit(1)

    # 如果没有指定输入路径，默认使用仓库根目录
    if not any(a == "--input" or a.startswith("--input=") for a in forward_args):
        forward_args = ["--input", str(repo_root)] + forward_args

    # 运行分析工具
    cmd = [str(exe), *forward_args]
    _run(cmd, cwd=repo_root)


if __name__ == "__main__":
    main()
