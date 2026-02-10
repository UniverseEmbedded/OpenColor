"""
照片透视变换应用模块
Gradio界面应用，用于校准照片的透视校正、角点检测和网格对齐
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import gradio as gr
import numpy as np
from PIL import Image


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 3. 导入核心逻辑
from oc_calib.board_spec import BoardSpec
from oc_calib.calibration import WarpParams, estimate_coarse_homography, get_board_corners_from_h
from oc_core_02.utils.io_utils import copy_file
from oc_core_02.utils.manifest import write_manifest
# 2. 从 common 导入工具
from oc_core_02.utils.paths import ensure_data, get_out_dir, RESOURCES
from oc_calib.spec_adapter import SpecAdapter, extract_layer_sequence

try:
    from oc_core_02.core.apriltag_utils import detect_apriltags_corners
except ImportError:
    detect_apriltags_corners = None

VERSION = "calib_photo_warp"

# 颜色映射表 (与 calib_sample_build 保持一致)
COLOR_MAP_BGR = {
    "White": (255, 255, 255),
    "Red": (0, 0, 255),
    "Yellow": (0, 255, 255),
    "Blue": (255, 0, 0),
    "Green": (0, 255, 0),
    "Cyan": (255, 255, 0),
    "Magenta": (255, 0, 255),
    "Black": (0, 0, 0),
}

def order_points_tl_tr_br_bl(pts):
    """Reorder 4 (x,y) points to [TL, TR, BR, BL] in image coordinates."""
    if pts is None or len(pts) != 4:
        return pts
    arr = np.array(pts, dtype=np.float32)
    s = arr.sum(axis=1)
    d = arr[:, 0] - arr[:, 1]
    tl = arr[np.argmin(s)]
    br = arr[np.argmax(s)]
    tr = arr[np.argmax(d)]
    bl = arr[np.argmin(d)]
    ordered = np.stack([tl, tr, br, bl], axis=0)
    return [(float(x), float(y)) for x, y in ordered]

# 尝试导入 Chroma 检测逻辑 (作为 fallback)
try:
    from oc_core_02.core.chroma_utils import detect_chroma_corners
except ImportError:
    detect_chroma_corners = None

def perspective_warp_bgr(img_bgr, pts, wp, inset_mode=False, rows=1, cols=1):
    """
    简化版的透视变换，参考 oc_core_02.core.calibration
    """
    if inset_mode:
        # 默认用户点击的是缩进一格的点
        # 目标坐标需要外扩
        # 假设 dst_size 对应的是整个 Board 的大小
        # 缩进一格后的点在 dst 坐标系下的位置是：
        # (1/cols * size, 1/rows * size), ( (cols-1)/cols * size, 1/rows * size ), ...
        cell_w = wp.dst_size / cols
        cell_h = wp.dst_size / rows
        dst_pts = np.array([
            [cell_w, cell_h],
            [wp.dst_size - cell_w, cell_h],
            [wp.dst_size - cell_w, wp.dst_size - cell_h],
            [cell_w, wp.dst_size - cell_h]
        ], dtype=np.float32)
    else:
        # 目标坐标：[0,0], [W,0], [W,H], [0,H]
        dst_pts = np.array([
            [0, 0],
            [wp.dst_size, 0],
            [wp.dst_size, wp.dst_size],
            [0, wp.dst_size]
        ], dtype=np.float32)
    
    src_pts = np.array(pts, dtype=np.float32)
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(img_bgr, M, (wp.dst_size, wp.dst_size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return warped

def render_grid_overlay(warped_bgr, rows, cols):
    overlay = warped_bgr.copy()
    h, w = warped_bgr.shape[:2]
    for i in range(rows + 1):
        y = int(i * h / rows)
        cv2.line(overlay, (0, y), (w, y), (0, 255, 0), 1)
    for j in range(cols + 1):
        x = int(j * w / cols)
        cv2.line(overlay, (x, 0), (x, h), (0, 255, 0), 1)
    return overlay

class AppState:
    def __init__(self):
        self.prototype_dir = Path(__file__).resolve().parent
        # 只确保 spec 文件被复制到本地以便下拉框读取，照片我们直接引用原始路径
        self.data_dir = ensure_data(self.prototype_dir, ["spec_a", "spec_b"])
        self.out_root = get_out_dir(self.prototype_dir)
        self.current_out_dir = self.out_root
        
        # 默认照片目录
        self.photos_dir = Path(r"D:\pama1234\pfp\p-2026-01\OpenColor-02\data\calibration\photos_02")
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        
        # 直接使用 RESOURCES 中的原始路径，避免复制
        self.default_photo_path = RESOURCES.get("photo_01b")
        
        self.current_points = []
        self.current_image = None
        self.current_spec = None
        self.current_spec_filename = None
        self.rotation_count = 0 # 0, 1, 2, 3 (对应 0, 90, 180, 270 度顺时针)
        self._ensure_specific_spec()

    def _ensure_specific_spec(self):
        gen_dir = self.prototype_dir.parent / "calib_board_gen"
        gen_out_dir = gen_dir / "out"
        
        if not gen_out_dir.exists() or not list(gen_out_dir.glob("*_board_spec.json")):
            logger.info(f"未找到规格文件目录或文件: {gen_out_dir}，正在尝试生成...")
            import subprocess
            try:
                subprocess.run([sys.executable, "-m", "oc_proto.calib_board_gen.main"], check=True)
                logger.info("生成成功。")
            except Exception as e:
                logger.error(f"生成规格文件失败: {e}")
        
        if gen_out_dir.exists():
            for spec_path in gen_out_dir.glob("*_board_spec.json"):
                dest = self.data_dir / spec_path.name
                if not dest.exists() or spec_path.stat().st_mtime > dest.stat().st_mtime:
                    copy_file(spec_path, dest)
                    logger.info(f"已同步规格文件: {dest}")

state = AppState()

def _resolve_spec_path_by_name(data_dir: Path, spec_name: str | None) -> Path | None:
    if not spec_name:
        return None
    for p in data_dir.glob("*.json"):
        try:
            spec = BoardSpec.load(p)
        except Exception:
            continue
        if getattr(spec, "name", None) == spec_name:
            return p
    return None

def rebuild_warped_from_json(warp_json_path: Path, photo_path: Path, out_dir: Path) -> None:
    if not warp_json_path.exists():
        raise FileNotFoundError(f"未找到 warp.json: {warp_json_path}")
    if not photo_path.exists():
        raise FileNotFoundError(f"未找到原始照片: {photo_path}")

    data = json.loads(warp_json_path.read_text(encoding="utf-8", errors="replace"))
    pts = data.get("points") or data.get("original_points")
    if not isinstance(pts, list) or len(pts) != 4:
        raise ValueError("warp.json 中的点数据无效")

    spec_name = data.get("spec")
    spec_path = _resolve_spec_path_by_name(state.data_dir, spec_name)
    if spec_path is None:
        candidates = list(state.data_dir.glob("*.json"))
        spec_path = candidates[0] if candidates else None

    spec = BoardSpec.load(spec_path) if spec_path is not None else None
    rows = spec.rows if spec is not None else 1
    cols = spec.cols if spec is not None else 1

    img_bgr = cv2.imread(str(photo_path), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise FileNotFoundError(f"无法读取原始照片: {photo_path}")

    dst_size = int(data.get("dst_size", 1000))
    wp = WarpParams(dst_size=dst_size)
    warped_bgr = perspective_warp_bgr(img_bgr, pts, wp, inset_mode=True, rows=rows, cols=cols)
    
    # 应用旋转 (如果存在)
    rotation_count = data.get("rotation_count", 0)
    warped_bgr = apply_rotation(warped_bgr, rotation_count)
    
    overlay_bgr = render_grid_overlay(warped_bgr, rows, cols)

    out_dir.mkdir(parents=True, exist_ok=True)
    warped_path = out_dir / "board_warped.png"
    overlay_path = out_dir / "board_overlay.png"
    cv2.imwrite(str(warped_path), warped_bgr)
    cv2.imwrite(str(overlay_path), overlay_bgr)

    params = {
        "points": pts,
        "spec": spec.name if spec is not None else None,
        "dst_size": dst_size,
        "point_order": data.get("point_order", "TL_TR_BR_BL"),
        "source_photo": str(photo_path)
    }
    outputs = ["board_warped.png", "board_overlay.png", warp_json_path.name]
    if spec_path is not None:
        outputs.append(spec_path.name)
    write_manifest(
        output_dir=out_dir,
        version=VERSION,
        inputs=[str(photo_path), str(warp_json_path)] + ([str(spec_path)] if spec_path else []),
        outputs=outputs,
        params=params
    )
    if spec_path is not None:
        copy_file(spec_path, out_dir / "board_spec.json")

def load_spec(spec_name):
    if not spec_name: return None, None, gr.update()
    spec_path = state.data_dir / spec_name
    spec = BoardSpec.load(spec_path)
    state.current_spec = spec
    state.current_spec_filename = spec_name
    
    # 根据规格自动推断子目录名称
    # 例如 8-Color_Board_A_board_spec.json -> Board_A
    sub_dir_name = spec_name.replace("_board_spec.json", "").replace("8-Color_", "")
    state.current_out_dir = state.out_root / sub_dir_name
    
    # 生成预览图，传入路径以供 SpecAdapter 使用
    preview = get_spec_preview(spec, spec_path)
    
    return f"已加载: {spec.name} ({spec.rows}x{spec.cols})", preview, str(state.current_out_dir)

def handle_out_dir_change(new_path):
    if new_path:
        state.current_out_dir = Path(new_path)
    return f"输出目录已设置为: {state.current_out_dir}"

def get_spec_preview(spec, spec_path=None):
    """根据 Spec 生成首层颜色预览图"""
    if spec is None:
        return None
    
    # 使用 SpecAdapter 统一处理，确保逻辑与 main.py 一致
    if spec_path:
        adapter = SpecAdapter(spec_path)
    else:
        # 即使没有路径，也尝试构造一个临时 Adapter 或者直接从 spec 对象获取 rows/cols
        rows, cols = spec.rows, spec.cols
        adapter = None
    
    if adapter:
        rows, cols = adapter.rows, adapter.cols

    cell_size = 40
    img = np.zeros((rows * cell_size, cols * cell_size, 3), dtype=np.uint8)
    
    for r in range(rows):
        for c in range(cols):
            # 优先使用 adapter，否则退回到 spec.cell_map
            if adapter:
                cell_raw = adapter._get_cell_raw(r, c)
            else:
                cell_raw = spec.cell_map.get(f"{r},{c}")
            
            color = (40, 40, 40) # 默认深灰色
            
            if cell_raw:
                # 使用 common.spec_adapter 中的统一逻辑
                _, _, layer_names = extract_layer_sequence(cell_raw)
                if layer_names:
                        mat_name = layer_names[0] # 底面是第 0 层
                        color = COLOR_MAP_BGR.get(mat_name, (40, 40, 40))
                
                y0, x0 = r * cell_size, c * cell_size
                cv2.rectangle(img, (x0, y0), (x0 + cell_size, y0 + cell_size), color, -1)
                cv2.rectangle(img, (x0, y0), (x0 + cell_size, y0 + cell_size), (100, 100, 100), 1)
                
                # 添加材质名称首字母标注
                if cell_raw and layer_names:
                    cv2.putText(img, layer_names[0][:1], (x0 + 2, y0 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
            
    # 因为是底面预览，物理上左右是反的，所以需要水平翻转以匹配照片视角
    img = cv2.flip(img, 1)
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

def handle_photo_select(photo_name):
    if not photo_name:
        return None, "未选择照片"
    photo_path = state.photos_dir / photo_name
    if not photo_path.exists():
        return None, f"文件不存在: {photo_path}"
    
    img_bgr = cv2.imread(str(photo_path))
    if img_bgr is None:
        return None, f"无法读取图片: {photo_path}"
    
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    state.current_image = img_rgb
    state.current_points = []
    return img_rgb, f"已加载照片: {photo_name}。请点击角点或自动检测。"

def handle_image_upload(img):
    state.current_image = img
    state.current_points = []
    return img, "已上传图片，请点击 4 个角点（左上、右上、右下、左下）或点击自动检测"

def handle_click(img, evt: gr.SelectData):
    if len(state.current_points) >= 4:
        state.current_points = []
    
    state.current_points.append((evt.index[0], evt.index[1]))
    
    # 在图上画点
    img_draw = img.copy()
    for i, p in enumerate(state.current_points):
        cv2.circle(img_draw, p, 10, (255, 0, 0), -1)
        cv2.putText(img_draw, str(i+1), (p[0]+15, p[1]+15), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    msg = f"已点击 {len(state.current_points)}/4 个点"
    if len(state.current_points) == 4:
        msg += "。点击“生成 Warped”进行变换。"
        
    return img_draw, msg

def auto_detect_tags(img):
    if img is None or state.current_spec is None:
        return img, "请先上传图片并选择 Board Spec"
    
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 策略 1: AprilTag 检测
    logger.info("尝试使用 AprilTag 检测...")
    wp = WarpParams(use_apriltag=True)
    H, debug = estimate_coarse_homography(img_gray, state.current_spec, wp)
    
    if H is None and detect_chroma_corners is not None:
        # 策略 2: Chroma 检测 (Fallback)
        logger.error("AprilTag 失败，尝试 Chroma 检测...")
        pts = detect_chroma_corners(img_bgr, state.current_spec)
        if pts is not None:
            # pts 已经是 4 个角点
            state.current_points = order_points_tl_tr_br_bl([(p[0], p[1]) for p in pts])
            img_draw = img.copy()
            for i, p in enumerate(state.current_points):
                p_int = (int(p[0]), int(p[1]))
                cv2.circle(img_draw, p_int, 10, (0, 255, 255), -1)
                cv2.putText(img_draw, str(i+1), (p_int[0]+15, p_int[1]+15), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            return img_draw, f"Chroma 检测成功！已自动设置 4 个角点。", False

    if H is not None:
        pts = get_board_corners_from_h(H, state.current_spec)
        state.current_points = order_points_tl_tr_br_bl([(p[0], p[1]) for p in pts])
        
        img_draw = img.copy()
        for i, p in enumerate(state.current_points):
            p_int = (int(p[0]), int(p[1]))
            cv2.circle(img_draw, p_int, 10, (0, 255, 0), -1)
            cv2.putText(img_draw, str(i+1), (p_int[0]+15, p_int[1]+15), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        return img_draw, f"AprilTag 检测成功！已自动设置 4 个角点。", True
    else:
        return img, "自动检测失败（已尝试 AprilTag 和 Chroma），请手动点击。", gr.update()

def apply_rotation(img_bgr, count):
    """根据 count 应用 90 度旋转"""
    count = count % 4
    if count == 1:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
    elif count == 2:
        return cv2.rotate(img_bgr, cv2.ROTATE_180)
    elif count == 3:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img_bgr

def generate_warped(img, inset_mode):
    if len(state.current_points) != 4:
        return None, None, "请先选择 4 个角点"
    
    if state.current_spec is None:
        return None, None, "请先选择 Board Spec"

    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    wp = WarpParams(dst_size=1000)

    original_points = list(state.current_points)
    ordered_points = order_points_tl_tr_br_bl(state.current_points)
    state.current_points = ordered_points

    warped_bgr = perspective_warp_bgr(
        img_bgr, state.current_points, wp, 
        inset_mode=inset_mode, 
        rows=state.current_spec.rows, 
        cols=state.current_spec.cols
    )
    
    # 应用旋转
    warped_bgr = apply_rotation(warped_bgr, state.rotation_count)
    
    overlay_bgr = render_grid_overlay(warped_bgr, state.current_spec.rows, state.current_spec.cols)
    
    state.current_out_dir.mkdir(parents=True, exist_ok=True)
    warped_path = state.current_out_dir / "board_warped.png"
    overlay_path = state.current_out_dir / "board_overlay.png"
    warp_json_path = state.current_out_dir / "warp.json"
    
    cv2.imwrite(str(warped_path), warped_bgr)
    cv2.imwrite(str(overlay_path), overlay_bgr)
    
    warp_data = {
        "points": state.current_points,
        "original_points": original_points,
        "spec": state.current_spec.name,
        "dst_size": wp.dst_size,
        "rotation_count": state.rotation_count, # 记录旋转次数
        "point_order": "TL_TR_BR_BL"
    }
    with open(warp_json_path, 'w') as f:
        json.dump(warp_data, f, indent=2)
    
    # 保存 spec 到输出目录
    spec_out_path = state.current_out_dir / "board_spec.json"
    if state.current_spec_filename:
        copy_file(state.data_dir / state.current_spec_filename, spec_out_path)
    
    write_manifest(
        output_dir=state.current_out_dir,
        version=VERSION,
        inputs=[state.current_spec_filename or state.current_spec.name],
        outputs=["board_warped.png", "board_overlay.png", "warp.json", "board_spec.json"],
        params=warp_data
    )
    
    return Image.fromarray(cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2RGB)), \
           Image.fromarray(cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)), \
           f"生成成功！(旋转: {state.rotation_count*90}°) 输出目录: {state.current_out_dir}"

def handle_rotate_cw(img, inset_mode):
    state.rotation_count = (state.rotation_count + 1) % 4
    return generate_warped(img, inset_mode)

def handle_rotate_ccw(img, inset_mode):
    state.rotation_count = (state.rotation_count - 1) % 4
    return generate_warped(img, inset_mode)

def auto_load_all(spec_name, img, inset_mode):
    msg1, spec_prev, _ = load_spec(spec_name)
    img_after, msg2 = handle_image_upload(img)
    # 尝试自动检测和生成
    res = auto_detect_tags(img_after)
    img_final, msg3 = res[0], res[1]
    new_inset_mode = res[2] if len(res) > 2 else inset_mode
    
    full_msg = " | ".join(filter(None, [msg1, msg3]))
    
    if "成功" in msg3:
        w_out, o_out, msg4 = generate_warped(img_final, new_inset_mode)
        full_msg = " | ".join(filter(None, [msg1, msg3, msg4]))
        return img_final, full_msg, w_out, o_out, new_inset_mode, spec_prev
    return img_final, full_msg, None, None, new_inset_mode, spec_prev

with gr.Blocks() as demo:
    gr.Markdown(f"# {VERSION} - 色盘校准透视变换原型")
    
    with gr.Row():
        with gr.Column():
            with gr.Group():
                gr.Markdown("### 1. 规格与照片选择")
                spec_files = [f.name for f in state.data_dir.glob("*.json")]
                default_spec = "8-Color_Board_A_board_spec.json"
                spec_dropdown = gr.Dropdown(
                    choices=spec_files, 
                    value=default_spec if default_spec in spec_files else (spec_files[0] if spec_files else None),
                    label="选择 Board Spec"
                )
                
                photo_files = [f.name for f in state.photos_dir.glob("*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]]
                photo_dropdown = gr.Dropdown(
                    choices=photo_files,
                    label="从 photos_02 目录选择照片"
                )
                
                out_dir_input = gr.Textbox(
                    label="输出目录 (子目录)",
                    value=str(state.current_out_dir),
                    placeholder="例如: Board_A"
                )
            
            spec_info = gr.Label(label="Spec 信息")
            spec_preview = gr.Image(label="首层颜色预览 (参考方向)", interactive=False)
            
            input_img = gr.Image(
                value=str(state.default_photo_path) if state.default_photo_path and state.default_photo_path.exists() else None,
                label="上传/显示色盘照片 (支持手动拖拽)", 
                type="numpy"
            )
            
            with gr.Row():
                inset_checkbox = gr.Checkbox(label="手动点击模式：缩进一格", value=False)
                detect_btn = gr.Button("自动检测 AprilTag")
            
            status_text = gr.Textbox(label="状态", interactive=False)
            
            warp_btn = gr.Button("生成 Warped", variant="primary")
            
        with gr.Column():
            warped_out = gr.Image(label="Warped 结果")
            with gr.Row():
                rotate_ccw_btn = gr.Button("🔄 逆时针 90°")
                rotate_cw_btn = gr.Button("🔄 顺时针 90°")
            overlay_out = gr.Image(label="网格叠加预览")
            result_info = gr.Textbox(label="结果信息", interactive=False)

    spec_dropdown.change(load_spec, inputs=[spec_dropdown], outputs=[spec_info, spec_preview, out_dir_input])
    out_dir_input.change(handle_out_dir_change, inputs=[out_dir_input], outputs=[status_text])
    photo_dropdown.change(handle_photo_select, inputs=[photo_dropdown], outputs=[input_img, status_text])
    input_img.upload(handle_image_upload, inputs=[input_img], outputs=[input_img, status_text])
    input_img.select(handle_click, inputs=[input_img], outputs=[input_img, status_text])
    detect_btn.click(auto_detect_tags, inputs=[input_img], outputs=[input_img, status_text, inset_checkbox])
    warp_btn.click(generate_warped, inputs=[input_img, inset_checkbox], outputs=[warped_out, overlay_out, result_info])
    
    rotate_cw_btn.click(handle_rotate_cw, inputs=[input_img, inset_checkbox], outputs=[warped_out, overlay_out, result_info])
    rotate_ccw_btn.click(handle_rotate_ccw, inputs=[input_img, inset_checkbox], outputs=[warped_out, overlay_out, result_info])

    # 自动加载逻辑
    demo.load(
        auto_load_all, 
        inputs=[spec_dropdown, input_img, inset_checkbox], 
        outputs=[input_img, status_text, warped_out, overlay_out, inset_checkbox, spec_preview]
    )

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="")
    ap.add_argument("--warp-json", type=str, default="", help="")
    ap.add_argument("--photo", type=str, default="", help="")
    ap.add_argument("--out-dir", type=str, default="", help="")
    args, _ = ap.parse_known_args()

    if args.rebuild:
        warp_json = Path(args.warp_json) if args.warp_json else state.current_out_dir / "warp.json"
        photo = Path(args.photo) if args.photo else state.default_photo_path
        out_dir = Path(args.out_dir) if args.out_dir else state.current_out_dir
        rebuild_warped_from_json(warp_json, photo, out_dir)
        logger.info(f"已重建 warped 输出: {out_dir}")
    else:
        demo.launch()
