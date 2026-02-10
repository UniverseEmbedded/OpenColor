#!/usr/bin/env python3

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# bmp_map4stl_nooverlap_plus.py
# 位图 -> 4个STL实体（R,G,B,W），使用矢量区域提取（无堆叠，无重叠）。
# 相比原版的改进：
# - 修复：mask_to_polygon不再丢弃额外外轮廓；返回MultiPolygon
# - 速度：轮廓提取前对每个区域进行bbox裁剪
# - 调试：可选的4色分配调试PNG

import argparse
import json
import os
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageFilter

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import trimesh  # pip install trimesh
# trimesh挤压的三角剖分引擎：pip install mapbox_earcut

# pip install scikit-image scikit-learn
from skimage.measure import find_contours  # type: ignore
from sklearn.cluster import MiniBatchKMeans  # type: ignore


# ---------------------------
# 辅助函数
# ---------------------------

def srgb_to_linear01(x: np.ndarray) -> np.ndarray:
    a = 0.055
    return np.where(x <= 0.04045, x / 12.92, ((x + a) / (1 + a)) ** 2.4)

def classify_rgba_to_rgbw_nearest(rgb255: Tuple[int, int, int]) -> str:
    # 在线性RGB中最近
    pal = {
        "R": (255, 0, 0),
        "G": (0, 255, 0),
        "B": (0, 0, 255),
        "W": (255, 255, 255),
    }
    rgb = np.array(rgb255, dtype=np.float32) / 255.0
    rgb_lin = srgb_to_linear01(rgb)
    keys = ["R", "G", "B", "W"]
    pal_lin = srgb_to_linear01(np.array([pal[k] for k in keys], dtype=np.float32) / 255.0)
    d2 = np.sum((pal_lin - rgb_lin[None, :]) ** 2, axis=1)
    return keys[int(np.argmin(d2))]

def connected_components_4n(mask: np.ndarray) -> np.ndarray:
    # 返回标签0..K，0表示背景
    H, W = mask.shape
    lbl = np.zeros((H, W), dtype=np.int32)
    cur = 0
    stack: List[Tuple[int, int]] = []
    for y in range(H):
        for x in range(W):
            if not mask[y, x] or lbl[y, x] != 0:
                continue
            cur += 1
            lbl[y, x] = cur
            stack.append((y, x))
            while stack:
                yy, xx = stack.pop()
                for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                    ny, nx = yy+dy, xx+dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and lbl[ny, nx] == 0:
                        lbl[ny, nx] = cur
                        stack.append((ny, nx))
    return lbl

def build_region_adjacency(region_id: np.ndarray, n_regions: int) -> List[List[int]]:
    H, W = region_id.shape
    adj = [set() for _ in range(n_regions + 1)]
    # 4邻域边界邻接
    for y in range(H):
        for x in range(W):
            a = region_id[y, x]
            if a == 0:
                continue
            if x + 1 < W:
                b = region_id[y, x + 1]
                if b != 0 and b != a:
                    adj[a].add(b); adj[b].add(a)
            if y + 1 < H:
                b = region_id[y + 1, x]
                if b != 0 and b != a:
                    adj[a].add(b); adj[b].add(a)
    return [sorted(list(s)) for s in adj]

def dsatur_4color(adj: List[List[int]], n_regions: int) -> Dict[int, int]:
    # DSATUR图着色，4色（0..3）
    colors = {i: -1 for i in range(1, n_regions + 1)}
    sat = {i: 0 for i in range(1, n_regions + 1)}
    deg = {i: len(adj[i]) for i in range(1, n_regions + 1)}

    def sat_deg(i: int) -> Tuple[int, int]:
        return (sat[i], deg[i])

    while True:
        uncolored = [i for i in range(1, n_regions + 1) if colors[i] < 0]
        if not uncolored:
            break
        v = max(uncolored, key=sat_deg)

        used = set()
        for u in adj[v]:
            c = colors[u]
            if c >= 0:
                used.add(c)

        # 选择最小的可用颜色
        for c in range(4):
            if c not in used:
                colors[v] = c
                break
        if colors[v] < 0:
            # 回退（应该很少见）
            colors[v] = 0

        # 更新邻居的饱和度
        for u in adj[v]:
            if colors[u] >= 0:
                continue
            neighbor_colors = set(colors[w] for w in adj[u] if colors[w] >= 0)
            sat[u] = len(neighbor_colors)

    return colors

