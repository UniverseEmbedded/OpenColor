from __future__ import annotations

import os
import sys

import gradio as gr

from oc_core_02.ui.bitmap import build_bitmap_ui
from oc_core_02.ui.board import build_board_ui
from oc_core_02.ui.calibration import build_calibration_ui, ui_run_mcrt_analysis
from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

# 核心模块由 pixi 自动管理 PYTHONPATH，不再需要手动 append
# 如果不在 pixi 环境运行，建议使用 pixi run

APP_TITLE = "LumenBoardTool (from-scratch)"

def build_ui(default_photo=None, default_spec=None):
    """构建Gradio用户界面"""
    with gr.Blocks(title=APP_TITLE) as demo:
        gr.Markdown(f"# {APP_TITLE}\n\n从零实现：校准板 → LUT → 位图映射 → 多耗材 STL + 预览。")

        with gr.Tabs():
            # 标签页 1: 校准板生成
            build_board_ui()

            # 标签页 2: 从照片提取数据
            calib_outputs = build_calibration_ui(default_photo=default_photo, default_spec=default_spec)

            # 标签页 3: 位图转打印文件
            bitmap_outputs = build_bitmap_ui()

            # 跨标签页依赖：MCRT 分析需要标签页 3 的颜色系统选择
            calib_outputs["mcrt_btn"].click(
                ui_run_mcrt_analysis,
                inputs=[
                    calib_outputs["obs_state"], 
                    calib_outputs["board_spec_state"], 
                    calib_outputs["all_samples_state"], 
                    bitmap_outputs["cs_dropdown"], # 从位图标签页获取
                    calib_outputs["mcrt_disable_cpp"]
                ],
                outputs=[
                    calib_outputs["obs_state"], 
                    calib_outputs["lut_prev"], 
                    calib_outputs["probe_html"]
                ]
            )

        gr.Markdown(
            "---\n"
            "**注意**：该工具做的是工程可用的最近邻 LUT 映射预览，并不保证严格色准；"
            "照片光照/反光会显著影响 LUT。\n"
            "建议：均匀漫反射光、避免高光、手机固定拍摄。"
        )

    return demo

if __name__ == "__main__":
    logger.debug("Gradio version: {}", gr.__version__)
    logger.debug("Python executable: {}", sys.executable)
    
    photo_path = os.environ.get("LBT_DEFAULT_PHOTO")
    spec_path = os.environ.get("LBT_DEFAULT_SPEC")
    
    demo = build_ui(default_photo=photo_path, default_spec=spec_path)
    demo.launch()
