"""投影分析模块 - 提供色板网格检测和校准功能

用于分析色板图像的梯度投影，估计网格间距和偏移量，辅助色板校准。
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

from calibrate_color_board_io import _write_png


def gradient_projections(warped_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """计算图像的梯度投影
    
    使用Sobel算子计算图像梯度，然后分别在水平和垂直方向投影，
    用于检测色板中的网格线位置。
    
    参数:
        warped_bgr: 校正后的BGR图像
        
    返回:
        (列投影, 行投影) - 两个一维数组
    """
    # 转换为灰度图
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # 计算水平和垂直梯度
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    # 计算梯度幅值
    mag = np.sqrt(gx * gx + gy * gy)
    # 在行列方向求平均
    col_sum = mag.mean(axis=0)
    row_sum = mag.mean(axis=1)
    return col_sum, row_sum


def estimate_pitch_fft(signal: np.ndarray, expected_pitch: float, search_frac: float = 0.35) -> float:
    """使用FFT估计信号的主周期（网格间距）
    
    通过频域分析估计一维信号的周期，在预期周期附近搜索，
    用于检测色板网格的像素间距。
    
    参数:
        signal: 一维信号数组
        expected_pitch: 预期周期（像素）
        search_frac: 搜索范围比例，默认在预期值的±35%范围内搜索
        
    返回:
        估计的周期（像素）
    """
    n = int(signal.shape[0])
    if n < 32 or expected_pitch <= 2:
        return float(expected_pitch)

    # 预处理：去均值和加窗
    x = signal.astype(np.float32)
    x = x - float(np.mean(x))
    x = x * np.hanning(n).astype(np.float32)

    # FFT变换
    spec = np.fft.rfft(x)
    power = (spec.real * spec.real + spec.imag * spec.imag).astype(np.float64)
    power[0] = 0.0  # 去除直流分量

    # 计算搜索频率范围
    p0 = float(expected_pitch)
    pmin = max(4.0, p0 * (1.0 - search_frac))
    pmax = min(float(n / 2), p0 * (1.0 + search_frac))

    fmin = 1.0 / pmax
    fmax = 1.0 / pmin

    # 在频率范围内搜索峰值
    freqs = np.fft.rfftfreq(n, d=1.0)
    lo = int(np.searchsorted(freqs, fmin, side="left"))
    hi = int(np.searchsorted(freqs, fmax, side="right"))
    hi = max(hi, lo + 1)

    idx = lo + int(np.argmax(power[lo:hi]))
    f = float(freqs[idx]) if idx < freqs.shape[0] else 0.0
    if f <= 0:
        return float(expected_pitch)

    # 周期 = 1/频率
    pitch = 1.0 / f
    pitch = float(np.clip(pitch, pmin, pmax))
    return pitch


def draw_projection_debug(signal: np.ndarray, pitch: float, out_path: Path, title: str) -> None:
    """绘制投影调试图像
    
    使用OpenCV绘制一维信号的波形图，并标注估计的周期位置。
    不依赖matplotlib，适合无GUI环境。
    
    参数:
        signal: 一维信号数组
        pitch: 估计的周期
        out_path: 输出图像路径
        title: 图像标题
    """
    w = 900
    h = 220
    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    # 归一化信号
    sig = signal.astype(np.float32)
    sig = sig - sig.min()
    if sig.max() > 1e-6:
        sig = sig / sig.max()

    # 重采样到画布宽度
    xs = np.linspace(0, sig.shape[0] - 1, w).astype(np.float32)
    xi = np.floor(xs).astype(int)
    xi2 = np.clip(xi + 1, 0, sig.shape[0] - 1)
    t = xs - xi
    ys = (1 - t) * sig[xi] + t * sig[xi2]
    ys = (h - 30) - (ys * (h - 60))

    # 绘制波形
    pts = np.stack([np.arange(w), ys.astype(np.int32)], axis=1).reshape(-1, 1, 2)
    cv2.polylines(canvas, [pts], False, (0, 255, 0), 1)

    # 添加标题
    cv2.putText(canvas, f"{title}  pitch_est={pitch:.2f}px", (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    # 绘制周期标记线
    if pitch > 5:
        step = max(1, int(round(pitch * (w / max(1, sig.shape[0])))))
        x = 0
        while x < w:
            cv2.line(canvas, (x, h - 25), (x, h - 15), (255, 255, 255), 1)
            x += step

    _write_png(out_path, canvas)


def refine_dxdy(signal_col: np.ndarray, signal_row: np.ndarray, nx: int, ny: int, pitch_x: float, pitch_y: float, search_steps: int = 61) -> Tuple[float, float, float]:
    """精细化网格偏移量(dx, dy)估计
    
    通过在可能的偏移范围内搜索，找到使网格线位置投影能量最大的偏移量。
    
    参数:
        signal_col: 列方向投影信号
        signal_row: 行方向投影信号
        nx: 水平方向网格数量
        ny: 垂直方向网格数量
        pitch_x: 水平方向网格间距
        pitch_y: 垂直方向网格间距
        search_steps: 搜索步数
        
    返回:
        (最优dx, 最优dy, 归一化得分)
    """
    col = signal_col.astype(np.float64)
    row = signal_row.astype(np.float64)

    def score_dx(dx: float) -> float:
        """计算给定dx的得分（网格线位置的能量和）"""
        s = 0.0
        for i in range(nx + 1):
            x = int(round(dx + i * pitch_x))
            if 0 <= x < col.shape[0]:
                s += float(col[x])
        return s

    def score_dy(dy: float) -> float:
        """计算给定dy的得分（网格线位置的能量和）"""
        s = 0.0
        for j in range(ny + 1):
            y = int(round(dy + j * pitch_y))
            if 0 <= y < row.shape[0]:
                s += float(row[y])
        return s

    # 在半个周期范围内搜索
    half_x = 0.5 * pitch_x
    half_y = 0.5 * pitch_y
    cands_x = np.linspace(-half_x, half_x, search_steps)
    cands_y = np.linspace(-half_y, half_y, search_steps)

    # 评估所有候选偏移
    sx = np.array([score_dx(dx) for dx in cands_x], dtype=np.float64)
    sy = np.array([score_dy(dy) for dy in cands_y], dtype=np.float64)

    best_dx = float(cands_x[int(np.argmax(sx))])
    best_dy = float(cands_y[int(np.argmax(sy))])

    # 计算归一化得分
    best = float(np.max(sx) + np.max(sy))
    base = float(col.mean() * (nx + 1) + row.mean() * (ny + 1) + 1e-6)
    score_norm = best / base
    return best_dx, best_dy, score_norm
