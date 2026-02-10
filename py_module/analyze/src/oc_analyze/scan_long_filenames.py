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
    get_report_output_dir,
)

OUTPUT_DIR = get_report_output_dir("filename")


def scan_directory_for_long_names(directory: Path, file_threshold: int, dir_threshold: int):
    results = []
    if not directory.exists():
        logger.warning(f"警告：目录不存在 - {directory}")
        return results
    
    logger.info(f"正在扫描目录：{directory} (仅扫描 git 追踪的文件/目录)")
    
    try:
        tracked_files = get_git_tracked_files(directory)
        
        seen_dirs = set()
        
        for fp in tracked_files:
            # 扫描文件名
            try:
                if not is_code_file(fp):
                    continue
                
                name_len = len(fp.stem)
                if name_len > file_threshold:
                    results.append(
                        {
                            "path": fp,
                            "name_len": name_len,
                            "type": "File",
                            "extension": fp.suffix,
                            "scan_root": directory,
                            "relative_path": fp.relative_to(directory),
                        }
                    )
                
                # 扫描目录名
                # 向上遍历父目录，直到到达扫描根目录
                current_p = fp.parent
                while current_p.is_relative_to(directory) and current_p != directory:
                    if current_p not in seen_dirs:
                        seen_dirs.add(current_p)
                        dir_name = current_p.name
                        dir_len = len(dir_name)
                        if dir_len > dir_threshold:
                            results.append(
                                {
                                    "path": current_p,
                                    "name_len": dir_len,
                                    "type": "Directory",
                                    "extension": "",
                                    "scan_root": directory,
                                    "relative_path": current_p.relative_to(directory),
                                }
                            )
                    current_p = current_p.parent
                    
            except Exception as e:
                logger.error(f"警告：处理文件 {fp} 时发生错误 - {e}")
                
    except Exception as e:
        logger.error(f"错误：扫描目录 {directory} 时发生异常 - {e}")
        raise
    
    file_hits = len([r for r in results if r["type"] == "File"])
    dir_hits = len([r for r in results if r["type"] == "Directory"])
    logger.info(f"在 {directory} 中找到 {file_hits} 个长文件名和 {dir_hits} 个长目录名")
    return results


def scan_total_path_length(directory: Path, total_threshold: int = 72):
    """扫描总路径长度（从项目根开始）超过阈值的文件和目录
    
    Args:
        directory: 要扫描的目录
        total_threshold: 总路径长度阈值（默认72）
        
    Returns:
        列表，包含超标的文件和目录信息
        如果目录已超标，不包含其中的文件
    """
    results = []
    if not directory.exists():
        logger.warning(f"警告：目录不存在 - {directory}")
        return results
    
    logger.info(f"正在扫描总路径长度：{directory} (阈值: {total_threshold})")
    
    try:
        tracked_files = get_git_tracked_files(directory)

        # 收集所有超标的目录（从项目根开始的相对路径）
        exceeded_dirs = set()

        # 首先检查所有目录
        all_dirs = set()
        for fp in tracked_files:
            if not is_code_file(fp):
                continue
            # 收集文件的所有父目录（相对于项目根）
            rel_path = fp.relative_to(PROJECT_ROOT)
            current = rel_path.parent
            while current != Path("."):
                all_dirs.add(current)
                current = current.parent

        # 检查哪些目录超标
        for dir_rel in all_dirs:
            total_len = len(str(dir_rel))
            if total_len > total_threshold:
                full_path = PROJECT_ROOT / dir_rel
                results.append({
                    "path": full_path,
                    "rel_path": dir_rel,
                    "total_len": total_len,
                    "type": "Directory",
                    "scan_root": directory,
                })
                exceeded_dirs.add(dir_rel)

        # 检查文件（排除已在超标目录中的）
        for fp in tracked_files:
            if not is_code_file(fp):
                continue

            rel_path = fp.relative_to(PROJECT_ROOT)
            total_len = len(str(rel_path))

            if total_len > total_threshold:
                # 检查是否在已超标的目录中
                parent = rel_path.parent
                is_under_exceeded_dir = False
                while parent != Path("."):
                    if parent in exceeded_dirs:
                        is_under_exceeded_dir = True
                        break
                    parent = parent.parent

                if not is_under_exceeded_dir:
                    results.append({
                        "path": fp,
                        "rel_path": rel_path,
                        "total_len": total_len,
                        "type": "File",
                        "extension": fp.suffix,
                        "scan_root": directory,
                    })

    except Exception as e:
        logger.error(f"错误：扫描总路径长度 {directory} 时发生异常 - {e}")
        raise

    file_hits = len([r for r in results if r["type"] == "File"])
    dir_hits = len([r for r in results if r["type"] == "Directory"])
    logger.info(f"在 {directory} 中找到 {file_hits} 个长路径文件和 {dir_hits} 个长路径目录")
    return results


