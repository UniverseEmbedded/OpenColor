#!/usr/bin/env python3
"""
批量替换项目中的 print 语句为 loguru logger
使用 git ls-files 获取文件列表，只处理被 git 追踪的文件

用法:
  python replace_print.py                    # 处理整个项目
  python replace_print.py <文件路径>         # 处理单个文件
"""

import subprocess
import sys
from pathlib import Path
from typing import List


# 获取项目根目录 (当前脚本在 py_module/analyze/src/oc_analyze/ 下，向上 4 级是项目根目录)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def get_git_tracked_files(project_root: Path = PROJECT_ROOT) -> List[Path]:
    """使用 git ls-files 获取被 git 追踪的文件列表"""
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
        output = result.stdout.decode("utf-8")
        files = [project_root / f for f in output.split("\0") if f]
        return files
    except subprocess.CalledProcessError as e:
        print(f"错误：调用 git 命令失败 - {e}")
        return []
    except Exception as e:
        print(f"错误：获取 git 追踪文件时发生异常 - {e}")
        return []


def get_git_tracked_python_files(project_root: Path = PROJECT_ROOT) -> List[Path]:
    """获取被 git 追踪的 Python 文件列表"""
    all_files = get_git_tracked_files(project_root)
    return [
        f
        for f in all_files
        if f.suffix == ".py" and not f.name.startswith("replace_print")
    ]


def has_logger_setup(content: str) -> bool:
    """检查文件是否已经设置了 logger"""
    return (
        "from oc_core_02.utils.logger import get_logger" in content
        and "logger = get_logger(__name__)" in content
    )


def add_logger_import(content: str) -> str:
    """在文件开头的 import 块中添加 logger 导入"""
    lines = content.split("\n")

    # 策略：
    # 1. 跳过 shebang (#!/usr/bin/env python3)
    # 2. 跳过编码声明 (# -*- coding: utf-8 -*-)
    # 3. 跳过 docstring
    # 4. 找到所有 import 语句（包括多行 import）
    # 5. 在最后一个 import 块后插入

    insert_idx = 0
    in_docstring = False
    docstring_char = None
    in_multiline_import = False
    paren_depth = 0
    last_import_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            if not in_multiline_import:
                continue

        # 跳过 shebang
        if stripped.startswith("#!"):
            insert_idx = i + 1
            continue

        # 跳过编码声明
        if "coding" in stripped and stripped.startswith("#"):
            insert_idx = i + 1
            continue

        # 处理 docstring
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    # 单行 docstring
                    insert_idx = i + 1
                    continue
                else:
                    in_docstring = True
                    docstring_char = '"""' if '"""' in stripped else "'''"
                    continue
        else:
            if docstring_char in stripped:
                in_docstring = False
                docstring_char = None
                insert_idx = i + 1
            continue

        # 如果在多行 import 中，跟踪括号深度
        if in_multiline_import:
            # 计算括号深度变化
            for char in stripped:
                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth -= 1

            last_import_idx = i

            # 括号平衡，多行 import 结束
            if paren_depth == 0:
                in_multiline_import = False
            continue

        # 检查是否是新的 import 语句
        if stripped.startswith(("import ", "from ")):
            last_import_idx = i

            # 检查是否以 ( 结尾（多行 import 开始）
            if stripped.endswith("("):
                in_multiline_import = True
                paren_depth = 1
            continue
        else:
            # 不是 import 语句，代码开始
            break

    # 确定插入位置
    if last_import_idx >= 0:
        # 有 import 语句，在最后一个 import 后插入
        insert_idx = last_import_idx + 1
        # 跳过空行
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1
    # 否则使用 docstring/shebang 后的位置

    # 在插入位置添加 logger 导入
    logger_import = [
        "",
        "from oc_core_02.utils.logger import get_logger",
        "",
        "logger = get_logger(__name__)",
    ]

    lines = lines[:insert_idx] + logger_import + lines[insert_idx:]

    return "\n".join(lines)


def detect_log_level(text: str) -> str:
    """根据文本内容检测日志级别"""
    text_lower = text.lower()
    if any(
        k in text_lower
        for k in ["[错误]", "错误", "失败", "严重错误", "exception", "error", "fatal"]
    ):
        return "error"
    elif any(k in text_lower for k in ["[警告]", "警告", "warning", "warn"]):
        return "warning"
    elif any(k in text_lower for k in ["[信息]", "信息", "info", "完成", "成功"]):
        return "info"
    else:
        return "info"