def _rings_from_mask(mask: np.ndarray, simplify_tol: float) -> List[np.ndarray]:
    # 在0.5处的轮廓，返回(x,y)像素坐标中的Nx2数组列表
    rings = []
    for c in find_contours(mask.astype(np.uint8), 0.5):
        if c.shape[0] < 6:
            continue
        # find_contours返回(row, col)浮点数；转换为(x,y)
        pts = np.stack([c[:, 1], c[:, 0]], axis=1)
        # 闭合
        if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
            pts = np.vstack([pts, pts[0]])
        # shapely简化前的基本点跳过（便宜）
        if simplify_tol > 0 and pts.shape[0] > 2000:
            step = max(1, int(simplify_tol))
            pts = pts[::step]
            if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
                pts = np.vstack([pts, pts[0]])
        rings.append(pts)
    return rings

def mask_to_multipolygon(mask: np.ndarray, min_area: float) -> MultiPolygon:
    """
    将二值掩码转换为（Multi）Polygon，不静默丢弃额外组件。
    策略：
      - 提取所有轮廓环
      - 为环构建多边形
      - 通过包含关系分配孔洞
      - 返回MultiPolygon
    """
    rings = _rings_from_mask(mask, simplify_tol=0.0)
    polys = []
    ring_infos = []

    for pts in rings:
        p = Polygon(pts)
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty or p.area < min_area:
            continue
        ring_infos.append((p, pts))

    if not ring_infos:
        return MultiPolygon([])

    # 按面积降序排序
    ring_infos.sort(key=lambda t: t[0].area, reverse=True)

    outers: List[Tuple[Polygon, np.ndarray]] = []
    holes_map: Dict[int, List[np.ndarray]] = {}

    for p, pts in ring_infos:
        container_idx = None
        container_area = None
        for i, (op, _) in enumerate(outers):
            if op.contains(p):
                if container_area is None or op.area < container_area:
                    container_idx = i
                    container_area = op.area
        if container_idx is None:
            outers.append((p, pts))
        else:
            holes_map.setdefault(container_idx, []).append(pts)

    out_polys = []
    for i, (op, opts) in enumerate(outers):
        holes = []
        for hpts in holes_map.get(i, []):
            holes.append([(float(x), float(y)) for x, y in hpts])
        pp = Polygon([(float(x), float(y)) for x, y in opts], holes)
        if not pp.is_valid:
            pp = pp.buffer(0)
        if pp.is_empty or pp.area < min_area:
            continue
        out_polys.append(pp)

    if not out_polys:
        return MultiPolygon([])
    g = unary_union(out_polys)
    if g.is_empty:
        return MultiPolygon([])
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    return g

def extrude_geom_to_mesh(geom, height_mm: float, pixel_mm: float):
    if geom is None or geom.is_empty:
        return None
    # 将像素坐标转换为毫米
    # shapely通过乘以坐标手动缩放
    def scale_poly(p: Polygon) -> Polygon:
        ext = [(x * pixel_mm, y * pixel_mm) for x, y in p.exterior.coords]
        holes = [[(x * pixel_mm, y * pixel_mm) for x, y in r.coords] for r in p.interiors]
        q = Polygon(ext, holes)
        if not q.is_valid:
            q = q.buffer(0)
        return q

    if isinstance(geom, Polygon):
        geom_mm = scale_poly(geom)
    else:
        parts = []
        for p in geom.geoms:
            parts.append(scale_poly(p))
        geom_mm = unary_union(parts).buffer(0)

    try:
        return trimesh.creation.extrude_polygon(geom_mm, height_mm)
    except Exception:
        return None

def save_debug_png(color_map: np.ndarray, out_path: str):
    # color_map是HxW，值0..3
    # 0:R 1:G 2:B 3:W（仅用于可视化）
    palette = np.array([
        [255, 0, 0],
        [0, 255, 0],
        [0, 0, 255],
        [255, 255, 255],
    ], dtype=np.uint8)
    img = palette[color_map]
    Image.fromarray(img, mode="RGB").save(out_path)


