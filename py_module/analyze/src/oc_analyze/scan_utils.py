"""
扫描工具共用模块

提供文件扫描相关的共用功能和常量
"""

import subprocess

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
from pathlib import Path
from typing import List, Set

# 获取项目根目录 (当前脚本在 py_module/analyze/src/oc_analyze/ 下，向上 4 级是项目根目录)
PROJECT_ROOT = Path(__file__).resolve().parents[4]

# 定义要扫描的默认目录
DEFAULT_SCAN_DIRS = [
    PROJECT_ROOT / "py_module",
    PROJECT_ROOT / "cpp_module",
    PROJECT_ROOT / "web",
]

# 定义代码文件的扩展名
CODE_EXTENSIONS: Set[str] = {
    ".py",
    ".pyx",
    ".pyi",
    ".cpp",
    ".cc",
    ".cxx",
    ".c",
    ".h",
    ".hpp",
    ".hxx",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".vue",
    ".rs",
    ".java",
    ".go",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".md",
}

# 默认报告输出目录的基础路径
DEFAULT_REPORT_BASE_DIR = PROJECT_ROOT / "doc" / "report"


def is_code_file(file_path: Path) -> bool:
    """判断是否为代码文件"""
    return file_path.suffix.lower() in CODE_EXTENSIONS


def get_git_tracked_files(
    directory: Path, project_root: Path = PROJECT_ROOT
) -> List[Path]:
    """使用 git ls-files 获取被 git 追踪的文件列表

    Args:
        directory: 要筛选的目录，只返回该目录下的文件
        project_root: 项目根目录，用于执行git命令

    Returns:
        指定目录下被git追踪的文件路径列表
    """
    try:
        # 使用 -c core.quotepath=false 避免中文路径被转义
        # 使用 -z 避免文件名转义问题，并以 NUL 分隔
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=project_root,
            capture_output=True,
            check=True,
        )
        # 解码并按 NUL 分隔，过滤掉空字符串
        # git ls-files -z 输出的是字节流，文件名按 utf-8 编码
        output = result.stdout.decode("utf-8")
        files = [project_root / f for f in output.split("\0") if f]

        # 过滤出在指定目录下的文件
        return [f for f in files if f.is_relative_to(directory)]
    except subprocess.CalledProcessError as e:
        logger.error(f"错误：调用 git 命令失败 - {e}")
        return []
    except Exception as e:
        logger.error(f"错误：获取 git 追踪文件时发生异常 - {e}")
        return []


def format_size(size_bytes: int) -> str:
    """格式化文件大小

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        格式化后的大小字符串（如 "16.00 KB"）
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_report_output_dir(report_type: str) -> Path:
    """获取报告输出目录

    Args:
        report_type: 报告类型（如 "filesize", "filename", "densedir" 等）

    Returns:
        报告输出目录路径
    """
    return DEFAULT_REPORT_BASE_DIR / report_type
