"""项目打包工具 - 在没有git的情况下打包项目，剔除大体积缓存目录

使用示例:
    # 基本使用（打包到默认位置）
    python package_project.py

    # 指定输出目录
    python package_project.py -o D:\\output

    # 指定输出文件名
    python package_project.py -n my_project.zip

    # 查看将被剔除的目录
    python package_project.py --dry-run

    # 添加额外的排除目录
    python package_project.py --exclude "*.log" --exclude "temp/"
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Set

# 获取项目根目录 (当前脚本在 py_module/analyze/src/oc_analyze/ 下，向上 4 级是项目根目录)
PROJECT_ROOT = Path(__file__).resolve().parents[4]

# 默认需要剔除的大体积缓存目录（相对于项目根目录）
DEFAULT_EXCLUDE_DIRS: List[str] = [
    # C++ 构建目录
    "cpp_module/build",
    # vcpkg 包管理器目录
    "cpp_module/vcpkg",
    # Pixi 虚拟环境
    ".pixi",
    # Tauri 资源目录
    "web/src-tauri/resources",
    # Rust 构建目录
    "web/src-tauri/target",
    # Node.js 依赖目录
    "web/node_modules",
]

# 默认需要剔除的大体积文件（相对于项目根目录）
DEFAULT_EXCLUDE_FILES: List[str] = [
    # 大体积图片文件
    "data/calibration/photos_02/all.png",
    # 大体积模型文件
    "data/thickness_gradient_card.stl",
    # 大体积字体文件
    "web/src/assets/MapleMonoNormal-NF-CN-Regular.woff2",
]

# 默认输出目录
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "dist"

# 默认排除的文件模式
DEFAULT_EXCLUDE_PATTERNS: List[str] = [
    # Python 缓存
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    # 版本控制
    ".git",
    ".gitignore",
    ".gitattributes",
    ".svn",
    ".hg",
    # IDE
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    "*~",
    # 构建产物
    "*.egg-info",
    "dist",
    "build",
    # 其他
    ".DS_Store",
    "Thumbs.db",
]


def setup_logger():
    """设置日志记录器"""
    try:
        # 尝试使用项目的日志模块
        sys.path.insert(0, str(PROJECT_ROOT / "py_module" / "opencolor" / "src"))
        from oc_core_02.utils.logger import get_logger

        return get_logger(__name__)
    except Exception:
        # 如果无法导入，使用标准库
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return logging.getLogger(__name__)


logger = setup_logger()


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_directory_size(path: Path) -> int:
    """计算目录的总大小"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
            elif entry.is_dir(follow_symlinks=False):
                total += get_directory_size(Path(entry.path))
    except OSError as e:
        logger.error("无法访问目录 {}: {}", path, e)
    return total


def should_exclude(
    file_path: Path,
    exclude_dirs: List[Path],
    exclude_patterns: List[str],
    project_root: Path,
    exclude_files: List[Path] = None,
) -> bool:
    """判断文件是否应该被排除

    Args:
        file_path: 文件路径
        exclude_dirs: 需要排除的目录列表
        exclude_patterns: 排除模式列表
        project_root: 项目根目录
        exclude_files: 需要排除的特定文件列表

    Returns:
        是否应该排除该文件
    """
    try:
        # 获取相对于项目根目录的路径
        rel_path = file_path.relative_to(project_root)
        rel_path_str = str(rel_path).replace("\\", "/")

        # 检查是否在特定排除文件列表中
        if exclude_files:
            for exclude_file in exclude_files:
                try:
                    if file_path.resolve() == exclude_file.resolve():
                        return True
                except (ValueError, OSError):
                    continue

        # 检查是否在排除目录中
        for exclude_dir in exclude_dirs:
            try:
                if file_path.is_relative_to(exclude_dir):
                    return True
            except ValueError:
                continue

        # 检查是否匹配排除模式
        for pattern in exclude_patterns:
            # 处理目录模式
            if pattern.endswith("/"):
                dir_pattern = pattern.rstrip("/")
                if dir_pattern in rel_path.parts:
                    return True
            # 处理通配符模式
            elif "*" in pattern:
                import fnmatch

                # 检查文件名
                if fnmatch.fnmatch(file_path.name, pattern):
                    return True
                # 检查路径的任何部分
                for part in rel_path.parts:
                    if fnmatch.fnmatch(part, pattern):
                        return True
            # 处理精确匹配
            else:
                if pattern in rel_path.parts:
                    return True
                if file_path.name == pattern:
                    return True

        return False
    except Exception as e:
        logger.error("检查排除规则时出错 {}: {}", file_path, e)
        return False


