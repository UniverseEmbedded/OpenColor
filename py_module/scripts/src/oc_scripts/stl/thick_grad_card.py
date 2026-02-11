"""
制作垂直厚度渐变校准卡片（单个STL）

用户工作流程（你的概念）：
- 在电脑屏幕上显示水平灰度渐变（X轴 = 背光强度）
- 将打印的卡片垂直靠在屏幕边框上（不要放在屏幕玻璃上）以避免刮伤
- 卡片具有垂直厚度渐变（Y轴 = 材料厚度）
- 照片捕捉2D场：X=已知输入强度，Y=已知厚度 => 拟合透射参数

几何：
- 主面板：宽度W，高度H
- 厚度沿Y平滑变化：t(y) 从底部t_min到顶部t_max（或反向）
- 边框支脚：顶部角落的小"耳朵"接触边框，使面板远离玻璃
- 背面可选加强筋以加固薄端

依赖：
  pip install numpy trimesh numpy

用法：
  python make_thickness_gradient_card_stl.py --out thickness_gradient_card.stl
"""

from __future__ import annotations
import argparse
import numpy as np
import trimesh


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def build_thickness_gradient_plate(
    W: float,
    H: float,
    t_min: float,
    t_max: float,
    ny: int = 220,
    thickness_profile: str = "linear",
    reverse: bool = False,
) -> trimesh.Trimesh:
    """
    构建沿Y方向（垂直）厚度变化的面板

    我们通过三角带构建封闭网格：
    - 顶面 z = t(y)
    - 底面 z = 0
    - 侧壁 + 帽
    """

    # y坐标从底部 (-H/2) 到顶部 (+H/2)
    y = np.linspace(-H / 2.0, H / 2.0, ny, dtype=np.float64)
    s = (y - y.min()) / (y.max() - y.min())  # 0..1 底部->顶部

    if reverse:
        s = 1.0 - s

    if thickness_profile == "linear":
        t = t_min + (t_max - t_min) * s
    elif thickness_profile == "ease":
        # 两端更平滑；在薄端保持拟合稳定，不那么突然
        s2 = s * s * (3.0 - 2.0 * s)  # smoothstep
        t = t_min + (t_max - t_min) * s2
    elif thickness_profile == "exp":
        # 类指数间距（如果你期望ln(T)与厚度线性相关）
        # 限制以避免t_min=0
        a = max(t_min, 0.05)
        b = t_max
        t = a * ((b / a) ** s)
    else:
        raise ValueError("thickness_profile 必须是: linear, ease, exp 之一")

    # 构建顶点：
    # 对于每个y_i，我们创建4个顶点：左上、右上、右下、左下
    # x跨度 [-W/2, +W/2]，顶部z为t_i，底部z为0
    xL, xR = -W / 2.0, W / 2.0

    verts = []
    for yi, ti in zip(y, t):
        verts.extend(
            [
                [xL, yi, ti],  # 0 左上
                [xR, yi, ti],  # 1 右上
                [xR, yi, 0.0],  # 2 右下
                [xL, yi, 0.0],  # 3 左下
            ]
        )
    verts = np.array(verts, dtype=np.float64)

    faces = []

    def vid(i: int, k: int) -> int:
        # i 在 [0..ny-1]，k 在 [0..3]
        return 4 * i + k

    # 连接连续y切片间的四边形
    for i in range(ny - 1):
        # 顶面（左上/右上之间）
        # 四边形: (i,0)->(i,1)->(i+1,1)->(i+1,0)
        faces.extend(
            [
                [vid(i, 0), vid(i, 1), vid(i + 1, 1)],
                [vid(i, 0), vid(i + 1, 1), vid(i + 1, 0)],
            ]
        )

        # 底面（z=0），注意绕向应相反
        faces.extend(
            [
                [vid(i, 3), vid(i + 1, 3), vid(i + 1, 2)],
                [vid(i, 3), vid(i + 1, 2), vid(i, 2)],
            ]
        )

        # 右壁（x=+W/2）：右上到右下
        faces.extend(
            [
                [vid(i, 1), vid(i, 2), vid(i + 1, 2)],
                [vid(i, 1), vid(i + 1, 2), vid(i + 1, 1)],
            ]
        )

        # 左壁（x=-W/2）：左下到左上
        faces.extend(
            [
                [vid(i, 3), vid(i, 0), vid(i + 1, 0)],
                [vid(i, 3), vid(i + 1, 0), vid(i + 1, 3)],
            ]
        )

    # 封闭底边（y=-H/2）和顶边（y=+H/2）
    # 底帽使用切片 i=0
    i0 = 0
    faces.extend(
        [
            [vid(i0, 0), vid(i0, 3), vid(i0, 2)],
            [vid(i0, 0), vid(i0, 2), vid(i0, 1)],
        ]
    )
    # 顶帽使用切片 i=ny-1
    i1 = ny - 1
    faces.extend(
        [
            [vid(i1, 0), vid(i1, 1), vid(i1, 2)],
            [vid(i1, 0), vid(i1, 2), vid(i1, 3)],
        ]
    )

    mesh = trimesh.Trimesh(
        vertices=verts, faces=np.array(faces, dtype=np.int64), process=False
    )
    # 清理（新trimesh API）
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def add_bezel_feet(
    base: trimesh.Trimesh,
    W: float,
    H: float,
    foot_depth: float,
    foot_thickness: float,
    foot_height: float,
    z_attach: float,
) -> trimesh.Trimesh:
    """
    在顶部角落添加两个小"支脚/耳朵"接触边框，使面板远离屏幕玻璃

    - foot_depth: 支脚在+Z（背面）方向伸出的距离
    - foot_thickness: 支脚沿X的厚度
    - foot_height: 支脚沿Y的高度
    - z_attach: 我们沿Z连接的位置（通常靠近面板顶部厚度）
    """
    # 将支脚放在靠近左上/右上角落
    # 我们将它们以z_attach为中心在Z方向连接，但它们向+Z延伸更远
    x_margin = 2.0
    y_top = H / 2.0
    y_center = y_top - foot_height / 2.0 - 1.0

    # 左支脚
    left = trimesh.creation.box(extents=(foot_thickness, foot_height, foot_depth))
    left.apply_translation(
        (
            -W / 2.0 + x_margin + foot_thickness / 2.0,
            y_center,
            z_attach + foot_depth / 2.0,
        )
    )

    # 右支脚
    right = trimesh.creation.box(extents=(foot_thickness, foot_height, foot_depth))
    right.apply_translation(
        (
            W / 2.0 - x_margin - foot_thickness / 2.0,
            y_center,
            z_attach + foot_depth / 2.0,
        )
    )

    combo = trimesh.util.concatenate([base, left, right])
    combo.merge_vertices()
    combo.update_faces(combo.unique_faces())
    combo.update_faces(combo.nondegenerate_faces())
    combo.remove_unreferenced_vertices()
    return combo


