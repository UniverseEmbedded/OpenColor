/**
 * @file report_utils.cpp
 * @brief 注释覆盖率分析工具 - 报告生成模块
 *
 * 本模块提供以下功能：
 * - 统计数据汇总
 * - JSON报告生成
 * - Markdown报告生成
 * - 终端输出
 */

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace {

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

}