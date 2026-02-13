# OpenColor 重构建议地图

本文档记录项目中建议重命名、移动或结构调整的文件、文件夹和代码元素。

## 更新记录

- **2026-02-10**: 全面更新文档，反映最新代码结构
  - 更新原型模块路径（oc_prototypes_02 → oc_proto）
  - 更新环节名称（移除 _01 后缀，calib_color_model_fit → calib_color_rts）
  - 添加新的模块（sdf, xgb）
  - 更新文档同步状态

---

## 已完成的重构

### 1. 原型模块重命名（已完成）

- `oc_prototypes_02` → `oc_proto` ✅
- 环节 `_01` 后缀已移除 ✅
  - `calib_board_gen_01` → `calib_board_gen`
  - `calib_photo_warp_01` → `calib_photo_warp`
  - `calib_sample_build_01` → `calib_sample_build`
  - `calib_color_model_fit_01` → `calib_color_rts`
  - `gen_masks_01` → `gen_masks`
  - `gen_vector_01` → `gen_vector`
  - `gen_model_exporter_01` → `gen_3mf`

### 2. calib_color_model_fit 重命名（已完成）

- `calib_color_model_fit` → `calib_color_rts` ✅
- 已在代码中完成重命名

---

## 高优先级重构

### 4. oc_core 模块合并（建议）

**当前问题**:
- `oc_core/` 和 `oc_core_02/` 两个目录并存
- `oc_core_02` 包含 SDF 相关功能
- `oc_core` 包含旧版核心功能

**建议**:
```
py_module/opencolor/src/
├── oc_core/              # 合并后的核心模块
│   ├── core/            # 核心算法（合并 oc_core + oc_core_02/core）
│   ├── ui/              # Gradio 界面（原 oc_core_02/ui）
│   └── utils/           # 工具函数
```

**影响范围**: 29 个文件

---

## 中优先级重构

### 5. scripts 模块重组

**当前问题**:
- `scripts/src/oc_scripts/` 包含大量松散脚本
- `bambu/` 子模块已弃用（`make_3mf.py` 是兼容层）
- `calibration/` 与 `prototypes` 的校准环节重复

**建议**:
```
py_module/scripts/
├── src/oc_scripts/
│   ├── planning/          # 保留：叠层规划
│   ├── stl/              # 保留：3D 几何生成
│   ├── svg/              # 保留：矢量处理
│   └── utils/            # 保留：工具脚本
│   # 删除：bambu/ (已弃用)
│   # 删除：calibration/ (与 prototypes 重复)
│   # 删除：color_contact_3mf.py (已弃用)
│   # 删除：make_rgbw_cubes_3mf.py (示例脚本)
```

---

### 6. analyze 模块合并到 scripts

**当前状态**: `py_module/analyze/` 是独立的模块
**建议**: 合并到 `py_module/scripts/src/oc_scripts/analyze/`

**理由**:
- `analyze` 模块功能单一，不需要独立模块
- 减少模块数量，简化项目结构

---

### 7. 根目录脚本清理

**建议删除的文件**:
- `analyze_black.py` - 一次性调试脚本
- `check_cells.py` - 硬编码路径，功能被 manifest 替代
- `debug_model_data.py` - 调试脚本
- `package_oc_prototypes_02.py` - 过时的打包脚本
- `draw_apriltags.py` - 功能已集成到 oc_core_02
- `process_dragon_girl.py` - 特定示例脚本
- `regenerate_all_palettes.py` - 一次性脚本
- `test_solver_consistency.py` - 测试脚本应移到 tests/
- `test_tmm_vulkan.py` - 测试脚本应移到 tests/

**注意**: 这些文件在 DEPC_MAP.md 中有详细分析

---

## 低优先级重构

### 8. 统一命名风格

**当前不一致**:
- `oc-core` vs `oc_core`（包名使用下划线）
- `oc-engine` vs `oc_engine`
- `oc-calib` vs `oc_calib`
- `oc-prototypes` vs `oc_prototypes`

**建议**: 统一使用下划线风格（Python 包名惯例）

---

### 9. engine handlers 命名

**当前**: `oc_engine/handlers/`
**建议**: 按功能分组
```
oc_engine/handlers/
├── calibration/          # board.py, lut.py, dataset.py
├── generation/           # bitmap.py, svg.py
├── validation/           # mcrt.py, health.py
```

---

### 10. 函数和变量命名

