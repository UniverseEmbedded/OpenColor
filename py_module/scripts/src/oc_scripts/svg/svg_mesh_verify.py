#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SVG网格验证器 - 将SVG转换为三角形网格并验证几何保真度

本工具用于验证SVG文件的几何保真度，通过将SVG路径三角化后对比原始图形。
支持两种工作模式：
1. triangulate模式：输出三角化后的SVG
2. compare模式：对比两个SVG并生成差异图

使用示例：
  pixi run python svg_mesh_verify.py --in test.svg --out test_tri.svg --tol 0.5
  pixi run python svg_mesh_verify.py --in test.svg --out test_tri_raster.svg --color-mode raster --raster-scale 4
  pixi run python svg_mesh_verify.py --mode compare --ref ref.svg --test test.svg --diff-out diff.png

注意：
- 这不是完整的SVG2渲染器。它针对"几何保真度"检查。
- 最佳视觉匹配模式是：--color-mode paint（复制<defs>并重用绘制字符串）。
"""

from __future__ import annotations

import argparse

import numpy as np
from lxml import etree

from svg_mesh_verify_geom import extract_shapes, rings_to_area_geom, stroke_to_polygons, triangulate_geom
from svg_mesh_verify_raster import (
    compare_images,
    copy_defs,
    make_svg_root_like,
    parse_viewbox,
    render_svg_to_image,
    sample_rgba_bilinear,
    set_opacity_attrs,
    tri_to_pathd,
)



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def main():
    """主函数 - SVG网格验证入口"""
    ap = argparse.ArgumentParser(description="SVG网格验证器")
    ap.add_argument("--mode", choices=["triangulate", "compare"], default="triangulate",
                    help="运行模式：triangulate=输出三角化SVG；compare=光栅化对比并输出loss图")

    ap.add_argument("--in", dest="inp", help="输入SVG路径（triangulate模式必填）")
    ap.add_argument("--out", dest="out", help="输出SVG路径（triangulate模式必填）")
    ap.add_argument("--tol", type=float, default=0.75, help="曲线打平容差（越小三角形越多）")
    ap.add_argument("--no-stroke", action="store_true", help="忽略描边")
    ap.add_argument("--no-fill", action="store_true", help="忽略填充")
    ap.add_argument("--color-mode", choices=["paint", "raster"], default="paint",
                    help="颜色模式：paint=沿用原始paint；raster=渲染成PNG后采样输出纯色三角形")
    ap.add_argument("--raster-scale", type=float, default=4.0, help="raster颜色模式的渲染缩放倍率")
    ap.add_argument("--sample", choices=["centroid", "vertices"], default="centroid",
                    help="raster颜色模式采样方式：centroid=重心；vertices=顶点平均")

    ap.add_argument("--ref", dest="ref_inp", help="参考SVG路径（compare模式必填）")
    ap.add_argument("--test", dest="test_inp", help="待对比SVG路径（compare模式必填）")
    ap.add_argument("--diff-out", dest="diff_out", help="loss分布图输出路径（PNG，compare模式必填）")
    ap.add_argument("--compare-scale", type=float, default=4.0, help="compare模式的渲染缩放倍率")
    ap.add_argument("--bg", choices=["white", "black", "transparent"], default="white",
                    help="compare模式对比时的合成背景：white/black/transparent")
    ap.add_argument("--diff-max", type=float, default=0.10, help="loss映射到全黑的阈值（越小越敏感）")
    ap.add_argument("--diff-gamma", type=float, default=1.0, help="loss图gamma（>1更凸显小差异）")
    args = ap.parse_args()

    if args.mode == "compare":
        if not args.ref_inp or not args.test_inp or not args.diff_out:
            ap.error("compare 模式必须同时提供 --ref / --test / --diff-out")

        try:
            with open(args.ref_inp, "rb") as f:
                ref_bytes = f.read()
        except OSError as e:
            logger.error(f"[错误] 读取参考SVG失败：{args.ref_inp}：{e}")
            raise

        try:
            with open(args.test_inp, "rb") as f:
                test_bytes = f.read()
        except OSError as e:
            logger.error(f"[错误] 读取待对比SVG失败：{args.test_inp}：{e}")
            raise

        parser = etree.XMLParser(remove_comments=False, recover=True)
        try:
            ref_root = etree.fromstring(ref_bytes, parser=parser)
            test_root = etree.fromstring(test_bytes, parser=parser)
        except Exception as e:
            logger.error(f"[错误] 解析SVG失败：{e}")
            raise

        vb_ref = parse_viewbox(ref_root)
        vb_test = parse_viewbox(test_root)
        if (vb_ref.x, vb_ref.y, vb_ref.w, vb_ref.h) != (vb_test.x, vb_test.y, vb_test.w, vb_test.h):
            logger.warning(f"[警告] 两个SVG的viewBox不一致：ref={vb_ref}，test={vb_test}。将以ref为基准渲染尺寸。")

        img_ref = render_svg_to_image(ref_bytes, vb_ref, scale=args.compare_scale)
        img_test = render_svg_to_image(test_bytes, vb_ref, scale=args.compare_scale)
        diff_img, metrics = compare_images(img_ref, img_test, bg=args.bg, diff_max=args.diff_max, diff_gamma=args.diff_gamma)

        try:
            diff_img.save(args.diff_out)
        except OSError as e:
            logger.error(f"[错误] 写入loss分布图失败：{args.diff_out}：{e}")
            raise

        logger.info("[完成] compare结果："
            f"尺寸={int(metrics['width'])}x{int(metrics['height'])} "
            f"MSE={metrics['mse']:.8f} RMSE={metrics['rmse']:.6f} MAE={metrics['mae']:.6f} "
            f"PSNR={metrics['psnr']:.2f}dB P95={metrics['p95']:.6f} MAX={metrics['max']:.6f} "
            f"loss图={args.diff_out}"
        )
        return

    if not args.inp or not args.out:
        ap.error("triangulate 模式必须同时提供 --in / --out")

    try:
        with open(args.inp, "rb") as f:
            svg_bytes = f.read()
    except OSError as e:
        logger.error(f"[错误] 读取输入文件失败：{args.inp}：{e}")
        raise

    try:
        parser = etree.XMLParser(remove_comments=False, recover=True)
        root = etree.fromstring(svg_bytes, parser=parser)
    except Exception as e:
        logger.error(f"[错误] 解析 SVG 失败：{args.inp}：{e}")
        raise

    vb = parse_viewbox(root)
    if vb.w <= 0 or vb.h <= 0:
        raise ValueError(f"viewBox 宽高非法：w={vb.w}, h={vb.h}")

    shapes = extract_shapes(root, tol=args.tol)

    img = None
    to_px = None
    if args.color_mode == "raster":
        img = render_svg_to_image(svg_bytes, vb, scale=args.raster_scale)

        def to_px(pt):
            x, y = pt
            px = (x - vb.x) / vb.w * (img.size[0] - 1)
            py = (y - vb.y) / vb.h * (img.size[1] - 1)
            return px, py

    out_root = make_svg_root_like(root, vb)
    if args.color_mode == "paint":
        copy_defs(root, out_root)

    g_all = etree.SubElement(out_root, "g")
    g_all.set("id", "triangulated")

    tri_count = 0

    def sample_triangle_rgba(a, b, c):
        """采样三角形颜色（RGBA）"""
        assert img is not None
        assert to_px is not None
        if args.sample == "centroid":
            cx = (a[0] + b[0] + c[0]) / 3.0
            cy = (a[1] + b[1] + c[1]) / 3.0
            px, py = to_px((cx, cy))
            return sample_rgba_bilinear(img, px, py)

        cols = []
        for pt in (a, b, c):
            px, py = to_px(pt)
            cols.append(np.array(sample_rgba_bilinear(img, px, py), dtype=float))
        r, gg, bb, aa = tuple(np.mean(cols, axis=0).tolist())
        return float(r), float(gg), float(bb), float(aa)

    def emit_triangle(parent_g, a, b, c, paint):
        """输出三角形到SVG"""
        nonlocal tri_count
        p = etree.SubElement(parent_g, "path")
        p.set("d", tri_to_pathd(a, b, c))

        if args.color_mode == "paint":
            pass
        else:
            p.set("stroke", "none")
            r, gg, bb, aa = sample_triangle_rgba(a, b, c)
            p.set("fill", f"rgb({int(r + 0.5)},{int(gg + 0.5)},{int(bb + 0.5)})")
            if aa < 255.0:
                p.set("fill-opacity", f"{aa / 255.0:.4f}")

        tri_count += 1

    for si, (sh, _m) in enumerate(shapes):
        g = etree.SubElement(g_all, "g")
        g.set("id", f"shape_{si}")

        g_fill = None
        g_stroke = None
        fill_d_parts = None
        stroke_d_parts = None
        if args.color_mode == "paint":
            if sh.fill and sh.fill.lower() != "none":
                g_fill = etree.SubElement(g, "g")
                g_fill.set("stroke", "none")
                g_fill.set("fill", sh.fill)
                set_opacity_attrs(g_fill, sh.opacity, sh.fill_opacity, None)
                fill_d_parts = []
            if sh.stroke and sh.stroke.lower() != "none":
                g_stroke = etree.SubElement(g, "g")
                g_stroke.set("stroke", "none")
                g_stroke.set("fill", sh.stroke)
                set_opacity_attrs(g_stroke, sh.opacity, sh.stroke_opacity, None)
                stroke_d_parts = []

        if not args.no_fill and sh.fill and sh.fill.lower() != "none" and sh.fill_rings:
            area = rings_to_area_geom(sh.fill_rings, sh.fill_rule)
            if area is not None and not area.is_empty:
                verts, tris = triangulate_geom(area)
                for t in tris:
                    a = (float(verts[t[0], 0]), float(verts[t[0], 1]))
                    b = (float(verts[t[1], 0]), float(verts[t[1], 1]))
                    c = (float(verts[t[2], 0]), float(verts[t[2], 1]))
                    if args.color_mode == "paint":
                        assert fill_d_parts is not None
                        fill_d_parts.append(tri_to_pathd(a, b, c))
                        tri_count += 1
                    else:
                        emit_triangle(g, a, b, c, sh.fill)

        if not args.no_stroke and sh.stroke and sh.stroke.lower() != "none" and sh.stroke_lines:
            area = stroke_to_polygons(
                sh.stroke_lines,
                stroke_width=sh.stroke_width,
                linecap=sh.stroke_linecap,
                linejoin=sh.stroke_linejoin,
                miterlimit=sh.stroke_miterlimit,
            )
            if area is not None and not area.is_empty:
                verts, tris = triangulate_geom(area)
                for t in tris:
                    a = (float(verts[t[0], 0]), float(verts[t[0], 1]))
                    b = (float(verts[t[1], 0]), float(verts[t[1], 1]))
                    c = (float(verts[t[2], 0]), float(verts[t[2], 1]))
                    if args.color_mode == "paint":
                        assert stroke_d_parts is not None
                        stroke_d_parts.append(tri_to_pathd(a, b, c))
                        tri_count += 1
                    else:
                        emit_triangle(g, a, b, c, sh.stroke)

        if args.color_mode == "paint":
            if g_fill is not None and fill_d_parts:
                p = etree.SubElement(g_fill, "path")
                p.set("stroke", "none")
                p.set("d", " ".join(fill_d_parts))
            if g_stroke is not None and stroke_d_parts:
                p = etree.SubElement(g_stroke, "path")
                p.set("stroke", "none")
                p.set("d", " ".join(stroke_d_parts))

    svg_out_bytes = etree.tostring(out_root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    try:
        with open(args.out, "wb") as f:
            f.write(svg_out_bytes)
    except OSError as e:
        logger.error(f"[错误] 写入输出文件失败：{args.out}：{e}")
        raise

    logger.info(f"[完成] 已写入：{args.out}（三角形数量：{tri_count}）")


if __name__ == "__main__":
    main()