def generate_report(all_hits, total_path_hits, scan_dirs, file_threshold: int, dir_threshold: int, total_threshold: int) -> str:
    hits_by_dir = {}
    for info in all_hits:
        scan_root = info.get("scan_root")
        dir_name = scan_root.name if isinstance(scan_root, Path) else "未知目录"
        hits_by_dir.setdefault(dir_name, []).append(info)
    
    total_hits_by_dir = {}
    for info in total_path_hits:
        scan_root = info.get("scan_root")
        dir_name = scan_root.name if isinstance(scan_root, Path) else "未知目录"
        total_hits_by_dir.setdefault(dir_name, []).append(info)

    lines = [
        "# 超长文件名与目录名报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描目录数**: {len(scan_dirs)}",
        f"**文件名长度阈值（不含扩展名）**: {file_threshold}",
        f"**目录名长度阈值**: {dir_threshold}",
        f"**总路径长度阈值（从项目根）**: {total_threshold}",
        f"**文件名/目录名命中总数**: {len(all_hits)}",
        f"**总路径长度命中总数**: {len(total_path_hits)}",
        "",
        "---",
        "",
    ]

    # 文件名/目录名长度部分
    lines.append("# 一、文件名/目录名长度检查")
    lines.append("")
    
    if not all_hits:
        lines.append("### 未找到超长文件名或目录名")
        lines.append("")
    else:
        for dir_name in sorted(hits_by_dir.keys()):
            hits = hits_by_dir[dir_name]
            hits_sorted = sorted(hits, key=lambda x: (x["type"], -x["name_len"]))
            lines.extend([f"## {dir_name}", "", f"找到 {len(hits)} 个超长项", "", "| 类型 | 路径 | 长度 | 后缀 |", "|------|---------|-------------|------|"])
            for info in hits_sorted:
                lines.append(f"| {info['type']} | `{info['relative_path']}` | {info['name_len']} | {info['extension']} |")
            lines.append("")
            lines.append("---")
            lines.append("")

    # 总路径长度部分
    lines.append("# 二、总路径长度检查（从项目根开始）")
    lines.append("")
    
    if not total_path_hits:
        lines.append("### 未找到总路径长度超标的文件或目录")
        lines.append("")
    else:
        for dir_name in sorted(total_hits_by_dir.keys()):
            hits = total_hits_by_dir[dir_name]
            hits_sorted = sorted(hits, key=lambda x: (-x["total_len"], x["type"]))
            lines.extend([f"## {dir_name}", "", f"找到 {len(hits)} 个超长路径项", "", "| 类型 | 相对路径 | 总长度 | 后缀 |", "|------|---------|-------------|------|"])
            for info in hits_sorted:
                lines.append(f"| {info['type']} | `{info['rel_path']}` | {info['total_len']} | {info.get('extension', '')} |")
            lines.append("")
            lines.append("---")
            lines.append("")

    # 统计信息
    lines.extend(["## 统计信息", "", "### 按类型统计（文件名/目录名）", "", "| 类型 | 数量 |", "|------|------|"])
    type_count = {"File": 0, "Directory": 0}
    for info in all_hits:
        type_count[info["type"]] += 1
    for t, count in type_count.items():
        lines.append(f"| {t} | {count} |")
    lines.append("")
    
    lines.extend(["### 按类型统计（总路径长度）", "", "| 类型 | 数量 |", "|------|------|"])
    total_type_count = {"File": 0, "Directory": 0}
    for info in total_path_hits:
        total_type_count[info["type"]] += 1
    for t, count in total_type_count.items():
        lines.append(f"| {t} | {count} |")
    lines.append("")

    lines.extend(["### 按文件后缀统计 (仅限文件)", "", "| 后缀 | 数量 |", "|---------|------|"])
    ext_count = {}
    for info in all_hits:
        if info["type"] == "File":
            ext = info["extension"]
            ext_count[ext] = ext_count.get(ext, 0) + 1
    for ext in sorted(ext_count.keys(), key=lambda x: ext_count[x], reverse=True):
        lines.append(f"| {ext} | {ext_count[ext]} |")
    lines.append("")

    lines.extend(["### Top 10 文件名/目录名长度排名", "", "| 排名 | 类型 | 路径 | 长度 |", "|------|------|---------|-------------|"])
    top = sorted(all_hits, key=lambda x: x["name_len"], reverse=True)[:10]
    for idx, info in enumerate(top, 1):
        scan_root = info.get("scan_root")
        display_path = f"{scan_root.name}/{info['relative_path']}" if isinstance(scan_root, Path) else str(info["relative_path"])
        lines.append(f"| {idx} | {info['type']} | `{display_path}` | {info['name_len']} |")
    lines.append("")
    
    lines.extend(["### Top 10 总路径长度排名", "", "| 排名 | 类型 | 相对路径 | 总长度 |", "|------|------|---------|-------------|"])
    top_total = sorted(total_path_hits, key=lambda x: x["total_len"], reverse=True)[:10]
    for idx, info in enumerate(top_total, 1):
        lines.append(f"| {idx} | {info['type']} | `{info['rel_path']}` | {info['total_len']} |")
    
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="扫描指定目录中文件名/目录名长度超限的代码文件并生成报告")
    p.add_argument("scan_dirs", nargs="*", help="要扫描的目录列表（不传则使用脚本内置默认目录）")
    p.add_argument("--threshold-file", type=int, default=24, help="文件名长度阈值（不含扩展名，默认24）")
    p.add_argument("--threshold-dir", type=int, default=24, help="目录名长度阈值（默认24）")
    p.add_argument("--threshold-total", type=int, default=72, help="总路径长度阈值（从项目根，默认72）")
    p.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR), help="报告输出目录（默认使用脚本内置目录）")
    return p.parse_args()


