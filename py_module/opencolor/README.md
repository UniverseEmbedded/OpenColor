# oc_core

OpenColor 核心算法模块 - Calibration board to LUT and bitmap pipeline tool

## 简介

本项目实现了一个"校准板 → 拍照采样 LUT → 位图映射 → 多耗材 STL + 预览"的完整闭环。

**核心点**
- 校准板：32×32 数据区 + 外圈 1 格边框（总 34×34）。
- 色系：支持 `RYBW`（White/Red/Yellow/Blue）与 `CMYW`（White/Cyan/Magenta/Yellow）。
- 层数：默认 5 层（4^5=1024 个配方刚好填满 32×32）。

## 开发环境

使用 [pixi](https://pixi.sh/) 管理：
```bash
pixi shell
```

## 运行

### 依赖
- Python 3.11+（推荐）

安装：
```bash
pip install -r requirements.txt
```

启动 UI：
```bash
python app.py
```

打开终端输出的本地地址（一般是 `http://127.0.0.1:7860`）。

## 工作流

### A. 生成校准板（打印）
1. 进入 **Calibration Board** 标签
2. 选择色系（RYBW/CMYW）、单元格尺寸、层高、总层数（默认 5）
3. 点击 **Generate STLs**，会得到 4 个 STL（每个耗材一个）
4. 在切片器里导入这 4 个 STL，并为它们分配对应耗材，打印完成

### B. 从照片提取 LUT
1. 进入 **Extract LUT from Photo** 标签
2. 上传校准板照片
3. 依次点四个角（顺序：左上、右上、右下、左下）
4. 可用滑块微调（Zoom / Barrel / OffsetX / OffsetY）
5. 点击 **Extract LUT**
6. 得到 `lut.npy`（32×32×3）与预览图

### C. 位图 → 预览/导出
1. 进入 **Bitmap → Print Files** 标签
2. 上传 PNG/JPG（可带透明）
3. 选择目标宽度(mm)、喷嘴宽度(mm)，以及背景去除选项
4. 选择 LUT 文件（上一步导出的 `.npy`）
5. 点击 **Process & Export**
6. 输出：
   - 2D 预览 PNG
   - 3D 预览 GLB
   - 4 个 STL（每个耗材一个）

## 输出格式
- LUT: `.npy`，shape `(32,32,3)`，dtype `uint8`
- STL: 每个耗材一份（便于切片器分配材料）
- 3D 预览: `.glb`（体素立柱，带颜色）

## 免责声明
- LUT 映射是最近邻匹配，属于工程可用但不保证严格色准。
- 照片质量对 LUT 影响很大：尽量使用均匀光照、避免强反光、保持板子尽量平面。