def add_back_ribs(
    base: trimesh.Trimesh,
    W: float,
    H: float,
    rib_count: int,
    rib_w: float,
    rib_d: float,
    rib_h: float,
    z0: float,
    y_start: float,
    y_end: float,
) -> trimesh.Trimesh:
    """
    在背面添加垂直加强筋以加固薄端
    这些加强筋位于+Z方向，因此不会接触屏幕玻璃（用户将卡片靠在边框上）
    """
    ribs = []
    xs = np.linspace(-W / 2 + 8, W / 2 - 8, rib_count)
    y_center = (y_start + y_end) / 2.0
    for x in xs:
        rib = trimesh.creation.box(extents=(rib_w, (y_end - y_start), rib_d))
        rib.apply_translation((x, y_center, z0 + rib_d / 2.0))
        ribs.append(rib)

    combo = trimesh.util.concatenate([base] + ribs)
    combo.merge_vertices()
    combo.update_faces(combo.unique_faces())
    combo.update_faces(combo.nondegenerate_faces())
    combo.remove_unreferenced_vertices()
    return combo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="thickness_gradient_card.stl")
    ap.add_argument("--w", type=float, default=120.0, help="卡片宽度（毫米）")
    ap.add_argument("--h", type=float, default=80.0, help="卡片高度（毫米）")
    ap.add_argument("--t_min", type=float, default=0.20, help="一端最小厚度（毫米）")
    ap.add_argument("--t_max", type=float, default=1.20, help="另一端最大厚度（毫米）")
    ap.add_argument("--ny", type=int, default=220, help="垂直分辨率（越多=越平滑）")
    ap.add_argument("--profile", choices=["linear", "ease", "exp"], default="ease")
    ap.add_argument(
        "--reverse", action="store_true", help="反转厚度方向（顶部薄而非底部薄）"
    )
    # 边框支脚
    ap.add_argument(
        "--feet", action="store_true", help="添加边框支脚以避免接触屏幕玻璃"
    )
    ap.add_argument(
        "--foot_depth", type=float, default=2.5, help="支脚在+Z方向伸出距离（毫米）"
    )
    ap.add_argument(
        "--foot_thickness", type=float, default=10.0, help="支脚沿X厚度（毫米）"
    )
    ap.add_argument(
        "--foot_height", type=float, default=10.0, help="支脚沿Y高度（毫米）"
    )
    # 加强筋
    ap.add_argument("--ribs", action="store_true", help="在背面添加加固加强筋")
    ap.add_argument("--rib_count", type=int, default=3)
    ap.add_argument("--rib_w", type=float, default=2.0)
    ap.add_argument("--rib_d", type=float, default=1.8)
    ap.add_argument(
        "--rib_y0", type=float, default=-40.0, help="加强筋起始Y（毫米，相对于中心）"
    )
    ap.add_argument(
        "--rib_y1", type=float, default=10.0, help="加强筋结束Y（毫米，相对于中心）"
    )
    args = ap.parse_args()

    # 基础渐变面板
    mesh = build_thickness_gradient_plate(
        W=args.w,
        H=args.h,
        t_min=args.t_min,
        t_max=args.t_max,
        ny=args.ny,
        thickness_profile=args.profile,
        reverse=args.reverse,
    )

    # 在y=+H/2处的近似顶部厚度
    top_t = args.t_max if not args.reverse else args.t_min

    if args.feet:
        # 在顶面附近连接支脚；添加小的额外偏移以确保支脚在面板后方
        mesh = add_bezel_feet(
            base=mesh,
            W=args.w,
            H=args.h,
            foot_depth=args.foot_depth,
            foot_thickness=args.foot_thickness,
            foot_height=args.foot_height,
            z_attach=top_t + 0.2,
        )

    if args.ribs:
        mesh = add_back_ribs(
            base=mesh,
            W=args.w,
            H=args.h,
            rib_count=args.rib_count,
            rib_w=args.rib_w,
            rib_d=args.rib_d,
            rib_h=args.h,
            z0=max(args.t_min, 0.2) + 0.2,
            y_start=args.rib_y0,
            y_end=args.rib_y1,
        )

    mesh.export(args.out)
    logger.info("已写入:", args.out)
    logger.info("厚度渐变:", ("顶部->底部反转" if args.reverse else "底部->顶部"))
    logger.info("t_min:", args.t_min, "t_max:", args.t_max)
    if args.feet:
        logger.info("边框支脚: 已启用（避免接触屏幕玻璃）")
    if args.ribs:
        logger.info("背面加强筋: 已启用")


if __name__ == "__main__":
    main()
