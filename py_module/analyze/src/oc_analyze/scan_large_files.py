import argparse

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from oc_analyze.scan_utils import (
    PROJECT_ROOT,
    DEFAULT_SCAN_DIRS,
    is_code_file,
    get_git_tracked_files,
    format_size,
    get_report_output_dir,
)

# 默认文件大小阈值（16KB）
DEFAULT_SIZE_THRESHOLD = 16 * 1024  # 16KB in bytes

# 输出报告目录
OUTPUT_DIR = get_report_output_dir("filesize")


def scan_directory(directory: Path, size_threshold: int) -> List[Dict[str, Any]]:
    """扫描目录，找出大于阈值的代码文件"""
    large_files = []
    
    if not directory.exists():
        logger.warning(f"警告：目录不存在 - {directory}")
        return large_files
    
    logger.info(f"正在扫描目录：{directory} (仅扫描 git 追踪的文件)")
    
    try:
        tracked_files = get_git_tracked_files(directory)
        
        for file_path in tracked_files:
            try:
                if is_code_file(file_path):
                    if not file_path.exists():
                        continue
                        
                    file_size = file_path.stat().st_size
                    
                    if file_size > size_threshold:
                        large_files.append({
                            'path': file_path,
                            'size': file_size,
                            'size_formatted': format_size(file_size),
                            'extension': file_path.suffix,
                            'scan_root': directory,
                            'relative_path': file_path.relative_to(directory),
                        })
            except OSError as e:
                logger.warning(f"警告：无法访问文件 {file_path} - {e}")
                    
    except Exception as e:
        logger.error(f"错误：扫描目录 {directory} 时发生异常 - {e}")
        raise
    
    logger.info(f"在 {directory} 中找到 {len(large_files)} 个大于{format_size(size_threshold)}的代码文件")
    return large_files


