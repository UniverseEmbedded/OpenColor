/**
 * @file comment_utils.cpp
 * @brief 注释覆盖率分析工具 - 注释提取和字符统计模块
 *
 * 本模块提供以下功能：
 * - Tree-sitter注释范围提取
 * - Python docstring识别
 * - 代码和注释字符统计
 * - UTF-8解码和字符分类
 */

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <tree_sitter/api.h>

namespace {

struct ByteRange {
  uint32_t start = 0;
  uint32_t end = 0;
};

static bool is_common_comment_node_type(std::string_view type) {
  if (type.find("comment") != std::string_view::npos) return true;
  if (type.find("doc") != std::string_view::npos && type.find("comment") != std::string_view::npos) return true;
  return false;
}

static bool is_python_docstring(TSNode node) {
  const char* type_c = ts_node_type(node);
  if (!type_c) return false;
  if (std::string_view(type_c) != "string") return false;

  TSNode parent = ts_node_parent(node);
  if (ts_node_is_null(parent)) return false;

  const char* parent_type_c = ts_node_type(parent);
  if (!parent_type_c) return false;
  if (std::string_view(parent_type_c) != "expression_statement") return false;

  TSNode grandparent = ts_node_parent(parent);
  if (ts_node_is_null(grandparent)) return false;

  const char* grandparent_type_c = ts_node_type(grandparent);
  if (!grandparent_type_c) return false;

  std::string_view grandparent_type(grandparent_type_c);
  if (grandparent_type != "module" && grandparent_type != "block") return false;

  uint32_t parent_index = 0;
  uint32_t sibling_count = ts_node_child_count(grandparent);
  bool found = false;
  for (uint32_t i = 0; i < sibling_count; i++) {
    TSNode sibling = ts_node_child(grandparent, i);
    if (ts_node_eq(parent, sibling)) {
      parent_index = i;
      found = true;
      break;
    }
  }
  if (!found) return false;

  for (uint32_t i = 0; i < sibling_count; i++) {
    TSNode sibling = ts_node_child(grandparent, i);
    const char* sibling_type_c = ts_node_type(sibling);
    if (!sibling_type_c) continue;
    std::string_view sibling_type(sibling_type_c);
    if (sibling_type == "decorator") continue;
    return ts_node_eq(parent, sibling);
  }

  return false;
}

static std::vector<ByteRange> extract_comment_ranges(const std::string& source, const TSLanguage* language, std::string_view lang_name, std::string& out_error) {
  out_error.clear();
  if (!language) {
    out_error = "未找到对应语言的 Tree-sitter grammar";
    return {};
  }

  struct ParserDel {
    void operator()(TSParser* p) const {
      if (p) ts_parser_delete(p);
    }
  };

  thread_local std::unique_ptr<TSParser, ParserDel> parser;
  if (!parser) {
    parser.reset(ts_parser_new());
    if (!parser) {
      out_error = "创建 Tree-sitter Parser 失败";
      return {};
    }
  }

  if (!ts_parser_set_language(parser.get(), language)) {
    out_error = "设置 Tree-sitter language 失败（可能 ABI 不兼容）";
    return {};
  }

  TSTree* tree = ts_parser_parse_string(parser.get(), nullptr, source.data(), static_cast<uint32_t>(source.size()));
  if (!tree) {
    out_error = "解析失败：未生成语法树";
    return {};
  }

  bool is_python = lang_name == "python";

  std::vector<ByteRange> ranges;
  TSNode root = ts_tree_root_node(tree);
  TSTreeCursor cursor = ts_tree_cursor_new(root);

  while (true) {
    TSNode node = ts_tree_cursor_current_node(&cursor);
    const char* type_c = ts_node_type(node);
    if (type_c) {
      std::string_view type(type_c);
      bool is_comment = is_common_comment_node_type(type);
      if (!is_comment && is_python && is_python_docstring(node)) {
        is_comment = true;
      }
      if (is_comment) {
        uint32_t start = ts_node_start_byte(node);
        uint32_t end = ts_node_end_byte(node);
        if (end > start && end <= source.size()) ranges.push_back(ByteRange{start, end});
      }
    }

    if (ts_tree_cursor_goto_first_child(&cursor)) {
      continue;
    }

    bool advanced = false;
    while (!advanced) {
      if (ts_tree_cursor_goto_next_sibling(&cursor)) {
        advanced = true;
        break;
      }
      if (!ts_tree_cursor_goto_parent(&cursor)) {
        ts_tree_cursor_delete(&cursor);
        ts_tree_delete(tree);
        goto done;
      }
    }
  }

done:
  if (!ranges.empty()) {
    std::sort(ranges.begin(), ranges.end(), [](const ByteRange& a, const ByteRange& b) {
      if (a.start != b.start) return a.start < b.start;
      return a.end < b.end;
    });
    std::vector<ByteRange> merged;
    merged.reserve(ranges.size());
    for (const auto& r : ranges) {
      if (merged.empty() || r.start > merged.back().end) {
        merged.push_back(r);
      } else {
        merged.back().end = std::max(merged.back().end, r.end);
      }
    }
    ranges.swap(merged);
  }

  return ranges;
}

static bool decode_one_utf8(const std::string& s, size_t i, uint32_t& out_cp, size_t& out_next) {
  const uint8_t b0 = static_cast<uint8_t>(s[i]);
  if (b0 < 0x80) {
    out_cp = b0;
    out_next = i + 1;
    return true;
  }
  auto need_cont = [&](size_t j) -> bool {
    if (j >= s.size()) return false;
    uint8_t bj = static_cast<uint8_t>(s[j]);
    return (bj & 0xC0) == 0x80;
  };

  if ((b0 & 0xE0) == 0xC0) {
    if (!need_cont(i + 1)) return false;
    uint8_t b1 = static_cast<uint8_t>(s[i + 1]);
    uint32_t cp = ((b0 & 0x1F) << 6) | (b1 & 0x3F);
    if (cp < 0x80) return false;
    out_cp = cp;
    out_next = i + 2;
    return true;
  }
  if ((b0 & 0xF0) == 0xE0) {
    if (!need_cont(i + 1) || !need_cont(i + 2)) return false;
    uint8_t b1 = static_cast<uint8_t>(s[i + 1]);
    uint8_t b2 = static_cast<uint8_t>(s[i + 2]);
    uint32_t cp = ((b0 & 0x0F) << 12) | ((b1 & 0x3F) << 6) | (b2 & 0x3F);
    if (cp < 0x800) return false;
    if (cp >= 0xD800 && cp <= 0xDFFF) return false;
    out_cp = cp;
    out_next = i + 3;
    return true;
  }
  if ((b0 & 0xF8) == 0xF0) {
    if (!need_cont(i + 1) || !need_cont(i + 2) || !need_cont(i + 3)) return false;
    uint8_t b1 = static_cast<uint8_t>(s[i + 1]);
    uint8_t b2 = static_cast<uint8_t>(s[i + 2]);
    uint8_t b3 = static_cast<uint8_t>(s[i + 3]);
    uint32_t cp = ((b0 & 0x07) << 18) | ((b1 & 0x3F) << 12) | ((b2 & 0x3F) << 6) | (b3 & 0x3F);
    if (cp < 0x10000 || cp > 0x10FFFF) return false;
    out_cp = cp;
    out_next = i + 4;
    return true;
  }
  return false;
}

static bool is_ws(uint32_t cp) {
  if (cp == 0x20 || cp == 0x09 || cp == 0x0A || cp == 0x0D || cp == 0x0B || cp == 0x0C) return true;
  if (cp == 0x3000) return true;
  return false;
}

static bool is_cjk(uint32_t cp) {
  if (cp >= 0x4E00 && cp <= 0x9FFF) return true;
  if (cp >= 0x3400 && cp <= 0x4DBF) return true;
  if (cp >= 0x20000 && cp <= 0x2A6DF) return true;
  if (cp >= 0x2A700 && cp <= 0x2B73F) return true;
  if (cp >= 0x2B740 && cp <= 0x2B81F) return true;
  if (cp >= 0x2B820 && cp <= 0x2CEAF) return true;
  if (cp >= 0xF900 && cp <= 0xFAFF) return true;
  return false;
}

static void count_coverage_chars(const std::string& s, const std::vector<ByteRange>& comment_ranges, uint64_t& out_code, uint64_t& out_comment, uint64_t& out_comment_zh) {
  out_code = 0;
  out_comment = 0;
  out_comment_zh = 0;

  size_t i = 0;
  size_t r_idx = 0;
  while (i < s.size()) {
    uint32_t cp = 0;
    size_t next = i + 1;
    if (!decode_one_utf8(s, i, cp, next)) {
      cp = 0xFFFD;
      next = i + 1;
    }

    while (r_idx < comment_ranges.size() && i >= comment_ranges[r_idx].end) {
      r_idx++;
    }
    bool in_comment = false;
    if (r_idx < comment_ranges.size()) {
      const auto& r = comment_ranges[r_idx];
      in_comment = (i >= r.start && i < r.end);
    }

    if (!is_ws(cp)) {
      if (in_comment) {
        out_comment++;
        if (is_cjk(cp)) out_comment_zh++;
      } else {
        out_code++;
      }
    }

    i = next;
  }
}

}