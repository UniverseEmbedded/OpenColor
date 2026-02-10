# Manifold 布尔运算问题调查报告

## 问题概述

**问题描述**: C++ 模块中的 `manifold_union_nogil` 函数在处理大量网格时失败，无法创建有效的 Manifold 对象。

**错误信息**: `第 X 个输入网格创建 Manifold 后为空 (NumTri=0)`

**发现时间**: 2026-02-10

**严重程度**: 高 - 影响 3D 模型导出流程中的层间并集功能

---

## 问题现象

### 错误日志示例
```
[错误] finalize_slot_mesh 失败: slot=BLACK, 原因=第 4 个输入网格创建 Manifold 后为空 (NumTri=0)
[错误] finalize_slot_mesh 失败: slot=BLACK, 原因=第 13 个输入网格创建 Manifold 后为空 (NumTri=0)
```

### 受影响的数据
- sbare女装: 第 4 个网格创建失败
- 描边龙娘: 第 13 个网格创建失败

---

## 受影响的文件

### C++ 源文件
| 文件路径 | 说明 |
|---------|------|
| `cpp_module/src/geometry/manifold_ops.cpp` | 包含 `manifold_from_mesh` 和 `manifold_union_nogil` 函数 |
| `cpp_module/src/geometry/manifold_ops.h` | 头文件 |

### Python 源文件
| 文件路径 | 说明 |
|---------|------|
| `py_module/sdf/src/oc_sdf/sdf_export.py` | 调用 `manifold_union_nogil` 进行 3D 并集运算 |
| `py_module/prototypes/src/oc_proto/gen_3mf/main.py` | 3MF 导出主模块 |
| `py_module/prototypes/src/oc_proto/gen_3mf/batch_process.py` | 批量处理脚本 |

---

## 问题根因分析

### 1. Manifold 库的要求
Manifold 库对输入网格有严格要求：
- **封闭性**: 网格必须是封闭流形（watertight）
- **流形性**: 每条边最多被两个面共享
- **方向一致性**: 所有面片法向朝外
- **无退化面**: 不存在面积为零的三角形

### 2. 当前流程的问题
```
SVG 多边形 → 挤出 → 层网格 → Manifold 对象 → 布尔并集
                    ↓
            [某些网格不满足要求]
                    ↓
            manifold::Manifold(mesh) 返回空对象
```

### 3. 具体失败点
在 `manifold_from_mesh` 函数中：
```cpp
manifold::Manifold m = manifold_from_mesh(vertices, faces);
if (m.NumTri() == 0) {
    // 创建失败！
}
```

即使输入数据有顶点和面片，Manifold 库仍可能拒绝创建对象。

---

## 如何测试

### 测试方法 1: 运行批量导出脚本
```bash
pixi run python -m oc_proto.gen_3mf.batch_process
```

预期结果：
- 会在第一个目录（sbare女装）的 BLACK 槽位失败
- 错误：`第 4 个输入网格创建 Manifold 后为空`

### 测试方法 2: 单个目录测试
```bash
pixi run python -m oc_proto.gen_3mf.main --input "py_module/prototypes/src/oc_proto/gen_vector/out/sbare女装_c022b2"
```

### 测试方法 3: 检查网格质量
可以在 Python 中添加调试代码检查网格属性：
```python
import trimesh

# 检查网格是否封闭
print(f"Is watertight: {mesh.is_watertight}")

# 检查是否流形
print(f"Is manifold: {mesh.is_manifold}")

# 检查边界边
print(f"Boundary edges: {mesh.edges_unique[mesh.edges_boundary]}")
```

---

## 修复方案

### 方案 1: 修复输入网格（推荐）
在创建 Manifold 对象之前，先修复网格：
```cpp
// 1. 封闭开放边界
// 2. 修复非流形边
// 3. 统一面片方向
```

### 方案 2: 跳过无效网格
修改 `manifold_union_nogil` 函数，跳过无法创建 Manifold 的网格：
```cpp
for (const auto& mesh_data : meshes) {
    manifold::Manifold m = manifold_from_mesh(v, f);
    if (m.NumTri() == 0) {
        logger.warning("跳过无效网格");
        continue;  // 跳过这个网格
    }
    // 处理有效网格
}
```

### 方案 3: 使用替代布尔运算库
- **CGAL**: 更健壮但速度较慢
- **libigl**: 支持非流形网格的布尔运算
- **trimesh 内置布尔运算**: 纯 Python，速度最慢

### 方案 4: 禁用 C++ 并集
在 `sdf_export.py` 中设置 `use_cpp_union=False`，回退到直接拼接模式。

---

## 临时解决方案

当前代码已添加错误检查，失败时会抛出具体错误信息：
- `第 X 个输入网格创建 Manifold 后为空 (NumTri=0)`
- `布尔运算后结果为空: 第 X 次合并后 NumTri=0`
- `最终并集结果为空 (NumTri=0)`

这有助于精确定位问题发生在哪个步骤。

---

## 相关代码修改历史

### 2026-02-10 修改
1. **C++ 代码** (`manifold_ops.cpp`): 添加详细的错误检查和状态验证
2. **Python 代码** (`sdf_export.py`): 移除 try-except 回退机制，失败直接报错

---

## 后续行动建议

1. **短期**: 使用方案 4（禁用 C++ 并集）或方案 2（跳过无效网格）
2. **中期**: 实施方案 1，在挤出后添加网格修复步骤
3. **长期**: 评估是否更换布尔运算库

---

## 参考链接

- Manifold 库文档: https://github.com/elalish/manifold
- Trimesh 文档: https://trimesh.org/