# ---------------------------
# 主程序
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="位图 -> 4个STL（R,G,B,W），按矢量区域（无堆叠，无重叠）。")
    ap.add_argument("image", help="输入位图（png/jpg）")
    ap.add_argument("--outdir", default="out_bmp4stl", help="输出目录")
    ap.add_argument("--name", default=None, help="基础名称")
    ap.add_argument("--width-mm", type=float, default=80.0, help="目标物理宽度（毫米）")
    ap.add_argument("--pixel-mm", type=float, default=0.5, help="每像素采样大小（毫米）")
    ap.add_argument("--thickness-mm", type=float, default=0.8, help="所有区域的挤压厚度")
    ap.add_argument("--alpha-threshold", type=int, default=1, help="alpha <= 阈值视为空")
    ap.add_argument("--blur", type=float, default=0.0, help="量化前高斯模糊半径（像素）")
    ap.add_argument("--k", type=int, default=16, help="区域提取前的kmeans调色板大小")
    ap.add_argument("--min-area-mm2", type=float, default=0.2, help="丢弃小于此面积（平方毫米）的岛屿")
    ap.add_argument("--debug-png", action="store_true", help="写入4色分配的调试PNG")
    ap.add_argument("--export-metadata", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    base = args.name or os.path.splitext(os.path.basename(args.image))[0]

    im = Image.open(args.image).convert("RGBA")

    if args.blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(radius=args.blur))

    # 通过pixel-mm调整大小到目标像素宽度
    target_w_px = max(1, int(round(args.width_mm / args.pixel_mm)))
    w0, h0 = im.size
    target_h_px = max(1, int(round(target_w_px * (h0 / w0))))
    im = im.resize((target_w_px, target_h_px), resample=Image.Resampling.LANCZOS)

    arr = np.asarray(im, dtype=np.uint8)  # H W 4
    H, W = arr.shape[0], arr.shape[1]

    alpha = arr[:, :, 3]
    valid = alpha > args.alpha_threshold

    rgb = arr[:, :, :3].reshape(-1, 3).astype(np.float32)
    valid_flat = valid.reshape(-1)
    rgb_valid = rgb[valid_flat]

    if rgb_valid.shape[0] == 0:
        logger.info("所有像素都是透明的；无事可做。")
        return

    # kmeans量化
    k = max(2, int(args.k))
    km = MiniBatchKMeans(n_clusters=min(k, rgb_valid.shape[0]), random_state=0, n_init="auto")
    km.fit(rgb_valid)
    centers = km.cluster_centers_.astype(np.float32)  # K x 3
    labels = np.full((H * W,), -1, dtype=np.int32)
    labels[valid_flat] = km.predict(rgb_valid)

    # 将kmeans中心映射到RGBW（最近）
    center_to_rgbw = [classify_rgba_to_rgbw_nearest(tuple(map(int, c))) for c in centers]

    # 为每个（kmeans标签）构建区域掩码，然后分割CC到区域
    region_id = np.zeros((H, W), dtype=np.int32)
    rid = 0
    rid_to_rgbw: Dict[int, str] = {}
    rid_to_center_rgb255: Dict[int, Tuple[int, int, int]] = {}

    for li in range(centers.shape[0]):
        m = (labels.reshape(H, W) == li)
        if not m.any():
            continue
        cc = connected_components_4n(m)
        ncc = int(cc.max())
        for cci in range(1, ncc + 1):
            rid += 1
            region_id[cc == cci] = rid
            rid_to_rgbw[rid] = center_to_rgbw[li]
            c = centers[li]
            rid_to_center_rgb255[rid] = (int(round(float(c[0]))), int(round(float(c[1]))), int(round(float(c[2]))))

    n_regions = rid
    if n_regions == 0:
        logger.info("未找到区域。")
        return

    # 邻接和4色图着色以确保导出时无重叠
    adj = build_region_adjacency(region_id, n_regions)
    colors = dsatur_4color(adj, n_regions)  # rid -> 0..3

    # 构建4个掩码（颜色类），然后对每个区域用bbox裁剪进行矢量化
    # 我们将在4个输出通道中累积多边形
    out_polys: List[List[Polygon]] = [[], [], [], []]

    min_area_px2 = args.min_area_mm2 / (args.pixel_mm ** 2)

    # 为了速度：为每个rid预计算bbox
    ys, xs = np.where(region_id > 0)
    # 回退：直接计算每个rid（简单且稳健）
    regions_meta = []
    for r in range(1, n_regions + 1):
        yy, xx = np.where(region_id == r)
        if yy.size == 0:
            continue
        y0, y1 = int(yy.min()), int(yy.max()) + 1
        x0, x1 = int(xx.min()), int(xx.max()) + 1
        # 为轮廓稳定性填充2像素
        pad = 2
        y0p = max(0, y0 - pad); y1p = min(H, y1 + pad)
        x0p = max(0, x0 - pad); x1p = min(W, x1 + pad)

        sub = (region_id[y0p:y1p, x0p:x1p] == r)
        if sub.sum() < 4:
            continue

        geom = mask_to_multipolygon(sub, min_area=min_area_px2)
        if geom.is_empty:
            continue

        # 将几何体移回完整图像坐标
        shifted_parts = []
        for p in geom.geoms:
            ext = [(x + x0p, y + y0p) for x, y in p.exterior.coords]
            holes = [[(x + x0p, y + y0p) for x, y in ring.coords] for ring in p.interiors]
            q = Polygon(ext, holes)
            if not q.is_valid:
                q = q.buffer(0)
            if q.is_empty or q.area < min_area_px2:
                continue
            shifted_parts.append(q)

        if not shifted_parts:
            continue

        g = unary_union(shifted_parts).buffer(0)
        cidx = int(colors[r])

        regions_meta.append(
            {
                "region_id": int(r),
                "center_rgb255": [int(rid_to_center_rgb255[r][0]), int(rid_to_center_rgb255[r][1]), int(rid_to_center_rgb255[r][2])],
                "class_rgbw": str(rid_to_rgbw[r]),
                "channel": int(cidx),
                "bbox_px": [int(x0), int(y0), int(x1), int(y1)],
            }
        )

        if isinstance(g, Polygon):
            out_polys[cidx].append(g)
        else:
            out_polys[cidx].extend(list(g.geoms))

    # 每个输出通道的并集，然后强制移除重叠（硬保证）
    unions = []
    for i in range(4):
        if out_polys[i]:
            unions.append(unary_union(out_polys[i]).buffer(0))
        else:
            unions.append(None)

    for i in range(4):
        if unions[i] is None or unions[i].is_empty:
            continue
        others = [unions[j] for j in range(4) if j != i and unions[j] is not None and not unions[j].is_empty]
        if others:
            unions[i] = unions[i].difference(unary_union(others)).buffer(0)

    # 4色分配的调试PNG
    if args.debug_png:
        cmap = np.zeros((H, W), dtype=np.uint8)
        for r in range(1, n_regions + 1):
            cmap[region_id == r] = np.uint8(colors[r])
        dbg = os.path.join(args.outdir, f"{base}_debug4color.png")
        save_debug_png(cmap, dbg)
        logger.info(f"已写入 {dbg}")

    # 导出4个STL；为方便起见，将0..3映射到R/G/B/W
    # 这些STL通道只是"非重叠分区"——您可以将它们分配给任何4个AMS插槽进行测试。
    ch_names = ["A", "B", "C", "D"]  # 中性命名；避免在此阶段暗示真正的RGBW
    exported: Dict[str, str] = {}
    for i in range(4):
        g = unions[i]
        if g is None or g.is_empty:
            logger.info(f"{ch_names[i]}: 空")
            continue
        mesh = extrude_geom_to_mesh(g, height_mm=args.thickness_mm, pixel_mm=args.pixel_mm)
        if mesh is None:
            logger.error(f"{ch_names[i]}: 挤压失败（earcut安装？无效几何？）")
            continue
        out = os.path.join(args.outdir, f"{base}_{ch_names[i]}.stl")
        mesh.export(out)
        exported[ch_names[i]] = os.path.abspath(out)
        logger.info(f"{ch_names[i]}: 已写入 {out}")

    if args.export_metadata:
        meta = {
            "schema_version": 1,
            "script": os.path.basename(__file__),
            "input": {"image": os.path.abspath(args.image)},
            "params": {
                "outdir": os.path.abspath(args.outdir),
                "name": args.name,
                "width_mm": float(args.width_mm),
                "pixel_mm": float(args.pixel_mm),
                "thickness_mm": float(args.thickness_mm),
                "alpha_threshold": int(args.alpha_threshold),
                "blur": float(args.blur),
                "k": int(args.k),
                "min_area_mm2": float(args.min_area_mm2),
                "debug_png": bool(args.debug_png),
            },
            "regions": regions_meta,
            "outputs": exported,
        }
        meta_path = os.path.join(args.outdir, f"{base}_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        logger.info(f"元数据：已写入 {meta_path}")

    logger.info("注意：此脚本将区域分区为4个非重叠STL通道用于测试流程和几何。")
    logger.info("      它尚未实现RGBW每层堆叠；旨在作为几何流程验证器。")

if __name__ == "__main__":
    main()
