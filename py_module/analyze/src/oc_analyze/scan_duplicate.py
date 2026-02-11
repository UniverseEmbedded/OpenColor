"""代码重复内容扫描工具

使用 Winnowing + LSH 算法检测代码中的重复内容

使用示例:
    # 基本使用（扫描默认目录）
    python scan_duplicate.py

    # 扫描指定目录
    python scan_duplicate.py /path/to/project

    # 指定最小匹配行数
    python scan_duplicate.py --min-lines 10

    # 指定相似度阈值
    python scan_duplicate.py --similarity 0.9
"""

from __future__ import annotations


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
import argparse
import hashlib
import sys
import tokenize
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from oc_analyze.scan_utils import (
    DEFAULT_SCAN_DIRS,
    PROJECT_ROOT,
    get_git_tracked_files,
    get_report_output_dir,
    is_code_file,
)

# 输出报告目录
OUTPUT_DIR = get_report_output_dir("duplicate")

# 默认配置
DEFAULT_MIN_LINES = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_K_GRAM_SIZE = 5
DEFAULT_WINDOW_SIZE = 4
DEFAULT_NUM_HASH_FUNCTIONS = 8  # LSH 哈希函数数量
DEFAULT_BANDS = 4  # LSH band 数量


@dataclass
class CodeBlock:
    """代码块信息"""

    file_path: Path
    start_line: int
    end_line: int
    content: str
    normalized_content: str
    content_hash: str
    fingerprints: Optional[Set[str]] = None  # 预计算的指纹
    minhash_signature: Optional[List[int]] = None  # MinHash 签名

    def __hash__(self) -> int:
        return id(self)


@dataclass
class DuplicateGroup:
    """重复代码组"""

    blocks: List[CodeBlock]
    similarity_score: float
    match_type: str  # "exact" 或 "similar"

    @property
    def file_count(self) -> int:
        """涉及多少个文件"""
        return len(set(b.file_path for b in self.blocks))

    @property
    def total_lines(self) -> int:
        """总重复行数"""
        return sum(b.end_line - b.start_line + 1 for b in self.blocks)

    @property
    def primary_content(self) -> str:
        """获取主要内容（用于展示）"""
        if not self.blocks:
            return ""
        return self.blocks[0].content


def normalize_line(line: str) -> str:
    """标准化单行代码"""
    line = line.strip()
    in_string = False
    string_char = None
    result = []
    for i, char in enumerate(line):
        if not in_string:
            if char in ('"', "'"):
                in_string = True
                string_char = char
            elif char == "#":
                break
        else:
            if char == string_char and (i == 0 or line[i - 1] != "\\"):
                in_string = False
                string_char = None
        result.append(char)
    return "".join(result).strip()


def normalize_content(content: str) -> str:
    """规范化代码内容用于比较"""
    lines = content.split("\n")
    normalized_lines = []
    for line in lines:
        norm_line = normalize_line(line)
        if norm_line:
            normalized_lines.append(norm_line)
    return "\n".join(normalized_lines)


def tokenize_code(content: str) -> List[str]:
    """将代码分词为 token 列表"""
    tokens = []
    try:
        import io

        for tok in tokenize.generate_tokens(io.StringIO(content).readline):
            tok_type = tok.type
            tok_string = tok.string
            if tok_type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING):
                continue
            if tok_type == tokenize.COMMENT:
                continue
            if tok_type == tokenize.INDENT or tok_type == tokenize.DEDENT:
                continue
            if tok_type == tokenize.NAME:
                keywords = {
                    "if",
                    "else",
                    "elif",
                    "for",
                    "while",
                    "def",
                    "class",
                    "return",
                    "import",
                    "from",
                    "as",
                    "try",
                    "except",
                    "finally",
                    "with",
                    "yield",
                    "lambda",
                    "and",
                    "or",
                    "not",
                    "in",
                    "is",
                    "None",
                    "True",
                    "False",
                    "pass",
                    "break",
                    "continue",
                    "raise",
                    "assert",
                    "del",
                    "global",
                    "nonlocal",
                    "async",
                    "await",
                }
                if tok_string not in keywords:
                    tokens.append("IDENT")
                else:
                    tokens.append(tok_string)
            elif tok_type == tokenize.STRING:
                tokens.append("STRING")
            elif tok_type == tokenize.NUMBER:
                tokens.append("NUMBER")
            else:
                tokens.append(tok_string)
    except Exception:
        return content.split()
    return tokens