def collect_excluded_dirs(exclude_dirs: List[str], project_root: Path) -> List[Path]:
    """收集需要排除的目录路径

    Args:
        exclude_dirs: 排除目录列表（相对路径字符串）
        project_root: 项目根目录

    Returns:
        绝对路径列表
    """
    excluded: List[Path] = []
    for dir_path in exclude_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            excluded.append(full_path.resolve())
        else:
            logger.warning("排除目录不存在: {}", dir_path)
    return excluded


def collect_excluded_files(exclude_files: List[str], project_root: Path) -> List[Path]:
    """收集需要排除的文件路径

    Args:
        exclude_files: 排除文件列表（相对路径字符串）
        project_root: 项目根目录

    Returns:
        绝对路径列表
    """
    excluded: List[Path] = []
    for file_path in exclude_files:
        full_path = project_root / file_path
        if full_path.exists():
            excluded.append(full_path.resolve())
        else:
            logger.warning("排除文件不存在: {}", file_path)
    return excluded


def scan_excluded_directories(exclude_dirs: List[Path]) -> dict:
    """扫描将被排除的目录，返回统计信息

    Args:
        exclude_dirs: 需要排除的目录列表

    Returns:
        包含统计信息的字典
    """
    stats = {
        "total_dirs": 0,
        "total_size": 0,
        "details": [],
    }

    for dir_path in exclude_dirs:
        if dir_path.exists():
            size = get_directory_size(dir_path)
            stats["total_dirs"] += 1
            stats["total_size"] += size
            stats["details"].append(
                {
                    "path": dir_path,
                    "relative_path": dir_path.relative_to(PROJECT_ROOT),
                    "size": size,
                    "size_formatted": format_size(size),
                }
            )

    return stats


