# OpenColor 依赖清理地图 (DEPC_MAP)

本文档列举项目中确定可以清理的文件及其理由。所有结论均基于代码阅读分析，而非猜测。

## 更新记录

- **2026-02-10**: 全面更新文档，反映最新代码结构变化
  - 更新路径引用（oc_prototypes_02 → oc_proto）
  - 更新环节名称（移除 _01 后缀）
  - 添加新的可清理文件分析
  - 更新验证方法和注意事项

---

## 确定可删除的文件

### 1. 根目录调试/分析脚本

| 文件 | 删除理由 | 替代方案 | 状态 |
|------|----------|----------|------|
| `analyze_black.py` | 硬编码了Black材料的原始参数(mu_a_raw, mu_s_raw)，进行手动TMM计算。这是**一次性调试脚本**，用于验证特定材料的TMM计算，没有通用性。代码逻辑与`calib_color_rts`中的模型预测完全重复。 | 使用`calib_color_rts`的训练和评估流程 | ⏳ 待删除 |
| `check_cells.py` | 硬编码了绝对路径`d:\pama1234\pfp\p-2026-01\OpenColor-02\py_module\prototypes\src\oc_proto\calib_color_rts\data`，**仅适用于特定开发环境**。功能只是读取dataset_cells*.json并打印行列数，完全被`calib_sample_build`的manifest.json和日志替代。 | 查看`calib_sample_build/out/*/manifest.json` | ⏳ 待删除 |
| `debug_model_data.py` | 硬编码了模型路径`py_module/prototypes/src/oc_proto/calib_color_rts/out/evaluation/four_flux_numpy/train_A`。这是**模型调试脚本**，用于检查加载的模型数据结构。功能与`calib_color_rts`中的模型加载和日志记录重复。 | 使用`calib_color_rts`的`--verbose`参数或查看诊断输出 | ⏳ 待删除 |
| `package_oc_prototypes_02.py` | **过时的打包脚本**。功能是将原型代码打包成zip，但现在已经使用pixi环境管理和可编辑安装(`pip install -e`)，不再需要手动打包。脚本中硬编码的文件列表可能已经过时。 | 使用`pixi install`和可编辑安装模式 | ⏳ 待删除 |
| `test_import.py` | **临时测试脚本**，用于验证导入功能。功能已被正式的测试流程替代。 | 使用`pixi run python -c "import oc_proto"` | ⏳ 待删除 |

### 2. scripts模块中的重复/过时脚本

| 文件 | 删除理由 | 替代方案 | 状态 |
|------|----------|----------|------|
| `scripts/src/oc_scripts/bambu/make_3mf.py` | **完全委托给model_export的兼容层**。文件注释明确说明"(Compatibility Layer delegating to model_export)"，只是`generate_bambu_project_from_template`的简单包装，没有额外功能。 | 直接使用`model_export.standard_3mf` | ⏳ 待删除 |
| `scripts/src/oc_scripts/color_contact_3mf.py` | **功能被opencolor和prototypes替代**。该脚本生成颜色互相接触的测试方块布局，但：1) 布局搜索逻辑(`_search_layout`, `_search_layout_cpp`)与`calib_board_gen`的配方生成重复；2) 3MF导出调用`model_export.standard_3mf`，没有独特价值；3) C++加速模块(`opencolor_color_contact_search.exe`)可能已不存在。 | 使用`calib_board_gen`生成校准板，或使用opencolor | ⏳ 待删除 |
| `scripts/src/oc_scripts/make_rgbw_cubes_3mf.py` | **简单的lib3mf示例脚本**。只是创建一个包含4个RGBW立方体的3MF文件，用于测试lib3mf功能。这个功能已被`model_export.standard_3mf`完全覆盖，且后者更通用。 | 使用`model_export.standard_3mf` | ⏳ 待删除 |

### 3. draw_apriltags.py 分析

