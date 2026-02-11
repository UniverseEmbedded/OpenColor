# 校准板颜色生成 Bug 报告

## 概述

在使用 `calib_board_gen` 模块生成多色校准板时，发现生成的 3MF 文件颜色显示不正确。

## 当前症状

1. **颜色数量不正确**：使用 RYBW 四色配置生成的色盘，在 Bambu Studio 中只显示 **Red** 和 **White** 两种颜色，缺少 **Yellow** 和 **Blue**
2. **出现不应有的三角形**：色盘两侧出现两个白色三角形（侧边三角形），这些是不应该出现的几何体

### 截图证据

在 Bambu Studio 中打开 `4-Color_Board_A.3mf`：
- 左侧材料列表只显示两种颜色（Red、White）
- 色盘主体显示为红色
- 色盘两侧各有一个白色三角形

## 受影响的文件

### 主要修改文件

| 文件路径 | 问题描述 |
|---------|---------|
| `py_module/prototypes/src/oc_proto/calib_board_gen/generate_8color_board.py` | 核心逻辑文件，包含以下问题： |
| - `_build_core_volumes()` (L749) | 标记区域颜色处理可能导致数据区域颜色丢失 |
| - `_build_triangle_meshes()` (L786) | 生成不应有的侧边三角形 |
| - `spec_to_meshes()` (L827) | 调用三角形生成函数 |

### 相关配置文件

| 文件路径 | 说明 |
|---------|------|
| `py_module/prototypes/src/oc_proto/calib_board_gen/color_profiles.py` | 颜色配置定义（RYBW、RGB等） |
| `py_module/model_export/src/model_export/standard_3mf.py` | 3MF导出逻辑 |
| `py_module/model_export/src/model_export/types.py` | 默认颜色定义 |

## 问题分析

### 问题1：颜色显示不正确

**根本原因**：`_build_core_volumes()` 函数中，标记区域统一使用 `slot_names[0]`（第一种颜色，即 Red），但可能存在逻辑错误导致数据区域的颜色也被覆盖或丢失。

**代码位置**：
```python
# generate_8color_board.py L778-782
else:
    # 处理标记区域的格子
    # 统一使用第一个颜色作为标记颜色，避免多色接触导致的边界边问题
    color_name = slot_names[0]
    volumes[color_name][:, r_cell, c_cell] = True
```

### 问题2：侧边三角形

**根本原因**：`_build_triangle_meshes()` 函数生成两个三角形用于连接 Tag 和色盘，但这些三角形在当前设计中是不需要的。

**代码位置**：
```python
# generate_8color_board.py L807-823
# 大Tag侧（右上角内侧连接处）
meshes[triangle_color].append(_triangle_prism_mesh(p0, p1, p2, 0.0, total_h))

# 小Tag侧（左下角内侧连接处）
meshes[triangle_color].append(_triangle_prism_mesh(q0, q1, q2, 0.0, total_h))
```

## 已尝试的修复

### 修复1：三角形函数添加 profile 参数

**修改内容**：为 `_build_triangle_meshes()` 添加 `profile` 参数，使用动态颜色替代硬编码 "White"

**状态**：已完成，但三角形仍然生成（只是颜色可能改变）

### 修复2：统一标记区域颜色

**修改内容**：简化 `_build_core_volumes()` 中的标记区域处理，统一使用第一种颜色

**状态**：已完成，但颜色显示问题仍然存在

## 建议的解决方案

### 方案1：移除侧边三角形

**方法**：修改 `spec_to_meshes()` 函数，忽略 `include_side_triangles` 参数或将其强制设为 `False`

**代码修改**：
```python
# 在 spec_to_meshes() 中
# 移除或注释掉以下代码
# if bool(include_side_triangles):
#     tri_meshes = _build_triangle_meshes(profile)
#     for slot_name in slot_names:
#         meshes_by_slot[slot_name].extend(tri_meshes[slot_name])
```

### 方案2：修复颜色生成逻辑

**方法**：检查 `_build_core_volumes()` 中数据区域的颜色分配是否正确

**检查点**：
1. 确认 `cell_map` 的键格式与查找逻辑匹配
2. 确认 `layers` 中的颜色索引正确转换为颜色名称
3. 确认体素体积的维度正确（z, y, x）

### 方案3：调试颜色导出

**方法**：在 `export_standard_3mf()` 中添加日志，确认每种颜色的网格是否被正确导出

**检查点**：
1. 确认 `meshes_by_slot` 包含所有颜色
2. 确认每种颜色的网格顶点数不为零
3. 确认 3MF 文件包含所有颜色对象

## 测试验证

### 测试命令

```bash
# 生成 RYBW 四色校准板
pixi run p2-calib-board-gen --profile rybw --num_boards 1

# 生成 RGB 三色校准板
pixi run p2-calib-board-gen --profile rgb --num_boards 1

# 生成 8 色校准板
pixi run p2-calib-board-gen --profile full_8 --num_boards 1
```

### 验证方法

1. **Bambu Studio 检查**：打开生成的 3MF 文件，确认：
   - 颜色数量正确（RYBW=4色，RGB=3色，full_8=8色）
   - 色盘主体显示多种颜色
   - 没有多余的白色三角形

2. **JSON 检查**：查看 `_board_spec.json` 文件，确认 `cell_map` 中包含多种颜色

3. **日志检查**：运行生成命令时，确认日志中显示所有颜色的网格信息

## 相关日志

正常生成时的日志输出：
```
INFO - 4色板/Red/体素网格(已并集) 顶点=1057 面=2018
INFO - 4色板/Yellow/体素网格(已并集) 顶点=734 面=1316
INFO - 4色板/Blue/体素网格(已并集) 顶点=743 面=1346
INFO - 4色板/White/体素网格(已并集) 顶点=815 面=1434
```

这表明四种颜色的网格都被生成了，但可能在导出阶段出现问题。

## 备注

- 问题可能涉及多个文件的交互
- 需要仔细检查体素网格生成、合并、导出三个阶段
- 建议逐步调试，确认每个阶段的颜色数据是否正确
