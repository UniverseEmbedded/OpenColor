/**
 * @file main.cpp
 * @brief 注释覆盖率分析工具 - 主程序入口
 *
 * 本程序用于分析代码库的注释覆盖率，支持多种编程语言。
 * 使用Tree-sitter进行语法解析，准确识别注释范围。
 */

#include <algorithm>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include <tree_sitter/api.h>

namespace fs = std::filesystem;

struct ByteRange {
  uint32_t start = 0;
  uint32_t end = 0;
};

struct FileEntry {
  std::string path;
  std::string lang;
  std::string source;
  std::string error;
};

struct FileStats {
  std::string path;
  std::string lang;
  uint64_t code_chars = 0;
  uint64_t comment_chars = 0;
  uint64_t comment_zh_chars = 0;
  std::string error;
};

struct LanguageStats {
  std::string lang;
  uint64_t total_code = 0;
  uint64_t total_comment = 0;
  uint64_t total_comment_zh = 0;
  uint64_t file_count = 0;
};

struct SummaryStats {
  uint64_t total_code = 0;
  uint64_t total_comment = 0;
  uint64_t total_comment_zh = 0;
  uint64_t file_count = 0;
  std::vector<LanguageStats> by_language;
  std::vector<FileStats> file_details;
};

static std::unordered_map<std::string, std::string> build_ext_to_lang() {
  std::unordered_map<std::string, std::string> m;
  m[".c"] = "c";
  m[".cpp"] = "cpp";
  m[".cc"] = "cpp";
  m[".cxx"] = "cpp";
  m[".hpp"] = "cpp";
  m[".h"] = "cpp";
  m[".hxx"] = "cpp";
  m[".py"] = "python";
  m[".js"] = "javascript";
  m[".ts"] = "typescript";
  m[".tsx"] = "typescript";
  m[".jsx"] = "javascript";
  m[".java"] = "java";
  m[".go"] = "go";
  m[".rs"] = "rust";
  m[".swift"] = "swift";
  m[".kt"] = "kotlin";
  m[".cs"] = "c_sharp";
  m[".php"] = "php";
  m[".rb"] = "ruby";
  m[".lua"] = "lua";
  m[".sh"] = "shell";
  m[".bash"] = "shell";
  m[".zsh"] = "shell";
  m[".fish"] = "shell";
  m[".sql"] = "sql";
  m[".html"] = "html";
  m[".css"] = "css";
  m[".scss"] = "scss";
  m[".less"] = "less";
  m[".xml"] = "xml";
  m[".json"] = "json";
  m[".yaml"] = "yaml";
  m[".yml"] = "yaml";
  m[".toml"] = "toml";
  m[".ini"] = "ini";
  m[".cmake"] = "cmake";
  m[".make"] = "make";
  m[".mk"] = "make";
  m[".dockerfile"] = "dockerfile";
  m[".dockerignore"] = "dockerignore";
  m[".gitignore"] = "gitignore";
  m[".gitattributes"] = "gitattributes";
  m[".editorconfig"] = "editorconfig";
  m[".eslintrc"] = "eslint";
  m[".prettierrc"] = "prettier";
  m[".prettierrc.json"] = "prettier";
  m[".prettierrc.yml"] = "prettier";
  m[".prettierrc.yaml"] = "prettier";
  m[".prettierrc.js"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.toml"] = "prettier";
  m[".prettierrc.json5"] = "prettier";
  m[".prettierrc.jsonc"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc.ts"] = "prettier";
  m[".prettierrc.cts"] = "prettier";
  m[".prettierrc.mts"] = "prettier";
  m[".prettierrc.tsx"] = "prettier";
  m[".prettierrc.jsx"] = "prettier";
  m[".prettierrc.vue"] = "prettier";
  m[".prettierrc.svelte"] = "prettier";
  m[".prettierrc.astro"] = "prettier";
  m[".prettierrc.gjs"] = "prettier";
  m[".prettierrc.gts"] = "prettier";
  m[".prettierrc.cjs.mjs"] = "prettier";
  m[".prettierrc.cjs.ts"] = "prettier";
  m[".prettierrc.cjs.tsx"] = "prettier";
  m[".prettierrc.cjs.jsx"] = "prettier";
  m[".prettierrc.mjs.js"] = "prettier";
  m[".prettierrc.mjs.ts"] = "prettier";
  m[".prettierrc.mjs.tsx"] = "prettier";
  m[".prettierrc.mjs.jsx"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc"] = "prettier";
  m[".prettierrc.json"] = "prettier";
  m[".prettierrc.yml"] = "prettier";
  m[".prettierrc.yaml"] = "prettier";
  m[".prettierrc.js"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc.ts"] = "prettier";
  m[".prettierrc.cts"] = "prettier";
  m[".prettierrc.mts"] = "prettier";
  m[".prettierrc.json5"] = "prettier";
  m[".prettierrc.jsonc"] = "prettier";
  m[".prettierrc.gjs"] = "prettier";
  m[".prettierrc.gts"] = "prettier";
  m[".prettierrc.cjs.mjs"] = "prettier";
  m[".prettierrc.cjs.ts"] = "prettier";
  m[".prettierrc.cjs.tsx"] = "prettier";
  m[".prettierrc.cjs.jsx"] = "prettier";
  m[".prettierrc.mjs.js"] = "prettier";
  m[".prettierrc.mjs.ts"] = "prettier";
  m[".prettierrc.mjs.tsx"] = "prettier";
  m[".prettierrc.mjs.jsx"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc"] = "prettier";
  m[".prettierrc.json"] = "prettier";
  m[".prettierrc.yml"] = "prettier";
  m[".prettierrc.yaml"] = "prettier";
  m[".prettierrc.js"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc.ts"] = "prettier";
  m[".prettierrc.cts"] = "prettier";
  m[".prettierrc.mts"] = "prettier";
  m[".prettierrc.json5"] = "prettier";
  m[".prettierrc.jsonc"] = "prettier";
  m[".prettierrc.gjs"] = "prettier";
  m[".prettierrc.gts"] = "prettier";
  m[".prettierrc.cjs.mjs"] = "prettier";
  m[".prettierrc.cjs.ts"] = "prettier";
  m[".prettierrc.cjs.tsx"] = "prettier";
  m[".prettierrc.cjs.jsx"] = "prettier";
  m[".prettierrc.mjs.js"] = "prettier";
  m[".prettierrc.mjs.ts"] = "prettier";
  m[".prettierrc.mjs.tsx"] = "prettier";
  m[".prettierrc.mjs.jsx"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc"] = "prettier";
  m[".prettierrc.json"] = "prettier";
  m[".prettierrc.yml"] = "prettier";
  m[".prettierrc.yaml"] = "prettier";
  m[".prettierrc.js"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc.ts"] = "prettier";
  m[".prettierrc.cts"] = "prettier";
  m[".prettierrc.mts"] = "prettier";
  m[".prettierrc.json5"] = "prettier";
  m[".prettierrc.jsonc"] = "prettier";
  m[".prettierrc.gjs"] = "prettier";
  m[".prettierrc.gts"] = "prettier";
  m[".prettierrc.cjs.mjs"] = "prettier";
  m[".prettierrc.cjs.ts"] = "prettier";
  m[".prettierrc.cjs.tsx"] = "prettier";
  m[".prettierrc.cjs.jsx"] = "prettier";
  m[".prettierrc.mjs.js"] = "prettier";
  m[".prettierrc.mjs.ts"] = "prettier";
  m[".prettierrc.mjs.tsx"] = "prettier";
  m[".prettierrc.mjs.jsx"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc"] = "prettier";
  m[".prettierrc.json"] = "prettier";
  m[".prettierrc.yml"] = "prettier";
  m[".prettierrc.yaml"] = "prettier";
  m[".prettierrc.js"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc.ts"] = "prettier";
  m[".prettierrc.cts"] = "prettier";
  m[".prettierrc.mts"] = "prettier";
  m[".prettierrc.json5"] = "prettier";
  m[".prettierrc.jsonc"] = "prettier";
  m[".prettierrc.gjs"] = "prettier";
  m[".prettierrc.gts"] = "prettier";
  m[".prettierrc.cjs.mjs"] = "prettier";
  m[".prettierrc.cjs.ts"] = "prettier";
  m[".prettierrc.cjs.tsx"] = "prettier";
  m[".prettierrc.cjs.jsx"] = "prettier";
  m[".prettierrc.mjs.js"] = "prettier";
  m[".prettierrc.mjs.ts"] = "prettier";
  m[".prettierrc.mjs.tsx"] = "prettier";
  m[".prettierrc.mjs.jsx"] = "prettier";
  m[".prettierrc.cjs"] = "prettier";
  m[".prettierrc.mjs"] = "prettier";
  m[".prettierrc"] = "prettier";
  return m;
}

static std::string get_language_from_ext(const std::string& ext) {
  static const auto ext_to_lang = build_ext_to_lang();
  auto it = ext_to_lang.find(ext);
  if (it != ext_to_lang.end()) return it->second;
  return "";
}

static std::optional<std::string> read_file_to_string(const fs::path& path) {
  std::ifstream f(path, std::ios::binary);
  if (!f.is_open()) return std::nullopt;
  std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
  return content;
}

static bool is_git_repo(const fs::path& dir) {
  return fs::exists(dir / ".git");
}

static bool is_git_tracked(const fs::path& file_path) {
  std::string path_str = file_path.string();
  std::string cmd = "git ls-files --error-unmatch \"" + path_str + "\" 2>/dev/null";
  int ret = std::system(cmd.c_str());
  return ret == 0;
}

static bool is_git_ignored(const fs::path& file_path) {
  std::string path_str = file_path.string();
  std::string cmd = "git check-ignore -q \"" + path_str + "\" 2>/dev/null";
  int ret = std::system(cmd.c_str());
  return ret == 0;
}

static std::vector<FileEntry> collect_files(const std::vector<fs::path>& input_paths, bool git_tracked_only) {
  std::vector<FileEntry> entries;

  for (const auto& input_path : input_paths) {
    if (!fs::exists(input_path)) {
      std::cerr << "错误：路径不存在: " << input_path.string() << std::endl;
      continue;
    }

    if (fs::is_regular_file(input_path)) {
      std::string ext = input_path.extension().string();
      std::string lang = get_language_from_ext(ext);
      if (lang.empty()) {
        std::cerr << "警告：未知扩展名: " << ext << " (" << input_path.string() << ")" << std::endl;
        continue;
      }

      if (git_tracked_only && is_git_repo(input_path.parent_path())) {
        if (!is_git_tracked(input_path)) {
          std::cerr << "警告：文件未被Git跟踪: " << input_path.string() << std::endl;
          continue;
        }
      }

      auto content = read_file_to_string(input_path);
      if (!content) {
        std::cerr << "错误：无法读取文件: " << input_path.string() << std::endl;
        continue;
      }

      entries.push_back(FileEntry{
        .path = input_path.string(),
        .lang = lang,
        .source = std::move(*content),
        .error = ""
      });
    } else if (fs::is_directory(input_path)) {
      bool repo = is_git_repo(input_path);

      for (const auto& entry : fs::recursive_directory_iterator(input_path)) {
        if (!entry.is_regular_file()) continue;

        auto path = entry.path();
        std::string ext = path.extension().string();
        std::string lang = get_language_from_ext(ext);
        if (lang.empty()) continue;

        if (git_tracked_only && repo) {
          if (!is_git_tracked(path)) continue;
        }

        if (git_tracked_only && repo) {
          if (is_git_ignored(path)) continue;
        }

        auto content = read_file_to_string(path);
        if (!content) {
          std::cerr << "错误：无法读取文件: " << path.string() << std::endl;
          continue;
        }

        entries.push_back(FileEntry{
          .path = path.string(),
          .lang = lang,
          .source = std::move(*content),
          .error = ""
        });
      }
    }
  }

  std::sort(entries.begin(), entries.end(), [](const FileEntry& a, const FileEntry& b) {
    return a.path < b.path;
  });

  return entries;
}

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

static double calculate_coverage(const SummaryStats& stats) {
  if (stats.total_code == 0) return 0.0;
  return static_cast<double>(stats.total_comment) / static_cast<double>(stats.total_code) * 100.0;
}

static double calculate_zh_coverage(const SummaryStats& stats) {
  if (stats.total_comment == 0) return 0.0;
  return static_cast<double>(stats.total_comment_zh) / static_cast<double>(stats.total_comment) * 100.0;
}

static std::string format_percentage(double value) {
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(2) << value << "%";
  return oss.str();
}

static std::string format_number(uint64_t value) {
  std::ostringstream oss;
  oss << value;
  return oss.str();
}

static void print_summary(const SummaryStats& stats) {
  double coverage = calculate_coverage(stats);
  double zh_coverage = calculate_zh_coverage(stats);

  std::cout << "\n========== 注释覆盖率报告 ==========\n";
  std::cout << "总文件数: " << stats.file_count << "\n";
  std::cout << "代码字符数: " << format_number(stats.total_code) << "\n";
  std::cout << "注释字符数: " << format_number(stats.total_comment) << "\n";
  std::cout << "其中中文字符: " << format_number(stats.total_comment_zh) << "\n";
  std::cout << "注释覆盖率: " << format_percentage(coverage) << "\n";
  std::cout << "中文占比: " << format_percentage(zh_coverage) << "\n";

  if (!stats.by_language.empty()) {
    std::cout << "\n---------- 按语言统计 ----------\n";
    for (const auto& lang : stats.by_language) {
      std::cout << lang.lang << ": ";
      std::cout << "文件=" << lang.file_count << ", ";
      std::cout << "代码=" << format_number(lang.total_code) << ", ";
      std::cout << "注释=" << format_number(lang.total_comment) << ", ";
      std::cout << "中文=" << format_number(lang.total_comment_zh);
      std::cout << "\n";
    }
  }

  std::cout << "==================================\n\n";
}

static std::string escape_json_string(const std::string& s) {
  std::ostringstream oss;
  for (char c : s) {
    switch (c) {
      case '"':  oss << "\\\""; break;
      case '\\': oss << "\\\\"; break;
      case '\b': oss << "\\b"; break;
      case '\f': oss << "\\f"; break;
      case '\n': oss << "\\n"; break;
      case '\r': oss << "\\r"; break;
      case '\t': oss << "\\t"; break;
      default:
        if (static_cast<unsigned char>(c) < 0x20) {
          oss << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
        } else {
          oss << c;
        }
        break;
    }
  }
  return oss.str();
}

static std::string generate_json_report(const SummaryStats& stats) {
  std::ostringstream oss;
  oss << "{\n";
  oss << "  \"summary\": {\n";
  oss << "    \"total_files\": " << stats.file_count << ",\n";
  oss << "    \"total_code_chars\": " << stats.total_code << ",\n";
  oss << "    \"total_comment_chars\": " << stats.total_comment << ",\n";
  oss << "    \"total_comment_zh_chars\": " << stats.total_comment_zh << ",\n";
  oss << "    \"coverage_percentage\": " << std::fixed << std::setprecision(2) << calculate_coverage(stats) << ",\n";
  oss << "    \"zh_percentage\": " << std::fixed << std::setprecision(2) << calculate_zh_coverage(stats) << "\n";
  oss << "  },\n";

  oss << "  \"by_language\": [\n";
  for (size_t i = 0; i < stats.by_language.size(); ++i) {
    const auto& lang = stats.by_language[i];
    oss << "    {\n";
    oss << "      \"language\": \"" << escape_json_string(lang.lang) << "\",\n";
    oss << "      \"file_count\": " << lang.file_count << ",\n";
    oss << "      \"code_chars\": " << lang.total_code << ",\n";
    oss << "      \"comment_chars\": " << lang.total_comment << ",\n";
    oss << "      \"comment_zh_chars\": " << lang.total_comment_zh << "\n";
    oss << "    }";
    if (i < stats.by_language.size() - 1) oss << ",";
    oss << "\n";
  }
  oss << "  ],\n";

  oss << "  \"file_details\": [\n";
  for (size_t i = 0; i < stats.file_details.size(); ++i) {
    const auto& file = stats.file_details[i];
    oss << "    {\n";
    oss << "      \"path\": \"" << escape_json_string(file.path) << "\",\n";
    oss << "      \"language\": \"" << escape_json_string(file.lang) << "\",\n";
    oss << "      \"code_chars\": " << file.code_chars << ",\n";
    oss << "      \"comment_chars\": " << file.comment_chars << ",\n";
    oss << "      \"comment_zh_chars\": " << file.comment_zh_chars << "\n";
    oss << "    }";
    if (i < stats.file_details.size() - 1) oss << ",";
    oss << "\n";
  }
  oss << "  ]\n";
  oss << "}\n";

  return oss.str();
}

static std::string generate_markdown_report(const SummaryStats& stats) {
  std::ostringstream oss;
  double coverage = calculate_coverage(stats);
  double zh_coverage = calculate_zh_coverage(stats);

  oss << "# 注释覆盖率报告\n\n";
  oss << "## 总体统计\n\n";
  oss << "| 指标 | 数值 |\n";
  oss << "|------|------|\n";
  oss << "| 总文件数 | " << stats.file_count << " |\n";
  oss << "| 代码字符数 | " << format_number(stats.total_code) << " |\n";
  oss << "| 注释字符数 | " << format_number(stats.total_comment) << " |\n";
  oss << "| 中文字符数 | " << format_number(stats.total_comment_zh) << " |\n";
  oss << "| 注释覆盖率 | " << format_percentage(coverage) << " |\n";
  oss << "| 中文占比 | " << format_percentage(zh_coverage) << " |\n\n";

  if (!stats.by_language.empty()) {
    oss << "## 按语言统计\n\n";
    oss << "| 语言 | 文件数 | 代码字符 | 注释字符 | 中文字符 |\n";
    oss << "|------|--------|----------|----------|----------|\n";
    for (const auto& lang : stats.by_language) {
      oss << "| " << lang.lang
          << " | " << lang.file_count
          << " | " << format_number(lang.total_code)
          << " | " << format_number(lang.total_comment)
          << " | " << format_number(lang.total_comment_zh)
          << " |\n";
    }
    oss << "\n";
  }

  if (!stats.file_details.empty()) {
    oss << "## 文件详情\n\n";
    oss << "| 文件路径 | 语言 | 代码字符 | 注释字符 | 中文字符 |\n";
    oss << "|----------|------|----------|----------|----------|\n";
    for (const auto& file : stats.file_details) {
      oss << "| " << file.path
          << " | " << file.lang
          << " | " << format_number(file.code_chars)
          << " | " << format_number(file.comment_chars)
          << " | " << format_number(file.comment_zh_chars)
          << " |\n";
    }
    oss << "\n";
  }

  return oss.str();
}

static bool write_file(const std::string& path, const std::string& content) {
  std::ofstream f(path, std::ios::binary);
  if (!f.is_open()) return false;
  f << content;
  return f.good();
}

extern "C" {
  TSLanguage* tree_sitter_c(void);
  TSLanguage* tree_sitter_cpp(void);
  TSLanguage* tree_sitter_python(void);
  TSLanguage* tree_sitter_javascript(void);
  TSLanguage* tree_sitter_typescript(void);
  TSLanguage* tree_sitter_java(void);
  TSLanguage* tree_sitter_go(void);
  TSLanguage* tree_sitter_rust(void);
  TSLanguage* tree_sitter_swift(void);
  TSLanguage* tree_sitter_kotlin(void);
  TSLanguage* tree_sitter_c_sharp(void);
  TSLanguage* tree_sitter_php(void);
  TSLanguage* tree_sitter_ruby(void);
  TSLanguage* tree_sitter_lua(void);
  TSLanguage* tree_sitter_bash(void);
  TSLanguage* tree_sitter_sql(void);
  TSLanguage* tree_sitter_html(void);
  TSLanguage* tree_sitter_css(void);
  TSLanguage* tree_sitter_json(void);
  TSLanguage* tree_sitter_yaml(void);
  TSLanguage* tree_sitter_toml(void);
  TSLanguage* tree_sitter_ini(void);
  TSLanguage* tree_sitter_cmake(void);
  TSLanguage* tree_sitter_make(void);
  TSLanguage* tree_sitter_dockerfile(void);
  TSLanguage* tree_sitter_gitignore(void);
  TSLanguage* tree_sitter_editorconfig(void);
  TSLanguage* tree_sitter_eslint(void);
  TSLanguage* tree_sitter_prettier(void);
  TSLanguage* tree_sitter_stylelint(void);
  TSLanguage* tree_sitter_babel(void);
  TSLanguage* tree_sitter_tsconfig(void);
}

static std::unordered_map<std::string, const TSLanguage*> build_language_map() {
  std::unordered_map<std::string, const TSLanguage*> m;
  m["c"] = tree_sitter_c();
  m["cpp"] = tree_sitter_cpp();
  m["python"] = tree_sitter_python();
  m["javascript"] = tree_sitter_javascript();
  m["typescript"] = tree_sitter_typescript();
  m["java"] = tree_sitter_java();
  m["go"] = tree_sitter_go();
  m["rust"] = tree_sitter_rust();
  m["swift"] = tree_sitter_swift();
  m["kotlin"] = tree_sitter_kotlin();
  m["c_sharp"] = tree_sitter_c_sharp();
  m["php"] = tree_sitter_php();
  m["ruby"] = tree_sitter_ruby();
  m["lua"] = tree_sitter_lua();
  m["shell"] = tree_sitter_bash();
  m["sql"] = tree_sitter_sql();
  m["html"] = tree_sitter_html();
  m["css"] = tree_sitter_css();
  m["json"] = tree_sitter_json();
  m["yaml"] = tree_sitter_yaml();
  m["toml"] = tree_sitter_toml();
  m["ini"] = tree_sitter_ini();
  m["cmake"] = tree_sitter_cmake();
  m["make"] = tree_sitter_make();
  m["dockerfile"] = tree_sitter_dockerfile();
  m["gitignore"] = tree_sitter_gitignore();
  m["editorconfig"] = tree_sitter_editorconfig();
  m["eslint"] = tree_sitter_eslint();
  m["prettier"] = tree_sitter_prettier();
  m["stylelint"] = tree_sitter_stylelint();
  m["babel"] = tree_sitter_babel();
  m["tsconfig"] = tree_sitter_tsconfig();
  return m;
}

static void print_usage(const char* program_name) {
  std::cout << "用法: " << program_name << " [选项] <路径...>\n";
  std::cout << "选项:\n";
  std::cout << "  --git-only      只分析Git跟踪的文件\n";
  std::cout << "  --json <文件>   生成JSON报告到指定文件\n";
  std::cout << "  --md <文件>     生成Markdown报告到指定文件\n";
  std::cout << "  -h, --help      显示帮助信息\n";
}

int main(int argc, char* argv[]) {
  if (argc < 2) {
    print_usage(argv[0]);
    return 1;
  }

  std::vector<fs::path> input_paths;
  bool git_tracked_only = false;
  std::optional<std::string> json_output_path;
  std::optional<std::string> md_output_path;

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--git-only") {
      git_tracked_only = true;
    } else if (arg == "--json") {
      if (i + 1 < argc) {
        json_output_path = argv[++i];
      } else {
        std::cerr << "错误: --json 需要指定文件路径\n";
        return 1;
      }
    } else if (arg == "--md") {
      if (i + 1 < argc) {
        md_output_path = argv[++i];
      } else {
        std::cerr << "错误: --md 需要指定文件路径\n";
        return 1;
      }
    } else if (arg == "-h" || arg == "--help") {
      print_usage(argv[0]);
      return 0;
    } else if (arg.starts_with("--")) {
      std::cerr << "错误: 未知选项 " << arg << "\n";
      print_usage(argv[0]);
      return 1;
    } else {
      input_paths.push_back(fs::path(arg));
    }
  }

  if (input_paths.empty()) {
    std::cerr << "错误: 需要指定至少一个输入路径\n";
    print_usage(argv[0]);
    return 1;
  }

  const auto language_map = build_language_map();

  std::vector<FileEntry> files = collect_files(input_paths, git_tracked_only);
  if (files.empty()) {
    std::cerr << "错误: 未找到任何文件\n";
    return 1;
  }

  SummaryStats summary;
  std::unordered_map<std::string, LanguageStats> lang_stats_map;

  for (const auto& file : files) {
    std::string error;
    const TSLanguage* lang = language_map.count(file.lang) ? language_map.at(file.lang) : nullptr;
    auto ranges = extract_comment_ranges(file.source, lang, file.lang, error);

    uint64_t code_chars = 0;
    uint64_t comment_chars = 0;
    uint64_t comment_zh_chars = 0;
    count_coverage_chars(file.source, ranges, code_chars, comment_chars, comment_zh_chars);

    summary.total_code += code_chars;
    summary.total_comment += comment_chars;
    summary.total_comment_zh += comment_zh_chars;
    summary.file_count++;

    if (!lang_stats_map.count(file.lang)) {
      lang_stats_map[file.lang] = LanguageStats{.lang = file.lang};
    }
    auto& ls = lang_stats_map[file.lang];
    ls.total_code += code_chars;
    ls.total_comment += comment_chars;
    ls.total_comment_zh += comment_zh_chars;
    ls.file_count++;

    summary.file_details.push_back(FileStats{
      .path = file.path,
      .lang = file.lang,
      .code_chars = code_chars,
      .comment_chars = comment_chars,
      .comment_zh_chars = comment_zh_chars,
      .error = error
    });
  }

  for (const auto& [lang, stats] : lang_stats_map) {
    summary.by_language.push_back(stats);
  }
  std::sort(summary.by_language.begin(), summary.by_language.end(), [](const LanguageStats& a, const LanguageStats& b) {
    return a.lang < b.lang;
  });

  print_summary(summary);

  if (json_output_path) {
    std::string json_report = generate_json_report(summary);
    if (!write_file(*json_output_path, json_report)) {
      std::cerr << "错误: 无法写入JSON报告文件: " << *json_output_path << "\n";
      return 1;
    }
    std::cout << "JSON报告已写入: " << *json_output_path << "\n";
  }

  if (md_output_path) {
    std::string md_report = generate_markdown_report(summary);
    if (!write_file(*md_output_path, md_report)) {
      std::cerr << "错误: 无法写入Markdown报告文件: " << *md_output_path << "\n";
      return 1;
    }
    std::cout << "Markdown报告已写入: " << *md_output_path << "\n";
  }

  return 0;
}