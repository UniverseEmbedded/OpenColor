<p align="center"> 
 <img alt="OpenColor logo" src="test.svg" width="128" height="128"> 
 <br> 
 <em>我已精通此间奥秘，亦已吸取潜藏教诲。 ————《司辰之书》</em> 
 <br> 
 <p align="center"> 
 | <a href="README.md">English</a> | <a href="README.md">简体中文</a> | 
 </p>
</p>

# OpenColor

OpenColor 是一个用于 FDM 3D 打印的多色叠层规划与生成工具集。它通过将不同颜色的材料（如 R, G, B, W）以微小层厚进行物理堆叠，在打印件表面或内部实现精细的色彩表现。该项目的逻辑类似于 HueForge，但提供了更灵活的开源实现和物理基础的模拟工具。

## 🚀 主要功能

- **多材料叠层规划**：将目标 RGBA 颜色自动转换为最优的材料堆叠序列。
- **图像/矢量转 3D**：支持将位图（BMP/PNG）和矢量图（SVG）直接转换为按材料分类的 STL 固体模型。
- **物理模拟预测**：内置基于蒙特卡洛（Monte Carlo）光线追踪的物理模型，用于高精度预测叠层后的视觉效果。
- **专用模型生成**：支持生成半球形壳体（Dome）、色彩校准板（Mix Card）以及叠层测试块。
- **灵活的材料配置**：通过 `materials.json` 定义不同耗材的吸收、散射及强度参数。

## 🛠️ 安装

本项目推荐使用 [pixi](https://pixi.sh/) 进行环境管理。

```bash
# 克隆仓库
git clone https://github.com/your-repo/OpenColor.git
cd OpenColor

# 使用 pixi 安装依赖并运行
pixi run gen
```

### 手动安装依赖

如果你不使用 pixi，可以手动安装以下主要依赖：

```bash
pip install numpy trimesh pillow shapely scikit-image cairosvg mapbox_earcut svgpathtools
```

## 📖 核心概念

### 叠层逻辑 (Stacking Logic)
OpenColor 的核心在于利用不同颜色耗材的半透明性。通过控制每层（通常为 0.08mm - 0.2mm）的材料种类，可以组合出成千上万种色彩。

### 规划器 (Planner)
[planner.py](file:///d:/pama1234/pfp/p-2026-01/OpenColor/planner.py) 提供了两种预测模式：
1. **快速模式 (Fast)**：基于加权平均的经验模型，适用于大规模像素转换。
2. **物理模式 (Phys)**：调用 [forward_mc.py](file:///d:/pama1234/pfp/p-2026-01/OpenColor/forward_mc.py)，考虑光的吸收和散射。

## ⌨️ 常用命令示例

### 1. 将颜色转换为叠层正方形
```bash
python color_square_stack.py --hex "#DDF4C4" --layers 5 --layer-height 0.08
```

### 2. 将 SVG 转换为多色 STL
```bash
python svg_stack_rgbw_testsvg.py --svg test.svg --width-mm 80 --view bottom
```

### 3. 生成半球形测试模型
```bash
python layercap_dome.py --radius 20 --z-slices 10 --slice-height 0.4
```

### 4. 运行物理模拟验证
```bash
python forward_mc.py --seq G-R-W-W-W --heights 0.12,0.08,0.08,0.08,0.08 --view bottom
```

## 📂 项目结构

有关各脚本功能的详细说明，请参阅 [PROJECT_MAP.md](file:///d:/pama1234/pfp/p-2026-01/OpenColor/PROJECT_MAP.md)。

- `planner.py`: 核心预测与规划算法。
- `forward_mc.py`: 蒙特卡洛物理模拟引擎。
- `materials.json`: 材料属性数据库。
- `bmp_map4stl_*.py`: 位图转换工具。
- `svg4stl_*.py`: SVG 转换工具。

## ⚖️ 许可

[请在此处添加您的许可证信息，例如 MIT]
