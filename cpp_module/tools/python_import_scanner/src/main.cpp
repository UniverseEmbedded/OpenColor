/**
 * @file main.cpp
 * @brief Python 引用关系扫描工具 - 主程序入口
 *
 * 本程序使用 Tree-sitter 解析 Python 代码，分析模块间的导入关系。
 * 可以识别孤立文件、循环依赖，并生成依赖关系报告。
 */

#include <algorithm>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <tree_sitter/api.h>

namespace fs = std::filesystem;

// 前向声明
extern "C" TSLanguage* tree_sitter_python(void);

// ============================================================================
// 数据结构定义
// ============================================================================

/**
 * @brief 导入信息结构体
 */
struct ImportInfo {
    std::string module_name;      // 导入的模块名（如 "oc_engine.handlers.board"）
    std::string original_name;    // 原始导入名（如 "board"）
    bool is_from_import;          // 是否是 from ... import 形式
    bool is_relative;             // 是否是相对导入（以 . 开头）
    int relative_level;           // 相对导入层级（1=., 2=..）
    std::string source_line;      // 源代码行（用于调试）
};

/**
 * @brief 文件分析结果
 */
struct FileAnalysis {
    std::string path;                      // 文件绝对路径
    std::string relative_path;             // 相对于项目根目录的路径
    std::string module_name;               // 推断的模块名
    std::vector<ImportInfo> imports;       // 导入的模块列表
    std::vector<std::string> imported_by;  // 被哪些模块导入
    bool has_main_block;                   // 是否有 if __name__ == "__main__"
    bool is_package;                       // 是否是包（有 __init__.py）
    int line_count;                        // 代码行数
    std::string error;                     // 解析错误信息
};

/**
 * @brief 依赖图
 */
struct DependencyGraph {
    std::unordered_map<std::string, FileAnalysis> files;           // 路径 -> 文件分析
    std::unordered_map<std::string, std::string> module_to_path;   // 模块名 -> 路径
    std::vector<std::string> orphan_files;                         // 孤立文件
    std::vector<std::vector<std::string>> cycles;                  // 循环依赖
};

/**
 * @brief 扫描配置
 */
struct ScanConfig {
    std::vector<fs::path> input_paths;
    bool git_tracked_only = false;
    std::optional<std::string> json_output_path;
    std::optional<std::string> md_output_path;
    std::vector<std::string> entry_modules;  // 入口模块（以此为基准分析）
    bool show_cycles = false;
};

// ============================================================================
// 工具函数
// ============================================================================

/**
 * @brief 读取文件内容为字符串
 */
static std::optional<std::string> read_file_to_string(const fs::path& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) return std::nullopt;
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    return content;
}

/**
 * @brief 检查是否是Git仓库
 */
static bool is_git_repo(const fs::path& dir) {
    return fs::exists(dir / ".git");
}

/**
 * @brief 检查文件是否被Git跟踪
 */
static bool is_git_tracked(const fs::path& file_path) {
    std::string path_str = file_path.string();
    std::string cmd = "git ls-files --error-unmatch \"" + path_str + "\" 2>nul";
    int ret = std::system(cmd.c_str());
    return ret == 0;
}

/**
 * @brief 检查文件是否被Git忽略
 */
static bool is_git_ignored(const fs::path& file_path) {
    std::string path_str = file_path.string();
    std::string cmd = "git check-ignore -q \"" + path_str + "\" 2>nul";
    int ret = std::system(cmd.c_str());
    return ret == 0;
}

/**
 * @brief 计算文件行数
 */
static int count_lines(const std::string& content) {
    int count = 0;
    for (char c : content) {
        if (c == '\n') count++;
    }
    return count + (content.empty() || content.back() == '\n' ? 0 : 1);
}

/**
 * @brief 查找项目根目录
 */
static fs::path find_project_root(const fs::path& start) {
    fs::path cur = start;
    for (int i = 0; i < 10; i++) {
        // 通过查找标志性文件/目录确定根目录
        if (fs::exists(cur / "pyproject.toml") ||
            fs::exists(cur / "setup.py") ||
            fs::exists(cur / ".git")) {
            return cur;
        }
        if (cur.parent_path() == cur) break;
        cur = cur.parent_path();
    }
    return start;
}

/**
 * @brief 从文件路径推断模块名
 */
