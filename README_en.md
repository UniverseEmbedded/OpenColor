<p align="center"> 
 <img alt="OpenColor logo" src="test.svg" width="128" height="128"> 
 <br> 
 <em>I have mastered these mysteries, and I have absorbed the lessons they hid.</em> 
 <br> 
 <p align="center"> 
 | <a href="README_en.md">English</a> | <a href="README.md">简体中文</a> | 
 </p>
</p>

> [!WARNING]
> Please note that the project is still in the draft stage. The formal version (main and main-XX branches on GitHub/git) will involve modifying BambuStudio to achieve full-color mixing functionality. The mainB and mainB-XX series branches are primarily used to publicize various color-mixing technologies, such as scripts, 3D models, and alpha test prototypes of open-source hardware.

# OpenColor

OpenColor is a multi-color layer planning and generation toolkit for FDM 3D printing. It achieves sophisticated color performance on the surface or inside of printed parts by physically stacking materials of different colors (such as R, G, B, W) with tiny layer thicknesses. The logic of this project is similar to HueForge, but it provides a more flexible open-source implementation and physics-based simulation tools.

## 🚀 Key Features

- **Multi-material Layer Planning**: Automatically convert target RGBA colors into optimal material stacking sequences.
- **Image/Vector to 3D**: Supports direct conversion of bitmaps (BMP/PNG) and vector graphics (SVG) into material-categorized STL solid models.
- **Physics Simulation Prediction**: Built-in physical model based on Monte Carlo ray tracing for high-precision prediction of visual effects after stacking.
- **Dedicated Model Generation**: Supports generating spherical shells (Dome), color calibration plates (Mix Card), and stacked test blocks.
- **Flexible Material Configuration**: Define absorption, scattering, and strength parameters for different filaments via `materials.json`.

## 🛠️ Installation

This project recommends using [pixi](https://pixi.sh/) for environment management.

```bash
# Clone the repository
git clone https://github.com/your-repo/OpenColor.git
cd OpenColor

# Install dependencies and run using pixi
pixi run gen
```

### Manual Installation

If you do not use pixi, you can manually install the following main dependencies:

```bash
pip install numpy trimesh pillow shapely scikit-image cairosvg mapbox_earcut svgpathtools
```

## 📖 Core Concepts

### Stacking Logic
The core of OpenColor lies in utilizing the translucency of different color filaments. By controlling the type of material for each layer (usually 0.08mm - 0.2mm), thousands of colors can be combined.

### Planner
[planner.py](file:///d:/pama1234/pfp/p-2026-01/OpenColor/planner.py) provides two prediction modes:
1. **Fast Mode**: An empirical model based on weighted averages, suitable for large-scale pixel conversion.
2. **Physics Mode (Phys)**: Calls [forward_mc.py](file:///d:/pama1234/pfp/p-2026-01/OpenColor/forward_mc.py), considering light absorption and scattering.

## ⌨️ Common Command Examples

### 1. Convert Color to Stacked Square
```bash
python color_square_stack.py --hex "#DDF4C4" --layers 5 --layer-height 0.08
```

### 2. Convert SVG to Multi-color STL
```bash
python svg_stack_rgbw_testsvg.py --svg test.svg --width-mm 80 --view bottom
```

### 3. Generate Spherical Test Model
```bash
python layercap_dome.py --radius 20 --z-slices 10 --slice-height 0.4
```

### 4. Run Physics Simulation Validation
```bash
python forward_mc.py --seq G-R-W-W-W --heights 0.12,0.08,0.08,0.08,0.08 --view bottom
```

## 📂 Project Structure

For detailed descriptions of each script's function, please refer to [PROJECT_MAP.md](file:///d:/pama1234/pfp/p-2026-01/OpenColor/PROJECT_MAP.md).

- `planner.py`: Core prediction and planning algorithms.
- `forward_mc.py`: Monte Carlo physics simulation engine.
- `materials.json`: Material properties database.
- `bmp_map4stl_*.py`: Bitmap conversion tools.
- `svg4stl_*.py`: SVG conversion tools.

## ⚖️ License

[Add your license information here, e.g., MIT]
