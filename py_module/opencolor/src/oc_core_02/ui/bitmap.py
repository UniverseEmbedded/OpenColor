import gradio as gr
import numpy as np
from PIL import Image

from oc_core_02.core.bitmap_pipeline import BitmapParams, process_bitmap
from oc_core_02.core.bitmap_pipeline_sdf import SDFParams, process_bitmap_sdf
from oc_core_02.ui.utils import _tmpdir, _zip_dir


def ui_apply_patch(lut: np.ndarray, coord, color: str, color_system: str):
    """手动修正 LUT 中的某个色块"""
    if lut is None or coord is None:
        raise gr.Error("请先选择色块")
    
    r, c = coord
    new_lut = lut.copy()
    
    # 解析颜色
    hex_s = color.lstrip('#')
    new_color = [int(hex_s[i:i + 2], 16) for i in (0, 2, 4)]
    
    new_lut[r, c] = new_color
    
    # 更新预览图
    lut_img = Image.fromarray(new_lut, mode="RGB").resize((512, 512), resample=Image.Resampling.NEAREST)
    
    # 保存新文件
    out = _tmpdir()
    npy_path = out / f"lut_{color_system}_patched.npy"
    np.save(npy_path, new_lut)
    
    return new_lut, lut_img, str(npy_path), "✅ 已修正"

def ui_process_bitmap(
    image: str,
    lut_file: str,
    color_system: str,
    target_width_mm: float,
    nozzle_width_mm: float,
    layer_height_mm: float,
    n_layers: int,
    alpha_threshold: int,
    auto_bg_remove: bool,
    bg_tol: int,
    algo: str,
    smooth_sigma: float,
    simplify_eps: float,
):
    """位图处理 UI 入口"""
    if image is None:
        raise gr.Error("请先上传位图")
    if lut_file is None:
        raise gr.Error("请先提供 LUT (.npy)")

    out = _tmpdir()
    p = BitmapParams(
        color_system=color_system,
        target_width_mm=float(target_width_mm),
        nozzle_width_mm=float(nozzle_width_mm),
        layer_height_mm=float(layer_height_mm),
        n_layers=int(n_layers),
        alpha_threshold=int(alpha_threshold),
        auto_bg_remove=bool(auto_bg_remove),
        bg_tol=int(bg_tol),
    )

    if algo == "SDF (Smooth)":
        sp = SDFParams(
            smooth_sigma=float(smooth_sigma),
            simplify_eps=float(simplify_eps)
        )
        outputs = process_bitmap_sdf(image_path=image, lut_path=lut_file, params=p, sdf_params=sp, out_dir=out)
    else:
        outputs = process_bitmap(image_path=image, lut_path=lut_file, params=p, out_dir=out)

    # 压缩所有输出文件
    zip_path = _zip_dir(out, f"bitmap_export_{color_system}")

    bambu_3mf = str(outputs["bambu_3mf"]) if "bambu_3mf" in outputs else None

    return str(outputs["preview_2d"]), str(outputs["preview_3d"]), str(zip_path), bambu_3mf

def build_bitmap_ui():
    from oc_core_02.core.color_systems import ALL_SYSTEMS
    
    with gr.Tab("Bitmap → Print Files"):
        with gr.Row():
            img_in = gr.Image(type="filepath", label="Bitmap (PNG/JPG, alpha supported)")
            with gr.Column():
                lut_in = gr.File(label="LUT (.npy)")
                cs3 = gr.Dropdown(choices=list(ALL_SYSTEMS.keys()), value="RYBW", label="Color System")
                target_w = gr.Number(value=60.0, label="Target width (mm)")
                nozzle = gr.Number(value=0.42, label="Nozzle / pixel size (mm)")
                lh2 = gr.Number(value=0.2, label="Layer height (mm)")
                n_layers2 = gr.Slider(3, 7, value=5, step=1, label="Layers")
                
                algo = gr.Dropdown(choices=["SDF (Smooth)", "Voxel (Legacy)"], value="SDF (Smooth)", label="Mesh Algorithm")
                with gr.Row():
                    smooth_s = gr.Slider(0.5, 3.0, value=1.2, step=0.1, label="SDF Smooth (sigma)")
                    simplify_e = gr.Slider(0.0, 3.0, value=1.0, step=0.1, label="Simplify (eps)")

                alpha_t = gr.Slider(0, 255, value=10, step=1, label="Alpha threshold")
                auto_bg = gr.Checkbox(value=False, label="Auto background remove (use top-left pixel)")
                bg_tol = gr.Slider(0, 60, value=15, step=1, label="BG tolerance")

                go = gr.Button("Process & Export")

        with gr.Row():
            prev2d = gr.Image(label="2D preview (matched)")
            prev3d = gr.Model3D(label="3D preview (GLB)")

        with gr.Row():
            zip_all = gr.File(label="Download all outputs (.zip)")
            bambu_3mf_out = gr.File(label="Download Bambu 3MF")

        go.click(
            ui_process_bitmap,
            inputs=[img_in, lut_in, cs3, target_w, nozzle, lh2, n_layers2, alpha_t, auto_bg, bg_tol, algo, smooth_s, simplify_e],
            outputs=[prev2d, prev3d, zip_all, bambu_3mf_out],
        )
        
        return {
            "cs_dropdown": cs3
        }
