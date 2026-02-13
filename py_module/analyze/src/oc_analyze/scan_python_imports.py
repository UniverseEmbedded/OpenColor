"""Python引用关系扫描工具 - 运行C++分析工具

默认直接执行已编译的程序，使用 --build 参数触发编译
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import re

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """执行命令并打印"""
    logger.info(f"[命令] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _collect_entry_modules_for_package(
    module_prefix: str, source_dir: Path
) -> list[str]:
    if not source_dir.exists():
        logger.warning(f"[警告] 入口模块目录不存在: {source_dir}")
        return []

    main_pattern = re.compile(r"if\s+__name__\s*==\s*[\"\']__main__[\"\']\s*:")
    entries: list[str] = []

    for py_path in source_dir.rglob("*.py"):
        if py_path.name == "__init__.py":
            continue
        try:
            content = py_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"读取文件失败: {py_path} | 错误: {e}")
            raise
        if not main_pattern.search(content):
            continue
        rel = py_path.relative_to(source_dir).as_posix()
        rel = rel[:-3] if rel.endswith(".py") else rel
        rel = rel.replace("/", ".")
        if rel:
            entries.append(f"{module_prefix}.{rel}")
        else:
            entries.append(module_prefix)

    if entries:
        logger.info(f"[信息] 入口模块 {module_prefix} 检测到 {len(entries)} 个入口脚本")
        return entries

    init_path = source_dir / "__init__.py"
    if init_path.exists():
        logger.info(f"[信息] 入口模块 {module_prefix} 未发现入口脚本，使用包根模块")
        return [module_prefix]

    fallback_entries: list[str] = []
    for py_path in source_dir.rglob("*.py"):
        if py_path.name == "__init__.py":
            continue
        rel = py_path.relative_to(source_dir).as_posix()
        rel = rel[:-3] if rel.endswith(".py") else rel
        rel = rel.replace("/", ".")
        if rel:
            fallback_entries.append(f"{module_prefix}.{rel}")
        else:
            fallback_entries.append(module_prefix)

    if fallback_entries:
        logger.info(
            f"[信息] 入口模块 {module_prefix} 未发现入口脚本且缺少 __init__.py，已降级为 {len(fallback_entries)} 个脚本入口"
        )
    return fallback_entries


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
    candidates.append(build_dir / config / "opencolor_python_import_scanner.exe")
    candidates.append(build_dir / "opencolor_python_import_scanner.exe")
    candidates.append(
        build_dir
        / "tools"
        / "python_import_scanner"
        / config
        / "opencolor_python_import_scanner.exe"
    )

    for c in candidates:
        if c.exists():
            return c

    for c in build_dir.rglob("opencolor_python_import_scanner.exe"):
        if c.is_file():
            return c

    raise FileNotFoundError("未找到 opencolor_python_import_scanner.exe，请检查构建输出")


def _build_cpp_tool(repo_root: Path) -> Path:
    """编译C++ Python导入扫描工具"""
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

    # 构建目录（与 scan_comment 共用）
    build_dir = cpp_dir / "build_dev_tools"
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
        "-DVCPKG_MANIFEST_FEATURES=tree-sitter-scanners",
        f"-DVCPKG_INSTALLED_DIR={build_dir / 'vcpkg_installed'}",
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
            "opencolor_python_import_scanner",
        ],
        cwd=cpp_dir,
    )

    # 查找可执行文件
    exe = _find_built_exe(build_dir, config)
    logger.info(f"[信息] 编译完成：{exe}")
    return exe


def main() -> None:
    """主函数 - 运行Python导入关系分析工具"""
    # 定位仓库根目录
    repo_root = _find_repo_root(Path(__file__).resolve())
    cpp_dir = repo_root / "cpp_module"
    build_dir = cpp_dir / "build_dev_tools"
    config = os.environ.get("CMAKE_BUILD_TYPE", "Release").strip()

    # 解析命令行参数
    raw_args = sys.argv[1:]
    need_build = False
    forward_args: list[str] = []
    has_entry_arg = False

    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg == "--build":
            need_build = True
        elif arg == "--entry":
            has_entry_arg = True
            forward_args.append(arg)
            if i + 1 < len(raw_args):
                i += 1
                forward_args.append(raw_args[i])
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
            logger.info("[提示] 请先运行：pixi run python -m oc_analyze.scan_python_imports --build")
            sys.exit(1)

    # 准备报告输出路径
    report_dir = repo_root / "doc" / "report" / "python_imports"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_report_path = report_dir / f"python_imports_report_{timestamp}.md"

    # 如果没有指定输入路径，默认使用 py_module 目录
    if not any(not a.startswith("--") and not a.startswith("-") for a in forward_args):
        py_module = repo_root / "py_module"
        forward_args = [str(py_module)] + forward_args

    # 如果没有指定入口模块，添加默认的三个入口模块
    # 注意：模块名现在使用包配置中的短名称（如 oc_engine 而不是 py_module.engine.src.oc_engine）
    if not has_entry_arg:
        default_entries: list[str] = []
        default_entries.extend(
            _collect_entry_modules_for_package(
                "oc_analyze", repo_root / "py_module" / "analyze" / "src" / "oc_analyze"
            )
        )
        default_entries.extend(
            _collect_entry_modules_for_package(
                "oc_engine", repo_root / "py_module" / "engine" / "src" / "oc_engine"
            )
        )
        default_entries.extend(
            _collect_entry_modules_for_package(
                "oc_proto",
                repo_root / "py_module" / "prototypes" / "src" / "oc_proto",
            )
        )
        default_entries.extend(
            _collect_entry_modules_for_package(
                "oc_core_02", repo_root / "py_module" / "opencolor" / "src" / "oc_core_02"
            )
        )
        unique_entries = list(dict.fromkeys(default_entries))
        logger.info(f"[信息] 使用默认入口模块: {', '.join(unique_entries)}")
        for entry in unique_entries:
            forward_args.extend(["--entry", entry])

    # 运行分析工具（添加--md参数）
    cmd = [str(exe), "--md", str(md_report_path), *forward_args]
    _run(cmd, cwd=repo_root)
    logger.info(f"[信息] Markdown报告已保存到: {md_report_path}")


if __name__ == "__main__":
    main()