def count_parens_outside_fstring(line: str) -> int:
    """计算一行中 f-string 外的括号数量变化"""
    count = 0
    in_string = False
    string_char = None
    i = 0
    while i < len(line):
        char = line[i]

        # 处理字符串
        if not in_string:
            if char in ('"', "'"):
                in_string = True
                string_char = char
            elif char == "(":
                count += 1
            elif char == ")":
                count -= 1
        else:
            # 在字符串内
            if char == string_char:
                # 检查是否是转义的
                if i > 0 and line[i - 1] != "\\":
                    in_string = False
                    string_char = None
            # 在 f-string 内，{ 和 } 不是代码括号
            # 但我们不需要特殊处理，因为它们在字符串内

        i += 1

    return count


def find_print_statements(content: str) -> list[tuple[int, int, str]]:
    """
    查找所有 print 语句的位置和内容
    返回: [(start_line, end_line, replacement), ...]
    """
    lines = content.split("\n")
    replacements = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # 匹配 print(
        if stripped.startswith("print("):
            indent = line[: len(line) - len(stripped)]
            start_line = i

            # 计算第一行的括号深度
            paren_depth = count_parens_outside_fstring(stripped)
            j = i

            # 继续收集直到括号平衡
            while paren_depth > 0 and j + 1 < len(lines):
                j += 1
                paren_depth += count_parens_outside_fstring(lines[j])

            end_line = j

            # 提取完整的 print 参数
            args_lines = []
            first_line = stripped[6:]  # 去掉 'print('
            args_lines.append(first_line)
            for k in range(i + 1, j + 1):
                args_lines.append(lines[k])

            args = "\n".join(args_lines).strip()
            # 去掉最后的外层右括号
            if args.endswith(")"):
                args = args[:-1]

            # 检测日志级别
            level = detect_log_level(args)

            # 构建替换语句
            replacement = f"{indent}logger.{level}({args})"

            replacements.append((start_line, end_line, replacement))
            i = j + 1
        else:
            i += 1

    return replacements


def apply_replacements(content: str, replacements: list[tuple[int, int, str]]) -> str:
    """应用替换"""
    lines = content.split("\n")

    # 从后往前替换，避免行号变化
    for start_line, end_line, replacement in reversed(replacements):
        lines = lines[:start_line] + [replacement] + lines[end_line + 1 :]

    return "\n".join(lines)


def process_file(py_file: Path) -> int:
    """处理单个文件，返回替换的数量"""
    try:
        content = py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = py_file.read_text(encoding="gbk")
        except Exception as e:
            print(f"读取文件失败: {py_file}, 错误: {e}")
            return 0
    except Exception as e:
        print(f"读取文件失败: {py_file}, 错误: {e}")
        return 0

    # 查找 print 语句
    replacements = find_print_statements(content)

    if not replacements:
        return 0

    # 检查是否已经有 logger 设置
    if not has_logger_setup(content):
        content = add_logger_import(content)
        # 重新查找（因为添加导入可能改变了行号）
        replacements = find_print_statements(content)

    if not replacements:
        return 0

    # 应用替换
    new_content = apply_replacements(content, replacements)

    try:
        py_file.write_text(new_content, encoding="utf-8")
        print(f"已处理: {py_file} (替换 {len(replacements)} 处)")
        return len(replacements)
    except Exception as e:
        print(f"写入文件失败: {py_file}, 错误: {e}")
        return 0


def main():
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        # 处理单个文件
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"错误: 文件不存在: {file_path}")
            sys.exit(1)
        if not file_path.suffix == ".py":
            print(f"错误: 不是 Python 文件: {file_path}")
            sys.exit(1)

        print(f"处理单个文件: {file_path}")
        count = process_file(file_path)
        print(f"替换完成，共替换 {count} 处")
    else:
        # 处理整个项目（仅 git 追踪的文件）
        print("开始批量替换 print 语句...")
        print(f"项目根目录: {PROJECT_ROOT}")
        print()

        # 获取 git 追踪的 Python 文件
        python_files = get_git_tracked_python_files()
        print(f"找到 {len(python_files)} 个被 git 追踪的 Python 文件")
        print()

        total_count = 0
        processed_files = 0

        for py_file in python_files:
            count = process_file(py_file)
            if count > 0:
                total_count += count
                processed_files += 1

        print()
        print(f"处理完成!")
        print(f"处理文件数: {processed_files}")
        print(f"替换总数: {total_count}")


if __name__ == "__main__":
    main()
