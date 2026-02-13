# 代码重复内容扫描报告

**生成时间**: 2026-02-09 20:36:29
**扫描目录数**: 3
**最小匹配行数**: 5
**相似度阈值**: 85%
**发现重复组数**: 223

---

## 统计摘要

| 类型 | 组数 | 重复行数 |
|-----|------|---------|
| 完全重复 | 57 | 1298 |
| 相似重复 | 166 | 6378 |
| **总计** | **223** | **7676** |

## 涉及文件统计

| 文件路径 | 重复块数 |
|---------|---------|
| `cpp_module\tools\comment_coverage_ts\src\main.cpp` | 66 |
| `cpp_module\tools\comment_coverage_ts\src\comment_utils.cpp` | 49 |
| `web\src\locales\zh-CN.json` | 40 |
| `web\src\locales\en-US.json` | 32 |
| `py_module\scripts\src\oc_scripts\svg\svg4stl_vector_plus.py` | 30 |
| `web\src\components\AppMain.vue` | 27 |
| `py_module\opencolor\src\oc_core_02\core\svg_processing.py` | 17 |
| `web\src\App.vue` | 16 |
| `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_logit_pairs.py` | 14 |
| `py_module\scripts\src\oc_scripts\svg\svg_stack_rgbw_testsvg.py` | 14 |
| `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_fullpairs.py` | 11 |
| `py_module\prototypes\src\oc_proto\gen_masks\island_suppress.py` | 11 |
| `py_module\scripts\src\oc_scripts\svg\svg4stl_vector.py` | 11 |
| `py_module\prototypes\src\oc_proto\gen_masks\joint_refinement_filter.py` | 10 |
| `py_module\prototypes\src\oc_proto\gen_3mf\main.py` | 9 |
| `py_module\prototypes\src\oc_proto\gen_vector\main.py` | 9 |
| `py_module\prototypes\src\oc_proto\gen_vector\resampler.py` | 8 |
| `web\src\composables\useAppState.js` | 8 |
| `py_module\scripts\src\oc_scripts\calibration\color_board\recipes.py` | 7 |
| `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_runner.py` | 7 |

## 重复详情

### 1. 相似重复 (相似度: 100%)

**涉及位置**:

- `web\src\locales\en-US.json` (第 331-340 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 501-510 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 471-480 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 441-450 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 461-470 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 191-200 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 591-600 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 211-220 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 481-490 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 391-400 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 141-150 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 121-130 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 71-80 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 381-390 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 241-250 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 101-110 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 411-420 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 91-100 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 181-190 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 571-580 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 401-410 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 221-230 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 521-530 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 81-90 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 421-430 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 251-260 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 131-140 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 491-500 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 451-460 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 291-300 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 161-170 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 561-570 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 511-520 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 261-270 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 201-210 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 31-40 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 341-350 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 171-180 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 281-290 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 331-340 行, 共 10 行)
- `web\src\locales\zh-CN.json` (第 151-160 行, 共 10 行)

**代码预览**:

```python
    "on": "On",
    "off": "Off",
    "brimBoth": "3mm Brim + Mixed",
    "brimOnly": "Brim Only",
    "brimNone": "No Brim",
    "quickMode": "Single Filament Card",
    "standardMode": "Color Palette",
    "themeAuto": "Follow System",
    "themeDark": "Dark Mode",
    "themeLight": "Light Mode",
```

---

### 2. 相似重复 (相似度: 100%)

**涉及位置**:

