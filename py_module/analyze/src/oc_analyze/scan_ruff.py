"""Ruff Python 代码分析工具

使用 ruff 检查 Python 代码的质量问题并生成报告

默认启用规则：E,W,F,B,A,PLC,PLE,PLW,RUF
- E,W: pycodestyle（代码风格）
- F: Pyflakes（逻辑错误）
- B: flake8-bugbear（潜在 Bug）
- A: flake8-builtins（内置变量覆盖）
- PLC,PLE,PLW: Pylint（代码质量、错误、警告）
- RUF: Ruff 特定规则

使用示例:
    # 基本使用（扫描默认目录，使用默认规则集）
    python scan_ruff.py

    # 扫描指定目录
    python scan_ruff.py /path/to/project

    # 指定输出目录
    python scan_ruff.py --output-dir /path/to/output

    # 仅检查基础规则（E,W,F）
    python scan_ruff.py --select E,W,F

    # 检查所有规则
    python scan_ruff.py --select ALL

    # 忽略特定规则
    python scan_ruff.py --ignore E501,W293
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from oc_analyze.scan_utils import (
    DEFAULT_SCAN_DIRS,
    PROJECT_ROOT,
    get_git_tracked_files,
    get_report_output_dir,
)

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

# 输出报告目录
OUTPUT_DIR = get_report_output_dir("ruff")

# 默认启用的 ruff 规则
# E,W,F: pycodestyle + Pyflakes（基础代码风格和逻辑错误）
# B: flake8-bugbear（潜在 Bug）
# A: flake8-builtins（内置变量覆盖）
# PLC,PLE,PLW: Pylint（代码质量、错误、警告）
# RUF: Ruff 特定规则
DEFAULT_SELECT_RULES = "E,W,F,B,A,PLC,PLE,PLW,RUF"


def check_ruff_installed() -> bool:
    """检查 ruff 是否已安装"""
    try:
        result = subprocess.run(["ruff", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_ruff_check(
    directory: Path,
    select_rules: str = DEFAULT_SELECT_RULES,
    ignore_rules: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """在指定目录上运行 ruff 检查

    Args:
        directory: 要检查的目录
        select_rules: 要启用的规则（逗号分隔）
        ignore_rules: 要忽略的规则（逗号分隔）

    Returns:
        ruff 检查结果的列表
    """
    issues = []

    if not directory.exists():
        logger.warning(f"警告：目录不存在 - {directory}")
        return issues

    logger.info(f"正在使用 ruff 检查目录：{directory}")

    try:
        # 获取 git 追踪的 Python 文件
        tracked_files = get_git_tracked_files(directory)
        python_files = [f for f in tracked_files if f.suffix == ".py"]

        if not python_files:
            logger.info(f"在 {directory} 中没有找到 Python 文件")
            return issues

        logger.info(f"找到 {len(python_files)} 个 Python 文件需要检查")

        # 构建 ruff 命令
        cmd = [
            "ruff",
            "check",
            "--output-format",
            "json",
            "--select",
            select_rules,
        ]

        if ignore_rules:
            cmd.extend(["--ignore", ignore_rules])

        # 添加文件列表
        cmd.extend([str(f) for f in python_files])

        # 运行 ruff
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

        # ruff 返回非零退出码表示发现问题，这是正常的
        if result.returncode not in [0, 1]:
            logger.error(f"ruff 检查失败：{result.stderr}")
            return issues

        # 解析 JSON 输出
        if result.stdout:
            try:
                ruff_output = json.loads(result.stdout)
                for item in ruff_output:
                    issue = {
                        "path": Path(item.get("filename", "")),
                        "line": item.get("location", {}).get("row", 0),
                        "column": item.get("location", {}).get("column", 0),
                        "code": item.get("code", ""),
                        "message": item.get("message", ""),
                        "url": item.get("url", ""),
                    }
                    issues.append(issue)
            except json.JSONDecodeError as e:
                logger.error(f"解析 ruff 输出失败：{e}")

    except Exception as e:
        logger.error(f"错误：运行 ruff 检查时发生异常 - {e}")
        raise

    logger.info(f"在 {directory} 中找到 {len(issues)} 个问题")
    return issues


def run_ruff_format_check(
    directory: Path,
) -> List[Dict[str, Any]]:
    """检查代码格式问题（使用 ruff format --check）

    Args:
        directory: 要检查的目录

    Returns:
        格式问题的列表
    """
    format_issues = []

    if not directory.exists():
        return format_issues

    try:
        # 获取 git 追踪的 Python 文件
        tracked_files = get_git_tracked_files(directory)
        python_files = [f for f in tracked_files if f.suffix == ".py"]

        if not python_files:
            return format_issues

        # 构建 ruff format 命令
        cmd = [
            "ruff",
            "format",
            "--check",
            "--diff",
        ]
        cmd.extend([str(f) for f in python_files])

        # 运行 ruff format
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

        # 如果有格式问题，解析输出
        if result.returncode == 1 and result.stdout:
            # ruff format --diff 的输出格式较为简单
            # 我们记录哪些文件需要格式化
            lines = result.stdout.strip().split("\n")
            current_file = None

            for line in lines:
                if line.startswith("---"):
                    # 提取文件名
                    parts = line.split()
                    if len(parts) >= 2:
                        file_path = parts[1].strip()
                        if file_path.startswith("a/"):
                            file_path = file_path[2:]
                        current_file = PROJECT_ROOT / file_path
                elif line.startswith("+++ ") and current_file:
                    # 记录该文件需要格式化
                    format_issues.append(
                        {
                            "path": current_file,
                            "line": 0,
                            "column": 0,
                            "code": "FORMAT",
                            "message": "代码格式需要调整（运行 `ruff format` 修复）",
                            "url": "",
                        }
                    )
                    current_file = None

    except Exception as e:
        logger.warning(f"警告：检查代码格式时发生异常 - {e}")
        # 格式检查失败不应阻止其他检查

    return format_issues


def categorize_issues(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按规则代码对问题进行分类

    Args:
        issues: 问题列表

    Returns:
        按规则代码分类的问题字典
    """
    categorized: Dict[str, List[Dict[str, Any]]] = {}

    for issue in issues:
        code = issue.get("code", "UNKNOWN")
        if code not in categorized:
            categorized[code] = []
        categorized[code].append(issue)

    return categorized