def generate_report(all_files: List[Dict[str, Any]], scan_dirs: List[Path], size_threshold: int) -> str:
    """生成markdown报告"""
    files_by_dir = {}
    for file_info in all_files:
        scan_root = file_info.get('scan_root')
        if not isinstance(scan_root, Path):
            scan_root = None

        if scan_root is None:
            dir_name = "未知目录"
        else:
            dir_name = scan_root.name

        if dir_name not in files_by_dir:
            files_by_dir[dir_name] = []
        files_by_dir[dir_name].append(file_info)
    
    # 生成报告内容
    report_lines = [
        "# 代码文件大小报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描目录数**: {len(scan_dirs)}",
        f"**文件大小阈值**: {format_size(size_threshold)}",
        f"**找到的大文件总数**: {len(all_files)}",
        "",
        "---",
        "",
    ]

    if not all_files:
        report_lines.append("### 未找到大于阈值的代码文件")
        report_lines.append("")
        return "\n".join(report_lines)
    
    # 按目录生成报告
    for dir_name in sorted(files_by_dir.keys()):
        files = files_by_dir[dir_name]
        # 按文件大小降序排序
        files_sorted = sorted(files, key=lambda x: x['size'], reverse=True)
        
        report_lines.extend([
            f"## {dir_name}",
            "",
            f"找到 {len(files)} 个大于{format_size(size_threshold)}的代码文件",
            "",
            "| 文件路径 | 大小 | 类型 |",
            "|---------|------|------|",
        ])
        
        for file_info in files_sorted:
            report_lines.append(
                f"| `{file_info['relative_path']}` | {file_info['size_formatted']} | {file_info['extension']} |"
            )
        
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
    
    # 统计信息
    report_lines.extend([
        "## 统计信息",
        "",
        "### 按文件类型统计",
        "",
        "| 文件类型 | 数量 |",
        "|---------|------|",
    ])
    
    ext_count = {}
    for file_info in all_files:
        ext = file_info['extension']
        ext_count[ext] = ext_count.get(ext, 0) + 1
    
    for ext in sorted(ext_count.keys(), key=lambda x: ext_count[x], reverse=True):
        report_lines.append(f"| {ext} | {ext_count[ext]} |")
    
    report_lines.append("")
    
    # 按大小范围统计
    report_lines.extend([
        "### 按大小范围统计",
        "",
        "| 大小范围 | 数量 |",
        "|---------|------|",
    ])

    size_ranges = [
        (size_threshold, 50 * 1024, f"{int(size_threshold / 1024)}KB - 50KB"),
        (50 * 1024, 100 * 1024, "50KB - 100KB"),
        (100 * 1024, 500 * 1024, "100KB - 500KB"),
        (500 * 1024, 1024 * 1024, "500KB - 1MB"),
        (1024 * 1024, float('inf'), "> 1MB"),
    ]
    
    for min_size, max_size, range_name in size_ranges:
        count = sum(1 for f in all_files if min_size <= f['size'] < max_size)
        report_lines.append(f"| {range_name} | {count} |")
    
    report_lines.append("")
    
    # 最大的10个文件
    report_lines.extend([
        "### 最大的10个文件",
        "",
        "| 排名 | 文件路径 | 大小 |",
        "|------|---------|------|",
    ])
    
    top_files = sorted(all_files, key=lambda x: x['size'], reverse=True)[:10]
    for idx, file_info in enumerate(top_files, 1):
        scan_root = file_info.get('scan_root')
        if isinstance(scan_root, Path):
            display_path = f"{scan_root.name}/{file_info['relative_path']}"
        else:
            display_path = str(file_info['relative_path'])
        report_lines.append(
            f"| {idx} | `{display_path}` | {file_info['size_formatted']} |"
        )
    
    return "\n".join(report_lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描指定目录中的大文件并生成报告")
    parser.add_argument(
        "scan_dirs",
        nargs="*",
        help="要扫描的目录列表（不传则使用脚本内置默认目录）",
    )
    parser.add_argument(
        "--threshold-kb",
        type=float,
        default=DEFAULT_SIZE_THRESHOLD / 1024,
        help=f"文件大小阈值（单位KB，默认{DEFAULT_SIZE_THRESHOLD / 1024:.0f}）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR),
        help="报告输出目录（默认使用脚本内置目录）",
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    if args.threshold_kb <= 0:
        raise ValueError(f"阈值必须大于0KB，当前: {args.threshold_kb}")

    size_threshold = int(args.threshold_kb * 1024)
    output_dir = Path(args.output_dir).expanduser().resolve()

    if args.scan_dirs:
        scan_dirs = [Path(p).expanduser().resolve() for p in args.scan_dirs]
    else:
        scan_dirs = DEFAULT_SCAN_DIRS

    logger.info("=" * 60)
    logger.info("开始扫描代码文件大小")
    logger.info("=" * 60)
    logger.info()

    logger.info(f"扫描目录数：{len(scan_dirs)}")
    logger.info(f"文件大小阈值：{format_size(size_threshold)}")
    logger.info(f"报告输出目录：{output_dir}")
    logger.info()
    
    all_large_files = []
    
    # 扫描所有目录
    for scan_dir in scan_dirs:
        try:
            files = scan_directory(scan_dir, size_threshold)
            all_large_files.extend(files)
            logger.info()
        except Exception as e:
            logger.error(f"错误：扫描目录 {scan_dir} 失败 - {e}")
            continue
    
    # 生成报告
    if all_large_files:
        logger.info(f"总共找到 {len(all_large_files)} 个大于{format_size(size_threshold)}的代码文件")
    else:
        logger.info(f"没有找到大于{format_size(size_threshold)}的代码文件")
    logger.info()
    
    try:
        report_content = generate_report(all_large_files, scan_dirs, size_threshold)
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"file_size_report_{timestamp}.md"
        report_path = output_dir / report_filename
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 写入报告
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"报告已生成：{report_path}")
        logger.info()
        
    except Exception as e:
        logger.error(f"错误：生成报告失败 - {e}")
        raise
    
    logger.info("=" * 60)
    logger.info("扫描完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"程序执行失败：{e}")
        sys.exit(1)
