from __future__ import annotations

from typing import Dict, List

import numpy as np

from .dataset import CalibrationDataset


def aggregate_dataset(dataset: CalibrationDataset):
    """
    对数据集中的所有观测进行汇总。
    
    汇总策略：
    1. 收集每个 cell_id 的所有 RGB 观测值。
    2. 对每个 cell_id 取中位数 (median) 以抗离群点。
    3. 计算标准差和观测次数。
    
    @param dataset: 校准数据集对象
    @return: 汇总结果字典，键为 cell_id，值为统计信息
    """
    all_measurements: Dict[str, List[np.ndarray]] = {}
    
    # 收集所有观测值
    for obs in dataset.observations:
        for cell_id, measure in obs.cell_measurements.items():
            if "rgb" in measure:
                if cell_id not in all_measurements:
                    all_measurements[cell_id] = []
                all_measurements[cell_id].append(np.array(measure["rgb"]))
    
    # 计算统计信息
    aggregated = {}
    for cell_id, values in all_measurements.items():
        vals_np = np.stack(values)
        median_rgb = np.median(vals_np, axis=0)  # 中位数（抗离群点）
        mean_rgb = np.mean(vals_np, axis=0)      # 平均值
        std_rgb = np.std(vals_np, axis=0)        # 标准差
        
        aggregated[cell_id] = {
            "median_rgb": median_rgb.tolist(),   # 中位数 RGB
            "mean_rgb": mean_rgb.tolist(),       # 平均 RGB
            "std_rgb": std_rgb.tolist(),         # 标准差
            "count": len(values)                 # 观测次数
        }
        
    dataset.aggregated_results = aggregated
    return aggregated