def count_issues_by_file(issues: List[Dict[str, Any]]) -> Dict[Path, int]:
    """统计每个文件的问题数量

    Args:
        issues: 问题列表

    Returns:
        文件路径到问题数量的映射
    """
    file_counts: Dict[Path, int] = {}

    for issue in issues:
        path = issue.get("path")
        if path:
            file_counts[path] = file_counts.get(path, 0) + 1

    return file_counts


def generate_report(
    all_issues: List[Dict[str, Any]],
    scan_dirs: List[Path],
    select_rules: str,
    ignore_rules: Optional[str],
) -> str:
    """生成 markdown 报告

    Args:
        all_issues: 所有发现的问题
        scan_dirs: 扫描的目录列表
        select_rules: 启用的规则
        ignore_rules: 忽略的规则

    Returns:
        markdown 格式的报告内容
    """
    # 分类统计
    categorized = categorize_issues(all_issues)
    file_counts = count_issues_by_file(all_issues)

    # 生成报告内容
    report_lines = [
        "# Ruff Python 代码分析报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描目录数**: {len(scan_dirs)}",
        f"**启用规则**: `{select_rules}`",
    ]

    if ignore_rules:
        report_lines.append(f"**忽略规则**: `{ignore_rules}`")

    report_lines.extend(
        [
            f"**发现问题总数**: {len(all_issues)}",
            f"**涉及文件数**: {len(file_counts)}",
            "",
            "---",
            "",
        ]
    )

    if not all_issues:
        report_lines.extend(
            [
                "## 检查结果",
                "",
                "✅ **未发现任何问题！** 代码质量良好。",
                "",
            ]
        )
        return "\n".join(report_lines)

    # 按规则类型统计
    report_lines.extend(
        [
            "## 按规则类型统计",
            "",
            "| 规则代码 | 问题数量 | 说明 |",
            "|---------|---------|------|",
        ]
    )

    # 按问题数量排序
    sorted_codes = sorted(
        categorized.keys(), key=lambda x: len(categorized[x]), reverse=True
    )

    for code in sorted_codes:
        count = len(categorized[code])
        # 获取该规则的第一条消息作为说明
        sample_issue = categorized[code][0] if categorized[code] else {}
        message = sample_issue.get("message", "")[:50]
        if len(sample_issue.get("message", "")) > 50:
            message += "..."
        report_lines.append(f"| `{code}` | {count} | {message} |")

    report_lines.append("")

    # 问题最多的文件
    report_lines.extend(
        [
            "## 问题最多的文件",
            "",
            "| 排名 | 文件路径 | 问题数量 |",
            "|------|---------|---------|",
        ]
    )

    sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[
        :20
    ]  # 只显示前20个

    for idx, (file_path, count) in enumerate(sorted_files, 1):
        # 尝试获取相对路径
        try:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            display_path = str(rel_path)
        except ValueError:
            display_path = str(file_path)

        report_lines.append(f"| {idx} | `{display_path}` | {count} |")

    report_lines.append("")

    # 详细问题列表
    report_lines.extend(
        [
            "## 详细问题列表",
            "",
        ]
    )

    for code in sorted_codes:
        issues = categorized[code]
        report_lines.extend(
            [
                f"### {code}",
                "",
                f"**说明**: {issues[0].get('message', '') if issues else ''}",
                f"**数量**: {len(issues)}",
                "",
                "| 文件 | 行号 | 列号 |",
                "|------|------|------|",
            ]
        )

        # 按文件和行号排序
        sorted_issues = sorted(
            issues, key=lambda x: (str(x.get("path", "")), x.get("line", 0))
        )

        for issue in sorted_issues[:50]:  # 每种规则最多显示50条
            try:
                rel_path = issue["path"].relative_to(PROJECT_ROOT)
                display_path = str(rel_path)
            except (ValueError, KeyError):
                display_path = str(issue.get("path", "未知"))

            line = issue.get("line", 0)
            column = issue.get("column", 0)
            report_lines.append(f"| `{display_path}` | {line} | {column} |")

        if len(sorted_issues) > 50:
            report_lines.append(f"| ... | ... | ... |")
            report_lines.append(f"| *还有 {len(sorted_issues) - 50} 条未显示* | | |")

        report_lines.append("")

    # 修复建议
    report_lines.extend(
        [
            "## 修复建议",
            "",
            "### 自动修复",
            "",
            "运行以下命令可以自动修复部分问题：",
            "",
            "```bash",
            "# 自动修复可修复的问题",
            "ruff check --fix .",
            "",
            "# 自动格式化代码",
            "ruff format .",
            "```",
            "",
            "### 规则说明",
            "",
            "- **E/W** 规则：pycodestyle（代码风格）",
            "- **F** 规则：Pyflakes（逻辑错误和未使用代码）",
            "- **B** 规则：flake8-bugbear（潜在 Bug，如循环变量捕获问题）",
            "- **A** 规则：flake8-builtins（检查是否覆盖 Python 内置函数）",
            "- **PLC/PLE/PLW** 规则：Pylint（代码质量、错误、警告）",
            "- **RUF** 规则：Ruff 特定规则（额外代码质量检查）",
            "",
            "更多规则信息请访问：https://docs.astral.sh/ruff/rules/",
            "",
        ]
    )

    return "\n".join(report_lines)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="使用 ruff 分析 Python 代码质量并生成报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
