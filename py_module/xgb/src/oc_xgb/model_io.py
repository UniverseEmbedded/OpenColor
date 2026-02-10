"""
模型IO模块
保存和加载物理GPR模型到npz和json文件
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
# 新的模型基类
from .model_base import ColorPredictionModel
# 为了向后兼容，保留旧的导入
from oc_xgb.xgb_fit import PhysGPRModel as LegacyPhysGPRModel, OpticalParams as LegacyOpticalParams, \
    GPRModel as LegacyGPRModel


def save_model(model, out_dir: Path, meta: dict) -> dict:
    """保存模型到目录
    
    Args:
        model: 模型实例（可以是新的 ColorPredictionModel 或旧的 PhysGPRModel）
        out_dir: 输出目录
        meta: 元数据
        
    Returns:
        dict: 模型元数据
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 如果是新的模型接口，使用其 save 方法
    if isinstance(model, ColorPredictionModel):
        model_meta = model.save(out_dir)
        model_meta.update(meta)
        (out_dir / "color_model.json").write_text(
            json.dumps(model_meta, indent=2, ensure_ascii=False), 
            encoding="utf-8"
        )
        return model_meta
    
    # 否则使用旧的保存逻辑（向后兼容）
    return _save_legacy_model(model, out_dir, meta)


def _save_legacy_model(model: LegacyPhysGPRModel, out_dir: Path, meta: dict) -> dict:
    """保存旧版模型（向后兼容）"""
    npz_path = out_dir / "phys_gpr_model.npz"

    pack = {
        "optical_mu_a": model.optical.mu_a,
        "optical_mu_s": model.optical.mu_s,
        "optical_g": model.optical.g,
        "optical_n_layers": np.array([model.optical.n_layers], dtype=np.int32),
        "optical_k1": np.array([model.optical.k1], dtype=np.float32),
        "optical_k2": np.array([model.optical.k2], dtype=np.float32),
        "optical_backing": np.array([model.optical.backing], dtype=np.float32),
    }

    alpha = getattr(model.optical, "alpha", None)
    beta = getattr(model.optical, "beta", None)
    gamma = getattr(model.optical, "gamma", None)
    if alpha is not None and beta is not None and gamma is not None:
        alpha = np.asarray(alpha, dtype=np.float32)
        beta = np.asarray(beta, dtype=np.float32)
        gamma = np.asarray(gamma, dtype=np.float32)
        if alpha.size > 0 and beta.size > 0 and gamma.size > 0:
            pack["optical_alpha"] = alpha
            pack["optical_beta"] = beta
            pack["optical_gamma"] = gamma
    
    # 保存GPR模型
    pack.update(_pack_gpr_legacy("L", model.gpr_L))
    pack.update(_pack_gpr_legacy("a", model.gpr_a))
    pack.update(_pack_gpr_legacy("b", model.gpr_b))

    np.savez_compressed(npz_path, **pack)

    meta_out = dict(meta)
    meta_out.update(
        {
            "model_type": "phys_gpr",
            "feature_names": model.feature_names,
            "material_keys": model.optical.material_keys,
            "files": {
                "model": npz_path.name,
            },
        }
    )
    (out_dir / "color_model.json").write_text(
        json.dumps(meta_out, indent=2, ensure_ascii=False), 
        encoding="utf-8"
    )
    return meta_out


def _pack_gpr_legacy(prefix: str, gpr: LegacyGPRModel) -> dict:
    """打包GPR模型数据（旧版）"""
    return {
        f"{prefix}_X_train": gpr.X_train,
        f"{prefix}_alpha": gpr.alpha,
        f"{prefix}_x_mean": gpr.x_mean,
        f"{prefix}_x_std": gpr.x_std,
        f"{prefix}_y_mean": np.array([gpr.y_mean], dtype=np.float32),
        f"{prefix}_y_std": np.array([gpr.y_std], dtype=np.float32),
        f"{prefix}_lengthscale": np.array([gpr.lengthscale], dtype=np.float32),
        f"{prefix}_signal_var": np.array([gpr.signal_var], dtype=np.float32),
        f"{prefix}_noise": np.array([gpr.noise], dtype=np.float32),
    }


def load_model(model_dir: Path):
    """加载模型
    
    Args:
        model_dir: 模型目录
        
    Returns:
        模型实例（新的 ColorPredictionModel 或旧的 PhysGPRModel）
    """
    # 尝试查找模型元数据文件
    meta_path = model_dir / "color_model.json"
    rts_meta_path = model_dir / "rts_model.json"
    
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    elif rts_meta_path.exists():
        metadata = json.loads(rts_meta_path.read_text(encoding="utf-8"))
        return _load_rts_model_as_legacy(metadata)
    else:
        raise FileNotFoundError(f"找不到模型元数据: {meta_path} 或 {rts_meta_path}")
    
    model_type = metadata.get("model_type", "phys_gpr")
    
    # 尝试使用新的模型加载机制
    try:
        # 导入模型模块以触发注册
        from . import models  # noqa: F401
        
        # 使用新的加载机制
        return ColorPredictionModel.load_from_dir(model_dir)
    except (ValueError, ImportError, KeyError) as e:
        logger.error(f"[model_io] 新模型加载失败，尝试旧版加载: {e}")
        # 回退到旧版加载
        return _load_legacy_model(model_dir, metadata)


