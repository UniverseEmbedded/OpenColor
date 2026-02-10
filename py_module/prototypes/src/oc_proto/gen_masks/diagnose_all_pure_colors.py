"""诊断所有纯色配方的表现"""

import json
import sys
from pathlib import Path

import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 添加路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oc_xgb.xgb_fit import rgb01_to_lab

def load_model(model_dir: Path):
    """加载FourFlux模型"""
    model_path = model_dir / "phys_gpr_model.npz"
    json_path = model_dir / "color_model.json"
    
    data = np.load(model_path)
    with open(json_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    return data, meta

def predict_fourflux(data: np.ndarray, recipe: list[int], n_layers: int = 5) -> np.ndarray:
    """使用FourFlux模型预测颜色"""
    mu_a = data['optical_mu_a']
    mu_s = data['optical_mu_s']
    g = data['optical_g']
    
    # 获取材料参数
    k = np.exp(np.clip(mu_a, -10, 10))
    s = np.exp(np.clip(mu_s, -10, 10))
    
    # 简化的预测：假设反射率与吸收系数相关
    # 实际应该用完整的FourFlux计算，这里简化处理
    total_k = np.zeros(3)
    total_s = np.zeros(3)
    
    for idx in recipe:
        total_k += k[idx]
        total_s += s[idx]
    
    # 简化的反射率估计
    reflectance = 1.0 / (1.0 + total_k / (total_s + 0.001))
    
    # 转换为Lab
    rgb = np.clip(reflectance, 0, 1)
    return rgb01_to_lab(rgb.astype(np.float32))

def diagnose_pure_color(data: np.ndarray, meta: dict, color_name: str, rgb_values: list[float]):
    """诊断单个纯色"""
    logger.info(f"\n{'='*60}")
    logger.info(f"诊断: {color_name} RGB{rgb_values}")
    logger.info(f"{'='*60}")
    
    # RGB -> Lab
    target_lab = rgb01_to_lab(np.array(rgb_values, dtype=np.float32))
    logger.info(f"目标Lab: [{float(target_lab[0]):.1f}, {float(target_lab[1]):.1f}, {float(target_lab[2]):.1f}]")
    
    # 查找材料索引
    material_keys = meta['material_keys']
    logger.info(f"材料列表: {material_keys}")
    
    # 尝试纯色配方
    color_upper = color_name.upper()
    if color_upper in material_keys:
        idx = material_keys.index(color_upper)
        pure_recipe = [idx] * 5
        
        # 获取材料参数
        mu_a = data['optical_mu_a'][idx]
        mu_s = data['optical_mu_s'][idx]
        k = np.exp(np.clip(mu_a, -10, 10))
        s = np.exp(np.clip(mu_s, -10, 10))
        
        logger.info(f"\n全{color_name}配方 (索引{idx}):")
        logger.info(f"  mu_a: {mu_a}")
        logger.info(f"  mu_s: {mu_s}")
        logger.info(f"  k(吸收): {k}")
        logger.info(f"  s(散射): {s}")
        
        # 简化的反射率估计
        # 对于多层相同材料，反射率会趋于稳态
        # R_inf = 1 + K/S - sqrt((K/S)^2 + 2*K/S)
        K = 2 * k
        S = 2 * s * (1 - 0.5)  # 假设g=0.5
        KS_ratio = K / (S + 1e-9)
        R_inf = 1 + KS_ratio - np.sqrt(KS_ratio**2 + 2*KS_ratio)
        R_inf = np.clip(R_inf, 0, 1)
        
        pred_lab = rgb01_to_lab(R_inf.astype(np.float32))
        delta_e = np.linalg.norm(pred_lab - target_lab)
        
        logger.info(f"  预测反射率: {R_inf}")
        logger.info(f"  预测Lab: [{float(pred_lab[0]):.1f}, {float(pred_lab[1]):.1f}, {float(pred_lab[2]):.1f}]")
        logger.info(f"  DeltaE: {delta_e:.2f}")
        
        if delta_e < 5:
            logger.info(f"  ✅ 表现良好")
        elif delta_e < 20:
            logger.info(f"  ⚠️ 偏差较大")
        else:
            logger.info(f"  ❌ 严重偏差")
            
        return delta_e
    else:
        logger.info(f"\n{color_name}不在材料列表中")
        return None

def main():
    # 加载模型
    model_dir = Path(__file__).resolve().parent.parent / "calib_color_rts" / "out_eval_four_flux" / "evaluation" / "train_A"
    logger.info(f"加载模型: {model_dir}")
    data, meta = load_model(model_dir)
    
    # 测试所有纯色
    pure_colors = {
        'WHITE': [1.0, 1.0, 1.0],
        'BLACK': [0.0, 0.0, 0.0],
        'RED': [1.0, 0.0, 0.0],
        'GREEN': [0.0, 1.0, 0.0],
        'BLUE': [0.0, 0.0, 1.0],
        'CYAN': [0.0, 1.0, 1.0],
        'MAGENTA': [1.0, 0.0, 1.0],
        'YELLOW': [1.0, 1.0, 0.0],
    }
    
    results = {}
    for color_name, rgb in pure_colors.items():
        delta_e = diagnose_pure_color(data, meta, color_name, rgb)
        results[color_name] = delta_e
    
    # 汇总
    logger.info(f"\n{'='*60}")
    logger.info("汇总")
    logger.info(f"{'='*60}")
    logger.info(f"{'颜色':<10} {'纯色配方dE':<15} {'状态'}")
    logger.info("-" * 60)
    
    for color_name, delta_e in results.items():
        if delta_e is None:
            status = "N/A"
            de_str = "N/A"
        elif delta_e < 5:
            status = "✅ 正常"
            de_str = f"{delta_e:.2f}"
        elif delta_e < 20:
            status = "⚠️ 偏差较大"
            de_str = f"{delta_e:.2f}"
        else:
            status = "❌ 严重偏差"
            de_str = f"{delta_e:.2f}"
        
        logger.info(f"{color_name:<10} {de_str:<15} {status}")

if __name__ == "__main__":
    main()
