command: pixi run python -m oc_proto.gen_masks.main "D:\pama1234\pfp\p-2026-01\OpenColor-05\data\image\龙娘.png"

## 生成结果摘要

从输出日志可以看到当前代码的一些表现：

### 求解阶段
- 待求解像素数：640,000（800x800）
- 唯一颜色数：214,643
- C++求解器用时：约1.6秒

### 后处理阶段（逐层独立进行）
每层都进行了引导滤波平滑和小块剔除：

| 层 | 引导滤波移动像素 | 边线长度(前→后) | 小块剔除移动像素 |
|---|-----------------|----------------|----------------|
| L00 | 22,212 | 115,134 → 82,997 | 1,485 |
| L01 | 70,970 | 208,251 → 92,519 | 5,037 |
| L02 | 148,587 | 401,523 → 150,408 | 14,826 |
| L03 | 167,948 | 443,555 → 151,648 | 17,313 |
| L04 | 198,312 | 514,035 → 153,075 | 18,185 |

### 色差统计（与求解输入对比）

| 层 | 平均ΔE76 | P95ΔE76 |
|---|---------|---------|
| L00 | 50.46 | 100.36 |
| L01 | 80.68 | 115.04 |
| L02 | 70.41 | 110.15 |
| L03 | 70.80 | 110.15 |
| L04 | 70.10 | 109.48 |

### 观察到的问题

1. **色差较大**：单层色差平均在50-80之间，这可能是因为单层的颜色与输入图（叠色后的目标）本身就有差异

2. **每层覆盖率100%**：所有层都覆盖了整个图像区域，这意味着每个像素在所有5层都有颜色

3. **边线长度显著减少**：后处理使边线长度减少了约60-70%，但这是逐层独立进行的

4. **没有叠层空缺/重叠**：`覆盖=640000, 空缺=0, 重叠=0`，说明每层都完全覆盖，没有像素缺失或多层重叠问题

这些结果可以作为后续改进的基准数据。

# gen_masks 管线优化问题分析文档

**文档版本**: 1.0  
**创建日期**: 2026-02-11  
**相关模块**: `py_module/prototypes/src/oc_proto/gen_masks`

---

## 1. 受影响/相关的文件

### 核心文件

| 文件路径 | 功能描述 | 涉及的问题 |
|---------|---------|-----------|
| `py_module/prototypes/src/oc_proto/gen_masks/main.py` | 主流程入口，协调整个管线 | 流程顺序、参数传递、联合优化调用范围 |
| `py_module/prototypes/src/oc_proto/gen_masks/main_solve.py` | 求解和后处理模块 | 后处理逐层独立进行，可能破坏叠层关系 |
| `py_module/prototypes/src/oc_proto/gen_masks/joint_refinement.py` | 联合优化核心实现 | 仅优化首层(layer_start=0, layer_end=1)，缺少全层联合优化 |
| `py_module/prototypes/src/oc_proto/gen_masks/joint_refinement_boundary.py` | 边界计算和连通域分析 | 边长计算、岛屿统计 |
| `py_module/prototypes/src/oc_proto/gen_masks/joint_refinement_cleanup.py` | 小连通域剔除和去噪 | 逐层处理，未考虑叠层影响 |
| `py_module/prototypes/src/oc_proto/gen_masks/joint_refinement_filter.py` | 引导滤波实现 | 单层滤波，未考虑竖向叠色结构 |
| `py_module/prototypes/src/oc_proto/gen_masks/optimizer.py` | 首层颜色优化 | 仅优化首层贴近原图 |
| `py_module/prototypes/src/oc_proto/gen_masks/solver.py` | 爬山求解器 | 各像素独立求解，无相邻关系考虑 |
| `py_module/prototypes/src/oc_proto/gen_masks/filters.py` | 图像滤波工具 | 引导滤波、高斯模糊等基础操作 |
| `py_module/prototypes/src/oc_proto/gen_masks/island_suppress.py` | 岛屿抑制 | 逐层独立进行 |