def create_project_archive(
    project_root: Path,
    output_path: Path,
    exclude_dirs: List[Path],
    exclude_patterns: List[str],
    exclude_files: List[Path] = None,
    dry_run: bool = False,
) -> dict:
    """创建项目压缩包

    Args:
        project_root: 项目根目录
        output_path: 输出文件路径
        exclude_dirs: 需要排除的目录列表
        exclude_patterns: 排除模式列表
        exclude_files: 需要排除的特定文件列表
        dry_run: 是否为试运行模式（不实际创建文件）

    Returns:
        包含统计信息的字典
    """
    stats = {
        "total_files": 0,
        "total_size": 0,
        "excluded_files": 0,
        "excluded_size": 0,
        "added_files": 0,
        "added_size": 0,
    }

    files_to_add: List[tuple] = []  # (file_path, arcname)

    # 遍历项目目录
    logger.info("正在扫描项目目录...")
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)

        # 过滤掉需要排除的目录（避免递归进入）
        dirs_to_remove = []
        for d in dirs:
            dir_path = root_path / d
            if should_exclude(
                dir_path, exclude_dirs, exclude_patterns, project_root, exclude_files
            ):
                dirs_to_remove.append(d)
                # 统计被排除的目录
                if dir_path.exists():
                    dir_size = get_directory_size(dir_path)
                    stats["excluded_files"] += 1
                    stats["excluded_size"] += dir_size

        for d in dirs_to_remove:
            dirs.remove(d)

        # 处理文件
        for file_name in files:
            file_path = root_path / file_name
            stats["total_files"] += 1

            try:
                file_size = file_path.stat().st_size
                stats["total_size"] += file_size
            except OSError as e:
                logger.error("无法获取文件大小 {}: {}", file_path, e)
                continue

            # 检查是否应该排除
            if should_exclude(
                file_path, exclude_dirs, exclude_patterns, project_root, exclude_files
            ):
                stats["excluded_files"] += 1
                stats["excluded_size"] += file_size
                continue

            # 计算在压缩包中的路径
            try:
                arcname = str(file_path.relative_to(project_root))
                files_to_add.append((file_path, arcname))
                stats["added_files"] += 1
                stats["added_size"] += file_size
            except ValueError as e:
                logger.error("计算相对路径失败 {}: {}", file_path, e)

    logger.info("扫描完成")
    logger.info("总文件数: {}", stats["total_files"])
    logger.info("总大小: {}", format_size(stats["total_size"]))
    logger.info("排除文件数: {}", stats["excluded_files"])
    logger.info("排除大小: {}", format_size(stats["excluded_size"]))
    logger.info("将添加文件数: {}", stats["added_files"])
    logger.info("将添加大小: {}", format_size(stats["added_size"]))

    if dry_run:
        logger.info("试运行模式，不创建压缩包")
        return stats

    # 创建压缩包
    logger.info("正在创建压缩包: {}", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, (file_path, arcname) in enumerate(files_to_add, 1):
                try:
                    zf.write(file_path, arcname)
                    if idx % 100 == 0 or idx == len(files_to_add):
                        logger.info("已处理: {}/{} 文件", idx, len(files_to_add))
                except Exception as e:
                    logger.error("添加文件失败 {}: {}", file_path, e)

        # 获取压缩包大小
        archive_size = output_path.stat().st_size
        stats["archive_size"] = archive_size
        stats["archive_size_formatted"] = format_size(archive_size)
        stats["compression_ratio"] = (
            (1 - archive_size / stats["added_size"]) * 100
            if stats["added_size"] > 0
            else 0
        )

        logger.info("压缩包创建成功: {}", output_path)
        logger.info("压缩包大小: {}", format_size(archive_size))
        logger.info("压缩率: {:.1f}%", stats["compression_ratio"])

    except Exception as e:
        logger.error("创建压缩包失败: {}", e)
        raise

    return stats


def print_exclusion_summary(exclude_stats: dict) -> None:
    """打印排除目录的摘要信息

    Args:
        exclude_stats: 排除目录的统计信息
    """
    logger.info("=" * 60)
    logger.info("将被排除的目录")
    logger.info("=" * 60)

    if not exclude_stats["details"]:
        logger.info("没有需要排除的目录")
        return

    # 按大小排序
    sorted_details = sorted(
        exclude_stats["details"], key=lambda x: x["size"], reverse=True
    )

    for item in sorted_details:
        logger.info("  {} - {}", item["relative_path"], item["size_formatted"])

    logger.info("-" * 60)
    logger.info("排除目录总数: {}", exclude_stats["total_dirs"])
    logger.info("排除总大小: {}", format_size(exclude_stats["total_size"]))


def print_final_summary(stats: dict, output_path: Path) -> None:
    """打印最终摘要信息

    Args:
        stats: 打包统计信息
        output_path: 输出文件路径
    """
    logger.info("=" * 60)
    logger.info("打包完成")
    logger.info("=" * 60)
    logger.info("输出文件: {}", output_path)
    logger.info("项目总文件数: {}", stats["total_files"])
    logger.info("项目总大小: {}", format_size(stats["total_size"]))
    logger.info("排除文件数: {}", stats["excluded_files"])
    logger.info("排除大小: {}", format_size(stats["excluded_size"]))
    logger.info("打包文件数: {}", stats["added_files"])
    logger.info("打包大小: {}", format_size(stats["added_size"]))

    if "archive_size" in stats:
        logger.info("压缩包大小: {}", stats["archive_size_formatted"])
        logger.info("压缩率: {:.1f}%", stats["compression_ratio"])


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="项目打包工具 - 在没有git的情况下打包项目，剔除大体积缓存目录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本使用（打包到默认位置）
  python package_project.py
  
  # 指定输出目录
  python package_project.py -o D:\\output
  
  # 指定输出文件名
  python package_project.py -n my_project.zip
  
  # 查看将被剔除的目录（试运行模式）
  python package_project.py --dry-run
  
  # 添加额外的排除模式
  python package_project.py --exclude "*.log" --exclude "temp/"
        """,
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"输出目录（默认: {DEFAULT_OUTPUT_DIR}）",
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        default=None,
        help="输出文件名（默认: OpenColor_YYYYMMDD_HHMMSS.zip）",
    )

    parser.add_argument(
        "--exclude", action="append", default=[], help="额外的排除模式（可多次使用）"
    )

    parser.add_argument(
        "--no-default-exclude", action="store_true", help="不使用默认的排除目录列表"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式，只显示将被排除的目录，不创建压缩包",
    )

    parser.add_argument(
        "--root",
        type=str,
        default=str(PROJECT_ROOT),
        help=f"项目根目录（默认: {PROJECT_ROOT}）",
    )

    return parser.parse_args()


def main() -> int:
    """主函数

    Returns:
        退出码（0表示成功）
    """
    args = parse_args()

    # 解析项目根目录
    project_root = Path(args.root).resolve()
    if not project_root.exists():
        logger.error("项目根目录不存在: {}", project_root)
        return 1

    logger.info("=" * 60)
    logger.info("项目打包工具")
    logger.info("=" * 60)
    logger.info("项目根目录: {}", project_root)

    # 确定排除目录
    if args.no_default_exclude:
        exclude_dir_list: List[str] = []
        exclude_file_list: List[str] = []
        logger.info("不使用默认排除目录")
    else:
        exclude_dir_list = DEFAULT_EXCLUDE_DIRS.copy()
        exclude_file_list = DEFAULT_EXCLUDE_FILES.copy()
        logger.info("使用默认排除目录和文件")

    # 收集排除目录和文件的绝对路径
    exclude_dirs = collect_excluded_dirs(exclude_dir_list, project_root)
    exclude_files = collect_excluded_files(exclude_file_list, project_root)

    # 扫描并显示将被排除的目录
    exclude_stats = scan_excluded_directories(exclude_dirs)
    print_exclusion_summary(exclude_stats)

    # 显示将被排除的特定文件
    if exclude_files:
        logger.info("")
        logger.info("=" * 60)
        logger.info("将被排除的特定文件")
        logger.info("=" * 60)
        for f in exclude_files:
            try:
                size = f.stat().st_size
                logger.info("  {} - {}", f.relative_to(project_root), format_size(size))
            except OSError:
                logger.info("  {} - 无法获取大小", f.relative_to(project_root))
        logger.info("-" * 60)
        logger.info("排除文件总数: {}", len(exclude_files))

    # 合并排除模式
    exclude_patterns = DEFAULT_EXCLUDE_PATTERNS.copy()
    exclude_patterns.extend(args.exclude)

    # 确定输出路径
    output_dir = Path(args.output_dir).resolve()
    if args.name:
        output_name = args.name
        if not output_name.endswith(".zip"):
            output_name += ".zip"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"OpenColor_{timestamp}.zip"

    output_path = output_dir / output_name

    if args.dry_run:
        logger.info("")
        logger.info("额外排除模式: {}", exclude_patterns)
        logger.info("")
        # 试运行模式下也扫描项目统计信息
        stats = create_project_archive(
            project_root=project_root,
            output_path=output_path,
            exclude_dirs=exclude_dirs,
            exclude_patterns=exclude_patterns,
            exclude_files=exclude_files,
            dry_run=True,
        )
        print_final_summary(stats, output_path)
        logger.info("")
        logger.info("试运行模式完成，未创建压缩包")
        return 0

    logger.info("")
    # 创建压缩包
    try:
        stats = create_project_archive(
            project_root=project_root,
            output_path=output_path,
            exclude_dirs=exclude_dirs,
            exclude_patterns=exclude_patterns,
            exclude_files=exclude_files,
            dry_run=args.dry_run,
        )

        print_final_summary(stats, output_path)
        return 0

    except Exception as e:
        logger.error("打包失败: {}", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
