from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Callable

from oc_calib.aggregate import aggregate_dataset
from oc_calib.board_spec import BoardSpec
from oc_calib.dataset import CalibrationDataset
from oc_calib.observation import Observation
from ..jobs import Job

# 全局数据集存储字典
_DATASETS: Dict[str, Dict[str, Any]] = {}
# 线程锁，用于保护数据集操作的线程安全
_LOCK = threading.Lock()


def _load_board_spec(params: Dict[str, Any]) -> BoardSpec | None:
    """从参数中加载标定板规格

    支持从 JSON 字符串或文件路径加载色盘规格

    参数:
        params: 包含色盘规格信息的参数字典

    返回:
        色盘规格对象，如果未指定则返回 None
    """
    board_spec_json = params.get("board_spec_json")
    board_spec_path = params.get("board_spec_path")

    if board_spec_json:
        if isinstance(board_spec_json, str):
            return BoardSpec.from_json(board_spec_json)
        return BoardSpec.from_json(json.dumps(board_spec_json, ensure_ascii=False))

    if board_spec_path:
        return BoardSpec.load(Path(str(board_spec_path)))

    return None


def _load_observation(params: Dict[str, Any]) -> Observation:
    """从参数中加载观测数据

    支持从 JSON 字符串或文件路径加载观测数据

    参数:
        params: 包含观测数据信息的参数字典

    返回:
        观测数据对象

    异常:
        ValueError: 缺少观测数据或文件不存在时抛出
    """
    obs_json = params.get("observation_json")
    obs_path = params.get("observation_path")

    if obs_json:
        if isinstance(obs_json, str):
            return Observation.from_json(obs_json)
        return Observation.from_json(json.dumps(obs_json, ensure_ascii=False))

    if obs_path:
        p = Path(str(obs_path))
        if not p.exists():
            raise ValueError("观测文件不存在")
        return Observation.from_json(p.read_text(encoding="utf-8"))

    raise ValueError("缺少 observation_path 或 observation_json")


def _get_dataset(dataset_id: str) -> Dict[str, Any]:
    """获取指定ID的数据集记录

    从全局数据集存储中获取指定ID的数据集

    参数:
        dataset_id: 数据集唯一标识符

    返回:
        包含数据集对象和输出目录的字典

    异常:
        ValueError: 数据集不存在时抛出
    """
    with _LOCK:
        record = _DATASETS.get(dataset_id)
        if not record:
            raise ValueError("数据集不存在")
        return record


def handle_dataset_create(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理数据集创建请求

    创建一个新的校准数据集，可选择性地添加色盘规格

    参数:
        job: 任务对象，包含输出目录等信息
        params: 包含可选色盘规格信息的参数字典
        progress: 进度回调函数

    返回:
        包含数据集ID和输出目录的字典
    """
    out_dir = Path(job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    progress(0.2, "prepare", "创建数据集")
    dataset = CalibrationDataset()
    board_spec = _load_board_spec(params)
    if board_spec:
        dataset.add_board(board_spec)

    record = {
        "dataset": dataset,
        "out_dir": str(out_dir),
    }
    with _LOCK:
        _DATASETS[dataset.dataset_id] = record

    progress(1.0, "done", "完成")
    return {
        "dataset_id": dataset.dataset_id,
        "out_dir": str(out_dir),
    }


def handle_dataset_add_observation(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理添加观测到数据集请求

    将观测数据添加到指定的数据集中

    参数:
        job: 任务对象
        params: 包含 dataset_id 和观测数据信息的参数字典
        progress: 进度回调函数

    返回:
        包含数据集ID、观测数量和色盘数量的字典

    异常:
        ValueError: 缺少 dataset_id 时抛出
    """
    dataset_id = params.get("dataset_id")
    if not dataset_id:
        raise ValueError("缺少 dataset_id")

    progress(0.2, "load", "读取观测")
    record = _get_dataset(str(dataset_id))
    dataset: CalibrationDataset = record["dataset"]

    obs = _load_observation(params)
    dataset.add_observation(obs)

    board_spec = _load_board_spec(params)
    if board_spec and board_spec.board_id not in dataset.boards:
        dataset.add_board(board_spec)

    progress(1.0, "done", "完成")
    return {
        "dataset_id": dataset.dataset_id,
        "observation_count": len(dataset.observations),
        "board_count": len(dataset.boards),
    }


def handle_dataset_aggregate(
    job: Job, params: Dict[str, Any], progress: Callable[[float, str, str], None]
) -> Dict[str, Any]:
    """处理数据集汇总请求

    汇总数据集中的所有观测数据，计算统计信息并保存结果

    参数:
        job: 任务对象
        params: 包含 dataset_id 和可选输出目录的参数字典
        progress: 进度回调函数

    返回:
        包含汇总结果、文件路径和输出目录的字典

    异常:
        ValueError: 缺少 dataset_id 时抛出
    """
    dataset_id = params.get("dataset_id")
    if not dataset_id:
        raise ValueError("缺少 dataset_id")

    record = _get_dataset(str(dataset_id))
    dataset: CalibrationDataset = record["dataset"]
    out_dir = Path(params.get("out_dir") or record.get("out_dir") or job.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    progress(0.3, "aggregate", "汇总观测")
    aggregated = aggregate_dataset(dataset)

    progress(0.8, "save", "保存数据集")
    dataset.save(out_dir)

    progress(1.0, "done", "完成")
    return {
        "dataset_id": dataset.dataset_id,
        "aggregated_results": aggregated,
        "dataset_path": str(out_dir / "calibration_dataset.json"),
        "summary_path": str(out_dir / "dataset_summary.md"),
        "out_dir": str(out_dir),
    }
