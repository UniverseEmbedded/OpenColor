"""SVG工具模块 - 提供SVG生成和转换功能"""


def _mm_ring_to_px_coords(ring_coords, *, mm_per_px_x: float, mm_per_px_y: float, pixel_h: int):
    """将毫米坐标转换为像素坐标

    将几何坐标（毫米）转换为图像坐标（像素），
    Y轴翻转以匹配图像坐标系（原点在左上角）

    Args:
        ring_coords: 环坐标列表 [(x, y), ...]
        mm_per_px_x: X方向每像素毫米数
        mm_per_px_y: Y方向每像素毫米数
        pixel_h: 图像高度（像素）

    Returns:
        像素坐标列表 [(px, py), ...]
    """
    pts = list(ring_coords)
    # 移除重复的闭合点
    if len(pts) >= 2 and (pts[0][0] == pts[-1][0]) and (pts[0][1] == pts[-1][1]):
        pts = pts[:-1]
    out = []
    for mx, my in pts:
        px_x = float(mx) / float(mm_per_px_x)
        px_y = float(pixel_h) - (float(my) / float(mm_per_px_y))
        out.append((px_x, px_y))
    return out


def _iter_polygons(geom):
    """迭代几何体中的所有多边形

    支持Polygon、MultiPolygon和GeometryCollection类型

    Args:
        geom: Shapely几何对象

    Returns:
        多边形列表
    """
    if geom is None:
        return []
    gt = getattr(geom, "geom_type", None)
    if gt == "Polygon":
        return [geom]
    if gt == "MultiPolygon":
        return list(getattr(geom, "geoms", []) or [])
    if gt == "GeometryCollection":
        out = []
        for g in list(getattr(geom, "geoms", []) or []):
            out.extend(_iter_polygons(g))
        return out
    return []


def _mm_geom_to_vtracer_tool_svg_text(geom, *, board_mm: float, pixel_w: int, pixel_h: int) -> str:
    """将几何体转换为vtracer工具SVG文本

    将Shapely几何对象转换为SVG路径字符串，用于vtracer工具处理

    Args:
        geom: Shapely几何对象
        board_mm: 板尺寸（毫米）
        pixel_w: 输出图像宽度（像素）
        pixel_h: 输出图像高度（像素）

    Returns:
        SVG文本字符串
    """
    mm_per_px_x = float(board_mm) / float(pixel_w)
    mm_per_px_y = float(board_mm) / float(pixel_h)

    subpaths = []
    for poly in _iter_polygons(geom):
        if poly is None or getattr(poly, "is_empty", True):
            continue

        # 处理外边界
        outer = _mm_ring_to_px_coords(poly.exterior.coords, mm_per_px_x=mm_per_px_x, mm_per_px_y=mm_per_px_y, pixel_h=int(pixel_h))
        if len(outer) >= 3:
            d = [f"M {outer[0][0]:.3f} {outer[0][1]:.3f}"]
            for x, y in outer[1:]:
                d.append(f"L {x:.3f} {y:.3f}")
            d.append("Z")
            subpaths.append(" ".join(d))

        # 处理内孔
        for hole in list(getattr(poly, "interiors", []) or []):
            inner = _mm_ring_to_px_coords(hole.coords, mm_per_px_x=mm_per_px_x, mm_per_px_y=mm_per_px_y, pixel_h=int(pixel_h))
            if len(inner) < 3:
                continue
            d = [f"M {inner[0][0]:.3f} {inner[0][1]:.3f}"]
            for x, y in inner[1:]:
                d.append(f"L {x:.3f} {y:.3f}")
            d.append("Z")
            subpaths.append(" ".join(d))

    d_attr = " ".join(subpaths)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(pixel_w)}" height="{int(pixel_h)}" viewBox="0 0 {int(pixel_w)} {int(pixel_h)}">'
        f'<path fill="#000000" d="{d_attr}"/>'
        f"</svg>"
    )
    return svg