### 配置文件/接口

| 文件路径 | 说明 |
|---------|------|
| `py_module/prototypes/src/oc_proto/gen_masks/__init__.py` | 模块导出接口 |

---

## 2. 管线目标（约束体系）

### 2.1 已明确实现的目标

#### 目标1: 色准最大化
- **描述**: 最终打印颜色与目标图像颜色的色差(ΔE76)尽可能小
- **实现位置**: `joint_refinement.py:545-549`, `optimizer.py:71-77`
- **约束类型**: 
  - 硬约束: `de_new <= (de_base_all[cand_idx] + slack_de76)`
  - 软约束: `color_weight * (de_new - de_cur)`

#### 目标2: 独立小色块最小化
- **描述**: 减少面积小的独立色块数量
- **实现位置**: `joint_refinement.py:653`, `joint_refinement_boundary.py:72-79`
- **约束类型**: 软约束 `island_weight * island_delta`
- **辅助手段**: 小连通域剔除 `_remove_small_components_replace_with_neighbors`

#### 目标3: 总边线长度最小化
- **描述**: 减少单层内不同颜色区域的边界长度
- **实现位置**: `joint_refinement.py:512-532`, `joint_refinement_boundary.py:15-24`
- **约束类型**: 软约束 `lambda_smooth * (new_cost - cur_cost)`
- **邻域**: 4连通 (上下左右)

#### 目标4: 混色一致性（局部色准）
- **描述**: 眯眼观察时局部区域的混色效果与目标一致
- **实现位置**: `joint_refinement.py:551-570`
- **约束类型**: 软约束 `mix_weight * (de_mix_new - de_mix_cur)`
- **实现方式**: 高斯模糊模拟眯眼效果

### 2.2 部分实现/存在问题 的目标

#### 目标5: 叠色结构相似性（横向）
- **描述**: 颜色相似的相邻像素，应使用相似的叠色配方
- **当前状态**: ⚠️ **间接实现，不够显式**
- **问题**: 
  - 通过混色一致性间接鼓励，但没有直接约束"叠色结构相似性"
  - 缺少显式的"叠色结构差异"度量

#### 目标6: 层间叠色连续性（竖向）
- **描述**: 相邻层之间的叠色结构应该有连续性
- **当前状态**: ❌ **未实现**
- **问题**: 每层独立优化，层与层之间缺乏约束

### 2.3 未实现/需要补充的目标

#### 目标7: 叠层保护（核心问题）
- **描述**: 优化和后处理操作不应破坏已建立的叠层关系
- **当前状态**: ❌ **存在问题**
- **问题**: 后处理（卷积、引导滤波、岛屿抑制）逐层独立进行，可能严重破坏叠层关系

#### 目标8: 叠色复杂度优化
- **描述**: 在满足色准的前提下，优先使用简单的叠色结构
- **当前状态**: ❌ **未实现**
- **意义**: 简单叠色更容易控制，打印更稳定

#### 目标9: 全局一致性约束
- **描述**: 避免局部色差过大，保证整体效果均匀
- **当前状态**: ⚠️ **部分实现**
- **问题**: 使用P95等统计量，但没有显式约束局部一致性

---

## 3. 目前实现的可见问题

### 3.1 核心架构问题

#### 问题1: 缺少全层联合优化
**严重程度**: 🔴 高

**描述**: 
当前的 `joint_l0` 联合优化默认只优化首层(`layer_start=0, layer_end=1`)，其他层保持初始求解结果不变。

**代码位置**: 
```python
# main.py:519-520
if bool(joint_l0_enabled) and int(n_layers) > 0:
    # ...
    layer_start=0,
    layer_end=1,  # 硬编码只优化首层
```

