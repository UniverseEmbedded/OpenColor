<p align="center"> 
 <img alt="OpenColor logo" src="test.svg" width="128" height="128"> 
 <br> 
 <em>I've mastered this, and gathered the lessons it concealed. — Book of Hours, Weather Factory</em> 
 <br> 
 <p align="center"> 
 | <a href="README_en.md">English</a> | <a href="README.md">简体中文</a> | 
 </p>
</p>

> [!WARNING]
> Note that the project is still in draft stage. The Web-UI is not functional. It is recommended to use the modules in [oc_proto](./py_module/prototypes/src/oc_proto/) sequentially to complete the bitmap to full-color stacked 3D model workflow.

# OpenColor

OpenColor is a multi-color stacking planning and generation toolkit for FDM 3D printing. It achieves fine color representation on the surface or interior of printed parts by physically stacking different colored materials (such as R, G, B, W) with small layer thicknesses.

## Core Features

- **Physics-driven color prediction**: Based on the Adding-Doubling physical model
- **Machine learning enhancement**: Uses XGBoost/GPR to correct residuals of the physical model, improving prediction accuracy
- **Complete calibration workflow**: End-to-end calibration from color palette generation, photo correction to model training
- **High-performance C++ core**: Vulkan-accelerated geometric processing and color solving
- **Modern UI**: Cross-platform desktop application built with Vue 3 + Tauri
- **Standard 3MF export**: Standard 3MF format support based on lib3mf

## Project Structure

```
OpenColor/
├── py_module/          # Python modules
│   ├── opencolor/      # Core algorithm library (oc_core_02)
│   ├── engine/         # HTTP API service (oc_engine)
│   ├── calibration/    # Auto calibration (oc_calib)
│   ├── model_export/   # 3MF export engine
│   ├── prototypes/     # Prototype development (oc_proto)
│   ├── scripts/        # Script collection (oc_scripts)
│   ├── analyze/        # Analysis and diagnostics (oc_analyze)
│   ├── sdf/            # SDF conversion (oc_sdf)
│   └── xgb/            # XGBoost models (oc_xgb)
├── cpp_module/         # C++ high-performance modules
│   ├── src/solver/     # Solver (opencolor_solver)
│   ├── src/geometry/   # Geometry processing (opencolor_geometry)
│   └── src/models/     # Prediction models (opencolor_models)
├── web/                # Web frontend + Tauri desktop shell
│   ├── src/            # Vue 3 frontend source code
│   └── src-tauri/      # Rust backend
├── data/               # Data files (calibration data, sample images)
└── doc/                # Documentation
```

## Quick Start

### Requirements

- Python 3.11+
- Node.js 20+
- Pixi (package manager)
- Vulkan SDK (optional for C++ modules)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd OpenColor

# Install all dependencies (Python + Node.js + C++)
pixi install

# Setup C++ environment (optional)
pixi run setup-cpp
```

### Run Web Application

```bash
# Development mode
pixi run web-tauri-dev

# Build production version
pixi run web-tauri-build
```

### Run Prototype Pipeline

```bash
# Calibration workflow
pixi run p2-calib-board-gen      # Generate calibration board
pixi run p2-calib-photo-warp-ui  # Photo perspective correction (UI)
pixi run p2-calib-sample-build   # Build sample dataset
pixi run p2-calib-color-rts      # Train color model

# Generation workflow
pixi run p2-gen-masks            # Generate masks
pixi run p2-gen-vtracer          # Vectorization
pixi run p2-gen-3mf              # Export STL/3MF
```

## Workflow

### 1. Calibration Workflow

Used for training color prediction models:

1. **Generate Calibration Board** (`calib_board_gen`): Generate specification files and 3MF print files for 8-color calibration board
2. **Photo Perspective Correction** (`calib_photo_warp`): Correct color palette photos via AprilTag or manual 4-point correction
3. **Build Sample Dataset** (`calib_sample_build`): Extract color samples from corrected photos
4. **Train Color Model** (`calib_color_rts`): Train color prediction model using physical model + GPR

### 2. Generation Workflow

Used for generating 3D print files from images:

1. **Generate Masks** (`gen_masks`): Real-time color matching solving based on trained model, generating layer masks
2. **Vectorization** (`gen_vector`): Convert masks to SVG vector polygons
3. **Model Export** (`gen_3mf`): Reconstruct 3D mesh from SVG polygons, export STL and 3MF

## Tech Stack

### Python
- **Numerical Computing**: NumPy, SciPy, JAX, XGBoost
- **Image Processing**: OpenCV, Pillow, scikit-image
- **Geometry Processing**: Trimesh, Shapely, Manifold3D
- **3D Formats**: lib3mf, pygltflib
- **UI**: Gradio
- **Data Validation**: Pydantic

### C++
- **Graphics**: Vulkan
- **Geometry**: Manifold, Clipper2, earcut-hpp
- **Python Bindings**: Pybind11
- **Shaders**: Shaderc
- **SVG**: nanosvg

### Web
- **Frontend**: Vue 3, TypeScript, Vite
- **Desktop**: Tauri v2 (Rust)
- **Internationalization**: vue-i18n

## Documentation

- [FILE_MAP.md](FILE_MAP.md) - Detailed file mapping
- [PROJECT_MAP.md](PROJECT_MAP.md) - Project-level structure description
- [py_module/PROJECT_MAP.md](py_module/PROJECT_MAP.md) - Python module detailed description
- [REFACTOR_MAP.md](REFACTOR_MAP.md) - Refactoring suggestion map
- [DEPC_MAP.md](DEPC_MAP.md) - Dependency cleanup map
- [IP_SAFETY.md](IP_SAFETY.md) - Intellectual Property Safety Document (Competitor Patent Avoidance)
- [cpp_module/README.md](cpp_module/README.md) - C++ module description
- [web/FILE_MAP.md](web/FILE_MAP.md) - Web frontend file mapping

## License

See [LICENSE_MAP.md](LICENSE_MAP.md)

## Acknowledgements

- Inspired by [HueForge](https://shop.thehueforge.com/)
- Reference open source project [Lumina-Layers](https://github.com/MOVIBALE/Lumina-Layers)
- Bambu Studio 3MF format reference [BambuStudio](https://github.com/bambulab/BambuStudio) (AGPL v3)
