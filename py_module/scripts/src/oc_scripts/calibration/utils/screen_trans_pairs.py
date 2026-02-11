"""
分析两张屏幕背光照片（白色参考 + 彩色样品），拍摄条件：
- 屏幕显示水平灰度渐变（X轴 = 入射强度）
- 打印卡片具有垂直厚度渐变/带状（Y轴 = 厚度）

目标：
- 提取样品相对于参考的稳健相对透射率：
    T_rel(x,y,c) = I_sample(x,y,c) / I_ref(x,y,c)
  这可以消除：
    - 屏幕亮度不均匀性
    - 相机暗角/曝光的一阶影响
- 沿Y方向检测水平"厚度带"并每带汇总

重要：
- 如果你的"白色"不是裸屏而是白色材料卡片，
  那么T_rel是"相对于白色材料的红色"，不是绝对透射率。
  要获得绝对透射率，还需拍摄裸屏照片并传入 --bare

用法：
  python analyze_screen_transmission_pairs.py ^
    --ref "白色透光.png" ^
    --sample "红色透光.png" ^
    --outdir out_transmission

可选：
  --bare "裸屏.png"         # 计算绝对透射率
  --max_bands 32            # 限制带数
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import cv2
import matplotlib.pyplot as plt


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    # x 在 [0,1] 范围内
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)


def load_image_linear(path: str) -> np.ndarray:
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    x = rgb.astype(np.float32) / 255.0
    return srgb_to_linear(x)  # 线性RGB


def luminance_lin(rgb_lin: np.ndarray) -> np.ndarray:
    # 线性亮度（Rec.709）
    r, g, b = rgb_lin[..., 0], rgb_lin[..., 1], rgb_lin[..., 2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def auto_roi(mask_src: np.ndarray) -> tuple[int, int, int, int]:
    """
    找到排除暗边/暗角的稳健ROI
    使用亮度百分位数阈值并取最大连通分量
    返回像素坐标 (x0, y0, x1, y1)
    """
    H, W = mask_src.shape[:2]
    lum = mask_src

    # 平滑以减少纹理
    lum_blur = cv2.GaussianBlur(lum, (0, 0), 5.0)

    # 按百分位数阈值（保留较亮区域）
    thr = np.percentile(lum_blur, 35)  # 保留前65%
    m = (lum_blur >= thr).astype(np.uint8) * 255

    # 形态学闭运算填充孔洞
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)

    # 最大连通分量
    num, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if num <= 1:
        # 回退：中心裁剪
        pad_x = int(0.10 * W)
        pad_y = int(0.10 * H)
        return pad_x, pad_y, W - pad_x, H - pad_y

    # 跳过背景 idx=0
    areas = stats[1:, cv2.CC_STAT_AREA]
    idx = 1 + int(np.argmax(areas))
    x, y, w, h, area = stats[idx]
    # 向内填充一点以避免边缘
    pad = int(0.02 * min(W, H))
    x0 = int(np.clip(x + pad, 0, W - 1))
    y0 = int(np.clip(y + pad, 0, H - 1))
    x1 = int(np.clip(x + w - pad, 1, W))
    y1 = int(np.clip(y + h - pad, 1, H))
    # 确保最小尺寸
    if (x1 - x0) < 0.4 * W or (y1 - y0) < 0.4 * H:
        pad_x = int(0.10 * W)
        pad_y = int(0.10 * H)
        return pad_x, pad_y, W - pad_x, H - pad_y
    return x0, y0, x1, y1


def detect_horizontal_bands(lum_roi: np.ndarray, max_bands: int = 32) -> list[int]:
    """
    沿Y方向检测水平带边界（厚度台阶）

    策略：
    - 沿X平均 -> Y方向1D轮廓
    - 平滑
    - 在|dy|中找峰值（大变化对应带边缘）
    - 将边缘转换为分段
    """
    H, W = lum_roi.shape
    # 跨X平均以消除屏幕渐变，保留Y台阶结构
    y_profile = np.median(lum_roi, axis=1)  # 稳健

    # 平滑
    y_s = cv2.GaussianBlur(y_profile.astype(np.float32), (1, 0), 3.0).reshape(-1)

    # 导数幅度
    dy = np.abs(np.diff(y_s, prepend=y_s[0]))

    # 找候选边缘：dy的前p%，但限制数量
    # 自适应阈值：均值 + k*标准差
    thr = float(np.mean(dy) + 2.5 * np.std(dy))
    cand = np.where(dy > thr)[0].astype(int)

    if cand.size == 0:
        # 回退：未找到台阶 -> 单一带
        return [0, H]

    # 将附近候选聚类为单一边缘
    edges = []
    cluster = [cand[0]]
    for v in cand[1:]:
        if v - cluster[-1] <= 6:
            cluster.append(v)
        else:
            edges.append(int(np.median(cluster)))
            cluster = [v]
    edges.append(int(np.median(cluster)))

    # 保留边界内的边缘并排序
    edges = sorted([e for e in edges if 3 < e < H - 3])

    # 如果边缘太多：按dy强度取最强的
    if len(edges) > (max_bands - 1):
        strength = np.array([dy[e] for e in edges])
        keep = np.argsort(-strength)[: (max_bands - 1)]
        edges = sorted([edges[i] for i in keep])

    # 构建边界列表
    bounds = [0] + edges + [H]
    # 移除太薄的带
    cleaned = [bounds[0]]
    for b in bounds[1:]:
        if b - cleaned[-1] >= 10:
            cleaned.append(b)
    if cleaned[-1] != H:
        cleaned[-1] = H

    # 确保至少有一个带
    if len(cleaned) < 2:
        return [0, H]
    return cleaned


def save_debug_overlay(
    rgb: np.ndarray, roi: tuple[int, int, int, int], bounds: list[int], out_path: Path
):
    """
    保存带有ROI矩形和检测到的带边界的叠加图像
    """
    vis = (np.clip(rgb ** (1 / 2.4), 0, 1) * 255.0).astype(np.uint8)  # 近似回到sRGB
    vis_bgr = cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)
    x0, y0, x1, y1 = roi
    cv2.rectangle(vis_bgr, (x0, y0), (x1, y1), (0, 255, 255), 3)

    # 在roi内绘制带线
    for b in bounds:
        yy = y0 + b
        cv2.line(vis_bgr, (x0, yy), (x1, yy), (255, 0, 0), 2)

    cv2.imwrite(str(out_path), vis_bgr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="参考照片（如白色卡片照片）")
    ap.add_argument("--sample", required=True, help="样品照片（如红色卡片照片）")
    ap.add_argument("--bare", default=None, help="可选裸屏照片（无卡片）用于绝对透射率")
    ap.add_argument("--outdir", default="out_transmission")
    ap.add_argument("--max_bands", type=int, default=32)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ref = load_image_linear(args.ref)
    samp = load_image_linear(args.sample)

    # 从参考亮度检测ROI
    lum_ref = luminance_lin(ref)
    roi = auto_roi(lum_ref)
    x0, y0, x1, y1 = roi

    ref_roi = ref[y0:y1, x0:x1, :]
    samp_roi = samp[y0:y1, x0:x1, :]
    lum_roi = luminance_lin(ref_roi)

    # 检测水平厚度带
    bounds = detect_horizontal_bands(lum_roi, max_bands=args.max_bands)

    # 相对透射率
    eps = 1e-6
    Trel = samp_roi / (ref_roi + eps)  # HxWx3
    Trel = np.clip(Trel, 0.0, 5.0)

    # 如果提供了裸屏则计算可选绝对透射率：
    Tabs = None
    if args.bare:
        bare = load_image_linear(args.bare)
        bare_roi = bare[y0:y1, x0:x1, :]
        Tabs = samp_roi / (bare_roi + eps)
        Tabs = np.clip(Tabs, 0.0, 5.0)

    # 每带汇总
    band_stats = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        band = Trel[a:b, :, :]  # 带切片

        # 像素上的稳健统计
        med = np.median(band.reshape(-1, 3), axis=0)
        p10 = np.percentile(band.reshape(-1, 3), 10, axis=0)
        p90 = np.percentile(band.reshape(-1, 3), 90, axis=0)

        band_stats.append(
            {
                "band_index": i,
                "y0_in_roi": int(a),
                "y1_in_roi": int(b),
                "height_px": int(b - a),
                "Trel_median_rgb": [float(x) for x in med],
                "Trel_p10_rgb": [float(x) for x in p10],
                "Trel_p90_rgb": [float(x) for x in p90],
            }
        )

    meta = {
        "ref": args.ref,
        "sample": args.sample,
        "bare": args.bare,
        "roi": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
        "num_bands": len(bounds) - 1,
        "note": (
            "Trel = sample/ref。如果ref是白色材料卡片（不是裸屏），"
            "那么这是相对透射率（红色vs白色），不是绝对值。"
        ),
    }

    (outdir / "bands.json").write_text(
        json.dumps({"meta": meta, "bands": band_stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 在参考图像上保存调试叠加
    save_debug_overlay(ref, roi, bounds, outdir / "debug_roi_and_bands.png")

    # 相对透射率热图（使用Trel的亮度或每通道）
    Trel_lum = 0.2126 * Trel[..., 0] + 0.7152 * Trel[..., 1] + 0.0722 * Trel[..., 2]
    plt.figure(figsize=(12, 5))
    plt.imshow(Trel_lum, cmap="viridis", aspect="auto")
    plt.title("相对透射率热图（T_rel亮度） = 样品 / 参考")
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(outdir / "Trel_heatmap.png", dpi=200)
    plt.close()

    # 为几个带绘制示例曲线
    # 对于每个选定的带，绘制Y带上的中位数作为X的函数
    pick = (
        [0, (len(bounds) - 2) // 2, len(bounds) - 2] if (len(bounds) - 1) >= 3 else [0]
    )
    plt.figure(figsize=(12, 7))
    for idx in pick:
        a, b = bounds[idx], bounds[idx + 1]
        band = Trel[a:b, :, :]
        # 带内跨Y的中位数 -> X的函数
        tx = np.median(band, axis=0)  # Wx3
        # 转换为"密度"
        Dx = -np.log(np.clip(tx, 1e-6, 10.0))
        plt.plot(Dx[:, 0], label=f"带 {idx}  D_R(x)")
        plt.plot(Dx[:, 1], label=f"带 {idx}  D_G(x)")
        plt.plot(Dx[:, 2], label=f"带 {idx}  D_B(x)")
    plt.title("示例相对密度曲线  D_rel(x) = -ln(T_rel(x))")
    plt.xlabel("X（ROI中的像素）")
    plt.ylabel("相对密度（任意单位）")
    plt.legend(ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(outdir / "profile_plots.png", dpi=200)
    plt.close()

    logger.info("完成。")
    logger.info("输出目录:", outdir)
    logger.info("带数:", len(bounds) - 1)
    logger.info("ROI:", roi)
    if not args.bare:
        logger.info("注意：未提供 --bare。结果是样品/参考的相对透射率。")


if __name__ == "__main__":
    main()
