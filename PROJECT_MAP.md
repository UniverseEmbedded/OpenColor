# OpenColor 项目地图

本项目是一个用于 FDM 3D 打印的多色叠层规划与生成工具集。它通过将不同颜色的材料（通常是 R, G, B, W 或类似组合）以微小层厚进行堆叠，从而在打印件表面或内部实现丰富的色彩表现。

## 核心逻辑与规划器 (Core Logic & Planners)

- **[planner.py](planner.py)**
  项目的核心库。包含色彩空间转换（sRGB 与线性空间）、材料预测模型以及叠层算法。它是大多数转换脚本的底层支撑。
- **[layerplan.py](layerplan.py)**
  RGBA 到叠层规划的工具。使用“灰盒”模型预测叠层后的颜色，并通过暴力破解算法寻找最优的材料组合顺序。
- **[legacy_layerplan.py](legacy_layerplan.py)**
  `layerplan.py` 的旧版本，保留用于兼容性或参考。

## 3D 模型生成 (3D Generation)

- **[color_square_stack.py](color_square_stack.py)**
  将单一的 RGBA 颜色转换为一个多层堆叠的正方形 3D 模型，并导出为按材料分类的 STL 文件。
- **[layercap_dome.py](layercap_dome.py)**
  生成一个半球形的壳体模型。该脚本将球面细分为多个区域，并在每个区域内进行 4 种材料的径向堆叠，同时应用 Z 轴压缩算法以减少打印层数。
- **[mixplane.py](mixplane.py)**
  生成一个包含多种材料组合或序列的测试板（Mix Card），用于颜色校准或实验观察。

## 图像与矢量图转换 (Image & SVG Conversion)

- **[bmp_map4stl_nooverlap_plus.py](bmp_map4stl_nooverlap_plus.py)**
  高性能的位图转 STL 工具。采用矢量区域提取技术，将图片转换为不重叠的 4 色（R, G, B, W）固体模型。
- **[bmp_map4stl_nooverlap.py](bmp_map4stl_nooverlap.py)**
  位图转 STL 的基础版本，重点在于处理带孔洞的区域多边形并确保 4 个输出文件之间没有体积重叠。
- **[svg4stl_vector_plus.py](svg4stl_vector_plus.py)**
  增强版 SVG 转 STL 工具。支持 SVG 变换属性（translate/scale 等）和严格的调色板匹配模式。
- **[svg4stl_vector.py](svg4stl_vector.py)**
  基础的 SVG 矢量转换工具，将 SVG 路径直接转换为挤出厚度的 STL 模型，不涉及光栅化。
- **[svg_stack_rgbw_testsvg.py](svg_stack_rgbw_testsvg.py)**
  专门用于“底面颜色”实验的工具，将 SVG 转换为按 RGBW 叠层的平面模型，使图像显示在与打印床接触的面上。

## 物理模拟与验证 (Physics & Validation)

- **[forward_mc.py](forward_mc.py)**
  基于物理的蒙特卡洛光线追踪模型。模拟光在叠层材料中的吸收、散射和菲涅尔反射，用于精确预测叠层的最终外观。
- **[validate_stack.py](validate_stack.py)**
  验证工具，用于对比 `planner.py` 的快速预测结果与 `forward_mc.py` 的高精度物理模拟结果，确保规划算法的准确性。