**影响**:
- 只有首层受益于联合优化的空间平滑
- 其他层的边线长度和小色块问题未得到解决
- 层间叠色结构不一致

**建议**:
- 扩展联合优化到所有层
- 或者采用分层级联优化策略

---

#### 问题2: 后处理逐层独立进行，破坏叠层关系
**严重程度**: 🔴 高

**描述**:
后处理流程（卷积平滑、引导滤波、岛屿抑制）对每层独立进行，没有考虑叠层关系。

**代码位置**:
```python
# main_solve.py:169-209
# 卷积平滑
labels_by_layer = smooth_labels_by_convolution(labels_by_layer, ...)

# 引导滤波
labels_by_layer = smooth_labels_by_guided_filter(labels_by_layer, ...)

# 岛屿抑制
labels_by_layer = suppress_small_islands_v2(labels_by_layer, ...)
```

**影响**:
- 每层独立平滑后，叠层结构可能完全混乱
- 可能出现"颜色对了但叠色方式完全不同"的情况
- 打印时层间对齐困难

**示例**:
```
优化前:
  像素A: [白, 红, 蓝] -> 紫色
  像素B: [白, 红, 蓝] -> 紫色

逐层平滑后:
  像素A: [白, 红, 蓝] -> 紫色
  像素B: [白, 粉, 青] -> 紫色 (颜色对了，但叠色方式完全不同)
```

**建议**:
- 后处理应基于全层预测结果进行
- 引入"叠色结构相似性"约束

---

#### 问题3: 初始求解各像素完全独立
**严重程度**: 🟡 中

**描述**:
`solver.solve()` 对每个唯一颜色独立进行爬山优化，没有考虑相邻像素关系。

**代码位置**:
```python
# solver.py:110-168
for i in tqdm(range(n_targets), desc="寻找初始候选", unit="color"):
    dists = np.linalg.norm(candidate_labs - target_labs[i], axis=1)
    best_idx = np.argmin(dists)
    best_indices[i] = random_indices[best_idx]
```

**影响**:
- 相邻像素可能有相似的最终颜色，但配方完全不同
- 为后续的边线长度优化带来更大压力
- 可能产生本可避免的小色块

**建议**:
- 初始求解时引入空间一致性先验
- 或者采用多尺度求解策略

---

### 3.2 约束实现问题

#### 问题4: 叠色结构相似性约束缺失
**严重程度**: 🟡 中

**描述**:
当前代码没有显式约束"相邻像素的叠色结构相似性"。

**当前代价函数**:
```python
# joint_refinement.py:653-658
delta = (
    mix_weight * (de_mix_new - de_mix_cur)      # 混色一致性
    + cw * (de_new - de_cur)                     # 色准
    + lam * (new_cost - cur_cost)                # 空间平滑（单层）
    + island_weight * island_delta               # 小色块惩罚
)
```

**缺失**:
- 没有 `stack_similarity_cost` 项
- 没有显式度量"叠色结构差异"的方法

**建议**:
增加叠色结构相似性约束:
```python
# 概念性代码
stack_similarity_cost = compute_stack_similarity_cost(
    recipe_new, recipe_neighbors, n_layers
)
delta += lam_stack * stack_similarity_cost
```

---

#### 问题5: 层间连续性约束缺失
**严重程度**: 🟡 中

**描述**:
当前优化是逐层进行的，层与层之间缺乏连续性约束。

**影响**:
- 相邻层可能在不同位置使用完全不同的颜色
- 叠色结构缺乏"竖向"平滑性

**建议**:
引入层间连续性约束:
```python
# 概念性代码
for z in range(n_layers - 1):
    layer_continuity_cost = compute_layer_continuity(
        recipes_layer_z, recipes_layer_z_plus_1
    )
    total_cost += lam_continuity * layer_continuity_cost
```

---

### 3.3 参数/策略问题

#### 问题6: 硬编码参数过多
**严重程度**: 🟢 低

