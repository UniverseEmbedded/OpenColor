# calib_board_gen_01

## 功能
生成8色校准板（Board Spec JSON + 3MF）。支持生成多个色盘（A-H），每个色盘包含不同的配方组合用于校准训练。

## 运行
```bash
pixi run python -m oc_prototypes_02.calib_board_gen_01.main --num_boards 2
```

## 参数
- `--num_boards`: 生成的板子数量（默认1，最大26对应A-Z）
- `--shrink`: 格子缩进量（默认0.0）

## 输出
- `out/8-Color_Board_A_board_spec.json` - 板子规格文件（包含行列数、格子配方等）
- `out/8-Color_Board_A.3mf` - 可直接打印的3MF文件
- `out/manifest.json` - 运行元数据

## 实现说明
- 调用项目根目录的 `generate_8color_board.py` 核心逻辑
- 使用 `type32_cubes.3mf` 作为打印模板
- 生成15x15的逻辑网格（17x17物理网格含边框）
- 配方池使用8种颜色：White, Black, Red, Green, Blue, Cyan, Magenta, Yellow
