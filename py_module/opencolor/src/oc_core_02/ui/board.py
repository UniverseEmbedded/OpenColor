import gradio as gr

from oc_calib.board import BoardParams, render_board_preview, export_board_stls
from oc_core_02.core.color_systems import ALL_SYSTEMS
from oc_core_02.ui.utils import _tmpdir, _zip_dir


def ui_generate_board(
    color_system: str, n_layers: int, cell_size_mm: float, layer_height_mm: float
):
    """生成校准板STL文件和预览图"""
    params = BoardParams(
        color_system=color_system,
        n_layers=n_layers,
        cell_size_mm=cell_size_mm,
        layer_height_mm=layer_height_mm,
    )
    preview = render_board_preview(params, px_per_cell=18)

    out = _tmpdir()
    stl_dir = out / "stls"
    stl_paths = export_board_stls(params, stl_dir)
    zip_path = _zip_dir(stl_dir, f"calibration_board_{color_system}")

    # 返回预览图像和zip文件
    return preview, str(zip_path)


def build_board_ui():
    with gr.Tab("Calibration Board"):
        with gr.Row():
            cs = gr.Dropdown(
                choices=list(ALL_SYSTEMS.keys()), value="RYBW", label="Color System"
            )
            n_layers = gr.Slider(3, 7, value=5, step=1, label="Layers (default 5)")
        with gr.Row():
            cell = gr.Number(value=0.42, label="Cell / Pixel size (mm)")
            lh = gr.Number(value=0.2, label="Layer height (mm)")

        btn = gr.Button("Generate STLs")
        with gr.Row():
            prev = gr.Image(label="Board preview (top-layer hint)")
            zip_out = gr.File(label="Download: calibration board STLs (.zip)")

        btn.click(
            ui_generate_board, inputs=[cs, n_layers, cell, lh], outputs=[prev, zip_out]
        )

        gr.Markdown(
            "**打印提示**：导入 zip 里的 4 个 STL 到切片器，分别分配到对应耗材槽位（按 Color System 的 slot 名称）。"
        )
