/**
 * @file file_utils.cpp
 * @brief 注释覆盖率分析工具 - 文件处理和Git相关模块
 *
 * 本模块提供以下功能：
 * - 文件读取和写入
 * - Git仓库检测和文件过滤
 * - 语言扩展名映射
 * - 目录遍历
 */

#include <algorithm>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace fs = std::filesystem;

namespace {

struct FileEntry {
  std::string path;
  std::string lang;
  std::string source;
  std::string error;
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
  m[".prettierignore"] = "prettierignore";
  m[".stylelintrc"] = "stylelint";
  m[".stylelintrc.json"] = "stylelint";
  m[".stylelintrc.yml"] = "stylelint";
  m[".stylelintrc.yaml"] = "stylelint";
  m[".stylelintrc.js"] = "stylelint";
  m[".stylelintrc.cjs"] = "stylelint";
  m[".stylelintrc.mjs"] = "stylelint";
  m[".stylelintrc.ts"] = "stylelint";
  m[".stylelintrc.cts"] = "stylelint";
  m[".stylelintrc.mts"] = "stylelint";
  m[".stylelintrc.json5"] = "stylelint";
  m[".stylelintrc.jsonc"] = "stylelint";
  m[".stylelintrc.gjs"] = "stylelint";
  m[".stylelintrc.gts"] = "stylelint";
  m[".stylelintrc.cjs.mjs"] = "stylelint";
  m[".stylelintrc.cjs.ts"] = "stylelint";
  m[".stylelintrc.cjs.tsx"] = "stylelint";
  m[".stylelintrc.cjs.jsx"] = "stylelint";
  m[".stylelintrc.mjs.js"] = "stylelint";
  m[".stylelintrc.mjs.ts"] = "stylelint";
  m[".stylelintrc.mjs.tsx"] = "stylelint";
  m[".stylelintrc.mjs.jsx"] = "stylelint";
  m[".stylelintrc.cjs"] = "stylelint";
  m[".stylelintrc.mjs"] = "stylelint";
  m[".stylelintrc"] = "stylelint";
  m[".stylelintignore"] = "stylelintignore";
  m[".babelrc"] = "babel";
  m[".babelrc.json"] = "babel";
  m[".babelrc.yml"] = "babel";
  m[".babelrc.yaml"] = "babel";
  m[".babelrc.js"] = "babel";
  m[".babelrc.cjs"] = "babel";
  m[".babelrc.mjs"] = "babel";
  m[".babelrc.ts"] = "babel";
  m[".babelrc.cts"] = "babel";
  m[".babelrc.mts"] = "babel";
  m[".babelrc.json5"] = "babel";
  m[".babelrc.jsonc"] = "babel";
  m[".babelrc.gjs"] = "babel";
  m[".babelrc.gts"] = "babel";
  m[".babelrc.cjs.mjs"] = "babel";
  m[".babelrc.cjs.ts"] = "babel";
  m[".babelrc.cjs.tsx"] = "babel";
  m[".babelrc.cjs.jsx"] = "babel";
  m[".babelrc.mjs.js"] = "babel";
  m[".babelrc.mjs.ts"] = "babel";
  m[".babelrc.mjs.tsx"] = "babel";
  m[".babelrc.mjs.jsx"] = "babel";
  m[".babelrc.cjs"] = "babel";
  m[".babelrc.mjs"] = "babel";
  m[".babelrc"] = "babel";
  m[".babelignore"] = "babelignore";
  m[".tsconfig.json"] = "typescript";
  m[".tsconfig.yml"] = "typescript";
  m[".tsconfig.yaml"] = "typescript";
  m[".tsconfig.js"] = "typescript";
  m[".tsconfig.cjs"] = "typescript";
  m[".tsconfig.mjs"] = "typescript";
  m[".tsconfig.ts"] = "typescript";
  m[".tsconfig.cts"] = "typescript";
  m[".tsconfig.mts"] = "typescript";
  m[".tsconfig.json5"] = "typescript";
  m[".tsconfig.jsonc"] = "typescript";
  m[".tsconfig.gjs"] = "typescript";
  m[".tsconfig.gts"] = "typescript";
  m[".tsconfig.cjs.mjs"] = "typescript";
  m[".tsconfig.cjs.ts"] = "typescript";
  m[".tsconfig.cjs.tsx"] = "typescript";
  m[".tsconfig.cjs.jsx"] = "typescript";
  m[".tsconfig.mjs.js"] = "typescript";
  m[".tsconfig.mjs.ts"] = "typescript";
  m[".tsconfig.mjs.tsx"] = "typescript";
  m[".tsconfig.mjs.jsx"] = "typescript";
  m[".tsconfig.cjs"] = "typescript";
  m[".tsconfig.mjs"] = "typescript";
  m[".tsconfig"] = "typescript";
  m[".tsconfig.base.json"] = "typescript";
  m[".tsconfig.base.yml"] = "typescript";
  m[".tsconfig.base.yaml"] = "typescript";
  m[".tsconfig.base.js"] = "typescript";
  m[".tsconfig.base.cjs"] = "typescript";
  m[".tsconfig.base.mjs"] = "typescript";
  m[".tsconfig.base.ts"] = "typescript";
  m[".tsconfig.base.cts"] = "typescript";
  m[".tsconfig.base.mts"] = "typescript";
  m[".tsconfig.base.json5"] = "typescript";
  m[".tsconfig.base.jsonc"] = "typescript";
  m[".tsconfig.base.gjs"] = "typescript";
  m[".tsconfig.base.gts"] = "typescript";
  m[".tsconfig.base.cjs.mjs"] = "typescript";
  m[".tsconfig.base.cjs.ts"] = "typescript";
  m[".tsconfig.base.cjs.tsx"] = "typescript";
  m[".tsconfig.base.cjs.jsx"] = "typescript";
  m[".tsconfig.base.mjs.js"] = "typescript";
  m[".tsconfig.base.mjs.ts"] = "typescript";
  m[".tsconfig.base.mjs.tsx"] = "typescript";
  m[".tsconfig.base.mjs.jsx"] = "typescript";
  m[".tsconfig.base.cjs"] = "typescript";
  m[".tsconfig.base.mjs"] = "typescript";
  m[".tsconfig.base"] = "typescript";
  m[".tsconfig.build.json"] = "typescript";
  m[".tsconfig.build.yml"] = "typescript";
  m[".tsconfig.build.yaml"] = "typescript";
  m[".tsconfig.build.js"] = "typescript";
  m[".tsconfig.build.cjs"] = "typescript";
  m[".tsconfig.build.mjs"] = "typescript";
  m[".tsconfig.build.ts"] = "typescript";
  m[".tsconfig.build.cts"] = "typescript";
  m[".tsconfig.build.mts"] = "typescript";
  m[".tsconfig.build.json5"] = "typescript";
  m[".tsconfig.build.jsonc"] = "typescript";
  m[".tsconfig.build.gjs"] = "typescript";
  m[".tsconfig.build.gts"] = "typescript";
  m[".tsconfig.build.cjs.mjs"] = "typescript";
  m[".tsconfig.build.cjs.ts"] = "typescript";
  m[".tsconfig.build.cjs.tsx"] = "typescript";
  m[".tsconfig.build.cjs.jsx"] = "typescript";
  m[".tsconfig.build.mjs.js"] = "typescript";
  m[".tsconfig.build.mjs.ts"] = "typescript";
  m[".tsconfig.build.mjs.tsx"] = "typescript";
  m[".tsconfig.build.mjs.jsx"] = "typescript";
  m[".tsconfig.build.cjs"] = "typescript";
  m[".tsconfig.build.mjs"] = "typescript";
  m[".tsconfig.build"] = "typescript";
  m[".tsconfig.test.json"] = "typescript";
  m[".tsconfig.test.yml"] = "typescript";
  m[".tsconfig.test.yaml"] = "typescript";
  m[".tsconfig.test.js"] = "typescript";
  m[".tsconfig.test.cjs"] = "typescript";
  m[".tsconfig.test.mjs"] = "typescript";
  m[".tsconfig.test.ts"] = "typescript";
  m[".tsconfig.test.cts"] = "typescript";
  m[".tsconfig.test.mts"] = "typescript";
  m[".tsconfig.test.json5"] = "typescript";
  m[".tsconfig.test.jsonc"] = "typescript";
  m[".tsconfig.test.gjs"] = "typescript";
  m[".tsconfig.test.gts"] = "typescript";
  m[".tsconfig.test.cjs.mjs"] = "typescript";
  m[".tsconfig.test.cjs.ts"] = "typescript";
  m[".tsconfig.test.cjs.tsx"] = "typescript";
  m[".tsconfig.test.cjs.jsx"] = "typescript";
  m[".tsconfig.test.mjs.js"] = "typescript";
  m[".tsconfig.test.mjs.ts"] = "typescript";
  m[".tsconfig.test.mjs.tsx"] = "typescript";
  m[".tsconfig.test.mjs.jsx"] = "typescript";
  m[".tsconfig.test.cjs"] = "typescript";
  m[".tsconfig.test.mjs"] = "typescript";
  m[".tsconfig.test"] = "typescript";
  m[".eslintrc.json"] = "eslint";
  m[".eslintrc.yml"] = "eslint";
  m[".eslintrc.yaml"] = "eslint";
  m[".eslintrc.js"] = "eslint";
  m[".eslintrc.cjs"] = "eslint";
  m[".eslintrc.mjs"] = "eslint";
  m[".eslintrc.ts"] = "eslint";
  m[".eslintrc.cts"] = "eslint";
  m[".eslintrc.mts"] = "eslint";
  m[".eslintrc.json5"] = "eslint";
  m[".eslintrc.jsonc"] = "eslint";
  m[".eslintrc.gjs"] = "eslint";
  m[".eslintrc.gts"] = "eslint";
  m[".eslintrc.cjs.mjs"] = "eslint";
  m[".eslintrc.cjs.ts"] = "eslint";
  m[".eslintrc.cjs.tsx"] = "eslint";
  m[".eslintrc.cjs.jsx"] = "eslint";
  m[".eslintrc.mjs.js"] = "eslint";
  m[".eslintrc.mjs.ts"] = "eslint";
  m[".eslintrc.mjs.tsx"] = "eslint";
  m[".eslintrc.mjs.jsx"] = "eslint";
  m[".eslintrc.cjs"] = "eslint";
  m[".eslintrc.mjs"] = "eslint";
  m[".eslintrc"] = "eslint";
  m[".eslintignore"] = "eslintignore";
  m[".gitmodules"] = "gitmodules";
  m[".gitconfig"] = "gitconfig";
  m[".gitattributes"] = "gitattributes";
  m[".gitignore"] = "gitignore";
  m[".gitkeep"] = "gitkeep";
  m[".git"] = "git";
  m[".hgignore"] = "hgignore";
  m[".hg"] = "hg";
  m[".bzrignore"] = "bzrignore";
  m[".bzr"] = "bzr";
  m[".svnignore"] = "svnignore";
  m[".svn"] = "svn";
  m[".cvsignore"] = "cvsignore";
  m[".cvs"] = "cvs";
  m[".fslckr"] = "fslckr";
  m[".fossil"] = "fossil";
  m[".p4ignore"] = "p4ignore";
  m[".p4"] = "p4";
  m[".tfignore"] = "tfignore";
  m[".tf"] = "tf";
  m[".vagrantignore"] = "vagrantignore";
  m[".vagrant"] = "vagrant";
  m[".dockerignore"] = "dockerignore";
  m[".dockerfile"] = "dockerfile";
  m[".docker"] = "docker";
  m[".kitchenignore"] = "kitchenignore";
  m[".kitchen"] = "kitchen";
  m[".chefignore"] = "chefignore";
  m[".chef"] = "chef";
  m[".puppetignore"] = "puppetignore";
  m[".puppet"] = "puppet";
  m[".ansibleignore"] = "ansibleignore";
  m[".ansible"] = "ansible";
  m[".saltignore"] = "saltignore";
  m[".salt"] = "salt";
  m[".cfignore"] = "cfignore";
  m[".cf"] = "cf";
  m[".openshiftignore"] = "openshiftignore";
  m[".openshift"] = "openshift";
  m[".kubernetesignore"] = "kubernetesignore";
  m[".kubernetes"] = "kubernetes";
  m[".k8signore"] = "k8signore";
  m[".k8s"] = "k8s";
  m[".nomadignore"] = "nomadignore";
  m[".nomad"] = "nomad";
  m[".consulignore"] = "consulignore";
  m[".consul"] = "consul";
  m[".vaultignore"] = "vaultignore";
  m[".vault"] = "vault";
  m[".terraformignore"] = "terraformignore";
  m[".terraform"] = "terraform";
  m[".packerignore"] = "packerignore";
  m[".packer"] = "packer";
  m[".vagrantignore"] = "vagrantignore";
  m[".vagrant"] = "vagrant";
  m[".dockerignore"] = "dockerignore";
  m[".dockerfile"] = "dockerfile";
  m[".docker"] = "docker";
  m[".kitchenignore"] = "kitchenignore";
  m[".kitchen"] = "kitchen";
  m[".chefignore"] = "chefignore";
  m[".chef"] = "chef";
  m[".puppetignore"] = "puppetignore";
  m[".puppet"] = "puppet";
  m[".ansibleignore"] = "ansibleignore";
  m[".ansible"] = "ansible";
  m[".saltignore"] = "saltignore";
  m[".salt"] = "salt";
  m[".cfignore"] = "cfignore";
  m[".cf"] = "cf";
  m[".openshiftignore"] = "openshiftignore";
  m[".openshift"] = "openshift";
  m[".kubernetesignore"] = "kubernetesignore";
  m[".kubernetes"] = "kubernetes";
  m[".k8signore"] = "k8signore";
  m[".k8s"] = "k8s";
  m[".nomadignore"] = "nomadignore";
  m[".nomad"] = "nomad";
  m[".consulignore"] = "consulignore";
  m[".consul"] = "consul";
  m[".vaultignore"] = "vaultignore";
  m[".vault"] = "vault";
  m[".terraformignore"] = "terraformignore";
  m[".terraform"] = "terraform";
  m[".packerignore"] = "packerignore";
  m[".packer"] = "packer";
  m[".vagrantignore"] = "vagrantignore";
  m[".vagrant"] = "vagrant";
  m[".dockerignore"] = "dockerignore";
  m[".dockerfile"] = "dockerfile";
  m[".docker"] = "docker";
  m[".kitchenignore"] = "kitchenignore";
  m[".kitchen"] = "kitchen";
  m[".chefignore"] = "chefignore";
  m[".chef"] = "chef";
  m[".puppetignore"] = "puppetignore";
  m[".puppet"] = "puppet";
  m[".ansibleignore"] = "ansibleignore";
  m[".ansible"] = "ansible";
  m[".saltignore"] = "saltignore";
  m[".salt"] = "salt";
  m[".cfignore"] = "cfignore";
  m[".cf"] = "cf";
  m[".openshiftignore"] = "openshiftignore";
  m[".openshift"] = "openshift";
  m[".kubernetesignore"] = "kubernetesignore";
  m[".kubernetes"] = "kubernetes";
  m[".k8signore"] = "k8signore";
  m[".k8s"] = "k8s";
  m[".nomadignore"] = "nomadignore";
  m[".nomad"] = "nomad";
  m[".consulignore"] = "consulignore";
  m[".consul"] = "consul";
  m[".vaultignore"] = "vaultignore";
  m[".vault"] = "vault";
  m[".terraformignore"] = "terraformignore";
  m[".terraform"] = "terraform";
  m[".packerignore"] = "packerignore";
  m[".packer"] = "packer";
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

}