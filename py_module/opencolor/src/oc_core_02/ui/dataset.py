from pathlib import Path

import gradio as gr

from oc_calib.aggregate import aggregate_dataset
from oc_calib.board_spec import BoardSpec, create_legacy_32x32_spec
from oc_calib.dataset import CalibrationDataset
from oc_core_02.ui.utils import _tmpdir, _zip_dir


def ui_add_to_dataset(dataset: CalibrationDataset, obs, board_spec):
    """将 Observation 添加到数据集"""
    if obs is None:
        raise gr.Error("没有可添加的观测结果")

    dataset.add_board(board_spec)
    dataset.add_observation(obs)

    # 重新汇总
    aggregate_dataset(dataset)

    msg = f"✅ 已添加 1 个观测。当前数据集包含 {len(dataset.observations)} 个观测，覆盖 {len(dataset.boards)} 种板型。"
    return dataset, msg


def ui_export_dataset(dataset: CalibrationDataset):
    """导出数据集"""
    if not dataset.observations:
        raise gr.Error("数据集为空")

    out = _tmpdir()
    dataset.save(out)
    zip_path = _zip_dir(out, "calibration_dataset")

    return str(zip_path), f"✅ 数据集已导出至 {zip_path}"


def ui_load_board_spec(file_path: str):
    """加载 BoardSpec"""
    if file_path is None:
        # 默认加载旧版 32x32
        spec = create_legacy_32x32_spec()
        return spec, f"已加载默认旧版 32x32 BoardSpec"

    try:
        spec = BoardSpec.load(Path(file_path))
        return spec, f"已加载 BoardSpec: {spec.name} ({spec.rows}x{spec.cols})"
    except Exception as e:
        raise gr.Error(f"加载 BoardSpec 失败: {str(e)}")
