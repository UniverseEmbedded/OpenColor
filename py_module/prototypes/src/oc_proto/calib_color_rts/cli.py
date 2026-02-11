"""
命令行接口模块
解析命令行参数，自动准备默认数据集
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
VERSION = "calib_color_model_fit"


def _prepare_default_data() -> Path | None:
    """
    自动准备默认数据：
    1. 尝试从 calib_sample_build/out 复制所有 dataset_cells*.json 文件。
    2. 如果没找到，尝试运行 calib_board_gen 生成规格，并根据规格生成 mock 数据。
    返回默认的 dataset 路径。
    """
    import subprocess
    import sys
    from oc_calib.spec_adapter import SpecAdapter, extract_layer_sequence
    from oc_xgb.xgb_fit import predict_ad_rgb01, OpticalParams
    import numpy as np

    MOCK_MATS = ["WHITE", "BLACK", "RED", "GREEN", "BLUE", "CYAN", "MAGENTA", "YELLOW"]
    mock_mu_a = np.zeros((len(MOCK_MATS), 3), dtype=np.float32)
    mock_mu_s = np.zeros((len(MOCK_MATS), 3), dtype=np.float32)
    mock_g = np.zeros((len(MOCK_MATS), 3), dtype=np.float32)

    for i, name in enumerate(MOCK_MATS):
        if name == "WHITE":
            mock_mu_a[i] = -5.0
            mock_mu_s[i] = 2.0
        elif name == "BLACK":
            mock_mu_a[i] = 3.0
            mock_mu_s[i] = -2.0
        elif name == "RED":
            mock_mu_a[i] = [-5.0, 3.0, 3.0]
            mock_mu_s[i] = 1.0
        elif name == "GREEN":
            mock_mu_a[i] = [3.0, -5.0, 3.0]
            mock_mu_s[i] = 1.0
        elif name == "BLUE":
            mock_mu_a[i] = [3.0, 3.0, -5.0]
            mock_mu_s[i] = 1.0
        elif name == "CYAN":
            mock_mu_a[i] = [3.0, -5.0, -5.0]
            mock_mu_s[i] = 1.0
        elif name == "MAGENTA":
            mock_mu_a[i] = [-5.0, 3.0, -5.0]
            mock_mu_s[i] = 1.0
        elif name == "YELLOW":
            mock_mu_a[i] = [-5.0, -5.0, 3.0]
            mock_mu_s[i] = 1.0

    mock_opt = OpticalParams(
        material_keys=MOCK_MATS, mu_a=mock_mu_a, mu_s=mock_mu_s, g=mock_g, n_layers=5
    )

    def _mock_measured_rgb(
        recipe: dict, layer_names: list[str], row: int, col: int
    ) -> list[int]:
        seq = [str(x).upper() for x in (layer_names or []) if str(x).strip()]
        if not seq:
            seq = []
            for k, v in (recipe or {}).items():
                if not str(k).startswith("_") and float(v) > 0.1:
                    seq.append(str(k).upper())

        if not seq:
            return [128, 128, 128]

        rgb01 = predict_ad_rgb01([seq], MOCK_MATS, mock_opt)[0]
        out = [int(max(0, min(255, v * 255.0 + 0.5))) for v in rgb01]
        return out

    def _is_mock_dataset(path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            logger.error(f"[{VERSION}] 读取数据集失败: {path} {e}")
            return False
        cells = data.get("cells", [])
        if not isinstance(cells, list) or not cells:
            return False
        vals = []
        for c in cells:
            rgb = c.get("measured_rgb")
            if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
                vals.append([int(rgb[0]), int(rgb[1]), int(rgb[2])])
        if not vals:
            return False
        first = vals[0]
        for v in vals[1:]:
            if v != first:
                return False
        return True

    prototype_dir = Path(__file__).resolve().parent
    local_data_dir = prototype_dir / "data"
    local_data_dir.mkdir(parents=True, exist_ok=True)

    # 定义源路径
    src_root = prototype_dir.parent / "calib_sample_build"
    src_out_dir = src_root / "out"

    # 1. 尝试同步现有的 dataset_cells*.json
    if src_out_dir.exists():
        # 扫描顶级目录
        for p in src_out_dir.glob("dataset_cells*.json"):
            dst_p = local_data_dir / p.name
            if not dst_p.exists() or p.stat().st_mtime > dst_p.stat().st_mtime:
                logger.info(f"[{VERSION}] 同步数据集: {p.name}")
                shutil.copy2(p, dst_p)

        # 扫描子目录 (Board_A, Board_B, etc.)
        for board_dir in src_out_dir.iterdir():
            if board_dir.is_dir():
                ds_path = board_dir / "dataset_cells.json"
                if ds_path.exists():
                    # 重命名为 dataset_cells_Board_X.json 以便识别
                    palette_id = board_dir.name.replace("Board_", "")
                    dst_name = (
                        f"dataset_cells_{palette_id}.json"
                        if palette_id != "A"
                        else "dataset_cells.json"
                    )
                    dst_p = local_data_dir / dst_name
                    if (
                        not dst_p.exists()
                        or ds_path.stat().st_mtime > dst_p.stat().st_mtime
                    ):
                        logger.info(
                            f"[{VERSION}] 从 {board_dir.name} 同步数据集 -> {dst_name}"
                        )
                        shutil.copy2(ds_path, dst_p)

    # 2. 检查是否集齐了 A-H 色盘，如果没有，尝试通过 calib_board_gen 生成
    required_ids = [chr(65 + i) for i in range(8)]
    missing_ids = []
    refresh_ids: set[str] = set()
    for rid in required_ids:
        if rid == "A":
            if (
                not (local_data_dir / "dataset_cells.json").exists()
                and not (local_data_dir / "dataset_cells_A.json").exists()
            ):
                missing_ids.append(rid)
            else:
                cand = local_data_dir / "dataset_cells.json"
                if not cand.exists():
                    cand = local_data_dir / "dataset_cells_A.json"
                if cand.exists() and _is_mock_dataset(cand):
                    refresh_ids.add("A")
        else:
            if not (local_data_dir / f"dataset_cells_{rid}.json").exists():
                missing_ids.append(rid)
            else:
                cand = local_data_dir / f"dataset_cells_{rid}.json"
                if cand.exists() and _is_mock_dataset(cand):
                    refresh_ids.add(rid)

    ids_to_generate = sorted(set(missing_ids) | refresh_ids)
    if ids_to_generate:
        logger.info(
            f"[{VERSION}] 缺失或为 Mock 的色盘 {ids_to_generate}，正在通过 calib_board_gen 自动生成板子规格并补全 Mock 数据..."
        )
        try:
            # 运行 calib_board_gen 生成 8 个板子
            # 设置 PYTHONPATH 包含项目根目录，以便 calib_board_gen 能找到 generate_8color_board
            # 设置 OPENCOLOR_PROJECT_ROOT 环境变量，以便 calib_board_gen 能找到模板文件
            project_root = prototype_dir.parents[
                4
            ]  # D:\pama1234\pfp\p-2026-01\OpenColor-02
            env = os.environ.copy()
            env["OPENCOLOR_PROJECT_ROOT"] = str(project_root)
            # 这里的 PYTHONPATH 应该包含 src 目录和项目根目录
            src_dir = prototype_dir.parent.parent
            env["PYTHONPATH"] = (
                f"{src_dir}{os.pathsep}{project_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
            )

            gen_cmd = [
                sys.executable,
                "-m",
                "oc_proto.calib_board_gen.main",
                "--num_boards",
                "8",
            ]
            res = subprocess.run(gen_cmd, capture_output=True, env=env, text=True)
            if res.returncode != 0:
                logger.error(f"[{VERSION}] 自动生成数据失败: {res.stderr}")
                return None  # 无法继续生成 mock 数据

            gen_out_dir = prototype_dir.parent / "calib_board_gen" / "out"
            specs = list(gen_out_dir.glob("*_board_spec.json"))
            specs.sort()

            if not specs:
                logger.error(
                    f"[{VERSION}] 错误: calib_board_gen 运行成功但未找到规格文件。"
                )
            else:
                for i, spec_path in enumerate(specs):
                    palette_id = chr(65 + i) if i < 26 else str(i)
                    # 只补全缺失的，或者如果 A 缺失也补全
                    dst_name = (
                        f"dataset_cells_{palette_id}.json"
                        if palette_id != "A"
                        else "dataset_cells.json"
                    )
                    dst_path = local_data_dir / dst_name

                    if palette_id in ids_to_generate:
                        adapter = SpecAdapter(spec_path)
                        cells = []
                        # Board spec 的 cell_map 使用 1-based 索引 (1,1) 到 (15,15)
                        # 但 SpecAdapter._get_cell_raw 期望 0-based 输入并内部转换
                        # 为了避免重复读取，我们直接遍历 0-based 范围
                        for r in range(adapter.rows):
                            for c in range(adapter.cols):
                                recipe = adapter.get_cell_recipe(r, c)
                                # 获取 layer_names - 使用与 get_cell_recipe 相同的坐标逻辑
                                cell_raw = adapter._get_cell_raw(r, c)
                                _, _, layer_names = extract_layer_sequence(cell_raw)

                                # 跳过无法获取配方的格子（如边框标记区域）
                                if not recipe and not layer_names:
                                    continue

                                measured_rgb = (
                                    _mock_measured_rgb(recipe, layer_names, r, c)
                                    if palette_id == "A"
                                    else [0, 0, 0]
                                )
                                cells.append(
                                    {
                                        "row": r,
                                        "col": c,
                                        "enabled": True,
                                        "has_recipe": bool(recipe),
                                        "recipe": recipe,
                                        "layer_names": layer_names,
                                        "measured_rgb": measured_rgb,
                                        "palette_id": palette_id,
                                    }
                                )

                        ds_data = {
                            "palette_id": palette_id,
                            "rows": adapter.rows,
                            "cols": adapter.cols,
                            "spec_path": str(spec_path),
                            "cells": cells,
                        }
                        dst_path.write_text(
                            json.dumps(ds_data, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        logger.info(f"[{VERSION}] 已补全 Mock 数据集: {dst_name}")
        except Exception as e:
            logger.error(f"[{VERSION}] 自动补全数据失败: {e}")

    dst_dataset = local_data_dir / "dataset_cells.json"
    if dst_dataset.exists():
        return dst_dataset

    # 如果只有 dataset_cells_A.json 之类的，选一个作为默认
    other_datasets = list(local_data_dir.glob("dataset_cells_*.json"))
    if other_datasets:
        return other_datasets[0]

    return None


@dataclass
class FitArgs:
    dataset: Path
    out_dir: Path
    n_layers: int
    opt_steps: int
    opt_reg: float
    gpr_noise: float
    gpr_lengthscale: float
    gpr_signal: float
    gpr_jitter: float
    use_vulkan: bool
    optical_model: str = "rts"
    memorize_mode: str = "off"  # "train" or "off" (默认 off，避免"背诵"误导)
    k1: float = 0.04
    k2: float = 0.0
    backing: float = 0.98
    optimize_k: bool = False
    pure_weight: float = 10.0
    layer_names_order: str = "bottom_first"
    # 黑白校准参数
    black_offset: float = 0.0  # 黑场偏移量（0-255范围，例如32表示黑色映射到32）
    white_offset: float = 0.0  # 白场偏移量（0-255范围，例如32表示白色映射到223）


def parse_args(argv: list[str] | None = None) -> FitArgs:
    p = argparse.ArgumentParser(prog=VERSION)

    # 自动准备数据并获取默认 dataset 路径
    default_dataset = _prepare_default_data()

    p.add_argument(
        "--dataset",
        type=Path,
        default=default_dataset,
        required=default_dataset is None,
        help="Path to dataset_cells.json (default: local data/dataset_cells.json)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "out",
        help="Output directory (default: local out/)",
    )

    p.add_argument("--n-layers", type=int, default=5)
    p.add_argument("--opt-steps", type=int, default=300)
    p.add_argument("--opt-reg", type=float, default=1e-6)
    p.add_argument("--gpr-noise", type=float, default=1e-7)
    p.add_argument("--gpr-lengthscale", type=float, default=0.1)
    p.add_argument("--gpr-signal", type=float, default=1.0)
    p.add_argument("--gpr-jitter", type=float, default=1e-9)
    p.add_argument(
        "--no-vulkan",
        action="store_false",
        dest="use_vulkan",
        help="Disable Vulkan acceleration",
    )
    p.set_defaults(use_vulkan=True)
    p.add_argument(
        "--optical-model",
        choices=["four_flux", "tmm", "rts"],
        default="rts",
        help="选择光学模型：rts(RT-Stacking, 默认推荐) 或 four_flux(四通量/adding-doubling, 已废弃) 或 tmm(相干-非相干混合, 已废弃)",
    )
    p.add_argument(
        "--layer-names-order",
        choices=["bottom_first", "top_first"],
        default="bottom_first",
        help="数据集中 layer_names 的顺序：bottom_first 表示第0层是底层；top_first 表示第0层是顶层",
    )
    p.add_argument(
        "--k1", type=float, default=0.04, help="Saunderson k1 参数（表面反射）"
    )
    p.add_argument(
        "--k2", type=float, default=0.0, help="Saunderson k2 参数（内部反射）"
    )
    p.add_argument("--backing", type=float, default=0.98, help="背板反射率")
    p.add_argument(
        "--optimize-k", action="store_true", help="拟合时优化 Saunderson k1/k2"
    )
    p.add_argument(
        "--pure-weight", type=float, default=10.0, help="纯色样本在物理拟合中的权重"
    )
    p.add_argument(
        "--memorize-mode",
        choices=["train", "off"],
        default="off",
        help="Memorize training set (default: off). Use 'train' only for debugging/in-sample sanity check.",
    )
    # 黑白校准参数
    p.add_argument(
        "--black-offset",
        type=float,
        default=0.0,
        help="黑场偏移量（0-255范围）。例如32表示将黑色的0映射到32，给模型更多'喘息空间'。默认0表示不启用。",
    )
    p.add_argument(
        "--white-offset",
        type=float,
        default=0.0,
        help="白场偏移量（0-255范围）。例如32表示将白色的255映射到223。默认0表示不启用。",
    )

    ns = p.parse_args(argv)

    if ns.dataset is None or not Path(ns.dataset).exists():
        raise FileNotFoundError(
            f"dataset not found: {ns.dataset}. Provide --dataset path/to/dataset_cells.json"
        )

    # 打印使用的文件路径
    logger.info(f"[{VERSION}] 使用数据集: {ns.dataset}")
    logger.info(f"[{VERSION}] 输出目录: {ns.out_dir}")

    return FitArgs(
        dataset=Path(ns.dataset),
        out_dir=Path(ns.out_dir),
        n_layers=int(ns.n_layers),
        opt_steps=int(ns.opt_steps),
        opt_reg=float(ns.opt_reg),
        gpr_noise=float(ns.gpr_noise),
        gpr_lengthscale=float(ns.gpr_lengthscale),
        gpr_signal=float(ns.gpr_signal),
        gpr_jitter=float(ns.gpr_jitter),
        use_vulkan=bool(ns.use_vulkan),
        optical_model=str(ns.optical_model),
        memorize_mode=str(ns.memorize_mode),
        k1=float(ns.k1),
        k2=float(ns.k2),
        backing=float(ns.backing),
        optimize_k=bool(ns.optimize_k),
        pure_weight=float(ns.pure_weight),
        layer_names_order=str(ns.layer_names_order),
        black_offset=float(ns.black_offset),
        white_offset=float(ns.white_offset),
    )