- `web\package.json` (第 11-20 行, 共 10 行)
- `web\src\locales\en-US.json` (第 441-450 行, 共 10 行)
- `web\src\locales\en-US.json` (第 171-180 行, 共 10 行)
- `web\src\locales\en-US.json` (第 451-460 行, 共 10 行)
- `web\src\locales\en-US.json` (第 81-90 行, 共 10 行)
- `web\src\locales\en-US.json` (第 181-190 行, 共 10 行)
- `web\src\locales\en-US.json` (第 551-560 行, 共 10 行)
- `web\src\locales\en-US.json` (第 481-490 行, 共 10 行)
- `web\src\locales\en-US.json` (第 501-510 行, 共 10 行)
- `web\src\locales\en-US.json` (第 561-570 行, 共 10 行)
- `web\src\locales\en-US.json` (第 71-80 行, 共 10 行)
- `web\src\locales\en-US.json` (第 471-480 行, 共 10 行)
- `web\src\locales\en-US.json` (第 491-500 行, 共 10 行)
- `web\src\locales\en-US.json` (第 191-200 行, 共 10 行)
- `web\src\locales\en-US.json` (第 291-300 行, 共 10 行)
- `web\src\locales\en-US.json` (第 431-440 行, 共 10 行)
- `web\src\locales\en-US.json` (第 141-150 行, 共 10 行)
- `web\src\locales\en-US.json` (第 511-520 行, 共 10 行)
- `web\src\locales\en-US.json` (第 241-250 行, 共 10 行)
- `web\src\locales\en-US.json` (第 121-130 行, 共 10 行)
- `web\src\locales\en-US.json` (第 461-470 行, 共 10 行)
- `web\src\locales\en-US.json` (第 31-40 行, 共 10 行)
- `web\src\locales\en-US.json` (第 201-210 行, 共 10 行)
- `web\src\locales\en-US.json` (第 281-290 行, 共 10 行)
- `web\src\locales\en-US.json` (第 401-410 行, 共 10 行)
- `web\src\locales\en-US.json` (第 381-390 行, 共 10 行)
- `web\src\locales\en-US.json` (第 151-160 行, 共 10 行)
- `web\src\locales\en-US.json` (第 251-260 行, 共 10 行)
- `web\src\locales\en-US.json` (第 131-140 行, 共 10 行)
- `web\src\locales\en-US.json` (第 211-220 行, 共 10 行)
- `web\src\locales\en-US.json` (第 161-170 行, 共 10 行)

**代码预览**:

```python
    "test": "vitest run",
    "test:unit": "vitest run",
    "test:unit:watch": "vitest",
    "test:e2e": "echo '⚠️ 已弃用：浏览器模式无法测试 Tauri API，请使用 pnpm test:e2e:tauri'",
    "test:e2e:ui": "echo '⚠️ 已弃用：浏览器模式无法测试 Tauri API，请使用 pnpm test:e2e:tauri'",
    "test:e2e:debug": "echo '⚠️ 已弃用：浏览器模式无法测试 Tauri API，请使用 pnpm test:e2e:tauri'",
    "test:e2e:tauri": "playwright test -c playwright.config.tauri.ts",
    "test:e2e:tauri:build": "pnpm tauri build && playwright test -c playwright.config.tauri.ts",
    "test:rust": "cd src-tauri && cargo test",
    "test:rust:verbose": "cd src-tauri && cargo test -- --nocapture",
```

---

