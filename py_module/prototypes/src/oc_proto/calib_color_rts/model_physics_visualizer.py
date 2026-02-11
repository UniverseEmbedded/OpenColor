import argparse
from pathlib import Path

import cv2
import numpy as np
from oc_proto.calib_color_model_fit.color_space import rgb01_to_lab, lab_to_rgb01
from oc_proto.calib_color_model_fit.dataset_io import (
    load_dataset,
    apply_bw_calibration_inverse,
)
from oc_proto.calib_color_model_fit.eval_pipeline import (
    _rts_fit_model,
    _rts_sigmoid,
    _rts_normalize_seq,
    _rts_build_seq_from_recipe,
    _rts_idx_mat,
    _rts_predict_linear_idx,
    _rts_linear01_to_srgb01_f64,
)
from oc_proto.calib_color_model_fit.xgb_fit import (
    fit_optical_params,
    predict_ad_rgb01,
    PhysGPRConfig,
    OpticalParams,
    get_optical_model,
)


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _delta_e76(lab1, lab2):
    return np.linalg.norm(lab1 - lab2, axis=-1)


def _generate_text_report(
    material_keys: list[str],
    optical_params: OpticalParams,
    model_type: str,
    impl_name: str,
    ds,
    out_dir: Path,
    layer_names_order: str = "bottom_first",
):
    report_path = out_dir / f"REPORT_{model_type}_{impl_name}.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 物理模型分析报告 - {model_type} ({impl_name})\n\n")
        f.write(f"生成时间: {np.datetime64('now')}\n\n")

        # 1. 物理参数
        f.write("## 1. 耗材物理参数 (基于色盘A推导)\n\n")
        f.write("| 耗材名称 | mu_a (R,G,B) | mu_s (R,G,B) | g (R,G,B) |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for i, m in enumerate(material_keys):
            ma = optical_params.mu_a[i]
            ms = optical_params.mu_s[i]
            mg = optical_params.g[i]
            f.write(f"| {m} | {ma.tolist()} | {ms.tolist()} | {mg.tolist()} |\n")

        f.write(f"\n**全局参数**:\n")
        f.write(f"- k1 (表面反射): {optical_params.k1:.4f}\n")
        f.write(f"- k2 (内部反射): {optical_params.k2:.4f}\n")
        f.write(f"- backing (底色反射率): {optical_params.backing:.4f}\n\n")

        # 2. 训练集对比 (色盘A)
        f.write("## 2. 真实图片 vs 预测 RGB 对比 (色盘A)\n\n")

        fit_cells = [c for c in ds.cells if c.enabled and c.recipe]
        recipes = []
        for c in fit_cells:
            r = dict(c.recipe)
            r["_layer_names"] = getattr(c, "layer_names", [])
            recipes.append(r)
        from oc_proto.calib_color_model_fit.xgb_features import build_layer_sequences

        sequences = build_layer_sequences(
            recipes, material_keys, n_layers=5, layer_names_order=layer_names_order
        )

        pred_rgb = predict_ad_rgb01(
            sequences,
            material_keys,
            optical_params,
            use_vulkan=(impl_name == "vulkan"),
            model_type=model_type,
        )
        pred_lab = rgb01_to_lab(pred_rgb)

        real_rgb = (
            np.stack([c.measured_rgb for c in fit_cells], axis=0).astype(np.float32)
            / 255.0
        )
        real_lab = rgb01_to_lab(real_rgb)

        de_errors = _delta_e76(real_lab, pred_lab)

        f.write(f"**统计摘要**:\n")
        f.write(f"- 平均 DeltaE76: {np.mean(de_errors):.4f}\n")
        f.write(f"- 最大 DeltaE76: {np.max(de_errors):.4f}\n")
        f.write(f"- 中位数 DeltaE76: {np.median(de_errors):.4f}\n\n")

        f.write("| 行 | 列 | 配方 | 真实 RGB (U8) | 预测 RGB (U8) | DeltaE76 |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")

        for i, c in enumerate(fit_cells):
            r_u8 = (real_rgb[i] * 255 + 0.5).astype(int).tolist()
            p_u8 = (pred_rgb[i] * 255 + 0.5).astype(int).tolist()
            recipe_str = ", ".join([f"{k}:{v}" for k, v in c.recipe.items() if v > 0])
            f.write(
                f"| {c.row} | {c.col} | {recipe_str} | {r_u8} | {p_u8} | {de_errors[i]:.2f} |\n"
            )

        # 3. 可视化测试样本对比
        f.write("\n## 3. 可视化测试样本对比 (Real vs Predicted)\n\n")

        # 3.1 纯色
        f.write("### 3.1 纯色预览 (5层)\n\n")
        f.write("| 目标 | 预测 RGB (U8) |\n")
        f.write("| :--- | :--- |\n")
        pure_targets = [
            "White",
            "Black",
            "Red",
            "Green",
            "Blue",
            "Cyan",
            "Magenta",
            "Yellow",
        ]
        pure_sequences = []
        pure_labels = []
        for t in pure_targets:
            matched = [m for m in material_keys if m.lower() == t.lower()]
            if matched:
                pure_sequences.append([matched[0]] * 5)
                pure_labels.append(t)

        pure_rgb_test = predict_ad_rgb01(
            pure_sequences,
            material_keys,
            optical_params,
            use_vulkan=(impl_name == "vulkan"),
            model_type=model_type,
        )
        for i, label in enumerate(pure_labels):
            p_u8 = (pure_rgb_test[i] * 255 + 0.5).astype(int).tolist()
            f.write(f"| {label} | {p_u8} |\n")

        # 3.2 典型样本对比
        f.write("\n### 3.2 典型样本对比 (色盘A前12个点)\n\n")
        f.write("| 样本标签 | 配方 | 真实 RGB (U8) | 预测 RGB (U8) | DeltaE76 |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")

        fit_cells = [c for c in ds.cells if c.enabled and c.recipe]
        sample_cells = fit_cells[:12]
        sample_recipes = []
        for c in sample_cells:
            r = dict(c.recipe)
            r["_layer_names"] = getattr(c, "layer_names", [])
            sample_recipes.append(r)
        sample_sequences = build_layer_sequences(
            sample_recipes,
            material_keys,
            n_layers=5,
            layer_names_order=layer_names_order,
        )
        sample_pred_rgb = predict_ad_rgb01(
            sample_sequences,
            material_keys,
            optical_params,
            use_vulkan=(impl_name == "vulkan"),
            model_type=model_type,
        )
        sample_real_rgb = (
            np.stack([c.measured_rgb for c in sample_cells], axis=0).astype(np.float32)
            / 255.0
        )

        sample_pred_lab = rgb01_to_lab(sample_pred_rgb)
        sample_real_lab = rgb01_to_lab(sample_real_rgb)
        sample_de = _delta_e76(sample_real_lab, sample_pred_lab)

        for i, c in enumerate(sample_cells):
            r_u8 = (sample_real_rgb[i] * 255 + 0.5).astype(int).tolist()
            p_u8 = (sample_pred_rgb[i] * 255 + 0.5).astype(int).tolist()
            recipe_str = ", ".join([f"{k}:{v}" for k, v in c.recipe.items() if v > 0])
            items = [f"{k[0]}{int(v)}" for k, v in c.recipe.items() if v > 0]
            label = "+".join(items)
            f.write(
                f"| {label} | {recipe_str} | {r_u8} | {p_u8} | {sample_de[i]:.2f} |\n"
            )

    return report_path


def _rts_sequences_from_cells(cells: list, n_layers: int) -> list[list[str]]:
    seqs: list[list[str]] = []
    for c in cells:
        if (
            isinstance(getattr(c, "layer_names", None), list)
            and len(getattr(c, "layer_names", []) or []) > 0
        ):
            seqs.append(_rts_normalize_seq(list(c.layer_names), n_layers))
            continue
        if bool(getattr(c, "recipe", None)):
            seqs.append(_rts_build_seq_from_recipe(dict(c.recipe), n_layers))
            continue
        seqs.append(["EMPTY"] * n_layers)
    return seqs


def _rts_predict_rgb01_for_sequences(
    seqs: list[list[str]], rts_model: dict
) -> np.ndarray:
    idx = _rts_idx_mat(
        seqs, rts_model["mats"], layer_names_order=str(rts_model["layer_names_order"])
    )
    pred_lin = _rts_predict_linear_idx(
        idx, rts_model["alpha"], rts_model["beta"], rts_model["gamma"]
    )
    pred_srgb01 = _rts_linear01_to_srgb01_f64(pred_lin).astype(np.float32)
    return pred_srgb01


def _generate_text_report_rts(
    rts_model: dict,
    model_type: str,
    impl_name: str,
    ds,
    out_dir: Path,
    n_layers: int,
):
    report_path = out_dir / f"REPORT_{model_type}_{impl_name}.md"

    mats = list(rts_model["mats"])
    alpha = np.asarray(rts_model["alpha"], dtype=np.float64)
    beta = np.asarray(rts_model["beta"], dtype=np.float64)
    gamma = np.asarray(rts_model["gamma"], dtype=np.float64)
    r = _rts_sigmoid(alpha)
    t = _rts_sigmoid(beta) * (1.0 - r)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 物理模型分析报告 - {model_type} ({impl_name})\n\n")
        f.write(f"生成时间: {np.datetime64('now')}\n\n")

        f.write("## 1. RTS 参数 (基于色盘A拟合)\n\n")
        f.write(
            "说明：RTS 直接拟合每种耗材的等效反射 r 与透射 t（按 RGB 三通道分别拟合），并用多次反射叠加公式做层叠。\n\n"
        )
        f.write("| 耗材名称 | r(R,G,B) | t(R,G,B) |\n")
        f.write("| :--- | :--- | :--- |\n")
        for i, m in enumerate(mats):
            f.write(f"| {m} | {r[i].tolist()} | {t[i].tolist()} |\n")

        f.write("\n**全局参数**:\n")
        f.write(f"- backing_gamma (R,G,B): {_rts_sigmoid(gamma).tolist()}\n")
        f.write(f"- 层数: {int(n_layers)}\n")
        f.write(f"- layer_names_order: {str(rts_model['layer_names_order'])}\n\n")

        fit_cells = [c for c in ds.cells if c.enabled and c.recipe]
        seqs = _rts_sequences_from_cells(fit_cells, n_layers)
        pred_rgb01 = _rts_predict_rgb01_for_sequences(seqs, rts_model)
        pred_lab = rgb01_to_lab(pred_rgb01)
        real_rgb01 = (
            np.stack([c.measured_rgb for c in fit_cells], axis=0).astype(np.float32)
            / 255.0
        )
        real_lab = rgb01_to_lab(real_rgb01)
        de_errors = _delta_e76(real_lab, pred_lab)

        f.write("## 2. 真实图片 vs 预测 RGB 对比 (色盘A)\n\n")
        f.write("**统计摘要**:\n")
        f.write(f"- 平均 DeltaE76: {np.mean(de_errors):.4f}\n")
        f.write(f"- 最大 DeltaE76: {np.max(de_errors):.4f}\n")
        f.write(f"- 中位数 DeltaE76: {np.median(de_errors):.4f}\n\n")

        f.write("| 行 | 列 | 配方 | 真实 RGB (U8) | 预测 RGB (U8) | DeltaE76 |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")

        for i, c in enumerate(fit_cells):
            r_u8 = (real_rgb01[i] * 255 + 0.5).astype(int).tolist()
            p_u8 = (pred_rgb01[i] * 255 + 0.5).astype(int).tolist()
            recipe_str = ", ".join([f"{k}:{v}" for k, v in c.recipe.items() if v > 0])
            f.write(
                f"| {c.row} | {c.col} | {recipe_str} | {r_u8} | {p_u8} | {de_errors[i]:.2f} |\n"
            )

        f.write("\n## 3. 可视化测试样本对比 (Real vs Predicted)\n\n")
        f.write("### 3.1 纯色预览 (5层)\n\n")
        f.write("| 目标 | 预测 RGB (U8) |\n")
        f.write("| :--- | :--- |\n")
        pure_targets = [
            "White",
            "Black",
            "Red",
            "Green",
            "Blue",
            "Cyan",
            "Magenta",
            "Yellow",
        ]
        pure_sequences = []
        pure_labels = []
        for t_name in pure_targets:
            matched = [m for m in mats if m.lower() == t_name.lower()]
            if matched:
                pure_sequences.append([matched[0]] * int(n_layers))
                pure_labels.append(t_name)
        if pure_sequences:
            pure_pred = _rts_predict_rgb01_for_sequences(pure_sequences, rts_model)
            for i, label in enumerate(pure_labels):
                p_u8 = (pure_pred[i] * 255 + 0.5).astype(int).tolist()
                f.write(f"| {label} | {p_u8} |\n")

        f.write("\n### 3.2 典型样本对比 (色盘A前12个点)\n\n")
        f.write("| 样本标签 | 配方 | 真实 RGB (U8) | 预测 RGB (U8) | DeltaE76 |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")

        sample_cells = fit_cells[:12]
        sample_seqs = _rts_sequences_from_cells(sample_cells, n_layers)
        sample_pred = _rts_predict_rgb01_for_sequences(sample_seqs, rts_model)
        sample_real = (
            np.stack([c.measured_rgb for c in sample_cells], axis=0).astype(np.float32)
            / 255.0
        )
        sample_de = _delta_e76(rgb01_to_lab(sample_real), rgb01_to_lab(sample_pred))
        for i, c in enumerate(sample_cells):
            r_u8 = (sample_real[i] * 255 + 0.5).astype(int).tolist()
            p_u8 = (sample_pred[i] * 255 + 0.5).astype(int).tolist()
            recipe_str = ", ".join([f"{k}:{v}" for k, v in c.recipe.items() if v > 0])
            items = [f"{k[0]}{int(v)}" for k, v in c.recipe.items() if v > 0]
            label = "+".join(items)
            f.write(
                f"| {label} | {recipe_str} | {r_u8} | {p_u8} | {sample_de[i]:.2f} |\n"
            )

    return report_path


def _run_single_visualization_rts(
    rts_model: dict,
    out_dir: Path,
    ds,
    n_layers: int,
) -> dict:
    model_type = "rts"
    impl_name = "numpy"

    report_path = _generate_text_report_rts(
        rts_model=rts_model,
        model_type=model_type,
        impl_name=impl_name,
        ds=ds,
        out_dir=out_dir,
        n_layers=n_layers,
    )

    mats = list(rts_model["mats"])

    pure_targets = [
        "White",
        "Black",
        "Red",
        "Green",
        "Blue",
        "Cyan",
        "Magenta",
        "Yellow",
    ]
    pure_sequences = []
    pure_labels = []
    for t_name in pure_targets:
        matched = [m for m in mats if m.lower() == t_name.lower()]
        if matched:
            pure_sequences.append([matched[0]] * int(n_layers))
            pure_labels.append(t_name)
    if pure_sequences:
        pure_rgb = _rts_predict_rgb01_for_sequences(pure_sequences, rts_model)
        pure_img = _create_color_strip(list(pure_rgb), pure_labels)
        pure_path = out_dir / f"pure_{model_type}_{impl_name}.png"
        cv2.imwrite(str(pure_path), pure_img)
    else:
        pure_path = out_dir / f"pure_{model_type}_{impl_name}.png"

    fit_cells = [c for c in ds.cells if c.enabled and c.recipe]
    sample_cells = fit_cells[:12]
    sample_seqs = _rts_sequences_from_cells(sample_cells, n_layers)
    sample_pred_rgb = _rts_predict_rgb01_for_sequences(sample_seqs, rts_model)
    sample_real_rgb = (
        np.stack([c.measured_rgb for c in sample_cells], axis=0).astype(np.float32)
        / 255.0
    )

    sample_labels = []
    for c in sample_cells:
        items = [f"{k[0]}{int(v)}" for k, v in c.recipe.items() if v > 0]
        sample_labels.append("+".join(items))

    comp_img = _create_comparison_strip(
        list(sample_real_rgb), list(sample_pred_rgb), sample_labels, cell_w=150
    )
    comp_path = out_dir / f"compare_{model_type}_{impl_name}.png"
    cv2.imwrite(str(comp_path), comp_img)

    return {
        "report_path": report_path.name,
        "pure_path": pure_path.name,
        "comp_path": comp_path.name,
        "model": model_type,
        "impl": impl_name,
    }


def _create_color_strip(
    colors_rgb: list[np.ndarray], labels: list[str], cell_w=200, cell_h=150
) -> np.ndarray:
    n = len(colors_rgb)
    canvas = np.zeros((cell_h, n * cell_w, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX

    for i, (rgb, label) in enumerate(zip(colors_rgb, labels)):
        x1, x2 = i * cell_w, (i + 1) * cell_w
        # Convert RGB [0,1] to BGR [0,255]
        bgr = (rgb[::-1] * 255.0).astype(np.uint8)
        canvas[:, x1:x2] = bgr

        # Text color based on brightness
        brightness = np.mean(rgb)
        t_color = (0, 0, 0) if brightness > 0.5 else (255, 255, 255)

        cv2.putText(canvas, label, (x1 + 10, 30), font, 0.5, t_color, 1)
        rgb_int = (rgb * 255).astype(int)
        cv2.putText(
            canvas, f"{rgb_int.tolist()}", (x1 + 10, cell_h - 10), font, 0.4, t_color, 1
        )

    return canvas


def _create_comparison_strip(
    real_rgbs: list[np.ndarray],
    pred_rgbs: list[np.ndarray],
    labels: list[str],
    cell_w=200,
    cell_h=200,
) -> np.ndarray:
    n = len(real_rgbs)
    canvas = np.zeros((cell_h, n * cell_w, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX

    for i, (real, pred, label) in enumerate(zip(real_rgbs, pred_rgbs, labels)):
        x1, x2 = i * cell_w, (i + 1) * cell_w

        # Top half: Real
        bgr_real = (real[::-1] * 255.0).astype(np.uint8)
        canvas[: cell_h // 2, x1:x2] = bgr_real

        # Bottom half: Predicted
        bgr_pred = (pred[::-1] * 255.0).astype(np.uint8)
        canvas[cell_h // 2 :, x1:x2] = bgr_pred

        # Divider
        cv2.line(canvas, (x1, cell_h // 2), (x2, cell_h // 2), (255, 255, 255), 1)

        # Labels
        # Text color based on brightness
        brightness_real = np.mean(real)
        t_color_real = (0, 0, 0) if brightness_real > 0.5 else (255, 255, 255)
        cv2.putText(canvas, f"R: {label}", (x1 + 5, 20), font, 0.4, t_color_real, 1)

        brightness_pred = np.mean(pred)
        t_color_pred = (0, 0, 0) if brightness_pred > 0.5 else (255, 255, 255)
        cv2.putText(
            canvas, "P:", (x1 + 5, cell_h // 2 + 20), font, 0.4, t_color_pred, 1
        )

        # RGB values
        r_u8 = (real * 255).astype(int)
        p_u8 = (pred * 255).astype(int)
        cv2.putText(
            canvas,
            f"{r_u8.tolist()}",
            (x1 + 5, cell_h // 2 - 10),
            font,
            0.35,
            t_color_real,
            1,
        )
        cv2.putText(
            canvas,
            f"{p_u8.tolist()}",
            (x1 + 5, cell_h - 10),
            font,
            0.35,
            t_color_pred,
            1,
        )

    return canvas


def _run_single_visualization(
    material_keys: list[str],
    optical_params: OpticalParams,
    model_type: str,
    use_vulkan: bool,
    out_dir: Path,
    ds,
    black_offset: float = 0.0,
    white_offset: float = 0.0,
    layer_names_order: str = "bottom_first",
) -> dict:
    impl_name = "vulkan" if use_vulkan else "numpy"

    # 1. 生成详细文本报告
    report_path = _generate_text_report(
        material_keys,
        optical_params,
        model_type,
        impl_name,
        ds,
        out_dir,
        layer_names_order=layer_names_order,
    )

    # 2. 纯色预览 (5层)
    pure_targets = [
        "White",
        "Black",
        "Red",
        "Green",
        "Blue",
        "Cyan",
        "Magenta",
        "Yellow",
    ]
    pure_sequences = []
    pure_labels = []
    for t in pure_targets:
        matched = [m for m in material_keys if m.lower() == t.lower()]
        if matched:
            pure_sequences.append([matched[0]] * 5)
            pure_labels.append(t)

    pure_rgb = predict_ad_rgb01(
        pure_sequences,
        material_keys,
        optical_params,
        use_vulkan=use_vulkan,
        model_type=model_type,
    )
    pure_img = _create_color_strip(list(pure_rgb), pure_labels)
    pure_path = out_dir / f"pure_{model_type}_{impl_name}.png"
    cv2.imwrite(str(pure_path), pure_img)

    # 3. 真实样本对比 (从 dataset 中选一些典型的混色)
    # 选前几个 enabled 且有 recipe 的 cell，通常包含了一些混色
    fit_cells = [c for c in ds.cells if c.enabled and c.recipe]
    # 我们选一些有代表性的：比如 row 0 和 row 1 的一些样本，它们通常包含纯色和简单的混色
    sample_cells = fit_cells[:12]  # 选前12个作为展示

    sample_recipes = []
    for c in sample_cells:
        r = dict(c.recipe)
        r["_layer_names"] = getattr(c, "layer_names", [])
        sample_recipes.append(r)
    from oc_proto.calib_color_model_fit.xgb_features import build_layer_sequences

    sample_sequences = build_layer_sequences(
        sample_recipes, material_keys, n_layers=5, layer_names_order=layer_names_order
    )

    sample_pred_rgb = predict_ad_rgb01(
        sample_sequences,
        material_keys,
        optical_params,
        use_vulkan=use_vulkan,
        model_type=model_type,
    )
    sample_real_rgb = (
        np.stack([c.measured_rgb for c in sample_cells], axis=0).astype(np.float32)
        / 255.0
    )

    sample_labels = []
    for c in sample_cells:
        # 简短的配方标签
        items = [f"{k[0]}{int(v)}" for k, v in c.recipe.items() if v > 0]
        sample_labels.append("+".join(items))

    comp_img = _create_comparison_strip(
        list(sample_real_rgb), list(sample_pred_rgb), sample_labels, cell_w=150
    )
    comp_path = out_dir / f"compare_{model_type}_{impl_name}.png"
    cv2.imwrite(str(comp_path), comp_img)

    return {
        "report_path": report_path.name,
        "pure_path": pure_path.name,
        "comp_path": comp_path.name,
        "model": model_type,
        "impl": impl_name,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--black-offset", type=float, default=0.0)
    p.add_argument("--white-offset", type=float, default=0.0)
    p.add_argument(
        "--layer-names-order",
        choices=["bottom_first", "top_first"],
        default="bottom_first",
        help="数据集中 layer_names 的顺序：bottom_first 表示第0层是底层；top_first 表示第0层是顶层",
    )
    args = p.parse_args()

    # 路径设置
    current_dir = Path(__file__).parent
    palette_a_path = current_dir / "data" / "dataset_cells.json"
    out_dir = current_dir / "out" / "visualization"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not palette_a_path.exists():
        logger.error(f"错误：未找到数据集文件: {palette_a_path}")
        return

    # 加载数据进行拟合
    ds = load_dataset(
        palette_a_path, black_offset=args.black_offset, white_offset=args.white_offset
    )
    fit_cells = [c for c in ds.cells if c.enabled and c.recipe]
    recipes = []
    for c in fit_cells:
        r = dict(c.recipe)
        r["_layer_names"] = getattr(c, "layer_names", [])
        recipes.append(r)
    y_rgb01 = (
        np.stack([c.measured_rgb for c in fit_cells], axis=0).astype(np.float32) / 255.0
    )
    y_lab = rgb01_to_lab(y_rgb01)
    material_keys = sorted(list(set().union(*[r.keys() for r in recipes])))

    from oc_proto.calib_color_model_fit.xgb_features import build_layer_sequences

    sequences = build_layer_sequences(
        recipes,
        material_keys,
        n_layers=5,
        layer_names_order=str(args.layer_names_order),
    )

    # 拟合配置
    cfg = PhysGPRConfig(
        n_layers=5,
        opt_steps=300,
        opt_reg=1e-6,
        gpr_noise=1e-7,
        gpr_lengthscale=0.1,
        gpr_signal=1.0,
        gpr_jitter=1e-9,
        use_vulkan=False,  # 拟合用 numpy 比较稳
        optical_model="four_flux",
    )

    logger.info("正在拟合四通量光学参数（用于 four_flux/tmm 可视化）...")
    optical_params = fit_optical_params(sequences, y_lab, material_keys, cfg)

    # 运行四种组合
    combinations = [
        ("four_flux", False),
        ("four_flux", True),
        ("tmm", False),
        ("tmm", True),
    ]

    results = []
    for m_type, use_vk in combinations:
        logger.info(f"正在生成可视化: {m_type} ({'vulkan' if use_vk else 'numpy'})...")
        res = _run_single_visualization(
            material_keys,
            optical_params,
            m_type,
            use_vk,
            out_dir,
            ds,
            layer_names_order=str(args.layer_names_order),
        )
        results.append(res)

    logger.info("正在拟合 RTS 参数并生成可视化...")
    rts_model = _rts_fit_model(
        train_ds=ds,
        n_layers=5,
        layer_names_order=str(args.layer_names_order),
        max_nfev=600,
        reg=1e-3,
    )
    results.append(
        _run_single_visualization_rts(
            rts_model=rts_model,
            out_dir=out_dir,
            ds=ds,
            n_layers=5,
        )
    )

    # 生成汇总索引报告
    report_path = out_dir / "INDEX.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 物理模型可视化报告索引\n\n")
        f.write(f"生成时间: {np.datetime64('now')}\n\n")

        for res in results:
            f.write(f"## 模型: {res['model']} | 实现: {res['impl']}\n\n")
            f.write(f"- [查看详细文本报告]({res['report_path']})\n")
            f.write(f"- [查看纯色预览图]({res['pure_path']})\n")
            f.write(f"- [查看真实vs预测对比图]({res['comp_path']})\n\n")
            f.write("---\n\n")

    logger.info(f"\n可视化完成，索引已保存到: {report_path}")


if __name__ == "__main__":
    main()
