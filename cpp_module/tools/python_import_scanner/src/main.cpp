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
    std::unordered_set<std::string> entry_reachable_files;         // 从入口模块可达的文件
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

/**
 * @brief 包配置信息
 * 从 pyproject.toml 和 pixi.toml 读取的包名映射
 */
struct PackageConfig {
    std::string name;           // 包名（如 oc_sdf）
    fs::path source_path;       // 源代码路径（如 py_module/sdf/src/oc_sdf）
    std::string module_prefix;  // 模块前缀（如 oc_sdf）
};

/**
 * @brief 包配置映射表
 * 键：源代码路径（绝对路径或相对于项目根目录）
 * 值：包配置信息
 */
using PackageMap = std::unordered_map<std::string, PackageConfig>;

// ============================================================================
// TOML 配置读取
// ============================================================================

/**
 * @brief 从 pyproject.toml 读取包配置
 * 解析 [project] name 和 [tool.hatch.build.targets.wheel] packages
 */
static std::optional<PackageConfig> read_pyproject_config(const fs::path& pyproject_path) {
    std::ifstream f(pyproject_path);
    if (!f.is_open()) return std::nullopt;

    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    f.close();

    PackageConfig config;
    config.source_path = pyproject_path.parent_path();

    // 解析 [project] name
    size_t project_pos = content.find("[project]");
    if (project_pos != std::string::npos) {
        size_t name_pos = content.find("name = \"", project_pos);
        if (name_pos != std::string::npos) {
            name_pos += 8; // 跳过 name = "
            size_t name_end = content.find("\"", name_pos);
            if (name_end != std::string::npos) {
                config.name = content.substr(name_pos, name_end - name_pos);
            }
        }
    }

    if (config.name.empty()) return std::nullopt;

    // 解析 [tool.hatch.build.targets.wheel] packages
    size_t hatch_pos = content.find("[tool.hatch.build.targets.wheel]");
    if (hatch_pos != std::string::npos) {
        size_t packages_pos = content.find("packages = [", hatch_pos);
        if (packages_pos != std::string::npos) {
            packages_pos += 12; // 跳过 packages = [
            size_t packages_end = content.find("]", packages_pos);
            if (packages_end != std::string::npos) {
                std::string packages_str = content.substr(packages_pos, packages_end - packages_pos);
                // 提取第一个包路径
                size_t quote_pos = packages_str.find("\"");
                if (quote_pos != std::string::npos) {
                    quote_pos++;
                    size_t quote_end = packages_str.find("\"", quote_pos);
                    if (quote_end != std::string::npos) {
                        std::string pkg_path = packages_str.substr(quote_pos, quote_end - quote_pos);
                        // 提取模块前缀（如 src/oc_sdf -> oc_sdf）
                        size_t slash_pos = pkg_path.find('/');
                        if (slash_pos != std::string::npos) {
                            config.module_prefix = pkg_path.substr(slash_pos + 1);
                        } else {
                            config.module_prefix = pkg_path;
                        }
                        // 构建完整的源代码路径
                        config.source_path = pyproject_path.parent_path() / pkg_path;
                    }
                }
            }
        }
    }

    // 解析 [tool.setuptools.packages.find] 配置（支持setuptools构建系统）
    if (config.module_prefix.empty()) {
        size_t setuptools_pos = content.find("[tool.setuptools.packages.find]");
        if (setuptools_pos != std::string::npos) {
            // 解析 where 字段
            size_t where_pos = content.find("where = [", setuptools_pos);
            if (where_pos != std::string::npos) {
                where_pos += 9; // 跳过 where = [
                size_t where_end = content.find("]", where_pos);
                if (where_end != std::string::npos) {
                    std::string where_str = content.substr(where_pos, where_end - where_pos);
                    // 提取第一个路径
                    size_t quote_pos = where_str.find("\"");
                    if (quote_pos != std::string::npos) {
                        quote_pos++;
                        size_t quote_end = where_str.find("\"", quote_pos);
                        if (quote_end != std::string::npos) {
                            std::string where_path = where_str.substr(quote_pos, quote_end - quote_pos);
                            // 在指定目录下查找包目录
                            fs::path search_path = pyproject_path.parent_path() / where_path;
                            if (fs::exists(search_path) && fs::is_directory(search_path)) {
                                for (const auto& entry : fs::directory_iterator(search_path)) {
                                    if (entry.is_directory()) {
                                        // 检查是否包含 Python 文件
                                        bool has_python_files = false;
                                        for (const auto& py_entry : fs::directory_iterator(entry.path())) {
                                            if (py_entry.is_regular_file() && py_entry.path().extension() == ".py") {
                                                has_python_files = true;
                                                break;
                                            }
                                        }
                                        if (has_python_files) {
                                            config.module_prefix = entry.path().filename().string();
                                            config.source_path = entry.path();
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (config.module_prefix.empty()) {
        // 如果没有找到 hatch 配置，尝试从 src 目录下的实际目录名推断模块前缀
        fs::path src_path = pyproject_path.parent_path() / "src";
        if (fs::exists(src_path) && fs::is_directory(src_path)) {
            // 遍历 src 目录下的所有子目录，找到包含 __init__.py 的目录
            for (const auto& entry : fs::directory_iterator(src_path)) {
                if (entry.is_directory()) {
                    // 检查是否包含 __init__.py 或 .py 文件
                    bool has_python_files = false;
                    for (const auto& py_entry : fs::directory_iterator(entry.path())) {
                        if (py_entry.is_regular_file() && py_entry.path().extension() == ".py") {
                            has_python_files = true;
                            break;
                        }
                    }
                    if (has_python_files) {
                        // 使用目录名作为模块前缀
                        config.module_prefix = entry.path().filename().string();
                        config.source_path = entry.path();
                        break;
                    }
                }
            }
        }

        // 如果还是没有找到，使用包名作为模块前缀
        if (config.module_prefix.empty()) {
            config.module_prefix = config.name;
            // 尝试常见的 src/<module> 路径
            fs::path src_pkg_path = pyproject_path.parent_path() / "src" / config.name;
            if (fs::exists(src_pkg_path)) {
                config.source_path = src_pkg_path;
            }
        }
    }

    return config;
}

/**
 * @brief 从 pixi.toml 读取本地包路径映射
 * 解析 [pypi-dependencies] 中的本地 editable 包
 */
static std::vector<fs::path> read_pixi_local_packages(const fs::path& pixi_path) {
    std::vector<fs::path> result;
    std::ifstream f(pixi_path);
    if (!f.is_open()) return result;

    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    f.close();

    // 找到 [pypi-dependencies] 部分
    size_t pypi_pos = content.find("[pypi-dependencies]");
    if (pypi_pos == std::string::npos) return result;

    // 解析每个包的 path 配置
    size_t pos = pypi_pos;
    while ((pos = content.find("path = \"", pos)) != std::string::npos) {
        pos += 8; // 跳过 path = "
        size_t end = content.find("\"", pos);
        if (end == std::string::npos) break;

        std::string path_str = content.substr(pos, end - pos);
        // 解析为绝对路径
        fs::path pkg_path = pixi_path.parent_path() / path_str;
        if (fs::exists(pkg_path)) {
            result.push_back(pkg_path);
        }
        pos = end;
    }

    return result;
}

/**
 * @brief 加载所有包配置
 */
static PackageMap load_package_configs(const fs::path& project_root) {
    PackageMap packages;

    // 1. 从 pixi.toml 获取本地包路径列表
    fs::path pixi_path = project_root / "pixi.toml";
    auto local_packages = read_pixi_local_packages(pixi_path);

    // 2. 从每个包的 pyproject.toml 读取详细配置
    for (const auto& pkg_path : local_packages) {
        fs::path pyproject_path = pkg_path / "pyproject.toml";
        if (fs::exists(pyproject_path)) {
            auto config_opt = read_pyproject_config(pyproject_path);
            if (config_opt) {
                auto& config = *config_opt;
                // 使用源代码路径作为键
                std::string key = config.source_path.string();
                // 统一使用正斜杠
                std::replace(key.begin(), key.end(), '\\', '/');
                packages[key] = config;

                std::cout << "[包配置] 加载: " << config.name
                          << " -> " << config.module_prefix
                          << " (" << config.source_path.string() << ")" << std::endl;
            }
        }
    }

    return packages;
}

/**
 * @brief 从入口模块递归收集所有可达的文件
 * @param graph 依赖图
 * @param entry_modules 入口模块名列表
 * @return 从入口可达的所有文件路径集合
 */
static std::unordered_set<std::string> collect_entry_reachable_files(
    const DependencyGraph& graph,
    const std::vector<std::string>& entry_modules
) {
    std::unordered_set<std::string> reachable;
    std::vector<std::string> queue;
    std::unordered_set<std::string> visited_modules;

    // 初始化队列：找到入口模块对应的文件
    for (const auto& entry_module : entry_modules) {
        auto it = graph.module_to_path.find(entry_module);
        if (it != graph.module_to_path.end()) {
            queue.push_back(it->second);
            reachable.insert(it->second);
        } else {
            std::cerr << "警告: 未找到入口模块: " << entry_module << std::endl;
        }
        visited_modules.insert(entry_module);
    }

    // BFS遍历：从入口模块开始，递归收集被导入的文件
    size_t idx = 0;
    while (idx < queue.size()) {
        const std::string& current_path = queue[idx++];
        auto file_it = graph.files.find(current_path);
        if (file_it == graph.files.end()) continue;

        const auto& analysis = file_it->second;

        // 遍历该文件导入的所有模块
        for (const auto& imp : analysis.imports) {
            auto module_it = graph.module_to_path.find(imp.module_name);
            if (module_it != graph.module_to_path.end()) {
                const std::string& target_path = module_it->second;

                // 如果该文件还没被加入可达集合
                if (reachable.insert(target_path).second) {
                    queue.push_back(target_path);
                }
            }
        }
    }

    return reachable;
}

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
 * @brief 从文件路径推断模块名（使用包配置）
 */
static std::string infer_module_name(
    const fs::path& file_path,
    const fs::path& project_root,
    const PackageMap& packages
) {
    // 获取绝对路径并统一格式
    fs::path abs_path = fs::absolute(file_path);
    std::string abs_path_str = abs_path.string();
    std::replace(abs_path_str.begin(), abs_path_str.end(), '\\', '/');

    // 尝试匹配包配置
    for (const auto& [pkg_path, config] : packages) {
        // 检查文件路径是否以包源代码路径开头
        // 注意：需要确保匹配完整的路径组件，而不是部分匹配
        if (abs_path_str.starts_with(pkg_path)) {
            // 提取相对路径
            std::string rel_path = abs_path_str.substr(pkg_path.length());
            // 确保匹配的是一个完整路径组件（以/开头或者是空字符串）
            if (!rel_path.empty() && !rel_path.starts_with("/")) {
                continue; // 不是完整匹配，跳过
            }
            if (rel_path.starts_with("/")) {
                rel_path = rel_path.substr(1);
            }

            // 处理 __init__.py -> 使用目录名作为模块名（先处理这个）
            if (rel_path.ends_with("/__init__.py")) {
                rel_path = rel_path.substr(0, rel_path.size() - 12); // 移除 "/__init__.py"
            } else if (rel_path == "__init__.py") {
                rel_path = ""; // 根目录的 __init__.py
            } else if (rel_path.ends_with(".py")) {
                // 移除 .py 后缀
                rel_path = rel_path.substr(0, rel_path.size() - 3);
            }

            // 将路径分隔符替换为点
            std::replace(rel_path.begin(), rel_path.end(), '/', '.');

            // 构建完整模块名
            if (rel_path.empty()) {
                return config.module_prefix;
            } else {
                return config.module_prefix + "." + rel_path;
            }
        }
    }

    // 如果没有匹配到包配置，使用默认逻辑
    fs::path rel_path = fs::relative(file_path, project_root);
    std::string path_str = rel_path.string();

    // 统一使用正斜杠
    std::replace(path_str.begin(), path_str.end(), '\\', '/');

    // 处理 __init__.py -> 使用目录名作为模块名（先处理这个）
    if (path_str.ends_with("/__init__.py")) {
        path_str = path_str.substr(0, path_str.size() - 12); // 移除 "/__init__.py"
    } else if (path_str == "__init__.py") {
        path_str = ""; // 根目录的 __init__.py
    } else if (path_str.ends_with(".py")) {
        // 移除 .py 后缀
        path_str = path_str.substr(0, path_str.size() - 3);
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

    auto has_excluded_component = [](const fs::path& path) {
        for (const auto& part : path) {
            std::string name = part.string();
            if (name == "__pycache__") return true;
            if (name == ".venv") return true;
            if (name == "venv") return true;
            if (name == "node_modules") return true;
            if (name == "build") return true;
            if (name == "dist") return true;
        }
        return false;
    };

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

                if (has_excluded_component(path)) continue;

                if (git_tracked_only && repo) {
                    if (!is_git_tracked(path)) continue;
                    if (is_git_ignored(path)) continue;
                }

                std::string path_str = path.string();
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

        // 调试：打印所有子节点类型
        bool debug_this = base_info.source_line.find("oc_xgb.color_space") != std::string::npos;
        if (debug_this) {
            std::cout << "[调试] 解析导入语句: " << base_info.source_line << std::endl;
        }

        // 第一遍遍历：收集模块名和相对导入信息
        uint32_t child_count = ts_node_child_count(node);
        for (uint32_t i = 0; i < child_count; i++) {
            TSNode child = ts_node_child(node, i);
            const char* child_type = ts_node_type(child);
            if (!child_type) continue;

            if (debug_this) {
                std::cout << "[调试]   子节点[" << i << "]: " << child_type 
                          << " = " << get_node_text(child, source) << std::endl;
            }

            // 相对导入的点号
            if (std::string_view(child_type) == "." || std::string_view(child_type) == "...") {
                is_relative = true;
                relative_level++;
                continue;
            }

            // 模块名
            if (std::string_view(child_type) == "dotted_name") {
                if (module_name.empty()) {
                    module_name = get_node_text(child, source);
                }
                continue;
            }

            // relative_import 节点包含点号与 dotted_name
            if (std::string_view(child_type) == "relative_import") {
                std::vector<TSNode> stack;
                stack.push_back(child);
                while (!stack.empty()) {
                    TSNode rel_child = stack.back();
                    stack.pop_back();
                    const char* rel_type = ts_node_type(rel_child);
                    if (rel_type) {
                        if (std::string_view(rel_type) == "." || std::string_view(rel_type) == "...") {
                            is_relative = true;
                            relative_level++;
                        } else if (std::string_view(rel_type) == "dotted_name") {
                            if (module_name.empty()) {
                                module_name = get_node_text(rel_child, source);
                            }
                        }
                    }
                    uint32_t rel_child_count = ts_node_child_count(rel_child);
                    for (uint32_t j = 0; j < rel_child_count; j++) {
                        stack.push_back(ts_node_child(rel_child, j));
                    }
                }
            }
        }

        if (debug_this) {
            std::cout << "[调试]   提取的模块名: '" << module_name << "'" << std::endl;
        }

        // 第二遍遍历：处理导入列表
        for (uint32_t i = 0; i < child_count; i++) {
            TSNode child = ts_node_child(node, i);
            const char* child_type = ts_node_type(child);
            if (!child_type) continue;

            // 导入的具体名称
            if (std::string_view(child_type) == "import_list" ||
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
static FileAnalysis analyze_python_file(
    const fs::path& file_path,
    const fs::path& project_root,
    TSLanguage* python_lang,
    const PackageMap& packages
) {
    FileAnalysis result;
    result.path = file_path.string();
    result.relative_path = fs::relative(file_path, project_root).string();
    result.module_name = infer_module_name(file_path, project_root, packages);
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
static std::string resolve_relative_import(
    const ImportInfo& imp,
    const std::string& current_module,
    bool current_is_package
) {
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
    int drop_levels = current_is_package ? std::max(levels - 1, 0) : levels;
    while (drop_levels > 0 && !parts.empty()) {
        parts.pop_back();
        drop_levels--;
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

static std::string resolve_sibling_import(const std::string& module_name, const std::string& current_module) {
    if (module_name.empty()) return "";
    auto pos = current_module.rfind('.');
    if (pos == std::string::npos) return "";
    std::string parent = current_module.substr(0, pos);
    if (parent.empty()) return "";
    return parent + "." + module_name;
}

/**
 * @brief 构建依赖图
 */
static DependencyGraph build_dependency_graph(
    const std::vector<fs::path>& files,
    const fs::path& project_root,
    TSLanguage* python_lang,
    const std::vector<std::string>& entry_modules,
    const PackageMap& packages
) {
    DependencyGraph graph;

    // 第一步：分析所有文件
    std::cout << "分析 " << files.size() << " 个 Python 文件..." << std::endl;

    for (size_t i = 0; i < files.size(); i++) {
        const auto& file = files[i];
        if (i % 50 == 0) {
            std::cout << "  进度: " << i << "/" << files.size() << "\r" << std::flush;
        }

        auto analysis = analyze_python_file(file, project_root, python_lang, packages);
        graph.files[analysis.path] = analysis;
        graph.module_to_path[analysis.module_name] = analysis.path;
    }
    std::cout << "  进度: " << files.size() << "/" << files.size() << std::endl;

    // 第二步：解析导入关系
    std::cout << "解析导入关系..." << std::endl;

    for (auto& [path, analysis] : graph.files) {
        for (auto& imp : analysis.imports) {
            // 解析相对导入
            std::string resolved_module = resolve_relative_import(
                imp,
                analysis.module_name,
                analysis.is_package
            );
            auto it = graph.module_to_path.find(resolved_module);
            if (it == graph.module_to_path.end() && !imp.is_relative) {
                std::string sibling_module = resolve_sibling_import(resolved_module, analysis.module_name);
                if (!sibling_module.empty()) {
                    auto sib_it = graph.module_to_path.find(sibling_module);
                    if (sib_it != graph.module_to_path.end()) {
                        resolved_module = sibling_module;
                        it = sib_it;
                    }
                }
            }
            if (it != graph.module_to_path.end()) {
                graph.files[it->second].imported_by.push_back(analysis.module_name);
            }

            imp.module_name = resolved_module;
        }
    }

    // 调试：输出 oc_xgb.color_space 的导入情况
    {
        auto it = graph.module_to_path.find("oc_xgb.color_space");
        if (it != graph.module_to_path.end()) {
            const auto& analysis = graph.files[it->second];
            std::cout << "[调试] oc_xgb.color_space 被 " << analysis.imported_by.size() << " 个模块导入" << std::endl;
            for (const auto& importer : analysis.imported_by) {
                std::cout << "[调试]   - " << importer << std::endl;
            }
        } else {
            std::cout << "[调试] oc_xgb.color_space 不在 module_to_path 中" << std::endl;
        }
    }

    // 调试：输出 joint_refinement_icm 的导入列表
    {
        auto it = graph.module_to_path.find("oc_proto.gen_masks.joint_refinement_icm");
        if (it != graph.module_to_path.end()) {
            const auto& analysis = graph.files[it->second];
            std::cout << "[调试] joint_refinement_icm 导入了 " << analysis.imports.size() << " 个模块:" << std::endl;
            for (const auto& imp : analysis.imports) {
                std::cout << "[调试]   - " << imp.module_name << " (from_import=" << imp.is_from_import << ", relative=" << imp.is_relative << ")" << std::endl;
                std::cout << "[调试]     原始行: " << imp.source_line << std::endl;
            }
        } else {
            std::cout << "[调试] joint_refinement_icm 不在 module_to_path 中" << std::endl;
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

    // 第五步：如果有入口模块，计算从入口可达的文件
    if (!entry_modules.empty()) {
        std::cout << "计算入口模块可达文件..." << std::endl;
        graph.entry_reachable_files = collect_entry_reachable_files(graph, entry_modules);
        std::cout << "从入口模块可达的文件数: " << graph.entry_reachable_files.size() << std::endl;
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
    oss << "| 循环依赖数 | " << graph.cycles.size() << " |\n";
    if (!graph.entry_reachable_files.empty()) {
        oss << "| 入口模块可达文件数 | " << graph.entry_reachable_files.size() << " |\n";
        oss << "| 其他文件数 | " << (graph.files.size() - graph.entry_reachable_files.size()) << " |\n";
    }
    oss << "\n";

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

    // 文件详情 - 分为两组
    if (!graph.entry_reachable_files.empty()) {
        // 准备两组文件
        std::vector<std::pair<std::string, FileAnalysis>> group1_files; // 入口可达
        std::vector<std::pair<std::string, FileAnalysis>> group2_files; // 其他文件

        for (const auto& [path, analysis] : graph.files) {
            if (graph.entry_reachable_files.count(path)) {
                group1_files.push_back({analysis.module_name, analysis});
            } else {
                group2_files.push_back({analysis.module_name, analysis});
            }
        }

        // 按模块名排序
        auto sort_by_name = [](const auto& a, const auto& b) { return a.first < b.first; };
        std::sort(group1_files.begin(), group1_files.end(), sort_by_name);
        std::sort(group2_files.begin(), group2_files.end(), sort_by_name);

        // 第一组：入口模块及其依赖
        oss << "## 第一组：入口模块及其依赖\n\n";
        oss << "从指定的入口模块开始，递归收集的所有可达文件（包括入口模块本身及其导入的所有模块）。\n\n";
        oss << "| 模块名 | 路径 | 行数 | 导入数 | 被引用数 |\n";
        oss << "|--------|------|------|--------|----------|\n";
        for (const auto& [name, analysis] : group1_files) {
            oss << "| `" << name << "` | " << analysis.relative_path
                << " | " << analysis.line_count
                << " | " << analysis.imports.size()
                << " | " << analysis.imported_by.size() << " |\n";
        }
        oss << "\n";

        // 第二组：其他文件
        if (!group2_files.empty()) {
            oss << "## 第二组：其他文件\n\n";
            oss << "未被入口模块直接或间接引用的文件。\n\n";
            oss << "| 模块名 | 路径 | 行数 | 导入数 | 被引用数 |\n";
            oss << "|--------|------|------|--------|----------|\n";
            for (const auto& [name, analysis] : group2_files) {
                oss << "| `" << name << "` | " << analysis.relative_path
                    << " | " << analysis.line_count
                    << " | " << analysis.imports.size()
                    << " | " << analysis.imported_by.size() << " |\n";
            }
            oss << "\n";
        }
    } else {
        // 没有入口模块时，显示所有文件
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

    // 加载包配置
    std::cout << "加载包配置..." << std::endl;
    PackageMap packages = load_package_configs(project_root);
    std::cout << "加载了 " << packages.size() << " 个包配置" << std::endl;

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
    auto graph = build_dependency_graph(files, project_root, python_lang, config.entry_modules, packages);

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
