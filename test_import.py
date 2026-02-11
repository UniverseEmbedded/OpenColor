#!/usr/bin/env python3
"""测试 add_logger_import 函数"""

from pathlib import Path


def add_logger_import(content: str) -> str:
    """在文件开头的 import 块中添加 logger 导入"""
    lines = content.split("\n")

    # 找到文件顶部的 import 块（跳过 docstring）
    code_start_idx = 0
    in_docstring = False
    docstring_char = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            continue

        # 处理 docstring
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    continue
                else:
                    in_docstring = True
                    docstring_char = '"""' if '"""' in stripped else "'''"
                    continue
        else:
            if docstring_char in stripped:
                in_docstring = False
                docstring_char = None
            continue

        # 如果不是 import/from 语句，记录代码开始位置
        if not stripped.startswith(("import ", "from ")):
            code_start_idx = i
            logger.info(f"代码开始于第 {i + 1} 行: {line[:50]}")
            break

    # 现在从 code_start_idx 向前找 import 块
    import_block_end = -1
    in_multiline_import = False

    logger.info(f"从第 {code_start_idx} 行向前查找 import 块...")

    for i in range(code_start_idx - 1, -1, -1):
        stripped = lines[i].strip()

        # 跳过空行
        if not stripped:
            continue

        logger.info(f"  检查第 {i + 1} 行: {stripped[:50]}")

        # 检查是否结束多行 import
        if in_multiline_import:
            if stripped.startswith("from ") and stripped.endswith("("):
                in_multiline_import = False
                import_block_end = i
                logger.info(f"    -> 多行 import 结束于第 {i + 1} 行")
            elif stripped.startswith(("import ", "from ")):
                import_block_end = i
                logger.info(f"    -> import 语句在第 {i + 1} 行")
            continue

        # 检查是否是 import 语句
        if stripped.startswith(("import ", "from ")):
            import_block_end = i
            logger.info(f"    -> 找到 import 语句在第 {i + 1} 行")
            # 检查是否以 ( 结尾（多行 import 开始）
            if stripped.endswith("("):
                in_multiline_import = True
                logger.info(f"    -> 多行 import 开始")
        else:
            # 不是 import 语句，停止
            logger.info(f"    -> 不是 import 语句，停止")
            break

    logger.info(f"import_block_end = {import_block_end}")

    if import_block_end >= 0:
        # 在 import 块后面添加 logger 导入
        logger_import = [
            "",
            "from oc_core_02.utils.logger import get_logger",
            "",
            "logger = get_logger(__name__)",
        ]

        # 找到 import 块后的插入位置（跳过空行）
        insert_idx = import_block_end + 1
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1

        logger.info(f"插入位置: 第 {insert_idx + 1} 行")

        lines = lines[:insert_idx] + logger_import + lines[insert_idx:]

    return "\n".join(lines)


# 测试
py_file = Path("py_module/scripts/src/oc_scripts/stl/mixplane.py")
content = py_file.read_text(encoding="utf-8")

new_content = add_logger_import(content)

# 检查是否添加了导入
if "from oc_core_02.utils.logger import get_logger" in new_content:
    logger.info("\n✓ 成功添加了 logger 导入")
else:
    logger.info("\n✗ 没有添加 logger 导入")
