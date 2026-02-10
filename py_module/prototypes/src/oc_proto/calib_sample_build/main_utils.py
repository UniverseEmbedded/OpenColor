"""样本构建模块 - 工具函数

本模块提供图像旋转、透视变换、颜色评分等工具函数
"""

import cv2
import numpy as np


def _apply_rotation(img_bgr: np.ndarray, rotation_count: int) -> np.ndarray:
    """应用旋转"""
    rotation_count = int(rotation_count) % 4
    if rotation_count == 1:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
    if rotation_count == 2:
        return cv2.rotate(img_bgr, cv2.ROTATE_180)
    if rotation_count == 3:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img_bgr


def _perspective_warp_bgr(img_bgr: np.ndarray, points, dst_size: int, *, inset_mode: bool, rows: int, cols: int) -> np.ndarray:
    """透视变换"""
    if inset_mode:
        cell_w = float(dst_size) / float(cols)
        cell_h = float(dst_size) / float(rows)
        dst_pts = np.array(
            [
                [cell_w, cell_h],
                [float(dst_size) - cell_w, cell_h],
                [float(dst_size) - cell_w, float(dst_size) - cell_h],
                [cell_w, float(dst_size) - cell_h],
            ],
            dtype=np.float32,
        )
    else:
        dst_pts = np.array(
            [[0.0, 0.0], [float(dst_size), 0.0], [float(dst_size), float(dst_size)], [0.0, float(dst_size)]],
            dtype=np.float32,
        )

    src_pts = np.array(points, dtype=np.float32)
    m = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return cv2.warpPerspective(
        img_bgr,
        m,
        (int(dst_size), int(dst_size)),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _corner_color_score(bgr: np.ndarray, expect: str) -> float:
    """计算角落颜色分数"""
    b = float(bgr[0])
    g = float(bgr[1])
    r = float(bgr[2])
    if expect == "Red":
        return r - max(g, b)
    if expect == "Blue":
        return b - max(r, g)
    if expect == "Yellow":
        return (r + g) * 0.5 - b
    if expect == "White":
        return (r + g + b) / 3.0
    if expect == "Black":
        return 255.0 - (r + g + b) / 3.0
    return 0.0


def _score_warped_corners(warped_bgr: np.ndarray, *, rows: int, cols: int, corner_expect: dict[str, str]) -> float:
    """评分变换后的角落"""
    h, w = warped_bgr.shape[:2]
    cell_w = float(w) / float(cols)
    cell_h = float(h) / float(rows)
    score = 0.0
    for (rr, cc), expect in corner_expect.items():
        cx = int((float(cc) + 0.5) * cell_w)
        cy = int((float(rr) + 0.5) * cell_h)
        x0 = max(0, cx - 2)
        x1 = min(w, cx + 3)
        y0 = max(0, cy - 2)
        y1 = min(h, cy + 3)
        patch = warped_bgr[y0:y1, x0:x1]
        if patch.size == 0:
            continue
        mean_bgr = patch.reshape(-1, 3).mean(axis=0)
        score += _corner_color_score(mean_bgr, expect)
    return float(score)


def _choose_inset_mode(img_bgr: np.ndarray, points, *, dst_size: int, rotation_count: int, rows: int, cols: int) -> bool:
    """选择内嵌模式"""
    warped_inset = _apply_rotation(
        _perspective_warp_bgr(img_bgr, points, dst_size, inset_mode=True, rows=rows, cols=cols),
        rotation_count,
    )
    warped_full = _apply_rotation(
        _perspective_warp_bgr(img_bgr, points, dst_size, inset_mode=False, rows=rows, cols=cols),
        rotation_count,
    )

    expect_no_flip = {
        (0, 0): "Blue",
        (0, cols - 1): "Red",
        (rows - 1, cols - 1): "Blue",
        (rows - 1, 0): "Yellow",
    }
    expect_flip = {
        (0, 0): "Red",
        (0, cols - 1): "Blue",
        (rows - 1, cols - 1): "Yellow",
        (rows - 1, 0): "Blue",
    }

    s_inset = max(
        _score_warped_corners(warped_inset, rows=rows, cols=cols, corner_expect=expect_no_flip),
        _score_warped_corners(warped_inset, rows=rows, cols=cols, corner_expect=expect_flip),
    )
    s_full = max(
        _score_warped_corners(warped_full, rows=rows, cols=cols, corner_expect=expect_no_flip),
        _score_warped_corners(warped_full, rows=rows, cols=cols, corner_expect=expect_flip),
    )
    return bool(s_inset >= s_full)


def parse_roi(roi, cell_w, cell_h):
    """解析ROI
    
    roi supports:
      - None: returns central 60% box
      - [rx, ry, rw, rh] normalized in [0,1] within cell
      - [x0, y0, x1, y1] absolute pixels within cell
    Returns pixel box (x0,y0,x1,y1) within cell.
    """
    if roi is None:
        margin = 0.2
        x0 = int(cell_w * margin)
        y0 = int(cell_h * margin)
        x1 = int(cell_w * (1 - margin))
        y1 = int(cell_h * (1 - margin))
        return x0, y0, x1, y1

    if not (isinstance(roi, (list, tuple)) and len(roi) == 4):
        return parse_roi(None, cell_w, cell_h)

    if all(isinstance(x, (int, float)) for x in roi):
        if max(roi) <= 1.0:
            rx, ry, rw, rh = roi
            x0 = int(cell_w * rx)
            y0 = int(cell_h * ry)
            x1 = int(cell_w * (rx + rw))
            y1 = int(cell_h * (ry + rh))
            return x0, y0, x1, y1

        x0, y0, x1, y1 = map(int, roi)
        return x0, y0, x1, y1

    return parse_roi(None, cell_w, cell_h)


def sample_cell_mean_rgb(img_bgr, x0, y0, x1, y1):
    """采样单元格平均RGB"""
    roi = img_bgr[y0:y1, x0:x1]
    if roi.size == 0:
        return [0.0, 0.0, 0.0]
    mean_bgr = roi.reshape(-1, 3).mean(axis=0)
    mean_rgb = mean_bgr[::-1]
    return [float(x) for x in mean_rgb]
