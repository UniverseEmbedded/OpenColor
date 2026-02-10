# calib_photo_warp_01

## 功能
上传色盘照片，加载 Board Spec，通过 AprilTag 或手动 4 点进行透视校正。提供Gradio Web界面进行交互式操作。

## 运行
```bash
pixi run python -m oc_prototypes_02.calib_photo_warp_01.app
```

## 功能说明
1. **选择 Spec**: 从 `data/` 目录加载 JSON 规格文件
2. **上传图片**: 拖拽或点击上传色盘照片
3. **定位方式**:
   - **自动**: 点击 "自动检测 AprilTag"，支持AprilTag和Chroma色块检测
   - **手动**: 按左上、右上、右下、左下顺序点击图片4个角点
4. **旋转调整**: 支持顺时针/逆时针90度旋转
5. **生成**: 点击 "生成 Warped" 输出校正后的图像

## 输出
- `out/Board_A/board_warped.png` - 透视校正后的色盘图像
- `out/Board_A/board_overlay.png` - 带网格叠加的预览图
- `out/Board_A/warp.json` - 变换参数（角点坐标、规格名、旋转信息）
- `out/Board_A/board_spec.json` - 同步的规格文件
- `out/Board_A/manifest.json` - 运行元数据

## 重建模式
支持从已有的 warp.json 重建 warped 输出：
```bash
pixi run python -m oc_prototypes_02.calib_photo_warp_01.app --rebuild --warp-json <path> --photo <path> --out-dir <path>
```

## 依赖
- 需要 `calib_board_gen_01` 生成的规格文件
- 照片默认从 `data/calibration/photos_02` 目录加载
