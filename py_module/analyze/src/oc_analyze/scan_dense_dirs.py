import argparse

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from oc_analyze.scan_utils import (
    PROJECT_ROOT,
    DEFAULT_SCAN_DIRS,
    is_code_file,
    get_git_tracked_files,
    get_report_output_dir,
)

# 默认文件数量阈值（一个目录下超过此数量的代码文件会被报告）
DEFAULT_FILE_THRESHOLD = 16

# 输出报告目录
OUTPUT_DIR = get_report_output_dir("densedir")


def scan_directory_for_dense_dirs(
    directory: Path, file_threshold: int
) -> List[Dict[str, Any]]:
    """扫描目录，找出包含过多代码文件的子目录

    Args:
        directory: 要扫描的目录
        file_threshold: 文件数量阈值，超过此数量的目录会被记录

    Returns:
        包含过多文件的目录信息列表
    """
    results = []

    if not directory.exists():
        logger.warning(f"警告：目录不存在 - {directory}")
        return results

    logger.info(f"正在扫描目录：{directory} (仅扫描 git 追踪的文件)")

    try:
        tracked_files = get_git_tracked_files(directory)

        # 统计每个目录下的代码文件数量
        dir_file_count: Dict[Path, List[Path]] = defaultdict(list)

        for file_path in tracked_files:
            try:
                if not is_code_file(file_path):
                    continue

                # 将文件归属到其所在目录
                parent_dir = file_path.parent
                dir_file_count[parent_dir].append(file_path)

            except Exception as e:
                logger.error(f"警告：处理文件 {file_path} 时发生错误 - {e}")

        # 找出文件数量超过阈值的目录
        for dir_path, files in dir_file_count.items():
            if len(files) > file_threshold:
                # 按文件扩展名统计
                ext_count: Dict[str, int] = defaultdict(int)
                for f in files:
                    ext_count[f.suffix] += 1

                results.append(
                    {
                        "path": dir_path,
                        "file_count": len(files),
                        "scan_root": directory,
                        "relative_path": dir_path.relative_to(directory),
                        "extensions": dict(ext_count),
                        "files": files,
                    }
                )

    except Exception as e:
        logger.error(f"错误：扫描目录 {directory} 时发生异常 - {e}")
        raise

    logger.info(
        f"在 {directory} 中找到 {len(results)} 个文件过多的目录（>{file_threshold}个文件）"
    )
    return results


