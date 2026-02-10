"""
生成用于屏幕背光透射拍摄的 16:9 校准图像。

功能：
- 16:9 画布（默认 1920x1080）
- 连续水平灰度渐变（0..255）
- 16 个离散灰度块（用于鲁棒拟合）
- 两个标记的 ROI："BARE"（无材料）和 "COVER"（放置材料处）
  标签是可选的；可以关闭以获得纯图形。

依赖：
  pip install pillow numpy

用法：
  python make_screen_gradient_16x9.py --out screen_calibration.png --w 1920 --h 1080
"""

from __future__ import annotations
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def main():
    """主函数：生成屏幕校准图像"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="screen_calibration.png", help="输出文件路径")
    ap.add_argument("--w", type=int, default=1920, help="图像宽度")
    ap.add_argument("--h", type=int, default=1080, help="图像高度")
    ap.add_argument("--show_text", action="store_true", help="绘制标签（需要字体）")
    args = ap.parse_args()

    W, H = args.w, args.h
    img = Image.new("RGB", (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ------------------------
    # 区域布局（比例）
    # ------------------------
    pad = int(0.04 * W)
    top_band_h = int(0.20 * H)   # 离散块区域
    grad_band_h = int(0.22 * H)  # 连续渐变区域
    roi_band_h = int(0.46 * H)   # ROI 区域

    y0 = pad
    y1 = y0 + top_band_h
    y2 = y1 + int(0.03 * H)
    y3 = y2 + grad_band_h
    y4 = y3 + int(0.03 * H)
    y5 = y4 + roi_band_h

    # ------------------------
    # 1) 16 级离散块
    # ------------------------
    n_blocks = 16
    block_w = (W - 2 * pad) // n_blocks
    for i in range(n_blocks):
        val = int(round(i * 255 / (n_blocks - 1)))
        x1 = pad + i * block_w
        x2 = pad + (i + 1) * block_w if i < n_blocks - 1 else W - pad
        draw.rectangle([x1, y0, x2, y1], fill=(val, val, val))

    # 边框
    draw.rectangle([pad, y0, W - pad, y1], outline=(255, 255, 255), width=3)

    # ------------------------
    # 2) 连续渐变带
    # ------------------------
    grad_w = W - 2 * pad
    # 创建水平渐变 0..255
    ramp = np.tile(np.linspace(0, 255, grad_w, dtype=np.uint8), (grad_band_h, 1))
    grad_rgb = np.dstack([ramp, ramp, ramp])
    grad_img = Image.fromarray(grad_rgb, mode="RGB")
    img.paste(grad_img, (pad, y2))

    draw.rectangle([pad, y2, W - pad, y3], outline=(255, 255, 255), width=3)

    # ------------------------
    # 3) ROI 区域：BARE vs COVER
    # ------------------------
    roi_gap = int(0.03 * W)
    roi_w = (W - 2 * pad - roi_gap) // 2
    roi_h = roi_band_h

    bare_box = [pad, y4, pad + roi_w, y4 + roi_h]
    cover_box = [pad + roi_w + roi_gap, y4, pad + roi_w + roi_gap + roi_w, y4 + roi_h]

    # 用亮中性色填充 ROI（对透射有用）
    draw.rectangle(bare_box, fill=(240, 240, 240))
    draw.rectangle(cover_box, fill=(240, 240, 240))

    # 在每个 ROI 中绘制内部参考条（帮助对齐/缩放）
    bar_n = 8
    bar_margin = int(0.04 * roi_w)
    bar_top = y4 + int(0.10 * roi_h)
    bar_bottom = y4 + int(0.90 * roi_h)
    bar_area_w = roi_w - 2 * bar_margin
    bar_w = bar_area_w // bar_n

    for j in range(bar_n):
        val = int(round(j * 255 / (bar_n - 1)))
        # 左侧 ROI 条
        bx1 = pad + bar_margin + j * bar_w
        bx2 = pad + bar_margin + (j + 1) * bar_w if j < bar_n - 1 else pad + bar_margin + bar_area_w
        draw.rectangle([bx1, bar_top, bx2, bar_bottom], fill=(val, val, val))
        # 右侧 ROI 条
        cx1 = cover_box[0] + bar_margin + j * bar_w
        cx2 = cover_box[0] + bar_margin + (j + 1) * bar_w if j < bar_n - 1 else cover_box[0] + bar_margin + bar_area_w
        draw.rectangle([cx1, bar_top, cx2, bar_bottom], fill=(val, val, val))

    # ROI 边框
    draw.rectangle(bare_box, outline=(255, 0, 0), width=6)   # BARE 红色边框
    draw.rectangle(cover_box, outline=(0, 255, 0), width=6)  # COVER 绿色边框

    # 可选标签
    if args.show_text:
        try:
            # 尝试默认 TrueType 字体；Windows 上用户可能需要调整路径
            font = ImageFont.truetype("arial.ttf", size=int(0.035 * H))
        except Exception:
            font = ImageFont.load_default()

        draw.text((bare_box[0] + 20, bare_box[1] + 20), "BARE (no material)", fill=(0, 0, 0), font=font)
        draw.text((cover_box[0] + 20, cover_box[1] + 20), "COVER (place material here)", fill=(0, 0, 0), font=font)

    img.save(args.out)
    logger.info("Wrote:", args.out)


if __name__ == "__main__":
    main()