static std::string infer_module_name(const fs::path& file_path, const fs::path& project_root) {
    // 获取相对路径
    fs::path rel_path = fs::relative(file_path, project_root);
    std::string path_str = rel_path.string();

    // 统一使用正斜杠
    std::replace(path_str.begin(), path_str.end(), '\\', '/');

    // 移除 .py 后缀
    if (path_str.ends_with(".py")) {
        path_str = path_str.substr(0, path_str.size() - 3);
    }

    // 处理 __init__.py -> 使用目录名作为模块名
    if (path_str.ends_with("/__init__")) {
        path_str = path_str.substr(0, path_str.size() - 9);
    }

    // 将路径分隔符替换为点
    std::replace(path_str.begin(), path_str.end(), '/', '.');

    return path_str;
}

/**
 * @brief 收集所有Python文件
 */
static std::vector<fs::path> collect_python_files(const std::vector<fs::path>& input_paths, bool git_tracked_only) {
    std::vector<fs::path> files;
    std::unordered_set<std::string> seen;

    for (const auto& input_path : input_paths) {
        if (!fs::exists(input_path)) {
            std::cerr << "错误：路径不存在: " << input_path.string() << std::endl;
            continue;
        }

        if (fs::is_regular_file(input_path)) {
            if (input_path.extension() == ".py") {
                std::string path_str = input_path.string();
                if (!seen.count(path_str)) {
                    files.push_back(input_path);
                    seen.insert(path_str);
                }
            }
        } else if (fs::is_directory(input_path)) {
            bool repo = is_git_repo(input_path);

            for (const auto& entry : fs::recursive_directory_iterator(input_path)) {
                if (!entry.is_regular_file()) continue;

                auto path = entry.path();
                if (path.extension() != ".py") continue;

                // 跳过常见排除目录
                std::string path_str = path.string();
                if (path_str.find("__pycache__") != std::string::npos) continue;
                if (path_str.find(".venv") != std::string::npos) continue;
                if (path_str.find("venv") != std::string::npos) continue;
                if (path_str.find("node_modules") != std::string::npos) continue;
                if (path_str.find("build") != std::string::npos) continue;
                if (path_str.find("dist") != std::string::npos) continue;

                if (git_tracked_only && repo) {
                    if (!is_git_tracked(path)) continue;
                    if (is_git_ignored(path)) continue;
                }

                if (!seen.count(path_str)) {
                    files.push_back(path);
                    seen.insert(path_str);
                }
            }
        }
    }

    std::sort(files.begin(), files.end());
    return files;
}

// ============================================================================
// Tree-sitter 解析
// ============================================================================

/**
 * @brief 提取节点文本
 */
static std::string get_node_text(TSNode node, const std::string& source) {
    uint32_t start = ts_node_start_byte(node);
    uint32_t end = ts_node_end_byte(node);
    if (end > source.size()) end = source.size();
    if (start >= end) return "";
    return source.substr(start, end - start);
}

/**
 * @brief 解析 import 语句
 */
static std::vector<ImportInfo> parse_import_statement(TSNode node, const std::string& source) {
    std::vector<ImportInfo> results;
    const char* type = ts_node_type(node);

    if (!type) return results;

    // 处理 import xxx 语句
    if (std::string_view(type) == "import_statement") {
        // 查找 dotted_name 或 aliased_import
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; i++) {
            TSNode child = ts_node_child(node, i);
            const char* child_type = ts_node_type(child);
            if (!child_type) continue;

            if (std::string_view(child_type) == "dotted_name") {
                ImportInfo info;
                info.module_name = get_node_text(child, source);
                info.original_name = info.module_name;
                info.is_from_import = false;
                info.is_relative = false;
                info.relative_level = 0;
                info.source_line = get_node_text(node, source);
                results.push_back(info);
            } else if (std::string_view(child_type) == "aliased_import") {
                // import xxx as yyy
                ImportInfo info;
                info.is_from_import = false;
                info.is_relative = false;
                info.relative_level = 0;
                info.source_line = get_node_text(node, source);

                uint32_t aliased_child_count = ts_node_child_count(child);
                for (uint32_t j = 0; j < aliased_child_count; j++) {
                    TSNode aliased_child = ts_node_child(child, j);
                    const char* aliased_type = ts_node_type(aliased_child);
                    if (!aliased_type) continue;

                    if (std::string_view(aliased_type) == "dotted_name") {
                        info.module_name = get_node_text(aliased_child, source);
                        info.original_name = info.module_name;
                    }
                }
                if (!info.module_name.empty()) {
                    results.push_back(info);
                }
            }
        }
    }
    // 处理 from xxx import yyy 语句
    else if (std::string_view(type) == "import_from_statement") {
        ImportInfo base_info;
        base_info.is_from_import = true;
        base_info.source_line = get_node_text(node, source);

        std::string module_name;
        bool is_relative = false;
        int relative_level = 0;

        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; i++) {
            TSNode child = ts_node_child(node, i);
            const char* child_type = ts_node_type(child);
            if (!child_type) continue;

            // 相对导入的点号
            if (std::string_view(child_type) == "." || std::string_view(child_type) == "...") {
                is_relative = true;
                relative_level++;
            }
            // 模块名
            else if (std::string_view(child_type) == "dotted_name") {
                module_name = get_node_text(child, source);
            }
            // 导入的具体名称
            else if (std::string_view(child_type) == "import_list" ||
                     std::string_view(child_type) == "wildcard_import") {
                // 处理 from xxx import * 或 from xxx import a, b, c
                ImportInfo info = base_info;
                info.module_name = module_name;
                info.is_relative = is_relative;
                info.relative_level = relative_level;
                info.original_name = module_name;
                results.push_back(info);
            }
        }

        // 如果没有找到 import_list，但有模块名，也记录
        if (results.empty() && !module_name.empty()) {
            ImportInfo info = base_info;
            info.module_name = module_name;
            info.is_relative = is_relative;
            info.relative_level = relative_level;
            info.original_name = module_name;
            results.push_back(info);
        }
    }

    return results;
}