def generate_report(
    all_dense_dirs: List[Dict[str, Any]], scan_dirs: List[Path], file_threshold: int
) -> str:
    """生成markdown报告

    Args:
        all_dense_dirs: 所有包含过多文件的目录信息
        scan_dirs: 扫描的目录列表
        file_threshold: 文件数量阈值

    Returns:
        Markdown格式的报告内容
    """
    # 按扫描根目录分组
    dirs_by_root = {}
    for dir_info in all_dense_dirs:
        scan_root = dir_info.get("scan_root")
        dir_name = scan_root.name if isinstance(scan_root, Path) else "未知目录"
        dirs_by_root.setdefault(dir_name, []).append(dir_info)

    # 生成报告内容
    report_lines = [
        "# 密集目录扫描报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描目录数**: {len(scan_dirs)}",
        f"**文件数量阈值**: {file_threshold}",
        f"**找到的密集目录总数**: {len(all_dense_dirs)}",
        "",
        "---",
        "",
    ]

    if not all_dense_dirs:
        report_lines.append("### 未找到文件数量超过阈值的目录")
        report_lines.append("")
        return "\n".join(report_lines)

    # 按扫描根目录生成报告
    for dir_name in sorted(dirs_by_root.keys()):
        dense_dirs = dirs_by_root[dir_name]
        # 按文件数量降序排序
        dirs_sorted = sorted(dense_dirs, key=lambda x: x["file_count"], reverse=True)

        report_lines.extend(
            [
                f"## {dir_name}",
                "",
                f"找到 {len(dense_dirs)} 个文件数量超过 {file_threshold} 的目录",
                "",
                "| 目录路径 | 文件数量 | 文件类型分布 |",
                "|---------|---------|-------------|",
            ]
        )

        for dir_info in dirs_sorted:
            # 格式化文件类型分布
            ext_dist = ", ".join(
                [
                    f"{ext}: {count}"
                    for ext, count in sorted(dir_info["extensions"].items())
                ]
            )
            report_lines.append(
                f"| `{dir_info['relative_path']}` | {dir_info['file_count']} | {ext_dist} |"
            )

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    # 详细列表
    report_lines.extend(
        [
            "## 详细文件列表",
            "",
            "以下列出每个密集目录中的代码文件：",
            "",
        ]
    )

    for dir_name in sorted(dirs_by_root.keys()):
        dense_dirs = dirs_by_root[dir_name]
        dirs_sorted = sorted(dense_dirs, key=lambda x: x["file_count"], reverse=True)

        for dir_info in dirs_sorted:
            report_lines.extend(
                [
                    f"### {dir_name}/{dir_info['relative_path']}",
                    "",
                    f"**文件数量**: {dir_info['file_count']}",
                    "",
                    "| 文件名 | 类型 |",
                    "|-------|------|",
                ]
            )

            # 按文件名排序
            sorted_files = sorted(dir_info["files"], key=lambda x: x.name)
            for file_path in sorted_files:
                rel_file_path = file_path.relative_to(dir_info["path"])
                report_lines.append(f"| `{rel_file_path}` | {file_path.suffix} |")

            report_lines.append("")

    # 统计信息
    report_lines.extend(
        [
            "## 统计信息",
            "",
            "### 按文件数量范围统计",
            "",
            "| 文件数量范围 | 目录数量 |",
            "|-------------|---------|",
        ]
    )

    # 定义范围区间
    ranges = [
        (file_threshold + 1, 20, f"{file_threshold + 1} - 20"),
        (21, 30, "21 - 30"),
        (31, 50, "31 - 50"),
        (51, 100, "51 - 100"),
        (101, float("inf"), "> 100"),
    ]

    for min_count, max_count, range_name in ranges:
        count = sum(
            1 for d in all_dense_dirs if min_count <= d["file_count"] <= max_count
        )
        if count > 0:
            report_lines.append(f"| {range_name} | {count} |")

    report_lines.append("")

    # 文件最多的10个目录
    report_lines.extend(
        [
            "### 文件最多的10个目录",
            "",
            "| 排名 | 目录路径 | 文件数量 |",
            "|------|---------|---------|",
        ]
    )

    top_dirs = sorted(all_dense_dirs, key=lambda x: x["file_count"], reverse=True)[:10]
    for idx, dir_info in enumerate(top_dirs, 1):
        scan_root = dir_info.get("scan_root")
        if isinstance(scan_root, Path):
            display_path = f"{scan_root.name}/{dir_info['relative_path']}"
        else:
            display_path = str(dir_info["relative_path"])
        report_lines.append(f"| {idx} | `{display_path}` | {dir_info['file_count']} |")

    return "\n".join(report_lines)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="扫描指定目录中包含过多代码文件的子目录并生成报告"
    )
    parser.add_argument(
        "scan_dirs",
        nargs="*",
        help="要扫描的目录列表（不传则使用脚本内置默认目录）",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_FILE_THRESHOLD,
        help=f"文件数量阈值（默认{DEFAULT_FILE_THRESHOLD}）",
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

    if args.threshold <= 0:
        raise ValueError(f"阈值必须大于0，当前: {args.threshold}")

    output_dir = Path(args.output_dir).expanduser().resolve()

    if args.scan_dirs:
        scan_dirs = [Path(p).expanduser().resolve() for p in args.scan_dirs]
    else:
        scan_dirs = DEFAULT_SCAN_DIRS

    logger.info("=" * 60)
    logger.info("开始扫描密集目录")
    logger.info("=" * 60)
    logger.info("")

    logger.info(f"扫描目录数：{len(scan_dirs)}")
    logger.info(f"文件数量阈值：{args.threshold}")
    logger.info(f"报告输出目录：{output_dir}")
    logger.info("")

    all_dense_dirs = []

    # 扫描所有目录
    for scan_dir in scan_dirs:
        try:
            dense_dirs = scan_directory_for_dense_dirs(scan_dir, args.threshold)
            all_dense_dirs.extend(dense_dirs)
            logger.info("")
        except Exception as e:
            logger.error(f"错误：扫描目录 {scan_dir} 失败 - {e}")
            continue

    # 生成报告
    if all_dense_dirs:
        logger.info(
            f"总共找到 {len(all_dense_dirs)} 个文件数量超过 {args.threshold} 的目录"
        )
    else:
        logger.info(f"没有找到文件数量超过 {args.threshold} 的目录")
    logger.info("")

    try:
        report_content = generate_report(all_dense_dirs, scan_dirs, args.threshold)

        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"dense_dir_report_{timestamp}.md"
        report_path = output_dir / report_filename

        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        # 写入报告
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"报告已生成：{report_path}")
        logger.info("")

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