def main():
    args = parse_args()
    if args.threshold_file <= 0 or args.threshold_dir <= 0 or args.threshold_total <= 0:
        raise ValueError(f"阈值必须大于0，当前: file={args.threshold_file}, dir={args.threshold_dir}, total={args.threshold_total}")
    output_dir = Path(args.output_dir).expanduser().resolve()
    scan_dirs = [Path(p).expanduser().resolve() for p in args.scan_dirs] if args.scan_dirs else DEFAULT_SCAN_DIRS

    logger.info("=" * 60)
    logger.info("开始扫描超长文件名与目录名")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"扫描目录数：{len(scan_dirs)}")
    logger.info(f"文件名长度阈值：{args.threshold_file}")
    logger.info(f"目录名长度阈值：{args.threshold_dir}")
    logger.info(f"总路径长度阈值：{args.threshold_total}")
    logger.info(f"报告输出目录：{output_dir}")
    logger.info("")

    # 扫描文件名/目录名长度
    all_hits = []
    for d in scan_dirs:
        try:
            hits = scan_directory_for_long_names(d, args.threshold_file, args.threshold_dir)
            all_hits.extend(hits)
            logger.info("")
        except Exception as e:
            logger.error(f"错误：扫描目录 {d} 失败 - {e}")
            continue

    if all_hits:
        logger.info(f"总共找到 {len(all_hits)} 个超长文件名/目录名")
    else:
        logger.info("没有找到超长文件名或目录名")
    logger.info("")
    
    # 扫描总路径长度
    logger.info("-" * 60)
    logger.info("开始扫描总路径长度")
    logger.info("-" * 60)
    logger.info("")
    
    total_path_hits = []
    for d in scan_dirs:
        try:
            hits = scan_total_path_length(d, args.threshold_total)
            total_path_hits.extend(hits)
            logger.info("")
        except Exception as e:
            logger.error(f"错误：扫描总路径长度 {d} 失败 - {e}")
            continue
    
    if total_path_hits:
        logger.info(f"总共找到 {len(total_path_hits)} 个超长路径项")
    else:
        logger.info("没有找到总路径长度超标的文件或目录")
    logger.info("")

    try:
        content = generate_report(all_hits, total_path_hits, scan_dirs, args.threshold_file, args.threshold_dir, args.threshold_total)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_name = f"long_filename_report_{ts}.md"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / report_name
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
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
