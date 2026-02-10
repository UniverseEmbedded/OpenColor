# model_export

OpenColor 项目的 3MF 模型导出模块。

## 功能

- 标准 3MF 导出 (`standard_3mf.py`)
- 网格数据结构定义 (`types.py`)

## 安装

作为开发依赖安装：
```bash
pixi add --pypi model_export={path="py_module/model_export", editable=true}
```


## 标准 3MF 导出示例

```python
from model_export import export_standard_3mf, MeshData

# 准备网格数据
meshes = [MeshData(vertices=..., faces=...)]
slot_names = ["White", "Black", "Red"]

# 导出标准 3MF
export_standard_3mf(
    out_path="output.3mf",
    meshes=meshes,
    slot_names=slot_names,
)
```