### 3. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\analyze\src\oc_analyze\package_project.py` (第 71-80 行, 共 10 行)
- `web\src\components\GenerateOutputCard.vue` (第 311-320 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 411-420 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\__init__.py` (第 91-100 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 431-440 行, 共 10 行)
- `py_module\analyze\src\oc_analyze\scan_ruff.py` (第 427-436 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 381-390 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\__init__.py` (第 81-90 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_3mf\__init__.py` (第 31-40 行, 共 10 行)
- `web\src\components\calibrate\StandardCalibrateMode.vue` (第 191-200 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\__init__.py` (第 51-60 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\__init__.py` (第 71-80 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 451-460 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 421-430 行, 共 10 行)
- `web\src\components\GenerateOutputCard.vue` (第 321-330 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 461-470 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 401-410 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 391-400 行, 共 10 行)
- `py_module\analyze\src\oc_analyze\scan_utils.py` (第 31-40 行, 共 10 行)
- `py_module\analyze\src\oc_analyze\scan_duplicate.py` (第 651-660 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 371-380 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\__init__.py` (第 101-110 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 441-450 行, 共 10 行)
- `py_module\analyze\src\oc_analyze\scan_ruff.py` (第 417-426 行, 共 10 行)

**代码预览**:

```python
    ".ruff_cache",
    # 版本控制
    ".git",
    ".gitignore",
    ".gitattributes",
    ".svn",
    ".hg",
    # IDE
    ".idea",
    ".vscode",
```

---

### 4. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\engine\src\oc_engine\handlers\svg.py` (第 21-30 行, 共 10 行)
- `web\src\App.vue` (第 351-360 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 171-180 行, 共 10 行)
- `web\src\App.vue` (第 301-310 行, 共 10 行)
- `web\src\components\CalibrateView.vue` (第 371-380 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 151-160 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 181-190 行, 共 10 行)
- `web\src\App.vue` (第 391-400 行, 共 10 行)
- `web\src\App.vue` (第 311-320 行, 共 10 行)
- `web\src\App.vue` (第 361-370 行, 共 10 行)
- `web\src\components\CalibrateView.vue` (第 381-390 行, 共 10 行)
- `py_module\engine\src\oc_engine\main.py` (第 21-30 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 191-200 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 131-140 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 201-210 行, 共 10 行)
- `web\src\App.vue` (第 331-340 行, 共 10 行)
- `py_module\scripts\src\oc_scripts\svg\svg_mesh_verify.py` (第 31-40 行, 共 10 行)
- `web\src\composables\useAppState.js` (第 141-150 行, 共 10 行)

**代码预览**:

```python
    has_fill_spec,
    parse_fill_from_attrs,
    classify_rgb_to_rgbw_strict,
    classify_rgb_to_rgbw_nearest,
    approx_closed_rings_from_path,
    build_polygons_from_rings,
    transform_svg_units_to_mm,
    union_clean,
    extrude_polygon_to_mesh,
)
```

---

### 5. 相似重复 (相似度: 100%)

**涉及位置**:

- `cpp_module\tools\comment_coverage_ts\src\file_utils.cpp` (第 354-363 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 102-111 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 192-201 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 172-181 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 72-81 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 82-91 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 212-221 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 162-171 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 112-121 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 222-231 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 152-161 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 122-131 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 132-141 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 142-151 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 92-101 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 182-191 行, 共 10 行)
- `cpp_module\tools\comment_coverage_ts\src\main.cpp` (第 202-211 行, 共 10 行)

**代码预览**:

```python
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
```

---

### 6. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\scripts\src\oc_scripts\svg\svg4stl_vector_plus.py` (第 207-255 行, 共 49 行)
- `py_module\scripts\src\oc_scripts\svg\svg_stack_rgbw_testsvg.py` (第 148-191 行, 共 44 行)

**代码预览**:

```python
def parse_transform_attr(s: str) -> np.ndarray:
    """
    将SVG变换列表的最小子集解析为3x3仿射矩阵。
    支持：matrix(a,b,c,d,e,f), translate(tx,ty), scale(sx,sy), rotate(angle[,cx,cy])
    SVG中的顺序是左到右应用；对于列向量我们相应地进行右乘。
    我们构建矩阵M使得 p' = M * p。
    """
    if not s:
        return np.eye(3, dtype=np.float64)

...
```

---

### 7. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\scripts\src\oc_scripts\calibration\color_board\make.py` (第 114-161 行, 共 48 行)
- `py_module\scripts\src\oc_scripts\calibration\color_board\recipes.py` (第 57-99 行, 共 43 行)

**代码预览**:

```python
def make_layer_sequence(fractions: Dict[str, float], total_layers: int) -> List[str]:
    """
    将连续分数转换为离散每层序列。

    策略：
    - 将分数 -> 目标计数，使用最大余数舍入
    - 交错以避免长连续（简单贪婪间隔）
    """
    # 归一化
    chans = [c for c in ["R", "G", "B", "W"] if fractions.get(c, 0.0) > 0]
...
```

---

### 8. 相似重复 (相似度: 100%)

**涉及位置**:

- `web\src\App.vue` (第 51-60 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 31-40 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 11-20 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 21-30 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 111-120 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 91-100 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 101-110 行, 共 10 行)
- `web\src\components\GenerateView.vue` (第 41-50 行, 共 10 行)
- `web\src\components\GenerateView.vue` (第 31-40 行, 共 10 行)

**代码预览**:

```python
      :lutOutDir="lutOutDir"
      :lutZoom="lutZoom"
      :lutBarrel="lutBarrel"
      :lutOffsetX="lutOffsetX"
      :lutOffsetY="lutOffsetY"
      :lutAutoWb="lutAutoWb"
      :lutVignetteFix="lutVignetteFix"
      :lutWindowPx="lutWindowPx"
      :lutStatus="lutStatus"
      :lutOverlaySrc="lutOverlaySrc"
```

---

### 9. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\opencolor\src\oc_core_02\core\color_systems.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\models\phys_gpr_model.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_vector\resampler.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_3mf\evidence_rebuild.py` (第 1-10 行, 共 10 行)
- `py_module\opencolor\src\oc_core_02\utils\manifest.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\main_solve.py` (第 1-10 行, 共 10 行)
- `py_module\scripts\src\oc_scripts\calibration\color_board\projection.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\diagnostics.py` (第 1-10 行, 共 10 行)
- `py_module\opencolor\src\oc_core_02\utils\paths.py` (第 1-10 行, 共 10 行)

**代码预览**:

```python
"""
颜色系统定义模块

定义校准板使用的多材料颜色系统，包括色盘配置、角标映射等
支持 RYBW、CMYW 等标准颜色系统
"""

from __future__ import annotations

from dataclasses import dataclass
```

---

### 10. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\opencolor\src\oc_core_02\core\svg_processing.py` (第 1-10 行, 共 10 行)
- `py_module\opencolor\src\oc_core_02\utils\io_utils.py` (第 1-10 行, 共 10 行)
- `py_module\scripts\src\oc_scripts\planning\planner_search.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_3mf\main.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\runner.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\island_suppress.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\cli.py` (第 1-10 行, 共 10 行)
- `py_module\scripts\src\oc_scripts\color_contact_3mf.py` (第 1-10 行, 共 10 行)

**代码预览**:

```python
"""
SVG 处理模块

提供 SVG 文件解析、颜色提取、几何变换和网格生成功能
用于将 SVG 图形转换为可打印的 3D 网格模型
"""

from __future__ import annotations

import math
```

---

### 11. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_fullpairs.py` (第 53-76 行, 共 24 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_runner.py` (第 53-79 行, 共 27 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_logit_pairs.py` (第 56-79 行, 共 24 行)

**代码预览**:

```python
def load_palette(path, L=5):
    """从JSON文件加载调色板数据"""
    d = json.load(open(path, 'r'))
    cells = []
    for c in d['cells']:
        if not c.get('enabled', True):
            continue
        if not c.get('has_recipe', True):
            continue
        ln = c.get('layer_names')
...
```

---

### 12. 相似重复 (相似度: 100%)

**涉及位置**:

- `web\src\composables\useAppState.js` (第 161-170 行, 共 10 行)
- `web\src\composables\useCalibrate.js` (第 481-490 行, 共 10 行)
- `web\src\App.vue` (第 321-330 行, 共 10 行)
- `web\src\engine_contract.js` (第 11-20 行, 共 10 行)
- `web\src\App.vue` (第 341-350 行, 共 10 行)
- `web\src\composables\usePreviewState.js` (第 151-160 行, 共 10 行)
- `web\src\composables\useCalibrate.js` (第 491-500 行, 共 10 行)

**代码预览**:

```python
    lutResultFile,
    lutJobId,
    lutObservationPath,
    boardSpecPath,
    boardSpecId,
    boardSpecName,
    boardSpecRows,
    boardSpecCols,
    datasetId,
    datasetOutDir,
```

---

### 13. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\calib_sample_build\main.py` (第 291-324 行, 共 34 行)
- `py_module\prototypes\src\oc_proto\calib_sample_build\main_utils.py` (第 127-161 行, 共 35 行)

**代码预览**:

```python
def parse_roi(roi, cell_w, cell_h):
    """
    roi supports:
      - None: returns central 60% box
      - [rx, ry, rw, rh] normalized in [0,1] within cell
      - [x0, y0, x1, y1] absolute pixels within cell
    Returns pixel box (x0,y0,x1,y1) within cell.
    """
    if roi is None:
        margin = 0.2
...
```

---

### 14. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\engine\src\oc_engine\handlers\health.py` (第 1-10 行, 共 10 行)
- `py_module\engine\src\oc_engine\handlers\svg.py` (第 1-10 行, 共 10 行)
- `py_module\scripts\src\oc_scripts\planning\forward_mc.py` (第 7-16 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_board_gen\main.py` (第 1-10 行, 共 10 行)
- `py_module\scripts\src\oc_scripts\planning\planner_models.py` (第 1-10 行, 共 10 行)
- `py_module\opencolor\src\oc_core_02\core\mesh_export.py` (第 1-10 行, 共 10 行)

**代码预览**:

```python
"""健康检查处理器 - 提供引擎状态查询功能

本模块提供引擎健康检查相关的API端点，用于：
- 返回引擎版本信息
- 声明引擎支持的功能列表
- 提供基本的存活检测接口
"""

from __future__ import annotations

```

---

### 15. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\gen_masks\dot_pattern_test.py` (第 102-123 行, 共 22 行)
- `py_module\prototypes\src\oc_proto\gen_masks\gray_test.py` (第 68-103 行, 共 36 行)

**代码预览**:

```python
def _find_model_dir(calib_root: Path) -> Path:
    """查找模型目录"""
    candidates: list[tuple[int, float, Path]] = []
    for meta_path in calib_root.rglob("color_model.json"):
        model_dir = meta_path.parent
        npz_path = model_dir / "phys_gpr_model.npz"
        if not npz_path.exists():
            continue
        try:
            mtime = meta_path.stat().st_mtime
...
```

---

### 16. 完全重复 (相似度: 100%)

**涉及位置**:

- `py_module\opencolor\src\oc_core_02\utils\vtracer_bridge.py` (第 52-78 行, 共 27 行)
- `py_module\prototypes\src\oc_proto\gen_vector\resampler.py` (第 95-120 行, 共 26 行)

**代码预览**:

```python
def _loops_to_evenodd_polygon(loops):
    rings = []
    for pts in loops or []:
        if pts is None:
            continue
        arr = np.asarray(pts, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[0] < 3 or arr.shape[1] != 2:
            continue
        p = Polygon(arr)
        if not p.is_valid:
...
```

---

### 17. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\engine\src\oc_engine\handlers\board.py` (第 26-46 行, 共 21 行)
- `py_module\engine\src\oc_engine\handlers\svg.py` (第 36-46 行, 共 11 行)
- `py_module\engine\src\oc_engine\handlers\bitmap.py` (第 16-36 行, 共 21 行)

**代码预览**:

```python
def _unique_path(p: Path) -> Path:
    """生成唯一的文件路径，避免文件名冲突
    
    如果目标路径已存在，则在文件名后添加数字后缀（_1, _2, ...）
    如果数字后缀达到1000，则使用时间戳作为后缀
    
    参数:
        p: 目标文件路径
        
    返回:
...
```

---

### 18. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\gen_vector\svg_utils.py` (第 31-56 行, 共 26 行)
- `py_module\sdf\src\oc_sdf\geometry_utils.py` (第 13-38 行, 共 26 行)

**代码预览**:

```python
def _iter_polygons(geom):
    """迭代几何体中的所有多边形

    支持Polygon、MultiPolygon和GeometryCollection类型

    Args:
        geom: Shapely几何对象

    Returns:
        多边形列表
...
```

---

### 19. 完全重复 (相似度: 100%)

**涉及位置**:

- `cpp_module\src\geometry\clipper_ops.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\geometry\earcut_triangulation.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\geometry\manifold_ops.cpp` (第 11-20 行, 共 10 行)
- `cpp_module\src\geometry\mesh_utils.cpp` (第 11-20 行, 共 10 行)
- `cpp_module\src\geometry\mesh_utils.h` (第 2-11 行, 共 10 行)

**代码预览**:

```python
#pragma once

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <clipper2/clipper.h>
#include <string>
#include <vector>

namespace py = pybind11;

```

---

### 20. 完全重复 (相似度: 100%)

**涉及位置**:

- `cpp_module\src\solver\hill_climbing_solver.cpp` (第 21-30 行, 共 10 行)
- `cpp_module\src\solver\hill_climbing_solver.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\solver\vulkan_buffer.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\solver\vulkan_context.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\solver\vulkan_predictors.cpp` (第 1-10 行, 共 10 行)

**代码预览**:

```python
#include <cstring>
#include <iostream>
#include <chrono>
#include <iomanip>
#include <unordered_map>
#include <thread>
#include <atomic>

namespace opencolor {
namespace solver {
```

---

### 21. 相似重复 (相似度: 100%)

**涉及位置**:

- `cpp_module\src\geometry\clipper_ops.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\geometry\mesh_utils.cpp` (第 11-20 行, 共 10 行)
- `cpp_module\src\geometry\manifold_ops.cpp` (第 11-20 行, 共 10 行)
- `cpp_module\src\geometry\earcut_triangulation.h` (第 1-10 行, 共 10 行)
- `cpp_module\src\geometry\mesh_utils.h` (第 2-11 行, 共 10 行)

**代码预览**:

```python
#pragma once

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <clipper2/clipper.h>
#include <string>
#include <vector>

namespace py = pybind11;

```

---

### 22. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\calib_sample_build\main_image.py` (第 1-10 行, 共 10 行)
- `py_module\xgb\src\oc_xgb\model_io.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_photo_warp\app.py` (第 1-10 行, 共 10 行)
- `py_module\sdf\src\oc_sdf\sdf_export.py` (第 1-10 行, 共 10 行)
- `py_module\xgb\src\oc_xgb\xgb_dataset.py` (第 1-10 行, 共 10 行)

**代码预览**:

```python
"""样本构建模块 - 图像处理和规格解析

本模块提供图像变换、规格文件解析等功能
"""

import json
import subprocess
import sys
from pathlib import Path

```

---

### 23. 完全重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_fullpairs.py` (第 53-76 行, 共 24 行)
- `py_module\prototypes\src\oc_proto\calib_color_rts\od_eval_logit_pairs.py` (第 56-79 行, 共 24 行)

**代码预览**:

```python
def load_palette(path, L=5):
    """从JSON文件加载调色板数据"""
    d = json.load(open(path, 'r'))
    cells = []
    for c in d['cells']:
        if not c.get('enabled', True):
            continue
        if not c.get('has_recipe', True):
            continue
        ln = c.get('layer_names')
...
```

---

### 24. 完全重复 (相似度: 100%)

**涉及位置**:

- `py_module\engine\src\oc_engine\handlers\bitmap.py` (第 16-36 行, 共 21 行)
- `py_module\engine\src\oc_engine\handlers\board.py` (第 26-46 行, 共 21 行)

**代码预览**:

```python
def _unique_path(p: Path) -> Path:
    """生成唯一的文件路径，避免文件名冲突

    如果目标路径已存在，则在文件名后添加数字后缀（_1, _2, ...）
    如果数字后缀达到1000，则使用时间戳作为后缀

    参数:
        p: 目标文件路径

    返回:
...
```

---

### 25. 相似重复 (相似度: 100%)

**涉及位置**:

- `web\src\App.vue` (第 181-190 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 161-170 行, 共 10 行)
- `web\src\components\AppMain.vue` (第 61-70 行, 共 10 行)
- `web\src\components\GenerateView.vue` (第 61-70 行, 共 10 行)

**代码预览**:

```python
      @update:mcrtBackend="mcrtBackend = $event"
      @update:mcrtLayerHeight="mcrtLayerHeight = $event"
      @update:mcrtBackingAlbedo="mcrtBackingAlbedo = $event"
      @update:mcrtColorSystem="mcrtColorSystem = $event"
      @genQuickCalibStl="runQuickCalibCardGenerate"
      @selectGroup="handleSelectMaterialGroup"
      @newGroup="handleNewMaterialGroup"
      @saveGroup="handleSaveMaterialGroup"
      @saveAsGroup="handleSaveAsMaterialGroup"
      @importGroup="handleImportMaterialGroup"
```

---

### 26. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\calib_color_rts\main.py` (第 1-10 行, 共 10 行)
- `cpp_module\scripts\build.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\gen_masks\gray_test.py` (第 1-10 行, 共 10 行)
- `py_module\prototypes\src\oc_proto\calib_sample_build\main.py` (第 1-10 行, 共 10 行)

**代码预览**:

```python
"""
评估管线模块
运行完整的模型评估流程：在多个色盘上评估训练好的模型性能
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
```

---

### 27. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\gen_masks\dot_pattern_test.py` (第 86-101 行, 共 16 行)
- `py_module\prototypes\src\oc_proto\gen_masks\gray_test.py` (第 46-67 行, 共 22 行)

**代码预览**:

```python
def _clear_dir_keep_root(d: Path) -> None:
    """清空目录但保留根目录"""
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        return
    for child in d.iterdir():
        if child.is_dir():
            _rmtree_retry(child)
        else:
            try:
...
```

---

### 28. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\scripts\src\oc_scripts\planning\layerplan.py` (第 119-132 行, 共 14 行)
- `py_module\scripts\src\oc_scripts\planning\planner_search.py` (第 48-69 行, 共 22 行)

**代码预览**:

```python
def _compositions(total: int, parts: int) -> Iterable[List[int]]:
    """将总数分解为'parts'个部分的非负整数组合"""
    # 通过切割位置组合实现星条法
    # 复杂度: C(total+parts-1, parts-1)
    for cuts in itertools.combinations(range(total + parts - 1), parts - 1):
        prev = -1
        comp: List[int] = []
        for c in cuts:
            comp.append(c - prev - 1)
            prev = c
...
```

---

### 29. 完全重复 (相似度: 100%)

**涉及位置**:

- `py_module\scripts\src\oc_scripts\svg\svg4stl_vector_plus.py` (第 169-185 行, 共 17 行)
- `py_module\scripts\src\oc_scripts\svg\svg_stack_rgbw_testsvg.py` (第 201-218 行, 共 18 行)

**代码预览**:

```python
def get_viewbox(svg_attrs: Dict[str, str]) -> Tuple[float, float, float, float]:
    vb = svg_attrs.get("viewBox") or svg_attrs.get("viewbox")
    if vb:
        parts = [p for p in re.split(r"[,\s]+", vb.strip()) if p]
        if len(parts) == 4:
            return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))

    def parse_len(v: str) -> float:
        if not v:
            return 100.0
...
```

---

### 30. 相似重复 (相似度: 100%)

**涉及位置**:

- `py_module\prototypes\src\oc_proto\gen_masks\dot_pattern_test.py` (第 73-85 行, 共 13 行)
- `py_module\prototypes\src\oc_proto\gen_masks\gray_test.py` (第 25-45 行, 共 21 行)

**代码预览**:

```python
def _rmtree_retry(p: Path, *, tries: int = 8, wait_s: float = 0.2) -> None:
    """带重试的目录删除"""
    for i in range(int(tries)):
        try:
            shutil.rmtree(p)
            return
        except PermissionError as e:
            if i >= int(tries) - 1:
                raise
            print(f"警告: 删除目录失败(可能被占用)，将重试 {i + 1}/{tries}: {p}，原因={e}")
...
```

---

## 修复建议

### 完全重复

完全重复的代码应该提取为公共函数或模块：

1. **提取公共函数**：将重复的代码块提取到一个独立的函数中
2. **创建共享模块**：如果多个文件有重复，考虑创建共享工具模块
3. **使用继承或组合**：对于类的重复，考虑使用继承或组合模式

### 相似重复

相似重复的代码可以通过参数化来统一：

1. **参数化差异**：将不同的部分作为参数传入
2. **使用策略模式**：如果逻辑相似但实现不同，考虑策略模式
3. **模板方法模式**：对于结构相似但细节不同的代码
