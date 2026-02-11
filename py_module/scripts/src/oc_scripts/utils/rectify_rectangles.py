#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""矩形检测 + 透视校正

此脚本尝试在照片中找到最大的矩形板/纸张，在原始图像上绘制其
四边形作为预览，并导出透视校正后的（俯视）裁剪图。

它设计用于对可能包含眩光的照片具有稳健性。

用法：
  python3 rectify_rectangles.py --in_dir ./photos --out_dir ./out
  python3 rectify_rectangles.py --inputs img1.jpg img2.jpg --out_dir ./out

输出：
  <out_dir>/preview/<name>_preview.jpg
  <out_dir>/rectified/<name>_rectified.jpg

如果文件名包含像#U767d这样的序列，它们将被解码为Unicode字符
用于输出名称。
"""

import argparse
import os
import re
import glob
from typing import List, Tuple, Optional

import cv2
import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 匹配Unicode编码的文件名模式，如 #U767d
U_HASH_RE = re.compile(r"#U([0-9a-fA-F]{4,6})")


def decode_u_hash(s: str) -> str:
    """解码文件名如 '#U767d#U8272#U53cd#U5149.jpg' -> '白色反光.jpg'"""

    def _rep(m: re.Match) -> str:
        code = int(m.group(1), 16)
        try:
            return chr(code)
        except ValueError:
            return m.group(0)

    return U_HASH_RE.sub(_rep, s)


def order_points(pts: np.ndarray) -> np.ndarray:
    """返回按顺序排列的点：左上、右上、右下、左下"""
    pts = np.asarray(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]

    return np.array([tl, tr, br, bl], dtype=np.float32)


def quad_from_contours(edges: np.ndarray) -> Optional[np.ndarray]:
    """在边缘图像中找到最佳四边形轮廓"""
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for c in contours[:25]:
        area = cv2.contourArea(c)
        if area < 0.02 * edges.shape[0] * edges.shape[1]:
            # 相对于图像太小
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            pts = approx.reshape(4, 2)
            return pts

    # 回退：在最大轮廓上使用minAreaRect
    c = contours[0]
    rect = cv2.minAreaRect(c)
    box = cv2.boxPoints(rect)
    return box.astype(np.float32)


def detect_quad(image_bgr: np.ndarray, max_dim: int = 1600) -> np.ndarray:
    """检测图像中的四边形。返回原始尺度的4个点"""
    h, w = image_bgr.shape[:2]
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        small = cv2.resize(
            image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
        )
    else:
        small = image_bgr.copy()

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # 减少眩光影响：使用CLAHE + 模糊
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # 两遍边缘检测：Canny然后形态学闭运算
    v = np.median(gray)
    lower = int(max(0, 0.66 * v))
    upper = int(min(255, 1.33 * v))
    edges = cv2.Canny(gray, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    edges = cv2.dilate(edges, kernel, iterations=1)

    quad = quad_from_contours(edges)

    # 对背光/低对比度边框的回退处理：按饱和度/亮度分割。
    # 当板子是大的彩色区域且背景较暗时效果很好。
    if quad is None:
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1]
        vch = hsv[:, :, 2]
        # 使用Otsu在组合信号上进行归一化和阈值处理
        combo = cv2.addWeighted(s, 0.7, vch, 0.3, 0)
        combo = cv2.GaussianBlur(combo, (7, 7), 0)
        _, mask = cv2.threshold(combo, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel2, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel2, iterations=1)
        quad = quad_from_contours(mask)

    if quad is None:
        raise RuntimeError("未能检测到矩形")

    # 映射回原始尺度
    quad = quad / scale
    return quad.astype(np.float32)


def warp_perspective(image_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """对图像进行透视变换，得到矩形校正后的图像"""
    quad = order_points(quad)
    (tl, tr, br, bl) = quad

    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(round(max(widthA, widthB)))

    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(round(max(heightA, heightB)))

    maxWidth = max(maxWidth, 1)
    maxHeight = max(maxHeight, 1)

    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(quad, dst)
    warped = cv2.warpPerspective(
        image_bgr, M, (maxWidth, maxHeight), flags=cv2.INTER_CUBIC
    )
    return warped


def draw_preview(image_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """在图像上绘制检测到的四边形作为预览"""
    overlay = image_bgr.copy()
    quad_i = order_points(quad).astype(int)
    cv2.polylines(overlay, [quad_i], isClosed=True, color=(0, 255, 0), thickness=8)
    for x, y in quad_i:
        cv2.circle(overlay, (int(x), int(y)), 18, (0, 255, 0), -1)
    return overlay


def collect_inputs(in_dir: Optional[str], inputs: List[str]) -> List[str]:
    """收集输入文件路径"""
    paths: List[str] = []
    if in_dir:
        # 目录中所有jpg/jpeg文件
        paths.extend(sorted(glob.glob(os.path.join(in_dir, "*.jpg"))))
        paths.extend(sorted(glob.glob(os.path.join(in_dir, "*.jpeg"))))
        paths.extend(sorted(glob.glob(os.path.join(in_dir, "*.JPG"))))
        paths.extend(sorted(glob.glob(os.path.join(in_dir, "*.JPEG"))))
    for p in inputs:
        paths.append(p)
    # 去重并检查存在性
    uniq = []
    seen = set()
    for p in paths:
        ap = os.path.abspath(p)
        if ap in seen:
            continue
        if os.path.exists(ap):
            uniq.append(ap)
            seen.add(ap)
    return uniq


def main() -> int:
    """主函数"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", default=None, help="包含图像的目录")
    ap.add_argument("--inputs", nargs="*", default=[], help="显式图像路径")
    ap.add_argument("--out_dir", required=True, help="输出目录")
    ap.add_argument("--max_dim", type=int, default=1600, help="检测的最大尺寸")
    args = ap.parse_args()

    paths = collect_inputs(args.in_dir, args.inputs)
    if not paths:
        raise SystemExit("未找到输入图像")

    preview_dir = os.path.join(args.out_dir, "preview")
    rect_dir = os.path.join(args.out_dir, "rectified")
    os.makedirs(preview_dir, exist_ok=True)
    os.makedirs(rect_dir, exist_ok=True)

    results = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            logger.warning(f"[警告] 无法读取：{p}")
            continue

        try:
            quad = detect_quad(img, max_dim=args.max_dim)
            prev = draw_preview(img, quad)
            rect = warp_perspective(img, quad)
        except Exception as e:
            logger.error(f"[错误] {os.path.basename(p)}: {e}")
            continue

        base = os.path.basename(p)
        decoded = decode_u_hash(os.path.splitext(base)[0])
        safe = decoded

        prev_path = os.path.join(preview_dir, f"{safe}_preview.jpg")
        rect_path = os.path.join(rect_dir, f"{safe}_rectified.jpg")

        # 高质量写入
        cv2.imwrite(prev_path, prev, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        cv2.imwrite(rect_path, rect, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        results.append((p, prev_path, rect_path))
        logger.info(f"[完成] {base} -> {os.path.basename(rect_path)}")

    if not results:
        raise SystemExit("没有图像被成功处理")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