**描述**:
一些关键参数被硬编码，不够灵活。

**示例**:
```python
# main.py:519-520
layer_start=0,
layer_end=1,  # 硬编码

# joint_refinement.py:1259
if max_cand > 0 and cand_idx.size > max_cand:
    rng = np.random.default_rng(12345 + int(z) * 100 + int(it))  # 硬编码随机种子
```

---

#### 问题7: 优化顺序可能不是最优
**严重程度**: 🟡 中

**描述**:
当前流程: 各自独立求解 → 首层联合优化 → 后处理

**可能的更优顺序**:
```
各自独立求解
    ↓
全层联合优化（新增）
    ↓
叠色结构相似性优化（新增）
    ↓
联合后处理（改进）
```

---

## 4. 改进建议汇总

### 短期改进（低 hanging fruit）

1. **扩展联合优化范围**
   - 修改 `main.py` 中的 `layer_end` 参数，支持优化所有层
   - 或者采用分层级联优化

2. **改进后处理流程**
   - 基于全层预测结果进行后处理
   - 引入叠色结构相似性约束

3. **增加叠色结构相似性度量**
   - 实现 `compute_stack_similarity()` 函数
   - 在代价函数中加入相应约束

### 中期改进

4. **实现全层联合优化**
   - 修改 `joint_refinement.py` 支持真正的多层联合优化
   - 同时考虑空间平滑和层间连续性

5. **引入多尺度优化策略**
   - 粗尺度确定大致叠色结构
   - 细尺度优化细节

### 长期改进

6. **重新设计优化流程**
   - 从"各自独立 → 单层优化 → 后处理"改为"全局联合优化"
   - 统一考虑所有约束目标

7. **引入机器学习辅助**
   - 训练模型预测"好的叠色结构"
   - 作为优化的先验知识

---

## 5. 关键代码片段分析

### 5.1 联合优化调用点

```python
# main.py:530-565
if joint_l0_use_icm:
    recipes_per_pixel = _joint_refine_layers_icm(
        recipes_per_pixel,
        solver=solver,
        cs=cs,
        # ...
        layer_start=0,
        layer_end=1,  # 只优化首层！
        # ...
    )
```

### 5.2 后处理流程

```python
# main_solve.py:168-209
if postprocess_mode != "none":
    labels_by_layer = volumes_to_labels(volumes_raw, cs, full_mask, n_layers)
    
    # 卷积平滑 - 逐层
    if postprocess_mode == "conv":
        labels_by_layer = smooth_labels_by_convolution(...)
    
    # 引导滤波 - 逐层
    if postprocess_mode in {"guided", "joint"}:
        labels_by_layer = smooth_labels_by_guided_filter(...)
    
    # 岛屿抑制 - 逐层
    if postprocess_mode in {"island", "joint"}:
        labels_by_layer = suppress_small_islands_v2(...)
    
    volumes = labels_to_volumes(labels_by_layer, cs, n_layers)
```

### 5.3 代价函数

```python
# joint_refinement.py:653-658
delta = (
    mix_weight * (de_mix_new - de_mix_cur)
    + cw * (de_new - de_cur)
    + lam * (new_cost - cur_cost)
    + island_weight * island_delta
)
# 缺少: stack_similarity_cost, layer_continuity_cost
```

---

## 6. 附录: 术语表

| 术语 | 说明 |
|-----|------|
| 叠色结构 | 多层打印时，每层使用的颜色组合 |
| 边线长度 | 单层内不同颜色区域的边界总长度 |
| 小色块/岛屿 | 面积小的独立颜色区域 |
| ΔE76 | CIE76色差公式计算的颜色差异 |
| 混色评估 | 使用高斯模糊模拟眯眼观察的效果 |
| 竖向/横向 | 竖向指层与层之间，横向指空间上相邻像素 |
| ICM | Iterated Conditional Modes，迭代条件模式 |

---

**文档结束**