/**
 * @brief 检查是否有 __main__ 块
 */
static bool has_main_block(TSNode root, const std::string& source) {
    TSTreeCursor cursor = ts_tree_cursor_new(root);
    bool found = false;

    while (!found) {
        TSNode node = ts_tree_cursor_current_node(&cursor);
        const char* type = ts_node_type(node);

        if (type && std::string_view(type) == "if_statement") {
            // 检查条件中是否有 __name__ == "__main__"
            std::string node_text = get_node_text(node, source);
            if (node_text.find("__name__") != std::string::npos &&
                node_text.find("__main__") != std::string::npos) {
                found = true;
                break;
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
                goto done;
            }
        }
    }

done:
    return found;
}

/**
 * @brief 分析单个Python文件
 */
static FileAnalysis analyze_python_file(const fs::path& file_path, const fs::path& project_root, TSLanguage* python_lang) {
    FileAnalysis result;
    result.path = file_path.string();
    result.relative_path = fs::relative(file_path, project_root).string();
    result.module_name = infer_module_name(file_path, project_root);
    result.is_package = (file_path.filename() == "__init__.py");

    // 读取文件内容
    auto content_opt = read_file_to_string(file_path);
    if (!content_opt) {
        result.error = "无法读取文件";
        return result;
    }

    std::string source = *content_opt;
    result.line_count = count_lines(source);

    // 创建 parser
    TSParser* parser = ts_parser_new();
    if (!parser) {
        result.error = "创建 parser 失败";
        return result;
    }

    if (!ts_parser_set_language(parser, python_lang)) {
        result.error = "设置 language 失败";
        ts_parser_delete(parser);
        return result;
    }

    // 解析
    TSTree* tree = ts_parser_parse_string(parser, nullptr, source.data(), static_cast<uint32_t>(source.size()));
    if (!tree) {
        result.error = "解析失败";
        ts_parser_delete(parser);
        return result;
    }

    TSNode root = ts_tree_root_node(tree);

    // 检查是否有 __main__ 块
    result.has_main_block = has_main_block(root, source);

    // 遍历语法树，查找所有 import 语句
    TSTreeCursor cursor = ts_tree_cursor_new(root);
    std::set<std::string> seen_imports;

    while (true) {
        TSNode node = ts_tree_cursor_current_node(&cursor);
        const char* type = ts_node_type(node);

        if (type) {
            std::string_view type_view(type);
            if (type_view == "import_statement" || type_view == "import_from_statement") {
                auto imports = parse_import_statement(node, source);
                for (auto& imp : imports) {
                    // 去重
                    std::string key = imp.module_name + "|" + std::to_string(imp.is_from_import);
                    if (!seen_imports.count(key)) {
                        result.imports.push_back(imp);
                        seen_imports.insert(key);
                    }
                }
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
                goto parse_done;
            }
        }
    }

parse_done:
    ts_tree_delete(tree);
    ts_parser_delete(parser);

    return result;
}