| 文件 | 处理建议 | 理由 | 状态 |
|------|----------|------|------|
| `draw_apriltags.py` | **保留但重构** | 该文件包含三个AprilTag检测实现：1) OpenCV (`detect_apriltags_cv2`)；2) pupil-apriltags (`detect_apriltags_pupil`)；3) 自定义实现(`detect_apriltags_custom`)。**前两个实现已完全集成到`opencolor/src/oc_core_02/core/`**（通过`calib_photo_warp`）。但是，该脚本的`main()`函数是一个完整的命令行工具，可以独立运行检测并可视化结果，有一定价值。建议：将`main()`函数和可视化逻辑移到`opencolor`的CLI或Gradio界面中，然后删除此文件。 | ⏳ 待重构 |

---

## 删除后的影响

### 无影响（可安全删除）
- `analyze_black.py`
- `check_cells.py`
- `debug_model_data.py`
- `test_import.py`
- `scripts/src/oc_scripts/bambu/make_3mf.py`
- `scripts/src/oc_scripts/make_rgbw_cubes_3mf.py`

### 需要替代方案
- `package_oc_prototypes_02.py` → 使用pixi环境
- `scripts/src/oc_scripts/color_contact_3mf.py` → 使用calib_board_gen

### 需要重构后删除
- `draw_apriltags.py` → 功能合并到opencolor

---

## 建议的清理命令

```bash
# 1. 删除根目录调试脚本
rm analyze_black.py
rm check_cells.py
rm debug_model_data.py
rm package_oc_prototypes_02.py
rm test_import.py

# 2. 删除scripts中的重复脚本
rm py_module/scripts/src/oc_scripts/bambu/make_3mf.py
rm py_module/scripts/src/oc_scripts/color_contact_3mf.py
rm py_module/scripts/src/oc_scripts/make_rgbw_cubes_3mf.py

# 3. 如果bambu目录为空，删除整个目录
rmdir py_module/scripts/src/oc_scripts/bambu

# 4. draw_apriltags.py 需要重构后删除
# 将其功能集成到 opencolor 后再删除
```

---

## 验证方法

在删除前，可以通过以下方式验证这些文件确实未被使用：

```bash
# 搜索文件被导入的情况
grep -r "from analyze_black" . --include="*.py"
grep -r "import analyze_black" . --include="*.py"
grep -r "from check_cells" . --include="*.py"
grep -r "from debug_model_data" . --include="*.py"
grep -r "from draw_apriltags" . --include="*.py"
grep -r "from color_contact_3mf" . --include="*.py"
grep -r "from make_3mf" . --include="*.py"
grep -r "from make_rgbw_cubes_3mf" . --include="*.py"
grep -r "from test_import" . --include="*.py"
```

---

## 注意事项

1. **draw_apriltags.py** 虽然功能重复，但其命令行界面和可视化功能有一定价值，建议先重构到opencolor再删除。

2. **color_contact_3mf.py** 中的C++加速模块调用(`opencolor_color_contact_search.exe`)如果还存在，可能需要保留该可执行文件的构建配置。

3. 删除后建议运行测试确保没有破坏任何功能：
   ```bash
   pixi run p2-calib-board-gen
   pixi run p2-calib-photo-warp-ui
   ```

4. **bambu目录**: 如果`scripts/src/oc_scripts/bambu/`目录在删除`make_3mf.py`后为空，应删除整个目录。

---

## 路径更新说明

由于最近的代码重构，以下路径已发生变化：

| 旧路径 | 新路径 |
|--------|--------|
| `py_module/prototypes/src/oc_prototypes_02/` | `py_module/prototypes/src/oc_proto/` |
| `calib_board_gen_01/` | `calib_board_gen/` |
| `calib_photo_warp_01/` | `calib_photo_warp/` |
| `calib_sample_build_01/` | `calib_sample_build/` |
| `calib_color_model_fit_01/` | `calib_color_rts/` |
| `gen_masks_01/` | `gen_masks/` |
| `gen_vector_01/` | `gen_vector/` |
| `gen_model_exporter_01/` | `gen_3mf/` |

---

## 新增模块说明

项目中新增了以下模块，这些模块**不应被清理**：

| 模块 | 路径 | 功能 | 状态 |
|------|------|------|------|
| `sdf` | `py_module/sdf/src/oc_sdf/` | SDF（有向距离场）位图到3D网格转换 | ✅ 保留 |
| `xgb` | `py_module/xgb/src/oc_xgb/` | XGBoost颜色预测与物理GPR模型 | ✅ 保留 |
