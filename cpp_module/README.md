# OpenColor C++ 模块

该目录包含 OpenColor 项目的 C++ 高性能计算模块，通过 pybind11 导出为 Python 扩展模块，为 Python 原型提供加速支持。

## 模块概览

| 模块名 | 功能描述 | 主要依赖 |
|--------|----------|----------|
| `opencolor_solver` | 颜色配方求解器（Hill Climbing + GPR） | Vulkan, shaderc |
| `opencolor_geometry` | 几何处理与3D布尔运算 | Clipper2, Manifold |
| `opencolor_models` | 颜色预测模型（四通道/TMM/MCRT） | Vulkan, shaderc |
| `opencolor_mcrt` | 蒙特卡洛光线追踪（保留模块） | Vulkan, shaderc |

## 目录结构

```
cpp_module/
├── CMakeLists.txt          # 主构建配置
├── src/
│   ├── solver/             # 求解器模块
│   │   ├── solver_pybind.cpp      # Python绑定入口
│   │   └── hill_climbing_solver.cpp  # 爬山算法实现
│   ├── geometry/           # 几何处理模块
│   │   └── geometry_pybind.cpp    # 几何运算Python绑定
│   ├── models/             # 颜色预测模型
│   │   ├── model_pybind.cpp       # 模型模块绑定
│   │   ├── model_base.cpp         # 模型基类
│   │   ├── models.cpp             # 模型注册与工厂
│   │   ├── four_flux_model.cpp    # 四通道模型
│   │   ├── tmm_model.cpp          # TMM传输矩阵模型
│   │   └── mcrt_model.cpp         # MCRT蒙特卡洛模型
│   ├── mcrt/               # 蒙特卡洛光线追踪
│   │   ├── mcrt_pybind.cpp
│   │   ├── mcrt_cpu.cpp
│   │   ├── mcrt_vulkan.cpp
│   │   └── mcrt_vulkan_context.cpp
│   ├── vulkan_init.cpp     # Vulkan初始化
│   ├── vulkan_app.cpp      # Vulkan应用框架
│   ├── vulkan_helpers.cpp  # Vulkan辅助函数
│   ├── main.cpp            # GUI入口（可选）
│   ├── color_contact_search.cpp
│   └── web_probe.cpp
├── build/                  # 构建输出目录
│   └── Release/
│       ├── opencolor_solver.pyd
│       ├── opencolor_geometry.pyd
│       ├── opencolor_models.pyd
│       └── opencolor_mcrt.pyd
└── vcpkg/                  # 包管理器
```

## 构建要求

- **CMake**: >= 3.24
- **C++标准**: C++20
- **Python**: 3.11+
- **Vulkan SDK**: 最新版本
- **vcpkg**: 用于依赖管理

## 依赖库

通过 vcpkg 自动安装：
- `pybind11` - Python/C++ 绑定
- `vulkan` - 图形计算
- `shaderc` - 着色器编译
- `clipper2` - 2D多边形操作
- `manifold` - 3D布尔运算与网格处理
- `tbb` - 并行算法库

## 构建步骤

```bash
# 1. 进入cpp_module目录
cd cpp_module

# 2. 创建构建目录
mkdir -p build && cd build

# 3. 配置（自动下载依赖）
cmake .. -DCMAKE_BUILD_TYPE=Release

# 4. 构建
cmake --build . --config Release -j

# 5. 输出文件位于 build/Release/*.pyd
```

## 模块详细说明

### opencolor_solver

颜色配方求解器，用于 `gen_masks` 模块。

**主要功能**:
- `HillClimbingSolver` - 基于爬山算法的配方优化
- 支持物理模型 + GPR 残差修正的混合预测
- 支持 GIL 释放的多线程求解 (`solve`, `predict_batch`)

**Python接口**:
```python
from opencolor_solver import HillClimbingSolver

solver = HillClimbingSolver(
    optical, gpr_L, gpr_a, gpr_b,  # 模型参数
    feature_names,
    n_random_samples=1000,         # 随机采样数
    hill_climb_iterations=10,      # 迭代次数
    n_layers=5,                    # 层数
    layer_names_order="bottom_first",
    use_vulkan=False
)
recipes = solver.solve(target_rgb)  # 求解最优配方
```

### opencolor_geometry

几何处理与3D布尔运算，用于 `gen_3mf` 模块。

**主要功能**:
- **2D多边形操作** (Clipper2):
  - `clipper_boolean` - 布尔运算（并/差/交）
  - `clipper_offset` - 多边形偏移/膨胀
- **三角化** (Earcut):
  - `earcut_triangulate_rings` - 多边形三角化
- **3D挤出**:
  - `extrude_rings` / `extrude_rings_nogil` - 2D多边形挤出为3D网格
- **3D布尔运算** (Manifold):
  - `manifold_union` / `manifold_union_nogil` - 网格并集
  - `manifold_difference` / `manifold_difference_nogil` - 网格差集
  - `manifold_intersection` - 网格交集
  - `manifold_volume` - 计算网格体积

**Python接口**:
```python
from opencolor_geometry import (
    clipper_boolean, clipper_offset,
    extrude_rings_nogil,
    manifold_union_nogil, manifold_difference_nogil,
    manifold_volume_nogil
)

# 挤出2D多边形为3D网格
vertices, faces, area = extrude_rings_nogil(rings, z_start=0, z_end=0.12)

# 3D布尔运算
union_v, union_f = manifold_union_nogil([(v1, f1), (v2, f2)])
volume = manifold_volume_nogil(vertices, faces)
```

### opencolor_models

颜色预测模型，用于 `calib_color_rts` 模块。

**支持的模型**:
- `FourFluxModel` - 四通道 Adding-Doubling 模型
- `TMMModel` - 传输矩阵法（相干/非相干混合）
- `MCRTModel` - 蒙特卡洛光线追踪

**Python接口**:
```python
from opencolor_models import create_model, predict_four_flux_vulkan

# 使用工厂创建模型
model = create_model("four_flux")
model.set_use_gpu(True)
results = model.predict(mu_a, mu_s, g, sequences, backing=0.98, k1=0.04, k2=0.0)

# 底层函数（向后兼容）
rgb = predict_four_flux_vulkan(mu_a, mu_s, g, seq_indices, backing, k1, k2)
```

## 性能优化

### GIL 释放
所有计算密集型函数都提供 `_nogil` 版本，在执行期间释放 Python GIL：
- `extrude_rings_nogil`
- `manifold_union_nogil`
- `manifold_difference_nogil`
- `manifold_volume_nogil`

### Vulkan 加速
支持 Vulkan GPU 加速的模块：
- `opencolor_solver` - 配方求解的物理模型预测
- `opencolor_models` - 四通道/TMM模型预测

## 与 Python 模块的集成

```python
# Python端自动加载
try:
    from opencolor_solver import HillClimbingSolver
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False
    print("警告: C++求解器不可用，将回退到Python实现")
```

## 开发指南

### 添加新的 C++ 模块

1. 在 `src/` 下创建新目录
2. 编写 pybind11 绑定代码
3. 在 `CMakeLists.txt` 中添加：
```cmake
add_library(new_module MODULE src/new_module/new_pybind.cpp)
target_include_directories(new_module PRIVATE ${_opencolor_vcpkg_include} ${_python_include})
target_link_libraries(new_module PRIVATE ...)
set_target_properties(new_module PROPERTIES PREFIX "" SUFFIX "${_python_ext_suffix}")
```

### 调试构建

```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
cmake --build . --config Debug
```

## 许可证

与 OpenColor 项目主许可证一致。