// ============================================================================
// 依赖分析
// ============================================================================

/**
 * @brief 解析相对导入为绝对模块名
 */
static std::string resolve_relative_import(const ImportInfo& imp, const std::string& current_module) {
    if (!imp.is_relative) return imp.module_name;

    // 分割当前模块
    std::vector<std::string> parts;
    std::stringstream ss(current_module);
    std::string part;
    while (std::getline(ss, part, '.')) {
        if (!part.empty()) parts.push_back(part);
    }

    // 根据相对层级回退
    int levels = imp.relative_level;
    while (levels > 0 && !parts.empty()) {
        parts.pop_back();
        levels--;
    }

    // 添加相对导入的模块名
    if (!imp.module_name.empty()) {
        std::stringstream import_ss(imp.module_name);
        while (std::getline(import_ss, part, '.')) {
            if (!part.empty()) parts.push_back(part);
        }
    }

    // 重新组合
    std::string result;
    for (size_t i = 0; i < parts.size(); i++) {
        if (i > 0) result += ".";
        result += parts[i];
    }

    return result;
}

/**
 * @brief 构建依赖图
 */
static DependencyGraph build_dependency_graph(
    const std::vector<fs::path>& files,
    const fs::path& project_root,
    TSLanguage* python_lang
) {
    DependencyGraph graph;

    // 第一步：分析所有文件
    std::cout << "分析 " << files.size() << " 个 Python 文件..." << std::endl;

    for (size_t i = 0; i < files.size(); i++) {
        const auto& file = files[i];
        if (i % 50 == 0) {
            std::cout << "  进度: " << i << "/" << files.size() << "\r" << std::flush;
        }

        auto analysis = analyze_python_file(file, project_root, python_lang);
        graph.files[analysis.path] = analysis;
        graph.module_to_path[analysis.module_name] = analysis.path;
    }
    std::cout << "  进度: " << files.size() << "/" << files.size() << std::endl;

    // 第二步：解析导入关系
    std::cout << "解析导入关系..." << std::endl;

    for (auto& [path, analysis] : graph.files) {
        for (auto& imp : analysis.imports) {
            // 解析相对导入
            std::string resolved_module = resolve_relative_import(imp, analysis.module_name);

            // 查找被导入的模块是否存在
            auto it = graph.module_to_path.find(resolved_module);
            if (it != graph.module_to_path.end()) {
                // 记录被谁导入
                graph.files[it->second].imported_by.push_back(analysis.module_name);
            }

            // 更新导入信息
            imp.module_name = resolved_module;
        }
    }

    // 第三步：找出孤立文件
    for (const auto& [path, analysis] : graph.files) {
        if (analysis.imported_by.empty() && !analysis.has_main_block) {
            graph.orphan_files.push_back(path);
        }
    }

    // 第四步：检测循环依赖（简化版，只检测直接循环）
    for (const auto& [path, analysis] : graph.files) {
        for (const auto& imp : analysis.imports) {
            auto it = graph.module_to_path.find(imp.module_name);
            if (it != graph.module_to_path.end()) {
                const auto& target = graph.files[it->second];
                // 检查目标是否也导入了当前模块
                for (const auto& target_imp : target.imports) {
                    if (target_imp.module_name == analysis.module_name) {
                        std::vector<std::string> cycle = {analysis.module_name, imp.module_name};
                        graph.cycles.push_back(cycle);
                    }
                }
            }
        }
    }

    return graph;
}

// ============================================================================
// 报告生成
// ============================================================================

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