def _load_rts_model_as_legacy(metadata: dict) -> LegacyPhysGPRModel:
    material_keys = metadata.get("material_keys")
    if not material_keys:
        raise KeyError("rts_model.json 缺少 material_keys")

    keep_indices: list[int] = []
    material_keys_filtered: list[str] = []
    for i, k in enumerate(material_keys):
        if str(k).strip().upper() == "EMPTY":
            continue
        keep_indices.append(int(i))
        material_keys_filtered.append(str(k))

    if not material_keys_filtered:
        raise ValueError("rts_model.json 的 material_keys 仅包含 EMPTY，无法用于求解")

    n_layers = int(metadata.get("n_layers", 5))
    params = metadata.get("params")
    if not isinstance(params, dict):
        raise KeyError("rts_model.json 缺少 params")

    if "alpha" not in params or "beta" not in params or "gamma" not in params:
        raise KeyError("rts_model.json 的 params 缺少 alpha/beta/gamma")

    alpha = np.asarray(params["alpha"], dtype=np.float32)
    beta = np.asarray(params["beta"], dtype=np.float32)
    gamma = np.asarray(params["gamma"], dtype=np.float32)

    n_mats_raw = int(len(material_keys))
    if alpha.shape != (n_mats_raw, 3) or beta.shape != (n_mats_raw, 3) or gamma.shape != (3,):
        raise ValueError(
            f"RTS 参数维度不匹配: alpha={tuple(alpha.shape)}, beta={tuple(beta.shape)}, gamma={tuple(gamma.shape)}, n_mats={n_mats_raw}"
        )

    alpha = np.ascontiguousarray(alpha[np.asarray(keep_indices, dtype=np.int32), :], dtype=np.float32)
    beta = np.ascontiguousarray(beta[np.asarray(keep_indices, dtype=np.int32), :], dtype=np.float32)

    n_mats = int(len(material_keys_filtered))

    optical = LegacyOpticalParams(
        material_keys=list(material_keys_filtered),
        mu_a=np.zeros((n_mats, 3), dtype=np.float32),
        mu_s=np.zeros((n_mats, 3), dtype=np.float32),
        g=np.zeros((n_mats, 3), dtype=np.float32),
        n_layers=n_layers,
        k1=0.04,
        k2=0.6,
        backing=0.98,
    )
    optical.alpha = alpha
    optical.beta = beta
    optical.gamma = gamma

    # 同步 C++ 端的特征维度计算逻辑
    # n_classes = n_mats + 1 (包含隐式 empty)
    # seq_feat_dim = n_layers * n_classes + n_classes * n_classes + 2 + n_classes
    # n_features = n_mats + 1 + 1 + 1 + 3 + seq_feat_dim + 3
    n_classes = n_mats + 1
    seq_feat_dim = n_layers * n_classes + n_classes * n_classes + 2 + n_classes
    n_features = n_mats + 1 + 1 + 1 + 3 + seq_feat_dim + 3

    dummy_gpr = LegacyGPRModel(
        X_train=np.zeros((1, n_features), dtype=np.float32),
        L=None,
        alpha=np.zeros((1,), dtype=np.float32),
        y_mean=0.0,
        y_std=1.0,
        x_mean=np.zeros((n_features,), dtype=np.float32),
        x_std=np.ones((n_features,), dtype=np.float32),
        lengthscale=1.0,
        signal_var=1.0,
        noise=1e-7,
    )

    return LegacyPhysGPRModel(
        optical=optical,
        gpr_L=dummy_gpr,
        gpr_a=dummy_gpr,
        gpr_b=dummy_gpr,
        feature_names=[],
    )


def _load_legacy_model(model_dir: Path, metadata: dict):
    """加载旧版模型（向后兼容）"""
    npz_path = model_dir / metadata["files"]["model"]
    data = np.load(npz_path)

    material_keys = metadata["material_keys"]
    feature_names = metadata.get("feature_names", [])
    n_layers = int(data["optical_n_layers"][0])
    k1 = float(data["optical_k1"][0]) if "optical_k1" in data else 0.04
    k2 = float(data["optical_k2"][0]) if "optical_k2" in data else 0.6
    backing = float(data["optical_backing"][0]) if "optical_backing" in data else 0.98

    optical = LegacyOpticalParams(
        material_keys=material_keys,
        mu_a=data["optical_mu_a"],
        mu_s=data["optical_mu_s"],
        g=data["optical_g"],
        n_layers=n_layers,
        k1=k1,
        k2=k2,
        backing=backing,
    )

    if "optical_alpha" in data and "optical_beta" in data and "optical_gamma" in data:
        optical.alpha = np.asarray(data["optical_alpha"], dtype=np.float32)
        optical.beta = np.asarray(data["optical_beta"], dtype=np.float32)
        optical.gamma = np.asarray(data["optical_gamma"], dtype=np.float32)

    def _unpack_gpr(prefix: str) -> LegacyGPRModel:
        return LegacyGPRModel(
            X_train=data[f"{prefix}_X_train"],
            L=None,
            alpha=data[f"{prefix}_alpha"],
            y_mean=float(data[f"{prefix}_y_mean"][0]),
            y_std=float(data[f"{prefix}_y_std"][0]),
            x_mean=data[f"{prefix}_x_mean"],
            x_std=data[f"{prefix}_x_std"],
            lengthscale=float(data[f"{prefix}_lengthscale"][0]),
            signal_var=float(data[f"{prefix}_signal_var"][0]),
            noise=float(data[f"{prefix}_noise"][0]),
        )

    gpr_L = _unpack_gpr("L")
    gpr_a = _unpack_gpr("a")
    gpr_b = _unpack_gpr("b")

    return LegacyPhysGPRModel(
        optical=optical,
        gpr_L=gpr_L,
        gpr_a=gpr_a,
        gpr_b=gpr_b,
        feature_names=feature_names,
    )


# 便捷函数
def create_model_from_checkpoint(model_dir: Path) -> ColorPredictionModel:
    """从检查点创建模型（使用新接口）"""
    from . import models  # noqa: F401
    return ColorPredictionModel.load_from_dir(model_dir)
