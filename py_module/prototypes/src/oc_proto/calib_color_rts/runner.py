"""
模型训练运行器模块
执行色彩模型拟合的完整流程：加载数据、训练物理GPR模型、生成诊断报告
支持多色盘数据加载和分别可视化
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from oc_core_02.utils.manifest import write_manifest
from oc_proto.calib_color_rts.cli import FitArgs, VERSION
from oc_xgb.color_space import rgb01_to_lab, lab_to_rgb01
from oc_proto.calib_color_rts.dataset_io import load_dataset, filter_training_cells, Dataset, Cell, apply_bw_calibration_inverse
from oc_proto.calib_color_rts.diagnostics import compute_diagnostics, render_boards_for_palette
from oc_xgb.model_io import save_model
from oc_xgb.xgb_features import infer_material_keys, build_gpr_features, build_layer_sequences
from oc_xgb.xgb_fit import PhysGPRConfig, predict_ad_rgb01, predict_phys_gpr_lab, train_phys_gpr, fit_optical_params



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _load_all_datasets(dataset_path: Path, black_offset: float = 0.0, white_offset: float = 0.0) -> dict[str, Dataset]:
    """
    加载所有色盘的数据集。
    如果 dataset_path 是单个文件，尝试查找同目录下的其他色盘数据文件。
    返回字典: {palette_id: Dataset}
    
    Args:
        dataset_path: 数据集路径
        black_offset: 黑场偏移量（0-255范围）
        white_offset: 白场偏移量（0-255范围）
    """
    datasets: dict[str, Dataset] = {}
    data_dir = dataset_path.parent
    
    # 标准色盘ID列表 A-H
    palette_ids = [chr(65 + i) for i in range(8)]  # A, B, C, D, E, F, G, H
    
    for pid in palette_ids:
        # 色盘A使用默认文件名，其他使用 _{pid} 后缀
        if pid == "A":
            candidate = data_dir / "dataset_cells.json"
            if not candidate.exists():
                candidate = data_dir / "dataset_cells_A.json"
        else:
            candidate = data_dir / f"dataset_cells_{pid}.json"
        
        if candidate.exists():
            try:
                ds = load_dataset(candidate, palette_id=pid, 
                                black_offset=black_offset, white_offset=white_offset)
                datasets[pid] = ds
            except Exception as e:
                logger.error(f"[{VERSION}] 警告: 加载色盘 {pid} 数据失败: {e}")
    
    return datasets


def _predict_for_dataset(
    ds: Dataset,
    model,
    cfg: PhysGPRConfig,
    material_keys: list[str],
    memorizer: dict[str, list[int]] | None = None
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """
    对单个数据集进行预测。
    返回: (pred_u8, X_all, diags)
    
    注意：如果数据集有黑白校准参数，预测结果会自动应用逆向映射。
    """
    # Predict for ALL cells
    recipes_all = []
    for c in ds.cells:
        r = dict(c.recipe)
        r["_layer_names"] = getattr(c, "layer_names", [])
        recipes_all.append(r)
    
    sequences_all = build_layer_sequences(
        recipes_all,
        model.optical.material_keys,
        cfg.n_layers,
        layer_names_order=cfg.layer_names_order,
    )
    base_rgb01 = predict_ad_rgb01(
        sequences_all, 
        model.optical.material_keys, 
        model.optical, 
        use_vulkan=cfg.use_vulkan,
        backing=model.optical.backing,
        k1=model.optical.k1,
        k2=model.optical.k2,
        model_type=cfg.optical_model,
    )
    base_lab = rgb01_to_lab(base_rgb01)
    X_all, _ = build_gpr_features(
        recipes_all, 
        model.optical.material_keys, 
        base_lab, 
        n_layers=cfg.n_layers,
        layer_names_order=cfg.layer_names_order,
        k1=model.optical.k1,
        k2=model.optical.k2,
        backing=model.optical.backing
    )
    pred_lab = predict_phys_gpr_lab(
        model, 
        sequences_all, 
        X_all, 
        use_vulkan=cfg.use_vulkan,
        optical_model=cfg.optical_model,
    )
    pred_rgb01 = lab_to_rgb01(pred_lab)
    pred_u8 = (pred_rgb01 * 255.0 + 0.5).astype(np.uint8)
    
    # 应用黑白校准的逆向映射（输出后）
    if ds.black_offset > 0 or ds.white_offset > 0:
        for i in range(len(pred_u8)):
            pred_u8[i] = apply_bw_calibration_inverse(pred_u8[i], ds.black_offset, ds.white_offset)
    
    bias_round = np.zeros(3, dtype=np.float32)
    
    # 应用 memorizer 覆盖
    if memorizer:
        for i, c in enumerate(ds.cells):
            if not (c.enabled and bool(c.recipe)):
                continue
            key = f"{int(c.row)},{int(c.col)}"
            v = memorizer.get(key)
            if v is not None:
                pred_u8[i, :] = np.array(v, dtype=np.uint8)
    
    return pred_u8, X_all, bias_round


def _collect_recipes_from_cells(cells: list[Cell]) -> list[dict[str, float]]:
    recipes: list[dict[str, float]] = []
    for c in cells:
        r = dict(c.recipe)
        r["_layer_names"] = c.layer_names
        recipes.append(r)
    return recipes


def _infer_material_keys_from_recipes(recipes: list[dict[str, float]]) -> list[str]:
    material_keys_raw = infer_material_keys(recipes)
    if "WHITE" not in [k.upper() for k in material_keys_raw]:
        material_keys_raw.append("WHITE")
    return sorted(list(set(k.upper() for k in material_keys_raw)))


def _needs_synthesis(ds: Dataset) -> bool:
    vals = []
    for c in ds.cells:
        if not (c.enabled and bool(c.recipe)):
            continue
        vals.append(c.measured_rgb)
    if not vals:
        return False
    for v in vals:
        if int(v[0]) != 0 or int(v[1]) != 0 or int(v[2]) != 0:
            return False
    return True


def _infer_train_palette_id(dataset_path: Path) -> str:
    name = dataset_path.name
    if name in {"dataset_cells.json", "dataset_cells_A.json"}:
        return "A"
    m = re.match(r"dataset_cells_([A-Za-z])\.json$", name)
    if m:
        return m.group(1).upper()
    return "A"


def synthesize_palettes_from_a(
    datasets: dict[str, Dataset],
    train_palette_id: str,
    cfg: PhysGPRConfig,
    force_synthesis_ids: list[str] | None = None
) -> None:
    train_ds = datasets.get(train_palette_id)
    if train_ds is None:
        train_ds = datasets.get("A")
    if train_ds is None and datasets:
        train_ds = list(datasets.values())[0]
    if train_ds is None:
        return

    train_cells = filter_training_cells(train_ds)
    train_recipes = _collect_recipes_from_cells(train_cells)
    if not train_recipes:
        return

    material_keys = _infer_material_keys_from_recipes(train_recipes)
    sequences = build_layer_sequences(train_recipes, material_keys, cfg.n_layers, layer_names_order=cfg.layer_names_order)
    train_rgb01 = np.stack([c.measured_rgb for c in train_cells], axis=0).astype(np.float32) / 255.0
    y_lab = rgb01_to_lab(train_rgb01)
    optical = fit_optical_params(sequences, y_lab, material_keys, cfg)

    force_ids = [fid.upper() for fid in (force_synthesis_ids or [])]

    for pid, ds in datasets.items():
        pid_u = pid.upper()
        if pid_u == train_ds.palette_id.upper():
            continue
            
        # 检查是否需要强制合成（即使用 A 的参数覆盖现有数据用于训练）
        should_force = pid_u in force_ids
        needs_syn = _needs_synthesis(ds)
        
        if not needs_syn and not should_force:
            continue
            
        # 如果色盘本身有真实测量值，但你希望用“色盘A的物理参数”生成合成对照值，
        # 则将合成值写入 target_rgb（用于训练误差/对照渲染），并保留 measured_rgb 作为真实测量值。
        # 这样可以避免评估阶段出现“predicted_board 和 measured_board 过于相似”的假象（训练泄露/覆盖）。
        if not needs_syn and should_force:
            # 保留 measured_rgb，不做覆盖；合成值稍后写入 target_rgb
            pass
        
        recipes = _collect_recipes_from_cells(ds.cells)
        seq = build_layer_sequences(recipes, material_keys, cfg.n_layers, layer_names_order=cfg.layer_names_order)
        pred_rgb01 = predict_ad_rgb01(
            seq, 
            material_keys, 
            optical, 
            use_vulkan=cfg.use_vulkan,
            backing=cfg.backing,
            k1=cfg.k1,
            k2=cfg.k2,
            model_type=cfg.optical_model,
        )
        pred_u8 = (pred_rgb01 * 255.0 + 0.5).astype(np.uint8)
        
        for i, c in enumerate(ds.cells):
            if needs_syn:
                # 没有真实测量值的色盘：将外推合成值写入 measured_rgb，供后续流程使用
                c.measured_rgb = pred_u8[i]
            else:
                # 有真实测量值的色盘（例如 B~E）：将外推合成值写入 target_rgb，作为“合成对照/训练目标”
                # measured_rgb 保留真实测量值，用于评估真实误差
                c.target_rgb = pred_u8[i]

        msg = "生成合成对照(target_rgb)" if should_force and (not needs_syn) else ("自动补充合成(measured_rgb)" if needs_syn else "跳过")
        logger.info(f"[{VERSION}] 已用色盘{train_ds.palette_id}的物理参数 {msg}: 色盘 {ds.palette_id}")


def run_fit(args: FitArgs) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载所有色盘的数据（应用黑白校准）
    datasets = _load_all_datasets(Path(args.dataset), 
                                  black_offset=args.black_offset, 
                                  white_offset=args.white_offset)
    if not datasets:
        raise RuntimeError(f"未找到任何有效的数据集文件")
    
    # 打印黑白校准信息
    if args.black_offset > 0 or args.white_offset > 0:
        logger.info(f"[{VERSION}] 黑白校准已启用: black_offset={args.black_offset}, white_offset={args.white_offset}")
    else:
        logger.info(f"[{VERSION}] 黑白校准已禁用")
    
    logger.info(f"[{VERSION}] 加载了 {len(datasets)} 个色盘的数据: {list(datasets.keys())}")

    cfg = PhysGPRConfig(
        n_layers=args.n_layers,
        opt_steps=args.opt_steps,
        opt_reg=args.opt_reg,
        gpr_noise=args.gpr_noise,
        gpr_lengthscale=args.gpr_lengthscale,
        gpr_signal=args.gpr_signal,
        gpr_jitter=args.gpr_jitter,
        use_vulkan=args.use_vulkan,
        k1=args.k1,
        k2=args.k2,
        backing=args.backing,
        optimize_k=args.optimize_k,
        pure_weight=args.pure_weight,
        optical_model=args.optical_model,
        layer_names_order=args.layer_names_order,
    )

    # 只使用色盘A的真实数据来拟合物理/耗材参数（optical）
    train_pid = "A"
    if train_pid not in datasets:
        raise RuntimeError(f"未找到色盘A的数据集（dataset_cells_A.json / dataset_cells.json）。当前已有: {list(datasets.keys())}")
    # 为 B~E 生成“外推合成对照值”写入 target_rgb（不覆盖其真实 measured_rgb）
    # 同时对缺失测量值的色盘（例如 F~H）自动写入 measured_rgb
    synthesize_palettes_from_a(datasets, train_pid, cfg, force_synthesis_ids=["B","C","D","E"])

    
    # 训练只使用色盘A的真实训练样本（避免 B~E 真实数据泄露进训练/造成“看起来像作假”的评估）
    all_train_cells: list[Cell] = []
    ds_a = datasets["A"]
    train_cells_a = filter_training_cells(ds_a)
    for c in train_cells_a:
        c.palette_id = "A"
    all_train_cells.extend(train_cells_a)
    logger.info(f"[{VERSION}] 色盘 A: {len(train_cells_a)} 个训练样本 (仅此色盘参与训练)")

    # 其他色盘仅用于评估/对照渲染：其真实 measured_rgb 不参与训练目标
    for pid in sorted([k for k in datasets.keys() if k.upper() != "A"]):
        ds = datasets[pid]
        n_enabled = sum(1 for c in ds.cells if c.enabled and bool(c.recipe))
        logger.info(f"[{VERSION}] 色盘 {pid}: {n_enabled} 个有效格子 (不参与训练)")

    if len(all_train_cells) < 10:
        raise RuntimeError(f"训练样本不足: {len(all_train_cells)}。请检查数据集配置。")
    
    train_recipes = []
    for c in all_train_cells:
        r = dict(c.recipe)
        r["_layer_names"] = c.layer_names
        train_recipes.append(r)
    
    material_keys = _infer_material_keys_from_recipes(train_recipes)
    
    logger.info(f"[{VERSION}] 总训练样本数: {len(all_train_cells)}")
    
    # 训练集"背诵"模式
    memorize_enabled = (args.memorize_mode == "train")
    memorizer: dict[str, dict[str, list[int]]] = {}  # {palette_id: {row,col: rgb}}
    if memorize_enabled:
        for c in all_train_cells:
            pid = c.palette_id
            if pid not in memorizer:
                memorizer[pid] = {}
            key = f"{int(c.row)},{int(c.col)}"
            memorizer[pid][key] = [int(x) for x in c.measured_rgb.tolist()]
        logger.info(f"[{VERSION}] Memorizer 已启用: 训练集预测值将被测量值覆盖")
    else:
        logger.info(f"[{VERSION}] Memorizer 已禁用: 显示模型真实预测误差")
    
    rgb01_train = np.stack([c.measured_rgb for c in all_train_cells], axis=0).astype(np.float32) / 255.0
    Y_train = rgb01_to_lab(rgb01_train)
    
    # 构造元数据用于冲突诊断
    meta_list = []
    for c in all_train_cells:
        meta_list.append({
            "palette": getattr(c, "palette_id", "A"),
            "row": int(c.row),
            "col": int(c.col)
        })
    
    model = train_phys_gpr(train_recipes, Y_train, material_keys, cfg, metadata=meta_list)
    logger.info(f"[{VERSION}] 训练特征数: {len(model.feature_names)}")
    
    # 对每个色盘分别进行预测和可视化
    all_diags: list[dict] = []
    all_summaries: dict[str, dict] = {}
    total_override = 0
    
    for pid, ds in sorted(datasets.items()):
        logger.info(f"[{VERSION}] 处理色盘 {pid}...")
        
        pid_memorizer = memorizer.get(pid) if memorize_enabled else None
        pred_u8, X_all, bias_round = _predict_for_dataset(ds, model, cfg, material_keys, pid_memorizer)
        
        # 计算诊断信息
        diags, summary = compute_diagnostics(
            cells_all=ds.cells,
            material_keys=material_keys,
            feature_names=model.feature_names,
            X_all=X_all,
            pred_rgb=pred_u8,
            out_dir=out_dir,
            palette_id=pid,
        )
        
        all_diags.extend(diags)
        all_summaries[pid] = summary
        
        # 统计覆盖数量
        if memorize_enabled and pid_memorizer:
            n_override = 0
            for c in ds.cells:
                if c.enabled and bool(c.recipe):
                    key = f"{int(c.row)},{int(c.col)}"
                    if key in pid_memorizer:
                        n_override += 1
            total_override += n_override
        
        # 渲染该色盘的板子
        render_boards_for_palette(diags, out_dir, palette_id=pid, flip_first_layer=True)
    
    # 保存模型元数据
    meta = {
        "version": VERSION,
        "dataset_path": str(Path(args.dataset).resolve()),
        "palette_ids": list(datasets.keys()),
        "train_palette_id": "A",
        "train_real_palettes": ["A"],
        "forced_synthesis_ids": ["B","C","D","E"],
        "memorize_mode": args.memorize_mode,
        "color_space": "lab",
        "optical_model": cfg.optical_model,
        "layer_names_order": cfg.layer_names_order,
        "use_vulkan": bool(cfg.use_vulkan),
        "k1": float(cfg.k1),
        "k2": float(cfg.k2),
        "backing": float(cfg.backing),
        "phys_gpr_params": {
            "n_layers": cfg.n_layers,
            "opt_steps": cfg.opt_steps,
            "opt_reg": cfg.opt_reg,
            "gpr_noise": cfg.gpr_noise,
            "gpr_lengthscale": cfg.gpr_lengthscale,
            "gpr_signal": cfg.gpr_signal,
            "gpr_jitter": cfg.gpr_jitter,
        },
    }
    save_model(model, out_dir, meta)
    
    # 计算全局统计
    total_cells = sum(s["n_cells_total"] for s in all_summaries.values())
    total_fit = sum(s["n_cells_fit"] for s in all_summaries.values())
    mean_error = np.mean([s["mean_error_rgb"] for s in all_summaries.values()])
    p95_error = np.mean([s["p95_error_rgb"] for s in all_summaries.values()])
    mean_de = np.mean([s["mean_deltaE76"] for s in all_summaries.values()])
    p95_de = np.mean([s["p95_deltaE76"] for s in all_summaries.values()])
    
    # 打印训练结果摘要
    logger.info(f"[{VERSION}] --- 训练结果摘要 ---")
    logger.info(f"[{VERSION}] 色盘数量: {len(datasets)}")
    logger.info(f"[{VERSION}] 样本总数: {total_cells}")
    logger.info(f"[{VERSION}] 参与拟合样本数: {total_fit}")
    logger.error(f"[{VERSION}] 平均 RGB 误差: {mean_error:.4f}")
    logger.error(f"[{VERSION}] P95 RGB 误差: {p95_error:.4f}")
    logger.info(f"[{VERSION}] 平均 DeltaE76: {mean_de:.4f}")
    logger.info(f"[{VERSION}] P95 DeltaE76: {p95_de:.4f}")
    
    if memorize_enabled:
        logger.info(f"[{VERSION}] memorizer: 覆盖 {total_override}/{len(all_train_cells)} 个训练格子")
    
    # 保存全局诊断信息
    (out_dir / "fit_diagnostics.json").write_text(
        json.dumps(all_diags, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    global_summary = {
        "n_palettes": len(datasets),
        "palette_ids": list(datasets.keys()),
        "n_cells_total": total_cells,
        "n_cells_fit": total_fit,
        "mean_error_rgb": float(mean_error),
        "p95_error_rgb": float(p95_error),
        "mean_deltaE76": float(mean_de),
        "p95_deltaE76": float(p95_de),
        "per_palette": all_summaries,
    }
    (out_dir / "fit_summary.json").write_text(
        json.dumps(global_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    # Persist memorizer
    if memorize_enabled:
        (out_dir / "memorizer.json").write_text(
            json.dumps(
                {
                    "version": VERSION,
                    "datasets": {pid: str(ds.palette_id) for pid, ds in datasets.items()},
                    "key_format": "palette_id:row,col",
                    "n_entries": sum(len(m) for m in memorizer.values()),
                    "map": memorizer,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    else:
        mem_file = out_dir / "memorizer.json"
        if mem_file.exists():
            mem_file.unlink()
    
    # manifest
    write_manifest(
        out_dir,
        {
            "version": VERSION,
            "dataset": str(Path(args.dataset).resolve()),
            "summary": global_summary,
            "memorizer": {
                "enabled": memorize_enabled,
                "n_entries": sum(len(m) for m in memorizer.values()) if memorize_enabled else 0,
                "n_override": total_override,
                "file": "memorizer.json" if memorize_enabled else None,
            },
        },
    )