默认启用规则: {DEFAULT_SELECT_RULES}
  - E,W: pycodestyle（代码风格）
  - F: Pyflakes（逻辑错误）
  - B: flake8-bugbear（潜在 Bug）
  - A: flake8-builtins（内置变量覆盖）
  - PLC,PLE,PLW: Pylint（代码质量、错误、警告）
  - RUF: Ruff 特定规则

示例:
  # 基本使用（扫描默认目录，使用默认规则集）
  python scan_ruff.py

  # 扫描指定目录
  python scan_ruff.py /path/to/project

  # 指定输出目录
  python scan_ruff.py --output-dir /path/to/output

  # 仅检查基础规则（E,W,F）
  python scan_ruff.py --select E,W,F

  # 检查所有规则
  python scan_ruff.py --select ALL

  # 忽略特定规则
  python scan_ruff.py --ignore E501,W293
        """,
    )

    parser.add_argument(
        "scan_dirs",
        nargs="*",
        help="要扫描的目录列表（不传则使用脚本内置默认目录）",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR),
        help=f"报告输出目录（默认使用脚本内置目录）",
    )

    parser.add_argument(
        "--select",
        type=str,
        default=DEFAULT_SELECT_RULES,
        help=f"要启用的 ruff 规则（默认: {DEFAULT_SELECT_RULES}）",
    )

    parser.add_argument(
        "--ignore",
        type=str,
        default=None,
        help="要忽略的 ruff 规则",
    )

    parser.add_argument(
        "--no-format-check",
        action="store_true",
        help="跳过代码格式检查",
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 检查 ruff 是否已安装
    if not check_ruff_installed():
        logger.error("错误：未找到 ruff。请先安装 ruff：")
        logger.info("  pixi add ruff")
        logger.info("  或")
        logger.info("  pip install ruff")
        sys.exit(1)

    output_dir = Path(args.output_dir).expanduser().resolve()

    if args.scan_dirs:
        scan_dirs = [Path(p).expanduser().resolve() for p in args.scan_dirs]
    else:
        scan_dirs = DEFAULT_SCAN_DIRS

    logger.info("=" * 60)
    logger.info("开始 Ruff Python 代码分析")
    logger.info("=" * 60)
    logger.info("")

    logger.info(f"扫描目录数：{len(scan_dirs)}")
    logger.info(f"启用规则：{args.select}")
    if args.ignore:
        logger.info(f"忽略规则：{args.ignore}")
    logger.info(f"报告输出目录：{output_dir}")
    logger.info("")

    all_issues = []

    # 扫描所有目录
    for scan_dir in scan_dirs:
        try:
            issues = run_ruff_check(scan_dir, args.select, args.ignore)
            all_issues.extend(issues)
            logger.info("")
        except Exception as e:
            logger.error(f"错误：扫描目录 {scan_dir} 失败 - {e}")
            continue

    # 格式检查
    if not args.no_format_check:
        logger.info("=" * 60)
        logger.info("检查代码格式")
        logger.info("=" * 60)
        logger.info("")

        for scan_dir in scan_dirs:
            try:
                format_issues = run_ruff_format_check(scan_dir)
                all_issues.extend(format_issues)
                if format_issues:
                    logger.info(
                        f"在 {scan_dir.name} 中找到 {len(format_issues)} 个格式问题"
                    )
                else:
                    logger.info(f"{scan_dir.name} 代码格式良好")
            except Exception as e:
                logger.error(f"警告：检查 {scan_dir} 格式时失败 - {e}")

        logger.info("")

    # 生成报告
    logger.info("=" * 60)
    logger.info("生成报告")
    logger.info("=" * 60)
    logger.info("")

    try:
        report_content = generate_report(
            all_issues, scan_dirs, args.select, args.ignore
        )

        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"ruff_report_{timestamp}.md"
        report_path = output_dir / report_filename

        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        # 写入报告
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"报告已生成：{report_path}")
        logger.info("")

        # 打印摘要
        if all_issues:
            categorized = categorize_issues(all_issues)
            logger.info("=" * 60)
            logger.info("分析摘要")
            logger.info("=" * 60)
            logger.info(f"发现问题总数：{len(all_issues)}")
            logger.info(f"涉及文件数：{len(count_issues_by_file(all_issues))}")
            logger.info("")
            logger.info("按规则类型统计：")
            for code in sorted(
                categorized.keys(), key=lambda x: len(categorized[x]), reverse=True
            ):
                logger.info(f"  {code}: {len(categorized[code])}")
            logger.info("")
            logger.info("建议运行以下命令修复问题：")
            logger.info("  ruff check --fix .")
            logger.info("  ruff format .")
        else:
            logger.info("=" * 60)
            logger.info("分析摘要")
            logger.info("=" * 60)
            logger.info("✅ 未发现任何问题！代码质量良好。")

        logger.info("")

    except Exception as e:
        logger.error(f"错误：生成报告失败 - {e}")
        raise

    logger.info("=" * 60)
    logger.info("分析完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"程序执行失败：{e}")
        sys.exit(1)
