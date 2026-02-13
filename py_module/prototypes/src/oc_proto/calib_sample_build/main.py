"""
样本构建主模块
从校准照片中提取颜色样本数据，生成数据集文件
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from oc_calib.spec_adapter import SpecAdapter, extract_layer_sequence
from oc_core_02.utils.logger import get_logger
from oc_core_02.utils.paths import get_out_dir, PROJECT_ROOT
from oc_proto.calib_sample_build.main_utils import _perspective_warp_bgr, _apply_rotation, _choose_inset_mode, \
    sample_cell_mean_rgb

logger = get_logger(__name__)
VERSION = "calib_sample_build"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _resolve_warped_image_path(
    board_dir: Path, photos_root: Path, cache_dir: Path, *, rows: int, cols: int
) -> Path | None:
    warped = board_dir / "board_warped.png"
    if warped.exists():
        return warped

    warp_json = board_dir / "warp.json"
    if not warp_json.exists():
        return None

    board_name = board_dir.name
    if not board_name.startswith("Board_"):
        return None
    suffix = board_name.removeprefix("Board_")
    if not suffix:
        return None
    raw_img = photos_root / f"{suffix}.png"
    if not raw_img.exists():
        raw_img = photos_root / f"{suffix}.jpg"
    if not raw_img.exists():
        return None

    warp = _load_json(warp_json)
    points = warp.get("points")
    if not (
        isinstance(points, list)
        and len(points) == 4
        and all(isinstance(p, list) and len(p) == 2 for p in points)
    ):
        logger.error(f"[{VERSION}] 错误: warp.json 格式不正确: {warp_json}")
        return None

    dst_size = int(warp.get("dst_size") or 1000)
    rotation_count = int(warp.get("rotation_count") or 0) % 4
    point_order = str(warp.get("point_order") or "TL_TR_BR_BL")
    if point_order != "TL_TR_BR_BL":
        logger.warning(
            f"[{VERSION}] 警告: 暂未实现 point_order={point_order}，将按 TL_TR_BR_BL 处理: {warp_json}"
        )

    img_bgr = cv2.imread(str(raw_img), cv2.IMREAD_COLOR)
    if img_bgr is None:
        logger.error(f"[{VERSION}] 错误: 无法读取原始照片: {raw_img}")
        return None

    inset_mode = warp.get("inset_mode")
    if isinstance(inset_mode, bool):
        use_inset = inset_mode
    else:
        if rows == 17 and cols == 17:
            use_inset = _choose_inset_mode(
                img_bgr,
                points,
                dst_size=dst_size,
                rotation_count=rotation_count,
                rows=rows,
                cols=cols,
            )
            logger.info(
                f"[{VERSION}] 自动判定 inset_mode={use_inset} (rows={rows}, cols={cols})"
            )
        else:
            use_inset = False

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_warped = (
        cache_dir
        / f"{board_dir.name}_board_warped_dst{dst_size}_rot{rotation_count}_inset{int(use_inset)}_r{rows}c{cols}.png"
    )
    if (
        out_warped.exists()
        and out_warped.stat().st_mtime >= warp_json.stat().st_mtime
        and out_warped.stat().st_mtime >= raw_img.stat().st_mtime
    ):
        return out_warped

    warped_bgr = _perspective_warp_bgr(
        img_bgr, points, dst_size, inset_mode=use_inset, rows=rows, cols=cols
    )
    warped_bgr = _apply_rotation(warped_bgr, rotation_count)

    try:
        cv2.imwrite(str(out_warped), warped_bgr)
    except Exception as e:
        logger.error(f"[{VERSION}] 错误: 写入失败: {out_warped} ({e})")
        return None

    logger.info(
        f"[{VERSION}] 已从 {raw_img.name}+warp.json 生成输入: {out_warped} (inset_mode={use_inset}, rotation_count={rotation_count})"
    )
    return out_warped


def _resolve_board_spec_path(board_dir: Path) -> Path | None:
    spec_existing = board_dir / "board_spec.json"
    if spec_existing.exists():
        return spec_existing

    manifest_path = board_dir / "manifest.json"
    spec_name = None
    if manifest_path.exists():
        try:
            m = _load_json(manifest_path)
            spec_name = (m.get("params") or {}).get("spec")
        except Exception as e:
            logger.error(
                f"[{VERSION}] 警告: 读取 manifest.json 失败，将回退到按目录名推断 spec: {manifest_path} ({e})"
            )

    if not spec_name and board_dir.name.startswith("Board_"):
        suffix = board_dir.name.removeprefix("Board_")
        if suffix:
            spec_name = f"8-Color Board {suffix}"

    if not spec_name:
        return None

    spec_id = str(spec_name).replace(" ", "_")
    gen_dir = Path(__file__).resolve().parent.parent / "calib_board_gen"
    src = gen_dir / "out" / f"{spec_id}_board_spec.json"
    if not src.exists():
        logger.info(
            f"[{VERSION}] 未找到规格文件: {src}，正在尝试通过 calib_board_gen 生成..."
        )
        try:
            subprocess.run(
                [sys.executable, "-m", "oc_proto.calib_board_gen.main"], check=True
            )
        except Exception as e:
            logger.error(f"[{VERSION}] 生成规格文件失败: {e}")
            return None

    if not src.exists():
        return None

    return src


def ensure_board_spec(target_spec: Path):
    """Ensure the board spec file exists, generate it if necessary."""
    if target_spec.exists():
        return True

    # Try to find it in calib_board_gen/out
    # target_spec is typically .../calib_sample_build/data/xxx.json
    # prototype_dir = target_spec.parents[1]
    prototype_dir = Path(__file__).resolve().parent
    gen_dir = prototype_dir.parent / "calib_board_gen"
    gen_out_spec = gen_dir / "out" / target_spec.name

    if not gen_out_spec.exists():
        logger.info(f"未找到规格文件: {gen_out_spec}，正在尝试生成...")
        try:
            # 尝试多种生成方式，优先使用 pixi run 如果在 pixi 环境下
            cmd = [sys.executable, "-m", "oc_proto.calib_board_gen.main"]
            subprocess.run(cmd, check=True)
            logger.info("生成成功。")
        except Exception as e:
            logger.error(f"生成规格文件失败: {e}")
            return False

    if gen_out_spec.exists():
        target_spec.parent.mkdir(parents=True, exist_ok=True)
        # 如果目标路径已经存在但由于某种原因 .exists() 为 False (极少见)，
        # 或者我们需要强制覆盖，copy_file 应该能处理。
        import shutil

        shutil.copy2(gen_out_spec, target_spec)
        logger.info(f"已同步规格文件: {target_spec}")
        return True

    return False


def find_latest_patched(edit_module_dir: Path) -> Path | None:
    """Try to locate the most recent observation_patched.json under calib_cell_edit_01/out.
    Supports both flat out/ and timestamped subfolders."""
    out_dir = edit_module_dir / "out"
    if not out_dir.exists():
        return None
    candidates = list(out_dir.rglob("observation_patched.json"))
    if not candidates:
        return None
    # pick newest by mtime
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]






def draw_board_preview(cells, rows, cols, w, h):
    """根据 cells 数据绘制一个预览图 (用于校准前后对比)"""
    # 使用浮点数计算单位尺寸以减少累积误差
    cell_h = h / rows
    cell_w = w / cols
    preview = np.zeros((h, w, 3), dtype=np.uint8)

    # 创建一个查找字典
    cell_map = {(c["row"], c["col"]): c for c in cells}

    # 自动检测是否需要偏移 (15x15 数据放在 17x17 网格中)
    row_offset = 0
    col_offset = 0
    if rows == 17:
        max_r = max((c["row"] for c in cells), default=0)
        max_c = max((c["col"] for c in cells), default=0)
        if max_r < 16 and max_c < 16:
            row_offset = 1
            col_offset = 1

    for r in range(rows):
        for c in range(cols):
            # 修正：根据物理摆放逻辑，(0,0) 对应图像的右上角
            # 因此水平方向需要镜像翻转
            flipped_c = cols - 1 - c

            # 精确计算边界像素
            x0 = int(flipped_c * cell_w)
            x1 = int((flipped_c + 1) * cell_w)
            y0 = int(r * cell_h)
            y1 = int((r + 1) * cell_h)

            # 查找对应的逻辑单元格
            logical_r = r - row_offset
            logical_c = c - col_offset
            cell = cell_map.get((logical_r, logical_c))

            if cell and cell.get("measured_rgb"):
                rgb = cell["measured_rgb"]
                bgr = [int(rgb[2]), int(rgb[1]), int(rgb[0])]
                preview[y0:y1, x0:x1] = bgr
            else:
                preview[y0:y1, x0:x1] = (40, 40, 40)
    return preview


def run(
    warped_img_path: Path,
    spec_path: Path,
    patched_json_path: Path,
    out_dir: Path,
    ref_white=None,
    ref_black=None,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    img_bgr = cv2.imread(str(warped_img_path), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot read warped image: {warped_img_path}")

    spec = SpecAdapter(spec_path)

    # observation_patched.json is optional
    if patched_json_path.exists():
        patched = json.loads(
            patched_json_path.read_text(encoding="utf-8", errors="replace")
        )
    else:
        # Generate default observations if patched file is missing
        # 修正：生成逻辑网格数据 (通常是 15x15) 而不是物理网格数据
        logger.info(
            f"提示: 未找到 patched 文件 {patched_json_path}，将按 spec 生成默认逻辑网格数据。"
        )
        patched = []
        # 如果是 17x17 的物理板子，逻辑网格通常是 15x15
        logical_rows = 15 if spec.rows == 17 else spec.rows
        logical_cols = 15 if spec.cols == 17 else spec.cols

        for r in range(logical_rows):
            for c in range(logical_cols):
                has_recipe = bool(spec.get_cell_recipe(r, c))
                patched.append({"row": r, "col": c, "enabled": has_recipe, "roi": None})

    rows, cols = spec.rows, spec.cols
    h, w = img_bgr.shape[:2]
    cell_h_full = h / rows
    cell_w_full = w / cols

    active = spec.raw.get("active_range") if hasattr(spec, "raw") else None
    if isinstance(active, dict):
        sample_min_row = int(active.get("min_row", 0))
        sample_max_row = int(active.get("max_row", rows - 1))
        sample_min_col = int(active.get("min_col", 0))
        sample_max_col = int(active.get("max_col", cols - 1))
    else:
        sample_min_row, sample_max_row = 0, rows - 1
        sample_min_col, sample_max_col = 0, cols - 1
    sample_rows = max(1, sample_max_row - sample_min_row + 1)
    sample_cols = max(1, sample_max_col - sample_min_col + 1)
    cell_h_active = h / sample_rows
    cell_w_active = w / sample_cols

    # 之前尝试的 active_range 采样逻辑在处理包含边框的 warped 图时会导致偏移。
    # 对于标准 warped 图，我们始终使用全网格采样。
    use_active_sampling = False

    dataset = {
        "version": VERSION,
        "spec_name": spec.name,
        "rows": rows,
        "cols": cols,
        "warped_image": str(warped_img_path),
        "spec_path": str(spec_path),
        "patched_path": str(patched_json_path) if patched_json_path.exists() else None,
        "cells": [],
    }

    vis = img_bgr.copy()
    enabled_mask = np.zeros((h, w), dtype=np.uint8)
    has_recipe_mask = np.zeros((h, w), dtype=np.uint8)
    # Diagnostic board: show sum of recipe weights to check alignment
    recipe_sum_board = np.zeros((h, w), dtype=np.uint8)
    # First layer visualization: show the material of the bottom-most layer
    first_layer_vis = np.zeros((h, w, 3), dtype=np.uint8)

    # Define color map for materials (BGR)
    COLOR_MAP_BGR = {
        "White": (255, 255, 255),
        "Red": (0, 0, 255),
        "Yellow": (0, 255, 255),
        "Blue": (255, 0, 0),
        "Green": (0, 255, 0),
        "Cyan": (255, 255, 0),
        "Magenta": (255, 0, 255),
        "Black": (0, 0, 0),
    }

    enabled_count = 0

    # 自动检测是否需要偏移 (15x15 数据放在 17x17 网格中)
    row_offset = 0
    col_offset = 0
    if rows == 17:
        max_r_patched = max((int(obs["row"]) for obs in patched), default=0)
        max_c_patched = max((int(obs["col"]) for obs in patched), default=0)
        if max_r_patched < 16 and max_c_patched < 16:
            row_offset = 1
            col_offset = 1
            logger.info(
                f"[{VERSION}] 检测到 15x15 数据在 17x17 网格中，应用居中偏移 (+1)"
            )

    for obs in patched:
        # 逻辑坐标
        lr = int(obs["row"])
        lc = int(obs["col"])

        # 物理绘制坐标
        r = lr + row_offset
        c = lc + col_offset

        target_rgb = spec.get_cell_target_rgb(lr, lc)
        recipe = spec.get_cell_recipe(lr, lc)

        # 获取层叠顺序 (如果 spec 支持)
        # 从 spec cell_raw 中解析出真正的“每层颜色序列”。
        # 注意：很多 spec 的 slot_names 是 8 色调色板，不是 5 层序列；真正的层序通常在 layers (索引序列) 里。
        layer_names = []
        layer_indices = []
        slot_palette_names = []
        cell_raw = spec._get_cell_raw(lr, lc)
        if cell_raw:
            slot_palette_names, layer_indices, layer_names = extract_layer_sequence(
                cell_raw
            )

        has_recipe = bool(recipe)

        # --- 修改：保留所有格子，包括边框，除非它真的没有配方 ---
        if not has_recipe:
            continue
        # --- 修改结束 ---

        recipe_sum = sum(recipe.values()) if has_recipe else 0

        # Force disable if no recipe found in spec
        enabled = bool(obs.get("enabled", True))

        override_rgb = obs.get("override_rgb")
        roi = obs.get("roi")

        if use_active_sampling:
            # ... 原有逻辑保持不变，暂不处理 active_sampling 的镜像
            in_active = (
                sample_min_row <= lr <= sample_min_row + sample_rows - 1
                and sample_min_col <= lc <= sample_min_col + sample_cols - 1
            )
            if in_active:
                rr = lr - sample_min_row
                cc = lc - sample_min_col
                x0 = int(cc * cell_w_active)
                x1 = int((cc + 1) * cell_w_active)
                y0 = int(rr * cell_h_active)
                y1 = int((rr + 1) * cell_h_active)
            else:
                x0 = x1 = y0 = y1 = 0
        else:
            # 修正：根据物理摆放逻辑，(0,0) 对应图像的右上角。
            # 之前的逻辑错误地将 col 0 放在了左侧。
            flipped_c = cols - 1 - c
            x0 = int(flipped_c * cell_w_full)
            x1 = int((flipped_c + 1) * cell_w_full)
            y0 = int(r * cell_h_full)
            y1 = int((r + 1) * cell_h_full)

        if x1 > x0 and y1 > y0:
            cv2.rectangle(
                recipe_sum_board, (x0, y0), (x1, y1), min(255, int(recipe_sum * 10)), -1
            )
            # Draw first layer color
            first_layer_color = (40, 40, 40)  # Default dark gray
            if layer_names:
                mat_name = layer_names[0]
                first_layer_color = COLOR_MAP_BGR.get(mat_name, (40, 40, 40))
            cv2.rectangle(first_layer_vis, (x0, y0), (x1, y1), first_layer_color, -1)
            # Add text label for material name
            if layer_names:
                cv2.putText(
                    first_layer_vis,
                    layer_names[0][:1],
                    (x0 + 2, y0 + 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.3,
                    (128, 128, 128),
                    1,
                )

        if x1 > x0 and y1 > y0:
            # 计算单元格的中心采样点
            # 修正：同样应用水平翻转
            flipped_c = cols - 1 - c
            center_x = int((flipped_c + 0.5) * cell_w_full)
            center_y = int((r + 0.5) * cell_h_full)
            sample_half = 5
            sx0, sx1 = center_x - sample_half, center_x + sample_half
            sy0, sy1 = center_y - sample_half, center_y + sample_half
        else:
            sx0 = sy0 = sx1 = sy1 = 0

        if override_rgb is not None:
            measured_rgb = [float(x) for x in override_rgb]
            source = "override_rgb"
        elif sx1 > sx0 and sy1 > sy0:
            measured_rgb = sample_cell_mean_rgb(img_bgr, sx0, sy0, sx1, sy1)
            source = "mean_roi"
        else:
            measured_rgb = [0.0, 0.0, 0.0]
            source = "out_of_range"

        if x1 > x0 and y1 > y0:
            cv2.rectangle(has_recipe_mask, (x0, y0), (x1, y1), 255, -1)
        if enabled and x1 > x0 and y1 > y0:
            cv2.rectangle(enabled_mask, (x0, y0), (x1, y1), 255, -1)
            enabled_count += 1

        # Color coding: Green=Enabled, Gray=Disabled, Red=Missing Recipe (but was requested enabled)
        if enabled:
            color = (0, 255, 0)
        elif not has_recipe:
            color = (0, 0, 255)  # Red for missing recipe
        else:
            color = (80, 80, 80)

        if sx1 > sx0 and sy1 > sy0:
            cv2.rectangle(vis, (sx0, sy0), (sx1, sy1), color, 1)
            # 添加行列文字标注
            label = f"{lr},{lc}"
            cv2.putText(
                vis, label, (sx0 + 2, sy0 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1
            )

        dataset["cells"].append(
            {
                "row": lr,
                "col": lc,
                "enabled": enabled,
                "has_recipe": has_recipe,
                "measured_rgb": measured_rgb,
                "source": source,
                "roi": roi,
                "sample_box_px": [sx0, sy0, sx1, sy1],
                "target_rgb": target_rgb,
                "recipe": recipe,
                "slot_palette_names": slot_palette_names,
                "layer_indices": layer_indices,
                "layer_names": layer_names,
            }
        )

    # --- 自动黑白场校准与预览保存 ---
    # 1. 绘制校准前的预览图
    preview_before = draw_board_preview(dataset["cells"], rows, cols, w, h)
    out_preview_before = out_dir / "preview_before_calib.png"
    cv2.imwrite(str(out_preview_before), preview_before)
    logger.info(f"[{VERSION}] 已保存校准前预览图: {out_preview_before.name}")

    # 2. 寻找或使用参考黑白点
    white_probe = None
    black_probe = None
    max_white_probe = -1.0
    max_black_probe = -1.0
    for c in dataset["cells"]:
        if not c["enabled"] or not c["recipe"]:
            continue
        w_val = sum(v for k, v in c["recipe"].items() if "white" in k.lower())
        b_val = sum(v for k, v in c["recipe"].items() if "black" in k.lower())
        if w_val > max_white_probe:
            max_white_probe = w_val
            white_probe = c
        if b_val > max_black_probe:
            max_black_probe = b_val
            black_probe = c

    if white_probe is not None and black_probe is not None:
        logger.info(
            f"[{VERSION}] 校准前探针格: 白色候选(R{white_probe['row']}C{white_probe['col']}, white_w={max_white_probe})"
            f" RGB={white_probe['measured_rgb']} sample_box={white_probe.get('sample_box_px')}"
        )
        logger.info(
            f"[{VERSION}] 校准前探针格: 黑色候选(R{black_probe['row']}C{black_probe['col']}, black_w={max_black_probe})"
            f" RGB={black_probe['measured_rgb']} sample_box={black_probe.get('sample_box_px')}"
        )

    darkest = None
    brightest = None
    for c in dataset["cells"]:
        if not c["enabled"]:
            continue
        rgb = c.get("measured_rgb")
        if not (isinstance(rgb, list) and len(rgb) == 3):
            continue
        lum = float(rgb[0]) + float(rgb[1]) + float(rgb[2])
        if darkest is None or lum < darkest[0]:
            darkest = (lum, c)
        if brightest is None or lum > brightest[0]:
            brightest = (lum, c)

    if darkest is not None and brightest is not None:
        dc = darkest[1]
        bc = brightest[1]
        logger.info(
            f"[{VERSION}] 校准前亮度最黑: R{dc['row']}C{dc['col']} RGB={dc['measured_rgb']} recipe={dc.get('recipe')} sample_box={dc.get('sample_box_px')}"
        )
        logger.info(
            f"[{VERSION}] 校准前亮度最白: R{bc['row']}C{bc['col']} RGB={bc['measured_rgb']} recipe={bc.get('recipe')} sample_box={bc.get('sample_box_px')}"
        )

    rgb_w = None
    rgb_b = None

    if ref_white is not None and ref_black is not None:
        rgb_w = np.array(ref_white, dtype=np.float32)
        rgb_b = np.array(ref_black, dtype=np.float32)
        logger.info(f"[{VERSION}] 使用外部参考校准: 白色={rgb_w}, 黑色={rgb_b}")
    else:
        white_ref_cell = None
        black_ref_cell = None
        max_white = -1.0
        max_black = -1.0

        for c in dataset["cells"]:
            if not c["enabled"] or not c["recipe"]:
                continue
            # 计算白色分量和黑色分量 (忽略大小写)
            w_val = sum(v for k, v in c["recipe"].items() if "white" in k.lower())
            b_val = sum(v for k, v in c["recipe"].items() if "black" in k.lower())

            if w_val > max_white:
                max_white = w_val
                white_ref_cell = c
            if b_val > max_black:
                max_black = b_val
                black_ref_cell = c

        if white_ref_cell is not None and black_ref_cell is not None:
            rgb_w = np.array(white_ref_cell["measured_rgb"], dtype=np.float32)
            rgb_b = np.array(black_ref_cell["measured_rgb"], dtype=np.float32)
            logger.info(
                f"[{VERSION}] 自动寻找参考点: 白色(R{white_ref_cell['row']}C{white_ref_cell['col']})={rgb_w}, 黑色(R{black_ref_cell['row']}C{black_ref_cell['col']})={rgb_b}"
            )

    if rgb_w is not None and rgb_b is not None:
        # 线性映射: (val - black) / (white - black) * 255
        denom = rgb_w - rgb_b
        for i in range(3):
            if abs(denom[i]) < 1e-3:
                denom[i] = 1.0

        for c in dataset["cells"]:
            val = np.array(c["measured_rgb"], dtype=np.float32)
            norm_val = (val - rgb_b) / denom * 255.0
            c["measured_rgb"] = [float(x) for x in np.clip(norm_val + 0.5, 0, 255)]

        logger.info(f"[{VERSION}] 校准完成: 已根据黑白参考点重新映射所有测量值")

        preview_after = draw_board_preview(dataset["cells"], rows, cols, w, h)
        out_preview_after = out_dir / "preview_after_calib.png"
        cv2.imwrite(str(out_preview_after), preview_after)
        logger.info(f"[{VERSION}] 已保存校准后预览图: {out_preview_after.name}")
    else:
        logger.info(f"[{VERSION}] 自动校准跳过: 未找到足够的黑白参考点")

    def check_duplicates(cells):
        from collections import defaultdict

        seen = defaultdict(list)
        duplicates = 0
        for i, c in enumerate(cells):
            if not c["enabled"] or not c["has_recipe"]:
                continue
            feat = (
                tuple(c.get("layer_names") or []),
                tuple(sorted(c.get("recipe", {}).items())),
            )
            seen[feat].append(c)

        for feat, group in seen.items():
            if len(group) > 1:
                duplicates += len(group)
                locs = [f"R{g['row']}C{g['col']}" for g in group]
                logger.warning(
                    f"[{VERSION}] 警告: 发现物理重复格子! 数量={len(group)}, 位置={locs}, 特征={feat}"
                )

        if duplicates > 0:
            logger.info(
                f"[{VERSION}] 统计: 共发现 {duplicates} 个格子存在特征冲突（物理属性完全相同）"
            )
        else:
            logger.info(f"[{VERSION}] 自检通过: 未发现重复的物理格子")

    check_duplicates(dataset["cells"])

    out_dataset = out_dir / "dataset_cells.json"
    out_preview = out_dir / "sample_preview.png"
    cv2.imwrite(str(out_preview), vis)

    out_recipe_sum = out_dir / "recipe_sum_board.png"
    cv2.imwrite(str(out_recipe_sum), recipe_sum_board)

    # 已经按照镜像坐标绘制，无需再次翻转
    out_first_layer = out_dir / "first_layer.png"
    out_enabled_mask = out_dir / "enabled_mask.png"

    # 4. 如果 rows/cols 是 17x17 (含边框)，裁剪所有预览图以只显示中间的 15x15 部分
    if rows == 17 and cols == 17:
        # 使用浮点数比例计算精确裁剪边界 (第1格到第16格)
        ch0 = int(1 * (h / 17))
        ch1 = int(16 * (h / 17))
        cw0 = int(1 * (w / 17))
        cw1 = int(16 * (w / 17))

        # 裁剪函数
        def crop_17_to_15(img):
            return img[ch0:ch1, cw0:cw1]

        preview_before = crop_17_to_15(preview_before)
        if rgb_w is not None and rgb_b is not None:
            preview_after = crop_17_to_15(preview_after)
        first_layer_vis = crop_17_to_15(first_layer_vis)
        enabled_mask = crop_17_to_15(enabled_mask)

        logger.info(f"[{VERSION}] 已对所有产物图进行边框裁剪 (17x17 -> 15x15)")

    # 保存最终产物
    cv2.imwrite(str(out_preview_before), preview_before)
    if rgb_w is not None and rgb_b is not None:
        cv2.imwrite(str(out_preview_after), preview_after)
    cv2.imwrite(str(out_first_layer), first_layer_vis)
    cv2.imwrite(str(out_enabled_mask), enabled_mask)

    with open(out_dataset, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    # Write simple manifest
    manifest = {
        "board_name": spec.name,
        "rows": rows,
        "cols": cols,
        "dataset": out_dataset.name,
        "preview_before": out_preview_before.name,
        "preview_after": out_preview_after.name
        if (rgb_w is not None and rgb_b is not None)
        else None,
        "first_layer": out_first_layer.name,
        "enabled_mask": out_enabled_mask.name,
        "calib_white": rgb_w.tolist() if rgb_w is not None else None,
        "calib_black": rgb_b.tolist() if rgb_b is not None else None,
    }
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Manifest 已写入: {manifest_path}")

    return rgb_w, rgb_b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--photos-root",
        type=str,
        default=str(PROJECT_ROOT / "data" / "calibration" / "photos_02"),
        help="包含多个 Board_XXX 目录的根路径",
    )
    ap.add_argument("--warped", type=str, default="", help="Path to board_warped.png")
    ap.add_argument("--spec", type=str, default="", help="Path to board_spec.json")
    ap.add_argument(
        "--patched", type=str, default="", help="Path to observation_patched.json"
    )
    args = ap.parse_args()

    prototype_dir = Path(__file__).resolve().parent
    photos_root = Path(args.photos_root)
    base_out_dir = get_out_dir(prototype_dir)
    input_cache_dir = base_out_dir / "_inputs_cache"

    # 如果显式指定了 warped 和 spec，则走单次处理逻辑
    if args.warped and args.spec:
        warped = Path(args.warped)
        spec = Path(args.spec)
        patched = Path(args.patched) if args.patched else Path("non_existent.json")
        out_dir = base_out_dir / "manual"
        run(warped, spec, patched, out_dir)
        logger.info(f"[{VERSION}] 单次处理完成: {out_dir}")
        return

    # 否则走批量自动扫描逻辑
    if not photos_root.exists():
        logger.error(f"错误: 未找到照片根目录 {photos_root}")
        return

    logger.info(f"[{VERSION}] 开始扫描目录: {photos_root}")

    # 1. 优先寻找并处理 Board_A 以获取全局校准参考值
    global_white = None
    global_black = None
    board_a_dir = photos_root / "Board_A"

    if board_a_dir.is_dir():
        logger.info(f"\n[{VERSION}] 优先处理 Board_A 获取全局参考...")
        spec = _resolve_board_spec_path(board_a_dir)
        warped = None
        if spec and spec.exists():
            spec_shape = SpecAdapter(spec)
            warped = _resolve_warped_image_path(
                board_a_dir,
                photos_root,
                input_cache_dir,
                rows=spec_shape.rows,
                cols=spec_shape.cols,
            )
        patched = board_a_dir / "observation_patched.json"
        board_out = base_out_dir / board_a_dir.name

        if warped and spec and warped.exists() and spec.exists():
            try:
                global_white, global_black = run(warped, spec, patched, board_out)
                logger.info(
                    f"  Board_A 处理成功，获取到全局参考: 白色={global_white}, 黑色={global_black}"
                )
            except Exception as e:
                logger.error(f"  Board_A 预处理失败: {e}")
    else:
        logger.warning(
            f"\n[{VERSION}] 警告: 未找到 Board_A 目录，将回退到各个色盘独立校准模式。"
        )

    # 2. 批量处理所有色盘
    processed_count = 0
    for board_dir in photos_root.iterdir():
        if not board_dir.is_dir():
            continue

        manifest_path = board_dir / "manifest.json"
        # 我们优先处理有 manifest 的目录，或者显式命名的 Board_XXX 目录
        if not manifest_path.exists() and not board_dir.name.startswith("Board_"):
            continue

        # 如果是 Board_A 且已经处理过，可以选择跳过或重新应用全局参考处理一次（确保结果一致）
        # 这里我们选择重新处理一次，以便代码逻辑更统一
        logger.info(f"\n[{VERSION}] 正在处理色盘: {board_dir.name}")

        # 自动推断文件路径
        spec = _resolve_board_spec_path(board_dir)
        warped = None
        if spec and spec.exists():
            spec_shape = SpecAdapter(spec)
            warped = _resolve_warped_image_path(
                board_dir,
                photos_root,
                input_cache_dir,
                rows=spec_shape.rows,
                cols=spec_shape.cols,
            )
        patched = board_dir / "observation_patched.json"

        if not warped or not spec or not warped.exists() or not spec.exists():
            logger.info(
                f"  跳过: 缺少必要文件 (warped={bool(warped and warped.exists())}, spec={bool(spec and spec.exists())})"
            )
            continue

        # 为每个色盘创建独立的输出目录
        board_out = base_out_dir / board_dir.name

        try:
            run(
                warped,
                spec,
                patched,
                board_out,
                ref_white=global_white,
                ref_black=global_black,
            )
            processed_count += 1
            logger.info(f"  处理成功 -> {board_out}")
        except Exception as e:
            logger.error(f"  处理失败: {e}")

    logger.info(f"\n[{VERSION}] 批量处理完成。共成功处理 {processed_count} 个色盘。")
    logger.info(f"结果汇总在: {base_out_dir}")


if __name__ == "__main__":
    main()
