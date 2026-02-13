"""注释覆盖率报告生成脚本 - 运行注释覆盖率分析工具

默认直接执行已编译的程序，使用 --build 参数触发编译
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from oc_core_02.utils.logger import get_logger
from tqdm import tqdm

logger = get_logger(__name__)


def _run_with_progress(cmd: list[str], cwd: Path | None = None) -> None:
    """执行命令并显示tqdm进度条"""
    logger.info(f"[命令] {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    total_files = 0
    current_file = 0
    pbar = None

    # 读取stderr中的进度信息
    for line in process.stderr:
        line = line.rstrip('\n\r')

        # 解析总文件数
        if match := re.match(r'\[PROGRESS_TOTAL\] (\d+)', line):
            total_files = int(match.group(1))
            pbar = tqdm(total=total_files, desc="分析文件", unit="file")
            continue

        # 解析进度
        if match := re.match(r'\[PROGRESS\] (\d+) (.+)', line):
            current_file = int(match.group(1))
            file_path = match.group(2)
            if pbar:
                pbar.update(1)
                pbar.set_postfix_str(Path(file_path).name[:30])
            continue

        # 其他stderr输出直接打印
        if not line.startswith('[PROGRESS'):
            print(line, file=sys.stderr)

    # 等待进程完成
    process.wait()

    if pbar:
        pbar.close()

    # 输出stdout
    if process.stdout:
        for line in process.stdout:
            print(line, end='')

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)


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

    # 构建目录（与 scan_python_imports 共用）
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
            "opencolor_comment_coverage_ts",
        ],
        cwd=cpp_dir,
    )

    # 查找可执行文件
    exe = _find_built_exe(build_dir, config)
    logger.info(f"[信息] 编译完成：{exe}")
    return exe


def _get_git_tracked_files(repo_root: Path) -> list[str]:
    """获取Git跟踪的文件列表"""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode == 0:
            files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return files
        else:
            logger.warning(f"[警告] 获取Git跟踪文件失败：{result.stderr}")
            return []
    except Exception as e:
        logger.warning(f"[警告] 执行git命令失败：{e}")
        return []


def _is_code_file(file_path: str) -> bool:
    """检查文件是否是代码文件"""
    code_extensions = {
        '.c', '.cpp', '.cc', '.cxx', '.hpp', '.h', '.hxx',
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go',
        '.rs', '.cs', '.sh', '.bash', '.json', '.toml',
    }
    ext = Path(file_path).suffix.lower()
    return ext in code_extensions


def main() -> None:
    """主函数 - 运行注释覆盖率分析工具"""
    # 定位仓库根目录
    repo_root = _find_repo_root(Path(__file__).resolve())
    cpp_dir = repo_root / "cpp_module"
    build_dir = cpp_dir / "build_dev_tools"
    config = os.environ.get("CMAKE_BUILD_TYPE", "Release").strip()

    # 解析命令行参数
    raw_args = sys.argv[1:]
    need_build = False
    use_git_only = True  # 默认只分析Git跟踪的文件
    forward_args: list[str] = []

    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg == "--build":
            need_build = True
        elif arg == "--no-git-only":
            use_git_only = False
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

    # 准备报告输出路径
    report_dir = repo_root / "doc" / "report" / "comment"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_report_path = report_dir / f"comment_report_{timestamp}.md"

    # 如果使用git-only模式，获取Git跟踪的代码文件列表
    if use_git_only:
        logger.info("[信息] 正在获取Git跟踪的代码文件列表...")
        tracked_files = _get_git_tracked_files(repo_root)
        code_files = [f for f in tracked_files if _is_code_file(f)]

        if not code_files:
            logger.error("[错误] 未找到Git跟踪的代码文件")
            sys.exit(1)

        logger.info(f"[信息] 找到 {len(code_files)} 个代码文件")

        # 创建临时文件列表
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for file_path in code_files:
                f.write(file_path + '\n')
            file_list_path = f.name

        try:
            # 运行分析工具（使用--file-list参数和--md参数）
            cmd = [str(exe), "--progress", "--file-list", file_list_path, "--md", str(md_report_path), *forward_args]
            _run_with_progress(cmd, cwd=repo_root)
            logger.info(f"[信息] Markdown报告已保存到: {md_report_path}")
        finally:
            # 清理临时文件
            try:
                os.unlink(file_list_path)
            except:
                pass
    else:
        # 如果没有指定输入路径，默认使用仓库根目录
        if not any(not a.startswith("--") and not a.startswith("-") for a in forward_args):
            forward_args = [str(repo_root)] + forward_args

        # 运行分析工具（添加--md参数）
        cmd = [str(exe), "--progress", "--md", str(md_report_path), *forward_args]
        _run_with_progress(cmd, cwd=repo_root)
        logger.info(f"[信息] Markdown报告已保存到: {md_report_path}")


if __name__ == "__main__":
    main()
