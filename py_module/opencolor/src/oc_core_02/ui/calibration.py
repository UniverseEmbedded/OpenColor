import time
from pathlib import Path
from typing import List, Tuple

import cv2
import gradio as gr
import numpy as np
from PIL import Image, ImageDraw

from oc_calib.calibration import WarpParams, extract_lut_from_warped_bgr
from oc_core_02.core.mcrt_engine import MCRTEngine
from oc_core_02.ui.utils import _build_material_props


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 全局 MCRT 引擎实例
mcrt_engine = MCRTEngine()


def ui_reset_points(photo):
    """重置已选择的角点，并返回原始照片"""
    return [], "", photo


def ui_add_point(
    photo: np.ndarray, points: List[Tuple[float, float]], evt: gr.SelectData
):
    """在照片上添加角点，并在图片上绘制标注"""
    if photo is None:
        return points, "请先上传照片", photo

    # evt.index 给出 (x,y) 坐标
    x, y = evt.index
    pts = []
    if points:
        for p in points:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                pts.append((float(p[0]), float(p[1])))
    if len(pts) >= 4:
        # 替换最旧的点
        pts = pts[1:]
    pts.append((float(x), float(y)))

    text = " -> ".join([f"({int(px)},{int(py)})" for px, py in pts])
    if len(pts) < 4:
        text += "\n(继续点击，直到 4 个点：左上、右上、右下、左下)"
    else:
        text += "\n(已收集 4 点；可以微调参数后提取 LUT)"

    # 在图片上绘制点
    annotated_photo = photo.copy()

    # 确保是 uint8 且可写
    if annotated_photo.dtype != np.uint8:
        annotated_photo = annotated_photo.astype(np.uint8)

    # 绘制已有的点
    for i, (px, py) in enumerate(pts):
        pt = (int(px), int(py))
        # 画十字准星
        length = 15
        color_main = (0, 255, 255)  # 黄色准星
        cv2.line(
            annotated_photo,
            (pt[0] - length, pt[1]),
            (pt[0] + length, pt[1]),
            color_main,
            2,
        )
        cv2.line(
            annotated_photo,
            (pt[0], pt[1] - length),
            (pt[0], pt[1] + length),
            color_main,
            2,
        )
        # 画个小圆圈中心
        cv2.circle(annotated_photo, pt, radius=3, color=(255, 255, 255), thickness=-1)

        # 标号 (1-based)
        cv2.putText(
            annotated_photo,
            str(i + 1),
            (pt[0] + 15, pt[1] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            annotated_photo,
            str(i + 1),
            (pt[0] + 15, pt[1] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color_main,
            1,
            cv2.LINE_AA,
        )

    pts_out = [[float(px), float(py)] for px, py in pts]
    return pts_out, text, annotated_photo


def ui_auto_detect_points(photo: np.ndarray):
    from oc_scripts.calibration.color_board.calib_geom import (
        detect_board_quad_by_chroma,
    )

    if photo is None:
        return [], "请先上传照片", photo
    try:
        img_rgb = photo.astype(np.uint8)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        quad = detect_board_quad_by_chroma(img_bgr)
        pts = [(float(p[0]), float(p[1])) for p in quad.tolist()]
    except Exception as e:
        logger.error(f"[错误] 自动角点识别失败：{e}")
        return [], "自动角点识别失败，请手动点击 4 个角点", photo

    annotated_photo = photo.copy()
    if annotated_photo.dtype != np.uint8:
        annotated_photo = annotated_photo.astype(np.uint8)

    for i, (px, py) in enumerate(pts):
        pt = (int(px), int(py))
        length = 15
        color_main = (0, 255, 255)
        cv2.line(
            annotated_photo,
            (pt[0] - length, pt[1]),
            (pt[0] + length, pt[1]),
            color_main,
            2,
        )
        cv2.line(
            annotated_photo,
            (pt[0], pt[1] - length),
            (pt[0], pt[1] + length),
            color_main,
            2,
        )
        cv2.circle(annotated_photo, pt, radius=3, color=(255, 255, 255), thickness=-1)
        cv2.putText(
            annotated_photo,
            str(i + 1),
            (pt[0] + 15, pt[1] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            annotated_photo,
            str(i + 1),
            (pt[0] + 15, pt[1] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color_main,
            1,
            cv2.LINE_AA,
        )

    text = " -> ".join([f"({int(px)},{int(py)})" for px, py in pts])
    text += "\n(已自动识别 4 个角点，可直接提取 LUT)"
    pts_out = [[float(px), float(py)] for px, py in pts]
    return pts_out, text, annotated_photo


def render_enhanced_preview(samples, board_spec, cell_measurements):
    """渲染带有误差热力图和禁用标记的增强预览图"""
    h, w, _ = samples.shape
    # 放大预览图以获得更好的视觉效果
    scale = 16
    out_h, out_w = h * scale, w * scale
    img = (
        Image.fromarray(samples)
        .resize((out_w, out_h), resample=Image.Resampling.NEAREST)
        .convert("RGBA")
    )
    draw = ImageDraw.Draw(img)

    for r in range(h):
        for c in range(w):
            cell_key = f"{r},{c}"
            m = cell_measurements.get(cell_key, {})
            is_data = m.get("is_data", False)
            enabled = m.get("enabled", True)
            error = m.get("error", 0.0)

            x0, y0 = c * scale, r * scale
            x1, y1 = x0 + scale, y0 + scale

            if not is_data:
                # 边框和标记块：显著变暗并加上斜线
                draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0, 160))  # 更暗的遮罩
                draw.line([x0, y0, x1, y1], fill=(255, 255, 255, 100), width=1)
            else:
                if not enabled:
                    # 禁用的格子：半透明灰色覆盖 + 红色叉叉
                    draw.rectangle([x0, y0, x1, y1], fill=(100, 100, 100, 120))
                    draw.line([x0, y0, x1, y1], fill=(255, 0, 0), width=2)
                    draw.line([x0, y1, x1, y0], fill=(255, 0, 0), width=2)

                if error > 5.0:
                    # 误差热力图：更明显的边框
                    alpha = int(min(255, (error - 5.0) * 15))
                    draw.rectangle(
                        [x0, y0, x1, y1], outline=(255, 0, 0, alpha), width=3
                    )

    return img


def ui_run_mcrt_analysis(
    obs, board_spec, all_samples, color_system_name, disable_cpp: bool
):
    """运行 MCRT 分析以计算每个格子的矛盾性"""
    if obs is None or board_spec is None or all_samples is None:
        return obs, None, "请先提取数据"

    mat_props, slot_names = _build_material_props(board_spec, color_system_name)
    if not mat_props:
        return obs, None, f"无法确定材料列表：{color_system_name}"

    backend = "python" if disable_cpp else "vulkan"

    # 2. 遍历并计算
    total_error = 0.0
    count = 0

    progress = gr.Progress()
    data_keys = [
        k
        for k, m in obs.cell_measurements.items()
        if m.get("is_data") and m.get("enabled")
    ]
    if len(data_keys) == 0:
        return obs, None, "没有可分析的数据格，请先确认数据格已启用"

    total_cells = len(data_keys)

    max_layer_index = -1
    for key in data_keys:
        recipe = obs.cell_measurements[key].get("recipe")
        if recipe and "layers" in recipe:
            max_layer_index = max(max_layer_index, max(recipe["layers"]))
    if max_layer_index >= len(mat_props):
        return (
            obs,
            None,
            f"材料索引超出范围：最大 {max_layer_index}，材料数量 {len(mat_props)}",
        )

    for cell_idx, key in enumerate(data_keys):
        m = obs.cell_measurements[key]
        recipe = m.get("recipe")
        if not recipe or "layers" not in recipe:
            continue

        layers = recipe["layers"]
        h = 0.2  # 默认层高

        mu_a_stack = np.stack([mat_props[i].mu_a for i in layers])
        mu_s_stack = np.stack([mat_props[i].mu_s for i in layers])
        g_stack = np.array([mat_props[i].g for i in layers])
        n_stack = np.array([mat_props[i].n for i in layers])
        heights = np.array([h] * len(layers))

        # 运行 MCRT
        cell_index = cell_idx
        cell_base = cell_index / total_cells
        cell_span = 1.0 / total_cells

        def _on_progress(done: int, total: int):
            if total <= 0:
                return
            ratio = min(1.0, max(0.0, done / float(total)))
            progress(
                cell_base + ratio * cell_span,
                desc=f"MCRT 物理模拟中... {cell_index + 1}/{total_cells}",
            )

        spec = mcrt_engine.simulate_layer_stack(
            mu_a_stack,
            mu_s_stack,
            g_stack,
            n_stack,
            heights,
            samples=500,
            backing_albedo=np.ones(mcrt_engine.num_bins) * 0.9,
            progress_callback=_on_progress,
            backend=backend,
        )
        sim_rgb = mcrt_engine.spectral_to_rgb(spec)
        measured_rgb = np.array(m["rgb"])

        # 计算误差 (RGB 欧氏距离)
        error = np.linalg.norm(sim_rgb - measured_rgb)
        m["error"] = float(error)
        m["sim_rgb"] = sim_rgb.tolist()

        total_error += error
        count += 1

    avg_error = total_error / count if count > 0 else 0

    # 3. 重新渲染
    new_preview = render_enhanced_preview(
        all_samples, board_spec, obs.cell_measurements
    )
    return (
        obs,
        new_preview,
        f"MCRT 分析完成！平均误差: {avg_error:.2f}。已识别潜在矛盾点（红色光晕表示）。",
    )


def ui_extract_lut(
    photo: np.ndarray,
    board_spec,
    points: List[Tuple[float, float]],
    auto_detect: bool,
    use_apriltag: bool,
    zoom: float,
    barrel: float,
    offset_x: float,
    offset_y: float,
    window_px: int,
    auto_wb: bool,
    vignette_fix: bool,
):
    """从校准板照片中提取数据并生成 Observation"""
    from oc_scripts.calibration.color_board.calib_geom import (
        detect_board_quad_by_chroma,
    )
    from oc_calib.observation import Observation
    from oc_calib.calibration import (
        estimate_coarse_homography,
        get_board_corners_from_h,
        perspective_warp_bgr,
        render_grid_overlay_bgr,
    )
    import json

    if photo is None:
        gr.Info("请先上传照片")
        return None, None, None, None, None
    if board_spec is None:
        gr.Info("请先加载 BoardSpec")
        return None, None, None, None, None

    img_rgb = photo.astype(np.uint8)
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    wp = WarpParams(
        dst_size=1000,
        total_rows=board_spec.rows,
        total_cols=board_spec.cols,
        zoom=float(zoom),
        barrel=float(barrel),
        offset_x=float(offset_x),
        offset_y=float(offset_y),
        auto_wb=auto_wb,
        vignette_fix=vignette_fix,
        use_apriltag=use_apriltag,
    )

    pts = []
    tag_used = False
    tag_debug_info = {}

    # 1. 优先尝试 AprilTag 粗定位
    if use_apriltag:
        H_coarse, tag_debug_info = estimate_coarse_homography(img_gray, board_spec, wp)
        if H_coarse is not None:
            pts = get_board_corners_from_h(H_coarse, board_spec)
            tag_used = True
            logger.info(f"[INFO] 使用 AprilTag 进行粗定位成功。")

    # 2. 如果 AprilTag 失败或禁用，尝试旧的自动识别或使用手动点
    if not pts:
        if points and len(points) == 4:
            pts = [(float(p[0]), float(p[1])) for p in points]
        elif auto_detect:
            try:
                quad = detect_board_quad_by_chroma(img_bgr)
                pts = [(float(p[0]), float(p[1])) for p in quad.tolist()]
            except Exception as e:
                logger.error(f"[错误] 自动角点识别失败：{e}")
                gr.Info("定位失败（AprilTag 和颜色识别均失败），请手动点击 4 个角点")
                return None, None, None, None, None
        else:
            gr.Info("请在照片上点击 4 个角点（左上、右上、右下、左下）")
            return None, None, None, None, None

    warped = perspective_warp_bgr(img_bgr, pts, wp)
    grid = render_grid_overlay_bgr(
        warped, total_rows=board_spec.rows, total_cols=board_spec.cols, line_step=1
    )

    # 采样所有单元格（包含边框）
    all_samples = extract_lut_from_warped_bgr(
        warped,
        total_rows=board_spec.rows,
        total_cols=board_spec.cols,
        window_px=int(window_px),
    )

    # 根据 BoardSpec 提取 cell_measurements
    cell_measurements = {}
    for r in range(board_spec.rows):
        for c in range(board_spec.cols):
            is_data = f"{r},{c}" in board_spec.cell_map
            cell_measurements[f"{r},{c}"] = {
                "rgb": all_samples[r, c].tolist(),
                "confidence": 1.0 if is_data else 0.0,
                "is_data": is_data,
                "enabled": True,
                "error": 0.0,
                "recipe": board_spec.cell_map.get(f"{r},{c}") if is_data else None,
            }

    photo_id = str(int(time.time()))
    obs = Observation(
        board_id=board_spec.board_id,
        photo_id=photo_id,
        photo_path="memory",
        warp_corners=pts,
        warp_params=wp.__dict__,
        cell_measurements=cell_measurements,
        timestamp=time.time(),
    )

    # 调试输出
    debug_dir = Path("debug")
    debug_dir.mkdir(exist_ok=True)

    # 1) tag_debug.json
    tag_debug_path = debug_dir / f"tag_debug_{photo_id}.json"
    tag_debug_info["final_corners"] = pts
    tag_debug_info["tag_used_bool"] = tag_used
    with open(tag_debug_path, "w", encoding="utf-8") as f:
        json.dump(tag_debug_info, f, indent=2, ensure_ascii=False)

    # 2) debug_overlay.png
    debug_overlay = img_rgb.copy()
    # 画出检测到的所有 Tag
    for det in tag_debug_info.get("detections", []):
        c = np.array(det["corners"], dtype=np.int32)
        cv2.polylines(debug_overlay, [c], True, (0, 255, 0), 2)
        cv2.putText(
            debug_overlay,
            f"ID:{det['id']}",
            (c[0][0], c[0][1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
        )

    # 画出最终板框
    if pts:
        c_pts = np.array(pts, dtype=np.int32)
        cv2.polylines(debug_overlay, [c_pts], True, (255, 0, 0), 3)

    cv2.imwrite(
        str(debug_dir / f"debug_overlay_{photo_id}.png"),
        cv2.cvtColor(debug_overlay, cv2.COLOR_RGB2BGR),
    )

    lut_img = render_enhanced_preview(all_samples, board_spec, cell_measurements)

    grid_rgb = cv2.cvtColor(grid, cv2.COLOR_BGR2RGB)
    warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)

    return warped_rgb, grid_rgb, lut_img, obs, all_samples


def ui_probe_lut(all_samples, board_spec, obs, evt: gr.SelectData):
    """点击预览图查看详情并支持禁用切换"""
    if all_samples is None or board_spec is None or obs is None:
        return obs, None, "请先提取数据"

    # 获取点击的格子坐标
    px, py = evt.index
    c, r = int(px), int(py)

    cell_key = f"{r},{c}"
    m = obs.cell_measurements.get(cell_key)

    if not m or not m.get("is_data"):
        return obs, None, f"<b>坐标 ({r}, {c})</b>: 边框或非数据区"

    # 切换状态
    m["enabled"] = not m.get("enabled", True)

    # 更新预览图
    new_lut_img = render_enhanced_preview(
        all_samples, board_spec, obs.cell_measurements
    )

    status_str = "✅ 已启用" if m["enabled"] else "❌ 已禁用"
    recipe = m.get("recipe", {})
    recipe_str = f"配方: {recipe.get('slot_names', [])}"

    info = f"<b>格子 ({r}, {c})</b>: {status_str}<br>{recipe_str}<br>实测 RGB: {m['rgb']}<br>当前误差: {m['error']:.2f}"

    return obs, new_lut_img, info


def build_calibration_ui(default_photo=None, default_spec=None):
    from oc_calib.board_spec import BoardSpec, create_legacy_32x32_spec
    from oc_calib.dataset import CalibrationDataset
    from oc_core_02.ui.dataset import ui_load_board_spec

    with gr.Tab("Extract Data from Photo"):
        gr.Markdown(
            "上传校准板照片后，按顺序点击四个角点：**左上 → 右上 → 右下 → 左下**。\n\n"
            "支持加载 BoardSpec (.json)；如果不加载，默认使用旧版 32x32。"
        )

        with gr.Row():
            photo = gr.Image(
                type="numpy", label="Board photo (click corners)", value=default_photo
            )
            with gr.Column():
                with gr.Row():
                    spec_file = gr.File(
                        label="Load BoardSpec (.json)",
                        file_types=[".json"],
                        value=default_spec,
                    )
                    load_spec_btn = gr.Button("Load Spec")

                initial_spec = create_legacy_32x32_spec()
                initial_info = "已加载默认旧版 32x32 BoardSpec"
                if default_spec:
                    try:
                        initial_spec = BoardSpec.load(Path(default_spec))
                        initial_info = f"已加载 BoardSpec: {initial_spec.name} ({initial_spec.rows}x{initial_spec.cols})"
                    except Exception as e:
                        logger.error(f"加载默认规格失败: {e}")

                board_spec_state = gr.State(value=initial_spec)
                spec_info = gr.Markdown(initial_info)

                gr.Markdown(
                    "### 💡 操作指引\n请依次点击**色盘内容区（不含边框）**的四个十字顶点：\n1. **左上** (Border/Content junction)\n2. **右上**\n3. **右下**\n4. **左下**"
                )

                with gr.Row():
                    reset = gr.Button("重置 4 点")
                    auto_detect_btn = gr.Button("自动识别角点")
                pts_state = gr.State(value=[])
                pts_text = gr.Textbox(label="Clicked points", lines=4)

                with gr.Row():
                    auto_detect = gr.Checkbox(label="自动角点识别", value=True)
                    use_apriltag = gr.Checkbox(label="使用 AprilTag", value=True)
                    auto_wb = gr.Checkbox(label="Auto White Balance", value=False)
                    vignette_fix = gr.Checkbox(label="Vignette Fix", value=False)

                zoom = gr.Slider(0.85, 1.15, value=1.0, step=0.005, label="Zoom")
                barrel = gr.Slider(
                    -0.25, 0.25, value=0.0, step=0.001, label="Barrel (radial)"
                )
                offx = gr.Slider(-60, 60, value=0, step=1, label="Offset X (px)")
                offy = gr.Slider(-60, 60, value=0, step=1, label="Offset Y (px)")
                win = gr.Slider(4, 18, value=8, step=1, label="Sampling window (px)")

                extract = gr.Button("Extract Data", variant="primary")

        with gr.Row():
            warped = gr.Image(label="Warped")
            overlay = gr.Image(label="Warped + Grid")
            with gr.Column():
                lut_prev = gr.Image(label="Data preview (Click to probe)")
                probe_html = gr.HTML("Select a cell above...")

        with gr.Row():
            with gr.Column():
                add_to_ds_btn = gr.Button("Add to Dataset", variant="secondary")
                ds_status = gr.Markdown("Dataset is empty")
            with gr.Column():
                mcrt_btn = gr.Button("运行 MCRT 分析", variant="primary")
                mcrt_disable_cpp = gr.Checkbox(
                    label="不用 C++ 后端（强制 Python）", value=False
                )
                export_ds_btn = gr.Button("Export Dataset", variant="primary")
                ds_file = gr.File(label="Download Dataset (.zip)")

        # 隐藏的状态
        obs_state = gr.State(None)
        all_samples_state = gr.State(None)
        dataset_state = gr.State(CalibrationDataset())

        # 存储原始照片以便重置
        original_photo_state = gr.State(default_photo)

        load_spec_btn.click(
            ui_load_board_spec,
            inputs=[spec_file],
            outputs=[board_spec_state, spec_info],
        )
        reset.click(
            ui_reset_points,
            inputs=[original_photo_state],
            outputs=[pts_state, pts_text, photo],
        )
        auto_detect_btn.click(
            ui_auto_detect_points, inputs=[photo], outputs=[pts_state, pts_text, photo]
        )

        photo.select(
            ui_add_point,
            inputs=[photo, pts_state],
            outputs=[pts_state, pts_text, photo],
        )
        photo.upload(
            lambda x: (x, [], ""),
            inputs=[photo],
            outputs=[original_photo_state, pts_state, pts_text],
        )

        extract.click(
            ui_extract_lut,
            # cs is needed here but it's in the board tab?
            # Actually ui_extract_lut doesn't use cs. ui_run_mcrt_analysis does.
            # We'll need to pass cs_dropdown as an input if we want it here.
            # For now, let's assume it's passed from outside or uses a default.
            inputs=[
                photo,
                board_spec_state,
                pts_state,
                auto_detect,
                use_apriltag,
                zoom,
                barrel,
                offx,
                offy,
                win,
                auto_wb,
                vignette_fix,
            ],
            outputs=[warped, overlay, lut_prev, obs_state, all_samples_state],
        )

        lut_prev.select(
            ui_probe_lut,
            inputs=[all_samples_state, board_spec_state, obs_state],
            outputs=[obs_state, lut_prev, probe_html],
        )

        # mcrt_btn.click will be wired in app.py because it needs the color system dropdown from another tab
        return {
            "mcrt_btn": mcrt_btn,
            "mcrt_disable_cpp": mcrt_disable_cpp,
            "obs_state": obs_state,
            "board_spec_state": board_spec_state,
            "all_samples_state": all_samples_state,
            "lut_prev": lut_prev,
            "probe_html": probe_html,
            "add_to_ds_btn": add_to_ds_btn,
            "dataset_state": dataset_state,
            "ds_status": ds_status,
            "export_ds_btn": export_ds_btn,
            "ds_file": ds_file,
        }