static std::string generate_json_report(const DependencyGraph& graph) {
    std::ostringstream oss;
    oss << "{\n";

    // 摘要
    oss << "  \"summary\": {\n";
    oss << "    \"total_files\": " << graph.files.size() << ",\n";
    oss << "    \"orphan_files\": " << graph.orphan_files.size() << ",\n";
    oss << "    \"cycles\": " << graph.cycles.size() << "\n";
    oss << "  },\n";

    // 文件详情
    oss << "  \"files\": [\n";
    size_t file_idx = 0;
    for (const auto& [path, analysis] : graph.files) {
        oss << "    {\n";
        oss << "      \"path\": \"" << escape_json_string(path) << "\",\n";
        oss << "      \"module_name\": \"" << escape_json_string(analysis.module_name) << "\",\n";
        oss << "      \"line_count\": " << analysis.line_count << ",\n";
        oss << "      \"has_main_block\": " << (analysis.has_main_block ? "true" : "false") << ",\n";
        oss << "      \"is_package\": " << (analysis.is_package ? "true" : "false") << ",\n";

        // 导入
        oss << "      \"imports\": [\n";
        for (size_t i = 0; i < analysis.imports.size(); i++) {
            const auto& imp = analysis.imports[i];
            oss << "        {\n";
            oss << "          \"module\": \"" << escape_json_string(imp.module_name) << "\",\n";
            oss << "          \"is_from_import\": " << (imp.is_from_import ? "true" : "false") << ",\n";
            oss << "          \"is_relative\": " << (imp.is_relative ? "true" : "false") << "\n";
            oss << "        }";
            if (i < analysis.imports.size() - 1) oss << ",";
            oss << "\n";
        }
        oss << "      ],\n";

        // 被导入
        oss << "      \"imported_by\": [\n";
        for (size_t i = 0; i < analysis.imported_by.size(); i++) {
            oss << "        \"" << escape_json_string(analysis.imported_by[i]) << "\"";
            if (i < analysis.imported_by.size() - 1) oss << ",";
            oss << "\n";
        }
        oss << "      ]\n";

        oss << "    }";
        if (++file_idx < graph.files.size()) oss << ",";
        oss << "\n";
    }
    oss << "  ],\n";

    // 孤立文件
    oss << "  \"orphan_files\": [\n";
    for (size_t i = 0; i < graph.orphan_files.size(); i++) {
        oss << "    \"" << escape_json_string(graph.orphan_files[i]) << "\"";
        if (i < graph.orphan_files.size() - 1) oss << ",";
        oss << "\n";
    }
    oss << "  ]\n";

    oss << "}\n";
    return oss.str();
}

static std::string generate_markdown_report(const DependencyGraph& graph) {
    std::ostringstream oss;

    oss << "# Python 引用关系分析报告\n\n";

    // 摘要
    oss << "## 摘要\n\n";
    oss << "| 指标 | 数值 |\n";
    oss << "|------|------|\n";
    oss << "| 总文件数 | " << graph.files.size() << " |\n";
    oss << "| 孤立文件数 | " << graph.orphan_files.size() << " |\n";
    oss << "| 循环依赖数 | " << graph.cycles.size() << " |\n\n";

    // 孤立文件
    if (!graph.orphan_files.empty()) {
        oss << "## 孤立文件（未被引用）\n\n";
        oss << "以下文件没有被其他模块导入，也不是入口点（没有 `__main__` 块）：\n\n";
        for (const auto& path : graph.orphan_files) {
            oss << "- `" << path << "`\n";
        }
        oss << "\n";
    }

    // 入口点文件
    oss << "## 入口点文件\n\n";
    oss << "以下文件包含 `if __name__ == \"__main__\"` 块，可以作为程序入口：\n\n";
    for (const auto& [path, analysis] : graph.files) {
        if (analysis.has_main_block) {
            oss << "- `" << analysis.module_name << "` (" << analysis.relative_path << ")\n";
        }
    }
    oss << "\n";

    // 循环依赖
    if (!graph.cycles.empty()) {
        oss << "## 循环依赖\n\n";
        for (const auto& cycle : graph.cycles) {
            oss << "- ";
            for (size_t i = 0; i < cycle.size(); i++) {
                if (i > 0) oss << " -> ";
                oss << "`" << cycle[i] << "`";
            }
            oss << "\n";
        }
        oss << "\n";
    }

    // 文件详情
    oss << "## 文件详情\n\n";
    oss << "| 模块名 | 路径 | 行数 | 导入数 | 被引用数 |\n";
    oss << "|--------|------|------|--------|----------|\n";

    // 按模块名排序
    std::vector<std::pair<std::string, FileAnalysis>> sorted_files;
    for (const auto& [path, analysis] : graph.files) {
        sorted_files.push_back({analysis.module_name, analysis});
    }
    std::sort(sorted_files.begin(), sorted_files.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });

    for (const auto& [name, analysis] : sorted_files) {
        oss << "| `" << name << "` | " << analysis.relative_path
            << " | " << analysis.line_count
            << " | " << analysis.imports.size()
            << " | " << analysis.imported_by.size() << " |\n";
    }

    return oss.str();
}