**建议统一**:
- 使用 `snake_case` 命名函数和变量
- 避免单字母变量（循环变量除外）
- 使用描述性名称

**示例**:
```python
# 当前
p = rgb_pixels.astype(np.float32)
c = lut_flat_rgb.astype(np.float32)

# 建议
pixel_floats = rgb_pixels.astype(np.float32)
lut_floats = lut_flat_rgb.astype(np.float32)
```

---

### 11. 常量提取

**建议**: 将魔法数字提取为常量

**示例**:
```python
# 当前 (bitmap_pipeline.py)
MAX_PIXELS = 100000  # 已在代码中

# 建议添加到 config 模块
# oc_core/config.py
DEFAULT_MAX_PIXELS_FOR_PREVIEW = 100_000
DEFAULT_LUT_SIZE = 32
DEFAULT_CHUNK_SIZE = 8000
```

---

## 目录结构重构建议

### 重构后的理想结构

```
py_module/
├── opencolor/              # 合并后的核心模块
│   ├── src/oc_core/
│   │   ├── core/          # 核心算法（合并 oc_core + oc_core_02/core）
│   │   ├── ui/            # Gradio 界面
│   │   └── app.py         # 应用入口
│   └── pyproject.toml
├── engine/                 # API 服务
│   ├── src/oc_engine/
│   │   ├── handlers/
│   │   │   ├── calibration/
│   │   │   ├── generation/
│   │   │   └── validation/
│   │   └── main.py
│   └── pyproject.toml
├── calibration/            # 校准类型（保留，轻量级）
│   └── src/oc_calib/
├── model_export/           # 3MF 导出（保留）
│   └── src/model_export/
├── pipeline/               # 重命名后的 prototypes
│   └── src/oc_pipeline/
│       ├── calib_board_gen/
│       ├── calib_photo_warp/
│       ├── calib_sample_build/
│       ├── calib_color_rts/       # 已重命名
│       ├── gen_masks/
│       ├── gen_vector/
│       └── gen_3mf/
├── scripts/                # 脚本集（合并 analyze）
│   └── src/oc_scripts/
│       ├── planning/
│       ├── stl/
│       ├── svg/
│       ├── analyze/        # 原 analyze 模块
│       └── utils/
├── sdf/                    # SDF 模块（保留）
│   └── src/oc_sdf/
└── xgb/                    # XGBoost 模块（保留）
    └── src/oc_xgb/
```

---

## 重构优先级总结

| 优先级 | 重构项 | 工作量 | 影响范围 | 状态 |
|--------|--------|--------|----------|------|
| 🟢 完成 | 原型模块重命名 | 中 | 33 个文件 | ✅ 已完成 |
| 🟢 完成 | calib_color_model_fit → calib_color_rts | 小 | 30 个文件 | ✅ 已完成 |
| 🔴 高 | oc_core 模块合并 | 大 | 29 个文件 | ⏳ 待处理 |
| 🟡 中 | scripts 模块重组 | 中 | 内部结构 | ⏳ 待处理 |
| 🟡 中 | analyze → scripts | 小 | 模块合并 | ⏳ 待处理 |
| 🟡 中 | 根目录脚本清理 | 小 | 文件删除 | ⏳ 待处理 |
| 🟢 低 | 统一命名风格 | 小 | 配置更新 | ⏳ 待处理 |
| 🟢 低 | handlers 分组 | 小 | 目录结构 | ⏳ 待处理 |
| 🟢 低 | 函数变量命名 | 大 | 代码质量 | ⏳ 待处理 |

---

## 实施建议

1. **分阶段实施**: 先完成高优先级重构，再进行中低优先级
2. **创建分支**: 每个重构项在独立分支进行
3. **测试覆盖**: 重构后运行完整测试套件
4. **文档更新**: 同步更新所有文档（FILE_MAP, PROJECT_MAP 等）
5. **向后兼容**: 考虑提供 shim/alias 保持临时兼容

---

## 文档同步状态

| 文档 | 最后更新 | 状态 |
|------|----------|------|
| REFACTOR_MAP.md | 2026-02-10 | ✅ 当前文档 |
| DEPC_MAP.md | 2026-02-10 | ✅ 已同步 |
| FILE_MAP.md | 2026-02-10 | ✅ 已同步 |
| PROJECT_MAP.md | 2026-02-10 | ✅ 已同步 |
| py_module/PROJECT_MAP.md | 2026-02-10 | ✅ 已同步 |
| README.md | 2026-02-10 | ✅ 已同步 |