def compute_hash(text: str) -> str:
    """计算文本的 MD5 哈希"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def winnow_fingerprints(
    tokens: List[str],
    k: int = DEFAULT_K_GRAM_SIZE,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> Set[str]:
    """使用 Winnowing 算法生成指纹"""
    if len(tokens) < k:
        return set()

    kgrams = []
    for i in range(len(tokens) - k + 1):
        kgram = " ".join(tokens[i : i + k])
        kgram_hash = compute_hash(kgram)
        kgrams.append((i, kgram_hash))

    if not kgrams:
        return set()

    fingerprints = set()
    window = []

    for i, (pos, h) in enumerate(kgrams):
        h_int = int(h, 16)
        window.append((pos, h, h_int))

        if len(window) >= window_size:
            min_hash = min(window, key=lambda x: x[2])
            fingerprints.add(min_hash[1])
            window.pop(0)

    if window:
        min_hash = min(window, key=lambda x: x[2])
        fingerprints.add(min_hash[1])

    return fingerprints


def compute_minhash_signature(
    fingerprints: Set[str], num_hash_functions: int = DEFAULT_NUM_HASH_FUNCTIONS
) -> List[int]:
    """计算 MinHash 签名

    使用多个哈希函数对指纹集合进行签名，用于 LSH 快速筛选候选对
    """
    if not fingerprints:
        return [0] * num_hash_functions

    signature = []
    for i in range(num_hash_functions):
        # 使用不同的哈希函数 (h_i(x) = (a_i * x + b_i) % p)
        min_hash = float("inf")
        for fp in fingerprints:
            fp_int = int(fp, 16)
            # 简单的哈希函数族
            hash_val = ((i + 1) * fp_int + i * 31) % (2**32)
            min_hash = min(min_hash, hash_val)
        signature.append(int(min_hash))

    return signature


def extract_code_blocks(
    file_path: Path, min_lines: int = DEFAULT_MIN_LINES
) -> List[CodeBlock]:
    """从文件中提取代码块"""
    blocks = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"警告：无法读取文件 {file_path} - {e}")
        return blocks

    lines = content.split("\n")

    # 1. 提取函数和类
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("def ") or stripped.startswith("class "):
            start_line = i
            base_indent = len(line) - len(line.lstrip())

            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip():
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= base_indent and not next_line.strip().startswith(
                        "@"
                    ):
                        break
                j += 1

            end_line = j - 1
            block_content = "\n".join(lines[start_line : end_line + 1])
            normalized = normalize_content(block_content)

            if end_line - start_line + 1 >= min_lines and normalized:
                blocks.append(
                    CodeBlock(
                        file_path=file_path,
                        start_line=start_line + 1,
                        end_line=end_line + 1,
                        content=block_content,
                        normalized_content=normalized,
                        content_hash=compute_hash(normalized),
                    )
                )

            i = j
        else:
            i += 1

    # 2. 添加滑动窗口块
    window_size = max(min_lines, 10)
    for i in range(len(lines) - window_size + 1):
        in_existing_block = False
        for block in blocks:
            if block.start_line <= i + 1 <= block.end_line:
                in_existing_block = True
                break

        if in_existing_block:
            continue

        block_content = "\n".join(lines[i : i + window_size])
        normalized = normalize_content(block_content)

        if normalized:
            blocks.append(
                CodeBlock(
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=i + window_size,
                    content=block_content,
                    normalized_content=normalized,
                    content_hash=compute_hash(normalized),
                )
            )

    return blocks


def precompute_block_features(blocks: List[CodeBlock]) -> None:
    """预计算所有代码块的指纹和 MinHash 签名"""
    try:
        from tqdm import tqdm

        iterator = tqdm(blocks, desc="预计算特征", unit="块")
    except ImportError:
        iterator = blocks
        logger.info("预计算特征中...")

    for block in iterator:
        tokens = tokenize_code(block.content)
        block.fingerprints = winnow_fingerprints(tokens)
        block.minhash_signature = compute_minhash_signature(block.fingerprints)


def get_lsh_buckets(
    blocks: List[CodeBlock], bands: int = DEFAULT_BANDS
) -> Dict[Tuple[int, Tuple[int, ...]], List[CodeBlock]]:
    """使用 LSH 将代码块分桶

    将 MinHash 签名分成多个 band，每个 band 作为一个桶的键
    相似度高的代码块有很大概率落入同一个桶
    """
    buckets: Dict[Tuple[int, Tuple[int, ...]], List[CodeBlock]] = {}

    for block in blocks:
        if block.minhash_signature is None:
            continue

        sig = block.minhash_signature
        rows_per_band = len(sig) // bands

        for band_idx in range(bands):
            start = band_idx * rows_per_band
            end = start + rows_per_band if band_idx < bands - 1 else len(sig)
            band_signature = tuple(sig[start:end])

            bucket_key = (band_idx, band_signature)
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(block)

    return buckets


def calculate_similarity(block1: CodeBlock, block2: CodeBlock) -> float:
    """计算两个代码块的相似度（使用预计算的指纹）"""
    # 1. 完全匹配检查
    if block1.content_hash == block2.content_hash:
        return 1.0

    # 2. 规范化内容匹配
    if block1.normalized_content == block2.normalized_content:
        return 0.95

    # 3. 使用预计算的指纹计算 Jaccard 相似度
    if block1.fingerprints is None or block2.fingerprints is None:
        return 0.0

    fingerprints1 = block1.fingerprints
    fingerprints2 = block2.fingerprints

    if not fingerprints1 or not fingerprints2:
        return 0.0

    intersection = len(fingerprints1 & fingerprints2)
    union = len(fingerprints1 | fingerprints2)

    if union == 0:
        return 0.0

    return intersection / union


def find_duplicates_lsh(
    blocks: List[CodeBlock], similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> List[DuplicateGroup]:
    """使用 LSH 快速查找重复代码组"""
    groups = []
    processed_pairs = set()

    # 1. 预计算特征
    precompute_block_features(blocks)

    # 2. 处理完全重复（按哈希）
    hash_groups: Dict[str, List[CodeBlock]] = {}
    for block in blocks:
        if block.content_hash not in hash_groups:
            hash_groups[block.content_hash] = []
        hash_groups[block.content_hash].append(block)

    for h, group_blocks in hash_groups.items():
        if len(group_blocks) > 1:
            files = set(b.file_path for b in group_blocks)
            if len(files) > 1:
                groups.append(
                    DuplicateGroup(
                        blocks=group_blocks, similarity_score=1.0, match_type="exact"
                    )
                )

    # 3. 使用 LSH 找相似候选对
    logger.info("构建 LSH 桶...")
    buckets = get_lsh_buckets(blocks)

    # 收集候选对
    candidate_pairs = set()
    for bucket in buckets.values():
        if len(bucket) < 2:
            continue
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                b1, b2 = bucket[i], bucket[j]
                # 跳过同一文件的比较
                if b1.file_path == b2.file_path:
                    continue
                # 使用 id 排序确保唯一性
                pair_key = tuple(sorted([id(b1), id(b2)]))
                candidate_pairs.add((pair_key, b1, b2))

    logger.info(f"LSH 筛选出 {len(candidate_pairs)} 个候选对")

    # 4. 精确计算候选对的相似度
    try:
        from tqdm import tqdm

        candidate_iterator = tqdm(list(candidate_pairs), desc="精确比较", unit="对")
    except ImportError:
        candidate_iterator = list(candidate_pairs)
        logger.info(f"精确比较 {len(candidate_pairs)} 个候选对...")

    similar_groups_dict: Dict[int, List[CodeBlock]] = {}

    for _, block1, block2 in candidate_iterator:
        similarity = calculate_similarity(block1, block2)

        if similarity >= similarity_threshold:
            b1_id = id(block1)
            b2_id = id(block2)

            # 合并到组
            if b1_id in similar_groups_dict:
                if block2 not in similar_groups_dict[b1_id]:
                    similar_groups_dict[b1_id].append(block2)
            elif b2_id in similar_groups_dict:
                if block1 not in similar_groups_dict[b2_id]:
                    similar_groups_dict[b2_id].append(block1)
            else:
                similar_groups_dict[b1_id] = [block1, block2]

    # 转换为 DuplicateGroup
    processed_blocks = set()
    for group_blocks in similar_groups_dict.values():
        # 去重
        unique_blocks = []
        for b in group_blocks:
            if id(b) not in processed_blocks:
                unique_blocks.append(b)
                processed_blocks.add(id(b))

        if len(unique_blocks) > 1:
            avg_similarity = sum(
                calculate_similarity(unique_blocks[0], b) for b in unique_blocks[1:]
            ) / (len(unique_blocks) - 1)

            groups.append(
                DuplicateGroup(
                    blocks=unique_blocks,
                    similarity_score=avg_similarity,
                    match_type="similar",
                )
            )

    return groups


def scan_directory(
    directory: Path, min_lines: int = DEFAULT_MIN_LINES
) -> List[CodeBlock]:
    """扫描目录，提取所有代码块"""
    all_blocks = []

    if not directory.exists():
        logger.warning(f"警告：目录不存在 - {directory}")
        return all_blocks

    logger.info(f"正在扫描目录：{directory} (仅扫描 git 追踪的文件)")

    try:
        tracked_files = get_git_tracked_files(directory)
        code_files = [f for f in tracked_files if is_code_file(f)]

        logger.info(f"找到 {len(code_files)} 个代码文件")

        try:
            from tqdm import tqdm

            file_iterator = tqdm(code_files, desc="提取代码块", unit="文件")
        except ImportError:
            file_iterator = code_files

        for file_path in file_iterator:
            try:
                blocks = extract_code_blocks(file_path, min_lines)
                all_blocks.extend(blocks)
            except Exception as e:
                logger.warning(f"警告：处理文件 {file_path} 时出错 - {e}")

    except Exception as e:
        logger.error(f"错误：扫描目录 {directory} 时发生异常 - {e}")
        raise

    logger.info(f"提取了 {len(all_blocks)} 个代码块")
    return all_blocks


def generate_report(
    groups: List[DuplicateGroup],
    scan_dirs: List[Path],
    min_lines: int,
    similarity_threshold: float,
) -> str:
    """生成 Markdown 报告"""
    sorted_groups = sorted(
        groups, key=lambda g: (g.similarity_score, g.total_lines), reverse=True
    )

    report_lines = [
        "# 代码重复内容扫描报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描目录数**: {len(scan_dirs)}",
        f"**最小匹配行数**: {min_lines}",
        f"**相似度阈值**: {similarity_threshold:.0%}",
        f"**发现重复组数**: {len(groups)}",
        "",
        "---",
        "",
    ]

    if not groups:
        report_lines.extend(
            [
                "## 检查结果",
                "",
                "✅ **未发现重复内容！** 代码结构良好。",
                "",
            ]
        )
        return "\n".join(report_lines)

    exact_groups = [g for g in groups if g.match_type == "exact"]
    similar_groups = [g for g in groups if g.match_type == "similar"]

    total_exact_lines = sum(g.total_lines for g in exact_groups)
    total_similar_lines = sum(g.total_lines for g in similar_groups)

    report_lines.extend(
        [
            "## 统计摘要",
            "",
            "| 类型 | 组数 | 重复行数 |",
            "|-----|------|---------|",
            f"| 完全重复 | {len(exact_groups)} | {total_exact_lines} |",
            f"| 相似重复 | {len(similar_groups)} | {total_similar_lines} |",
            f"| **总计** | **{len(groups)}** | **{total_exact_lines + total_similar_lines}** |",
            "",
        ]
    )

    file_duplicates: Dict[Path, int] = {}
    for group in groups:
        for block in group.blocks:
            file_duplicates[block.file_path] = (
                file_duplicates.get(block.file_path, 0) + 1
            )

    report_lines.extend(
        [
            "## 涉及文件统计",
            "",
            "| 文件路径 | 重复块数 |",
            "|---------|---------|",
        ]
    )

    sorted_files = sorted(file_duplicates.items(), key=lambda x: x[1], reverse=True)[
        :20
    ]
    for file_path, count in sorted_files:
        try:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            display_path = str(rel_path)
        except ValueError:
            display_path = str(file_path)
        report_lines.append(f"| `{display_path}` | {count} |")

    report_lines.append("")

    report_lines.extend(
        [
            "## 重复详情",
            "",
        ]
    )

    for idx, group in enumerate(sorted_groups[:30], 1):
        match_type_str = "完全重复" if group.match_type == "exact" else "相似重复"

        report_lines.extend(
            [
                f"### {idx}. {match_type_str} (相似度: {group.similarity_score:.0%})",
                "",
                "**涉及位置**:",
                "",
            ]
        )

        for block in group.blocks:
            try:
                rel_path = block.file_path.relative_to(PROJECT_ROOT)
                display_path = str(rel_path)
            except ValueError:
                display_path = str(block.file_path)

            report_lines.append(
                f"- `{display_path}` (第 {block.start_line}-{block.end_line} 行, "
                f"共 {block.end_line - block.start_line + 1} 行)"
            )

        report_lines.extend(
            [
                "",
                "**代码预览**:",
                "",
                "```python",
            ]
        )

        preview_lines = group.primary_content.split("\n")[:10]
        report_lines.extend(preview_lines)

        if len(group.primary_content.split("\n")) > 10:
            report_lines.append("...")

        report_lines.extend(
            [
                "```",
                "",
                "---",
                "",
            ]
        )

    report_lines.extend(
        [
            "## 修复建议",
            "",
            "### 完全重复",
            "",
            "完全重复的代码应该提取为公共函数或模块：",
            "",
            "1. **提取公共函数**：将重复的代码块提取到一个独立的函数中",
            "2. **创建共享模块**：如果多个文件有重复，考虑创建共享工具模块",
            "3. **使用继承或组合**：对于类的重复，考虑使用继承或组合模式",
            "",
            "### 相似重复",
            "",
            "相似重复的代码可以通过参数化来统一：",
            "",
            "1. **参数化差异**：将不同的部分作为参数传入",
            "2. **使用策略模式**：如果逻辑相似但实现不同，考虑策略模式",
            "3. **模板方法模式**：对于结构相似但细节不同的代码",
            "",
        ]
    )

    return "\n".join(report_lines)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="扫描代码中的重复内容（使用 LSH 加速）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本使用（扫描默认目录）
  python scan_duplicate.py

  # 扫描指定目录
  python scan_duplicate.py /path/to/project

  # 指定最小匹配行数
  python scan_duplicate.py --min-lines 10

  # 指定相似度阈值
  python scan_duplicate.py --similarity 0.9

  # 调整 LSH 参数（更多 band = 更严格，更少候选）
  python scan_duplicate.py --bands 8
        """,
    )

    parser.add_argument(
        "scan_dirs",
        nargs="*",
        help="要扫描的目录列表（不传则使用脚本内置默认目录）",
    )

    parser.add_argument(
        "--min-lines",
        type=int,
        default=DEFAULT_MIN_LINES,
        help=f"最小匹配行数（默认: {DEFAULT_MIN_LINES}）",
    )

    parser.add_argument(
        "--similarity",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f"相似度阈值，0-1之间（默认: {DEFAULT_SIMILARITY_THRESHOLD}）",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR),
        help="报告输出目录（默认使用脚本内置目录）",
    )

    parser.add_argument(
        "--bands",
        type=int,
        default=DEFAULT_BANDS,
        help=f"LSH band 数量（默认: {DEFAULT_BANDS}，越多越严格）",
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    if args.similarity < 0 or args.similarity > 1:
        raise ValueError(f"相似度阈值必须在 0-1 之间，当前: {args.similarity}")

    if args.min_lines < 1:
        raise ValueError(f"最小匹配行数必须大于0，当前: {args.min_lines}")

    output_dir = Path(args.output_dir).expanduser().resolve()

    if args.scan_dirs:
        scan_dirs = [Path(p).expanduser().resolve() for p in args.scan_dirs]
    else:
        scan_dirs = DEFAULT_SCAN_DIRS

    logger.info("=" * 60)
    logger.info("开始扫描代码重复内容")
    logger.info("=" * 60)
    logger.info("")

    logger.info(f"扫描目录数：{len(scan_dirs)}")
    logger.info(f"最小匹配行数：{args.min_lines}")
    logger.info(f"相似度阈值：{args.similarity:.0%}")
    logger.info(f"LSH bands：{args.bands}")
    logger.info(f"报告输出目录：{output_dir}")
    logger.info("")

    # 检查 tqdm
    try:
        from tqdm import tqdm

        logger.info("✓ 已安装 tqdm，将显示进度条")
    except ImportError:
        logger.info("! 未安装 tqdm，建议安装：pixi add tqdm")
    logger.info("")

    # 收集所有代码块
    all_blocks = []
    for scan_dir in scan_dirs:
        try:
            blocks = scan_directory(scan_dir, args.min_lines)
            all_blocks.extend(blocks)
            logger.info("")
        except Exception as e:
            logger.error(f"错误：扫描目录 {scan_dir} 失败 - {e}")
            continue

    if not all_blocks:
        logger.info("未找到任何代码块，扫描结束")
        return

    logger.info(f"总共提取了 {len(all_blocks)} 个代码块")
    logger.info("")

    # 查找重复（使用 LSH 加速）
    logger.info("=" * 60)
    logger.info("正在分析重复内容...")
    logger.info("=" * 60)
    logger.info("")

    try:
        duplicate_groups = find_duplicates_lsh(all_blocks, args.similarity)
        logger.info(f"找到 {len(duplicate_groups)} 组重复内容")
        logger.info("")
    except Exception as e:
        logger.error(f"错误：分析重复内容时失败 - {e}")
        import traceback

        traceback.print_exc()
        raise

    # 生成报告
    logger.info("=" * 60)
    logger.info("生成报告")
    logger.info("=" * 60)
    logger.info("")

    try:
        report_content = generate_report(
            duplicate_groups, scan_dirs, args.min_lines, args.similarity
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"duplicate_report_{timestamp}.md"
        report_path = output_dir / report_filename

        output_dir.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"报告已生成：{report_path}")
        logger.info("")

        if duplicate_groups:
            exact_count = len([g for g in duplicate_groups if g.match_type == "exact"])
            similar_count = len(
                [g for g in duplicate_groups if g.match_type == "similar"]
            )

            logger.info("=" * 60)
            logger.info("扫描摘要")
            logger.info("=" * 60)
            logger.info(f"发现重复组数：{len(duplicate_groups)}")
            logger.info(f"  - 完全重复：{exact_count}")
            logger.info(f"  - 相似重复：{similar_count}")
            logger.info("")
            logger.info("建议检查报告并考虑重构重复代码")
        else:
            logger.info("=" * 60)
            logger.info("扫描摘要")
            logger.info("=" * 60)
            logger.info("✅ 未发现重复内容！代码结构良好。")

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