static void print_console_summary(const DependencyGraph& graph) {
    std::cout << "\n========== Python 引用关系分析结果 ==========\n";
    std::cout << "总文件数: " << graph.files.size() << "\n";
    std::cout << "孤立文件: " << graph.orphan_files.size() << "\n";
    std::cout << "循环依赖: " << graph.cycles.size() << "\n";

    if (!graph.orphan_files.empty()) {
        std::cout << "\n孤立文件列表（前10个）：\n";
        for (size_t i = 0; i < std::min(size_t(10), graph.orphan_files.size()); i++) {
            std::cout << "  - " << graph.orphan_files[i] << "\n";
        }
        if (graph.orphan_files.size() > 10) {
            std::cout << "  ... 还有 " << (graph.orphan_files.size() - 10) << " 个\n";
        }
    }

    std::cout << "=============================================\n";
}

// ============================================================================
// 主函数
// ============================================================================

static void print_usage(const char* program_name) {
    std::cout << "用法: " << program_name << " [选项] <路径...>\n";
    std::cout << "\n选项:\n";
    std::cout << "  --git-only          只分析Git跟踪的文件\n";
    std::cout << "  --json <文件>       生成JSON报告到指定文件\n";
    std::cout << "  --md <文件>         生成Markdown报告到指定文件\n";
    std::cout << "  --entry <模块>      指定入口模块（可多次使用）\n";
    std::cout << "  --show-cycles       显示循环依赖\n";
    std::cout << "  -h, --help          显示帮助信息\n";
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    ScanConfig config;

    // 解析命令行参数
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];

        if (arg == "--git-only") {
            config.git_tracked_only = true;
        } else if (arg == "--json") {
            if (i + 1 < argc) {
                config.json_output_path = argv[++i];
            } else {
                std::cerr << "错误: --json 需要指定文件路径\n";
                return 1;
            }
        } else if (arg == "--md") {
            if (i + 1 < argc) {
                config.md_output_path = argv[++i];
            } else {
                std::cerr << "错误: --md 需要指定文件路径\n";
                return 1;
            }
        } else if (arg == "--entry") {
            if (i + 1 < argc) {
                config.entry_modules.push_back(argv[++i]);
            } else {
                std::cerr << "错误: --entry 需要指定模块名\n";
                return 1;
            }
        } else if (arg == "--show-cycles") {
            config.show_cycles = true;
        } else if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return 0;
        } else if (arg.starts_with("--")) {
            std::cerr << "错误: 未知选项 " << arg << "\n";
            print_usage(argv[0]);
            return 1;
        } else {
            config.input_paths.push_back(fs::path(arg));
        }
    }

    if (config.input_paths.empty()) {
        std::cerr << "错误: 需要指定至少一个输入路径\n";
        print_usage(argv[0]);
        return 1;
    }

    // 查找项目根目录
    fs::path project_root = find_project_root(config.input_paths[0]);
    std::cout << "项目根目录: " << project_root.string() << std::endl;

    // 收集Python文件
    std::cout << "收集Python文件..." << std::endl;
    auto files = collect_python_files(config.input_paths, config.git_tracked_only);
    if (files.empty()) {
        std::cerr << "错误: 未找到任何Python文件\n";
        return 1;
    }
    std::cout << "找到 " << files.size() << " 个Python文件" << std::endl;

    // 获取 Python 语言解析器
    TSLanguage* python_lang = tree_sitter_python();
    if (!python_lang) {
        std::cerr << "错误: 无法获取 Python 语言解析器\n";
        return 1;
    }

    // 构建依赖图
    auto graph = build_dependency_graph(files, project_root, python_lang);

    // 输出控制台摘要
    print_console_summary(graph);

    // 生成JSON报告
    if (config.json_output_path) {
        std::string json_report = generate_json_report(graph);
        std::ofstream f(*config.json_output_path, std::ios::binary);
        if (!f.is_open()) {
            std::cerr << "错误: 无法写入JSON报告文件: " << *config.json_output_path << "\n";
            return 1;
        }
        f << json_report;
        std::cout << "JSON报告已写入: " << *config.json_output_path << std::endl;
    }

    // 生成Markdown报告
    if (config.md_output_path) {
        std::string md_report = generate_markdown_report(graph);
        std::ofstream f(*config.md_output_path, std::ios::binary);
        if (!f.is_open()) {
            std::cerr << "错误: 无法写入Markdown报告文件: " << *config.md_output_path << "\n";
            return 1;
        }
        f << md_report;
        std::cout << "Markdown报告已写入: " << *config.md_output_path << std::endl;
    }

    return 0;
}
