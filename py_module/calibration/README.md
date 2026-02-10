# OpenColor Calibration Module

此模块负责 OpenColor 的色盘（Calibration Board）定义、生成以及从实拍照片中提取色彩映射数据（LUT）。

## 核心功能

- **色盘定义 (Board Specification)**: 使用 `BoardSpec` 定义物理尺寸、网格行列以及单元格映射。
- **观测数据管理 (Observation)**: 记录单次拍摄的照片路径、检测到的角点以及对应的元数据。
- **数据集汇总 (Dataset)**: 汇总多次观测结果，支持中位数过滤等算法以提高校准精度。
- **图像处理**: 提供透视变换、畸变校正以及网格覆盖预览功能。

## 目录结构

- `src/calib/board_spec.py`: 色盘定义数据类。
- `src/calib/observation.py`: 观测数据结构。
- `src/calib/dataset.py`: 数据集汇总与序列化。
- `src/calib/aggregate.py`: 观测数据汇总逻辑。

## 使用方法

可以通过 `opencolor-calibration` 包名导入相关功能：

```python
from oc_calib.board_spec import BoardSpec
# ...
```
