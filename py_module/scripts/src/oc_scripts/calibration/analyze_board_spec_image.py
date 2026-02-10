from __future__ import annotations

import sys
import json
import cv2
import numpy as np
from pathlib import Path
from dataclasses import asdict

from oc_calib.board_spec import BoardSpec
from oc_calib.observation import Observation
from oc_scripts.calibration.color_board.calib_geom import detect_board_quad_by_chroma, warp_perspective, expand_quad


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def analyze_board(photo_path: Path, spec_path: Path, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    debug_dir = outdir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Spec
    spec = BoardSpec.load(spec_path)
    logger.info(f"加载规格文件: {spec.name} ({spec.rows}x{spec.cols})")

    # 2. Load Image
    data = np.fromfile(str(photo_path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {photo_path}")
    
    H, W = img.shape[:2]
    logger.info(f"图片尺寸: {W}x{H}")

    # 3. Detect Quad
    logger.info("正在检测色盘区域...")
    try:
        quad = detect_board_quad_by_chroma(img, debug_dir=debug_dir)
    except Exception as e:
        logger.error(f"自动检测失败: {e}，将使用全图范围")
        quad = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
        
    # 稍微向外扩展一点，确保覆盖边缘单元格
    quad = expand_quad(quad, 0.02, W, H)

    # 4. Warp
    # 使用 1024x1024 作为标准分析尺寸
    DST_SIZE = 1024
    warped, _M = warp_perspective(img, quad, DST_SIZE, DST_SIZE)
    
    # 保存扭曲矫正后的图片
    cv2.imencode(".png", warped)[1].tofile(str(outdir / "warped.png"))
    logger.info(f"已保存矫正后图片: {outdir / 'warped.png'}")

    # 5. Sample Cells
    measurements = {}
    cell_w = DST_SIZE / spec.cols
    cell_h = DST_SIZE / spec.rows
    
    overlay = warped.copy()
    
    logger.info(f"正在采样 {len(spec.cell_map)} 个单元格...")
    for cell_id, info in spec.cell_map.items():
        # cell_id 格式通常为 "r,c"
        try:
            r, c = map(int, cell_id.split(","))
        except ValueError:
            continue
            
        # 单元格中心在 warped 图像中的坐标
        cx = int((c + 0.5) * cell_w)
        cy = int((r + 0.5) * cell_h)
        
        # 采样区域大小 (取单元格大小的 25%)
        rw = max(1, int(cell_w * 0.125))
        rh = max(1, int(cell_h * 0.125))
        
        x0, y0 = max(0, cx - rw), max(0, cy - rh)
        x1, y1 = min(DST_SIZE, cx + rw), min(DST_SIZE, cy + rh)
        
        patch = warped[y0:y1, x0:x1]
        if patch.size == 0:
            continue
            
        # 取中值颜色以减少噪声和离群点影响
        bgr_median = np.median(patch.reshape(-1, 3), axis=0)
        rgb_median = bgr_median[::-1].tolist() # BGR -> RGB
        
        measurements[cell_id] = {
            "rgb": [int(v) for v in rgb_median],
            "recipe_index": info.get("recipe_index"),
            "layers": info.get("layers")
        }
        
        # 在叠加层上绘制采样框
        cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 255, 0), 1)

    cv2.imencode(".png", overlay)[1].tofile(str(outdir / "overlay.png"))
    logger.info(f"已保存采样覆盖图: {outdir / 'overlay.png'}")

    # 6. Create Observation
    obs = Observation(
        board_id=spec.board_id,
        photo_id=photo_path.stem,
        photo_path=str(photo_path),
        warp_corners=[tuple(p) for p in quad.tolist()],
        cell_measurements=measurements,
        diagnostics={
            "warped": "warped.png",
            "overlay": "overlay.png"
        }
    )
    
    obs_path = outdir / "observation.json"
    obs.save(obs_path)
    logger.info(f"已保存分析结果: {obs_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--photo", required=True, help="照片路径")
    parser.add_argument("--spec", required=True, help="规格 JSON 路径")
    parser.add_argument("--outdir", required=True, help="输出目录")
    args = parser.parse_args()
    
    try:
        analyze_board(Path(args.photo), Path(args.spec), Path(args.outdir))
    except Exception as e:
        logger.info(f"执行出错: {e}")
        sys.exit(1)
