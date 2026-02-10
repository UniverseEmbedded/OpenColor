提示：不要直接去用`python`或`.pixi\envs\default\python.exe`命令，建议使用`pixi run python`，尤其是对于用到了 C++ 模块的（casadi和ipopt）

> **最后更新：2025-02**
>
> 本 README 已扩展为同时支持 **两种环境方案**：
>
> 1. **pixi（推荐）**：统一管理 conda + PyPI + uv，提供锁文件与 tasks
> 2. **原生方案（conda/mamba + uv）**：保持你原来 README 的内容

OpenColor 是一个用于 FDM 3D 打印的多色叠层规划与生成工具集。它通过将不同颜色的材料（如 R, G, B, W）以微小层厚进行物理堆叠，在打印件表面或内部实现精细的色彩表现。

---

# 目录

* [✨ 特性](#-特性)
* [🚀 环境管理方式（任选其一）](#-环境管理方式任选其一)
  * [方式A：使用 pixi（2025 推荐方案）](#方式a使用-pixi2025-推荐方案)
  * [方式B：使用 Conda/Mamba + uv（保持原方案）](#方式b使用-condamamba--uv保持原方案)
* [🧩 Conda/Mamba 详细教程（来自原 README）](#-condamamba-详细教程来自原-readme)
* [🖥️ 系统依赖安装（C++ 模块编译所需）](#️-系统依赖安装c-模块编译所需)
* [🖥️ IDE 配置（VSCode / PyCharm）](#️-ide-配置vscode--pycharm)
* [🛠️ 开发](#️-开发)
* [📦 打包](#-打包)
* [📂 目录结构](#-目录结构)
* [🐞 FAQ](#-faq)

---

# ✨ 特性

- **物理驱动的颜色预测**: 基于 Adding-Doubling 的物理模型
- **机器学习增强**: 使用 XGBoost/GPR 修正物理模型的残差，提高预测精度
- **完整的校准流程**: 从色盘生成、照片校正到模型训练的端到端校准
- **高性能 C++ 核心**: Vulkan 加速的几何处理和颜色求解
- **现代化 UI**: Vue 3 + Tauri 构建的跨平台桌面应用
- **标准 3MF 导出**: 基于 lib3mf 的标准 3MF 格式支持

---

# 🚀 环境管理方式（任选其一）

你可以选择：

* **方式 A：pixi（推荐，锁文件，可复现，统一管理）**
* **方式 B：继续使用 conda/mamba + uv（保留原方案）**

两种方案完全兼容，不会冲突。

---

# 方式 A：使用 pixi（2025 推荐方案）

## ⭐ pixi 是什么？

Pixi 是一个统一管理 Python（PyPI）、conda（conda-forge）和系统级依赖的现代工具，同时使用：

* **rattler/resolvo（conda 侧）**
* **uv（PyPI 侧）**
* 自动生成 `pixi.lock`（可复现）
* 自带任务系统（类似 npm scripts）

你不再需要手动混用 conda + pip/uv。

---

## 📥 安装 pixi（2025-11 最新版，全平台）

### 🪟 Windows（优先推荐）

#### 使用 winget（最简单）

```powershell
winget install prefix-dev.pixi
```

#### 使用 PowerShell 脚本

```powershell
powershell -ExecutionPolicy ByPass -c "irm -useb https://pixi.sh/install.ps1 | iex"
```

查看脚本：

```powershell
powershell -c "irm -useb https://pixi.sh/install.ps1 | more"
```

---

### 🍎 macOS

```bash
curl -fsSL https://pixi.sh/install.sh | bash
# 或
brew install pixi
```

若默认 zsh：

```zsh
curl -fsSL https://pixi.sh/install.sh | zsh
```

---

### 🐧 Linux

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

### 发行版 Repo

```bash
# Arch
pacman -S pixi
# Alpine
apk add pixi
```

---

## 🖥️ 系统依赖安装（C++ 模块编译所需）

如果你需要使用 C++ 高性能模块（推荐），需要安装以下系统级依赖：

### 🪟 Windows

#### 1. Git

vcpkg 依赖管理需要 Git 来拉取依赖库。

**安装方式：**
- **winget（推荐）**：`winget install Git.Git`
- **官网下载**：[https://git-scm.com/download/win](https://git-scm.com/download/win)

#### 2. CMake (>= 3.24)

C++ 模块构建需要 CMake 3.24 或更高版本。

**安装方式：**
- **winget（推荐）**：`winget install Kitware.CMake`
- **官网下载**：[https://cmake.org/download/](https://cmake.org/download/)

#### 3. Visual Studio Build Tools（C++ 编译器）

需要安装 MSVC 编译器以编译 C++ 模块。

**安装方式：**

```powershell
# 使用 winget 安装 Visual Studio Build Tools
winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.Windows11SDK.22621"
```

或手动下载安装：
- 下载地址：[https://visualstudio.microsoft.com/downloads/](https://visualstudio.microsoft.com/downloads/)
- 选择 **"Build Tools for Visual Studio 2022"**
- 安装时勾选：
  - **使用 C++ 的桌面开发** 工作负载
  - **Windows 11 SDK**（或 Windows 10 SDK）

> **注意**：不需要安装完整的 Visual Studio IDE，只需 Build Tools 即可。

#### 4. Vulkan 运行时（通常已预装）

Vulkan 运行时通常随显卡驱动自动安装。如果你的显卡驱动较新（NVIDIA/AMD/Intel），一般已经支持 Vulkan。

**验证 Vulkan 是否可用：**
```powershell
vulkaninfo --summary
```

如果显示 GPU 信息，说明 Vulkan 运行时已就绪。

> **关于 Vulkan SDK**：本项目通过 vcpkg 自动管理 Vulkan 头文件和库文件，**无需单独安装 LunarG Vulkan SDK**。vcpkg 会下载所需的头文件和加载器，运行时则使用系统已安装的 Vulkan 驱动。

---

### 🍎 macOS

```bash
# 安装 Xcode Command Line Tools（包含 Git 和编译器）
xcode-select --install

# 安装 CMake
brew install cmake
```

---

### 🐧 Linux (Ubuntu/Debian)

```bash
# 安装 Git、CMake、编译器
sudo apt update
sudo apt install -y git cmake build-essential

# 安装 Vulkan 开发库
sudo apt install -y libvulkan-dev vulkan-tools
```

---

## 🛠️ 用 pixi 安装本项目

克隆仓库后运行：

```bash
pixi install
```

运行 Web 应用：

```bash
# 开发模式
pixi run web-tauri-dev

# 构建生产版本
pixi run web-tauri-build
```

### pixi 自动生成的任务（见 pixi.toml）

**Web 前端任务：**
* `pixi run web-install` — 安装前端依赖
* `pixi run web-dev` — 启动前端开发服务器
* `pixi run web-build` — 构建前端生产环境代码
* `pixi run web-tauri-dev` — 启动 Tauri 开发环境
* `pixi run web-tauri-build` — 构建 Tauri 应用

**校准流程任务：**
* `pixi run p2-calib-board-gen` — 生成校准板
* `pixi run p2-calib-photo-warp-ui` — 照片透视校正（UI）
* `pixi run p2-calib-sample-build` — 构建样本数据集
* `pixi run p2-calib-color-rts` — 训练色彩模型

**生成流程任务：**
* `pixi run p2-gen-masks` — 生成掩码
* `pixi run p2-gen-vtracer` — 矢量化
* `pixi run p2-gen-3mf` — 导出 STL/3MF

**C++ 模块任务：**
* `pixi run setup-cpp` — 设置 C++ 环境

---

# 方式 B：使用 Conda/Mamba + uv（保持原方案）

以下内容完整保留自你原 README，仅做轻微排版优化。

## 🚀 快速开始（改为 Conda 优先）

### 1. 推荐：使用 Conda（或 Mamba）管理虚拟环境（为什么）

* `pyvkfft` 在 conda-forge 上提供预编译二进制包（包含 Windows/Mac/Linux 的构建），在多数情况下一键安装比本地编译更简单、更稳妥。([Anaconda][1])
* 建议使用 Miniforge / Mambaforge（轻量并默认启用 conda-forge）来避免对系统 base 环境造成干扰。([conda-forge.org][5])

### 2. 如何安装 Mamba

Mamba 是一个用 C++ 实现的 Conda 替代品，能显著提升包的安装速度和依赖解析效率。

- **对于新用户（推荐）**:
  直接下载并安装 **Mambaforge**。它是一个独立的安装包，预装了 Conda、Mamba 和 Python，并默认配置了 `conda-forge` 频道，是开箱即用的最佳选择。
  - **下载地址**: [Mambaforge GitHub Releases](https://github.com/conda-forge/miniforge/releases)

- **对于已安装 Conda / Anaconda 的用户**:
  你可以在现有的 Conda `base` 环境中安装 Mamba。打开终端并运行以下命令：
  ```bash
  conda install mamba -n base -c conda-forge
  ```
  安装完成后，你就可以在终端中使用 `mamba` 命令来替代 `conda` 了。

### 3. 在 Conda 下创建环境（示例：Python 3.12）

（下面示例用 mamba 更快；没有 mamba 则把 `mamba` 换成 `conda` 即可）

```powershell
# Windows PowerShell 示例
# 1) 创建环境（Python 3.12）
mamba create -n opencolor python=3.12 -y

# 2) 激活环境
mamba activate opencolor
# 或
conda activate opencolor
```

> 注：不要在 `base` 环境里安装项目依赖，尽量用单独 environment。关于 conda env 的更多信息参见官方文档。([Anaconda][6])

### 4. 配置 conda-forge channel（只需做一次）

```bash
conda config --add channels conda-forge
conda config --set channel_priority strict
```

（若使用 Mambaforge 并已默认启用 conda-forge，则可跳过此步。）([GitHub][4])

### 5. 安装依赖

```bash
# 基础科学计算
mamba install numpy scipy scikit-image pillow shapely trimesh

# 图像与矢量处理
mamba install opencv cairosvg lxml

# 机器学习
mamba install xgboost

# 其他工具
mamba install tqdm pytest pydantic
```

#### 如果你需要 CUDA 支持（选择特定 nvrtc 版本）

conda-forge 提供以特定 `cuda-version` 编译的包，可以在安装时指定，例如（示例）：

```bash
# 安装带 nvrtc 11.8 支持的包（示例）
conda install cuda-version=11.8
# 或
mamba install cuda-version=11.8
```

（不同平台/版本有多个可选的 cuda-version；若你需要 CUDA 后端，务必选择与本机 CUDA 驱动/库兼容的版本。）([sources.debian.org][7])

### 6. OpenCL / CUDA 的注意事项

* 某些计算库需要一个工作中的 GPU 计算环境（GPU 驱动、CUDA 工具链或 OpenCL ICD 等）。
* 如果使用 CUDA 后端，可能需要额外安装 `cupy`/`pycuda`（以便在 Python 中使用 CUDA）。

### 7. 在 Conda 环境中把项目以"可编辑安装"方式安装（开发时）

进入项目根目录（含 `pyproject.toml`）后，在激活的 conda 环境里运行：

```bash
# 推荐先安装 pip / build 工具（conda 已带 pip）
pip install -U pip setuptools

# 然后安装项目（可编辑）
pip install -e .
# 或按照你习惯使用的包管理器（uv pip ...也可以在 Conda env 中执行）
```

---

## 可复现的 environment.yml（示例）

下面的 `environment.yml` 可直接保存为文件并用 `mamba env create -f environment.yml` 或 `conda env create -f environment.yml` 创建环境：

```yaml
name: opencolor
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.12
  - pip
  - numpy>=1.26
  - scipy>=1.17.0
  - scikit-image>=0.23
  - pillow>=10.0
  - shapely>=2.0
  - trimesh>=4.11
  - opencv
  - xgboost>=3.1.3
  - tqdm
  - pytest>=8.0
  - pydantic>=2.12.5
  - nodejs>=20
  - pip:
    - manifold3d
    - lib3mf>=2.4.1.post1
    - gradio>=4.44.0
    - pygltflib>=1.16.0
    - vtracer>=0.6.11
    - jax>=0.4.38
    - jaxlib>=0.4.38
```

> 用 `mamba env create -f environment.yml` 会更快一些（若安装了 mamba）。([mamba.readthedocs.io][9])

---

## Windows 专门提示（PowerShell 示例）

1. 使用 Mambaforge / Miniforge 安装器并打开新终端（不要污染 base）。（下载页：conda-forge）([conda-forge.org][5])
2. PowerShell 示例命令（整合上文步骤）：

```powershell
# 假设已安装 Mambaforge，并在 PowerShell 中
mamba create -n opencolor python=3.12 -y
mamba activate opencolor

# 确保 conda-forge 可用（若 Mambaforge 默认已启用则可略）
conda config --add channels conda-forge
conda config --set channel_priority strict

# 安装基础依赖
mamba install numpy scipy scikit-image pillow shapely trimesh opencv -y

# 在项目目录安装项目（可编辑）
pip install -U pip setuptools
pip install -e .
```

---

## 故障排查（常见问题与解决）

* **pip 在 Windows 上报编译错误且提示找不到 cl.exe / 编译器错误**：
  这说明 pip 在尝试从源码编译扩展（需要 MSVC/编译工具链）。推荐用 conda-forge 的二进制包来避免在本地编译。([Anaconda][1])
* **需要 CUDA 而系统没有合适的 CUDA 工具链 / nvcc**：
  使用 conda 安装 `cuda-version=<x>` 可以得到与某个 nvrtc 版本匹配的包；但仍需要与 GPU 驱动/库保持兼容（并按需安装 `cupy`/`pycuda`）。([sources.debian.org][7])
* **OpenCL 后端在 Linux 下缺少 ICD**：
  在 Linux 上用 conda 时可能需要额外安装 `ocl-icd-system`，conda 安装通常会处理这些，但是在某些发行版上你可能需要手动安装系统包。([pyvkfft.readthedocs.io][3])

---

## 最后的小建议

* 对于开发者机器（Windows/Mac/Linux），**优先用 conda-forge 安装依赖**，这样可以大幅减少折腾编译工具链和环境变量的可能性。([Anaconda][1])
* 若需要极致性能且愿意管理 CUDA 细节：在 conda 环境里指定 `cuda-version` 并安装与之兼容的 `cupy`/`pycuda`，同时确保驱动与系统库匹配。([sources.debian.org][7])

---

# 🖥️ IDE 配置（VSCode / PyCharm）

## pixi 环境位置说明

* **pixi 环境默认在项目目录下的 `.pixi/` 里**，不是像 conda 那样在用户目录统一放。

一般规则：

* **Windows**：`项目根\.pixi\envs\default\python.exe`
* **Linux/macOS**：`项目根/.pixi/envs/default/bin/python`

如果你不确定，在项目根运行：

```bash
pixi run python -c "import sys, pathlib; print(sys.executable); print(pathlib.Path().resolve())"
```

第一行就是 pixi 当前用的解释器路径。

## VSCode 配置 pixi 环境

### 步骤

1. 打开 VSCode，打开你的项目目录：
   `（示例）D:\pama1234\pfp\p-2026-01\OpenColor-02`

2. 按快捷键：

* `Ctrl+Shift+P` → 输入 `Python: Select Interpreter`。

3. 如果 VSCode 能自动发现，会看到类似：

   ```text
   .pixi\envs\default\python.exe
   ```

   直接点它即可。

4. 如果没有自动出现：

* 在命令面板里选：`Python: Select Interpreter` → `Enter interpreter path...`
* 浏览到：
  `（根目录）\.pixi\envs\default\python.exe`

5. 选完之后，VSCode 会在 `.vscode/settings.json` 写入类似：

   ```json
   {
     "python.defaultInterpreterPath": ".pixi/envs/default/python.exe"
   }
   ```

   之后在 VSCode 里运行/调试，都会用 pixi 这个环境。

> 小建议：
> 以后换机器或删环境，只要在项目根重新 `pixi install`，VSCode 配置就自动复用，无需再改。

## PyCharm 配置 pixi 环境

### 步骤（以 Windows 为例）

1. 打开 PyCharm，打开该项目。

2. 右下角 / 右上角找到 Python 版本（可能显示 `Python 3.x`），点一下 → `Add Interpreter...`
   或者：
   `File` → `Settings` → `Project: xxx` → `Python Interpreter` → 右侧齿轮 → `Add Interpreter...`

3. 选择：**"Add Local Interpreter"**（或类似选项，版本略有不同）。

4. 在弹出的窗口中，选择 **Existing environment / System Interpreter** 这一项，然后浏览到：

   ```text
   （根目录）\.pixi\envs\default\python.exe
   ```

5. 确认后，这个解释器就会作为项目 Python 解释器，所有运行配置、调试、单元测试都会用 pixi 的环境。

## CLI + IDE 一套工作流建议

组合起来推荐这样用：

1. 在项目根目录命令行里用 pixi 管理环境：

   ```powershell
   pixi install
   pixi run web-tauri-dev     # 手动跑一遍确认没问题
   ```

2. VSCode / PyCharm 里选 `.pixi/envs/default/python.exe` 作为解释器。

3. 之后：

* 装新依赖：在终端用 `pixi add xxx` 或 `pixi add --pypi xxx`
* 不用再在 IDE 里点"pip install"，保持一切依赖都通过 pixi 走，锁文件不会乱。

---

# 🛠️ 开发

### 运行

有多种方式可以运行此应用：

```bash
# 方式一：启动 Web 开发服务器
pixi run web-dev

# 方式二：启动 Tauri 桌面应用（开发模式）
pixi run web-tauri-dev

# 方式三：运行原型环节
pixi run p2-calib-board-gen
pixi run p2-gen-masks
```

### 调试

- **日志**: 应用的所有日志都将输出到控制台。
- **调试模式**: 在调试模式下运行时，允许多个应用实例同时存在，方便对比测试。

### 测试

```bash
# 运行前端单元测试
pixi run web-test-unit

# 运行 Rust 后端测试
pixi run web-test-rust

# 运行所有测试
pixi run web-test-all
```

---

# 📦 打包

支持两种方式：

## 1) 使用 pixi（推荐）

```bash
pixi run web-tauri-build
```

打包完成后，生成的安装包位于：
`web/src-tauri/target/release/bundle/nsis/` 目录下。

## 2) 手动构建

### Web 前端

```bash
# 进入 web 目录
cd web

# 安装依赖
pnpm install

# 构建生产版本
pnpm run build
```

### Tauri 应用

```bash
# 进入 web 目录
cd web

# 安装依赖
pnpm install

# 构建 Tauri 应用
pnpm tauri build
```

---

# 📂 目录结构

```
OpenColor/
├── py_module/          # Python 模块
│   ├── opencolor/      # 核心算法库 (oc-core)
│   ├── engine/         # HTTP API 服务 (oc-engine)
│   ├── calibration/    # 自动校准 (oc-calib)
│   ├── model_export/   # 3MF 导出引擎
│   ├── prototypes/     # 原型开发 (oc-prototypes)
│   ├── scripts/        # 脚本集 (oc-scripts)
│   └── analyze/        # 分析诊断 (oc-analyze)
├── cpp_module/         # C++ 高性能模块
│   ├── src/solver/     # 求解器 (opencolor_solver)
│   ├── src/geometry/   # 几何处理 (opencolor_geometry)
│   ├── src/models/     # 预测模型 (opencolor_models)
│   └── src/mcrt/       # 光线追踪 (opencolor_mcrt)
├── web/                # Web 前端 + Tauri 桌面壳
│   ├── src/            # Vue 3 前端源码
│   └── src-tauri/      # Rust 后端
├── data/               # 数据文件（校准数据、示例图像）
└── doc/                # 文档
```

---

# 🐞 FAQ

## Q: 项目支持哪些操作系统？

A: 支持 Windows、macOS（Intel/Apple Silicon）和 Linux。通过 pixi.toml 中的 `platforms` 配置指定。

## Q: C++ 模块是必需的吗？

A: 不是必需的。Python 模块有纯 Python 的回退实现，但 C++ 模块提供显著的性能提升，特别是在几何处理和颜色求解方面。

## Q: 如何构建 C++ 模块？

A: 

1. **首次设置**：运行 `pixi run setup-cpp`
   - 这会初始化 vcpkg 子模块
   - 自动下载 C++ 依赖（Vulkan 头文件、pybind11、shaderc 等）

2. **构建模块**：CMake 会在首次构建时自动通过 vcpkg 安装依赖
   ```bash
   cd cpp_module
   mkdir build && cd build
   cmake .. -DCMAKE_BUILD_TYPE=Release
   cmake --build . --config Release -j
   ```

3. **依赖管理**：
   - **Vulkan**：vcpkg 自动提供头文件和加载器，运行时依赖系统驱动
   - **其他库**：pybind11、shaderc、clipper2、manifold 等均由 vcpkg 自动下载

详见 [cpp_module/README.md](cpp_module/README.md)。

## Q: 校准流程是什么？

A: 校准流程用于训练颜色预测模型：
1. 生成校准板 (`p2-calib-board-gen`)
2. 照片透视校正 (`p2-calib-photo-warp-ui`)
3. 构建样本数据集 (`p2-calib-sample-build`)
4. 训练色彩模型 (`p2-calib-color-rts`)

## Q: 生成流程是什么？

A: 生成流程用于从图像生成 3D 打印文件：
1. 生成掩码 (`p2-gen-masks`)
2. 矢量化 (`p2-gen-vtracer`)
3. 模型导出 (`p2-gen-3mf`)

## Q: 需要安装 Vulkan SDK 吗？

A: **不需要单独安装 LunarG Vulkan SDK**。

本项目通过 vcpkg 自动管理 Vulkan 依赖：
- **头文件和库**：vcpkg 自动下载 Vulkan 头文件和加载器
- **运行时**：使用系统已安装的 Vulkan 运行时（通常随显卡驱动安装）

**验证 Vulkan 是否可用：**
```powershell
vulkaninfo --summary
```

如果显示 GPU 信息，说明 Vulkan 运行时已就绪。现代 NVIDIA/AMD/Intel 显卡驱动通常都已包含 Vulkan 支持。

## 参考链接

[3]: https://pyvkfft.readthedocs.io/en/latest/index.html
[4]: https://github.com/conda-forge/miniforge
[5]: https://conda-forge.org/download/
[6]: https://docs.anaconda.com/free/working-with-conda/environments/
[7]: https://sources.debian.org/src/nvidia-cuda-toolkit/
[9]: https://mamba.readthedocs.io/en/latest/user_guide/mamba.html
