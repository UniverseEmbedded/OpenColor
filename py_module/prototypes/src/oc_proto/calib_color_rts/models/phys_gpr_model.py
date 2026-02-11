"""
物理+GPR模型实现
基于四通量物理模型和GPR残差修正的颜色预测
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from oc_xgb.color_space import rgb01_to_lab, lab_to_rgb01
from oc_xgb.model_base import ColorPredictionModel, PredictionResult, ModelCapabilities
from oc_xgb.optical_model import NumpyFourFluxModel, VulkanFourFluxModel
from oc_xgb.optical_model import OpticalParams as RawOpticalParams


@dataclass
class OpticalParams:
    """光学参数"""

    material_keys: list[str]
    mu_a: np.ndarray  # 吸收系数 (M, 3)
    mu_s: np.ndarray  # 散射系数 (M, 3)
    g: np.ndarray  # 各向异性因子 (M, 3)
    n_layers: int
    k1: float = 0.0
    k2: float = 0.0
    backing: float = 0.98

    def to_raw(self):
        """转换为原始光学参数（兼容旧接口）"""
        return RawOpticalParams(mu_a=self.mu_a, mu_s=self.mu_s, g=self.g)


@dataclass
class GPRModel:
    """GPR模型数据"""

    X_train: np.ndarray
    L: np.ndarray | None
    alpha: np.ndarray
    y_mean: float
    y_std: float
    x_mean: np.ndarray
    x_std: np.ndarray
    lengthscale: float
    signal_var: float
    noise: float


@ColorPredictionModel.register(
    "phys_gpr",
    description="物理+GPR模型：基于四通量物理模型和GPR残差修正",
    supports_uncertainty=True,
    supports_batch_prediction=True,
)
class PhysGPRModelImpl(ColorPredictionModel):
    """物理+GPR模型实现

    结合物理模型（Adding-Doubling算法）和GPR残差修正的颜色预测模型。
    """

    def __init__(
        self,
        model_id: str,
        material_keys: list[str],
        n_layers: int,
        optical: OpticalParams | None = None,
        gpr_L: GPRModel | None = None,
        gpr_a: GPRModel | None = None,
        gpr_b: GPRModel | None = None,
        feature_names: list[str] | None = None,
        use_vulkan: bool = True,
    ):
        super().__init__(model_id, material_keys, n_layers)
        self.optical = optical
        self.gpr_L = gpr_L
        self.gpr_a = gpr_a
        self.gpr_b = gpr_b
        self.feature_names = feature_names or []
        self.use_vulkan = use_vulkan

        # 设置能力
        self._capabilities = ModelCapabilities(
            supports_uncertainty=True,
            supports_batch_prediction=True,
            requires_layer_sequence=True,
            supports_recipe_input=True,
            description="物理+GPR模型：基于四通量物理模型和GPR残差修正",
        )

        # 初始化预测模型
        self._optical_model = (
            VulkanFourFluxModel() if use_vulkan else NumpyFourFluxModel()
        )

    def predict_from_sequences(self, sequences: list[list[str]]) -> PredictionResult:
        """从层序列预测颜色"""
        if self.optical is None:
            raise RuntimeError("模型未初始化光学参数")

        # 1. 物理模型预测
        base_rgb01 = self._predict_physical(sequences)
        base_lab = rgb01_to_lab(base_rgb01)

        # 2. 构建GPR特征
        from oc_xgb.xgb_features import build_gpr_features

        recipes = self._sequences_to_recipes(sequences)
        X_features, _ = build_gpr_features(
            recipes,
            self.material_keys,
            base_lab,
            n_layers=self.n_layers,
            layer_names_order="top_first",
            k1=self.optical.k1,
            k2=self.optical.k2,
            backing=self.optical.backing,
        )

        # 3. GPR残差预测
        if self.gpr_L is not None and self.gpr_a is not None and self.gpr_b is not None:
            res_L = self._predict_gpr(self.gpr_L, X_features)
            res_a = self._predict_gpr(self.gpr_a, X_features)
            res_b = self._predict_gpr(self.gpr_b, X_features)

            # 4. 合并结果
            pred_lab = base_lab.copy()
            pred_lab[:, 0] += res_L
            pred_lab[:, 1] += res_a
            pred_lab[:, 2] += res_b
        else:
            pred_lab = base_lab

        pred_rgb01 = lab_to_rgb01(pred_lab)

        return PredictionResult(
            rgb01=np.clip(pred_rgb01, 0.0, 1.0),
            lab=pred_lab,
        )

    def _predict_physical(self, sequences: list[list[str]]) -> np.ndarray:
        """物理模型预测"""

        raw_params = RawOpticalParams(
            mu_a=self.optical.mu_a, mu_s=self.optical.mu_s, g=self.optical.g
        )

        return self._optical_model.predict_rgb(
            sequences,
            self.material_keys,
            raw_params,
            backing=self.optical.backing,
            k1=self.optical.k1,
            k2=self.optical.k2,
        )

    def _predict_gpr(self, gpr: GPRModel, X: np.ndarray) -> np.ndarray:
        """GPR预测"""
        X_norm = (X - gpr.x_mean) / (gpr.x_std + 1e-9)

        # 计算核矩阵
        sq_dist = (
            np.sum(X_norm**2, axis=1).reshape(-1, 1)
            + np.sum(gpr.X_train**2, axis=1)
            - 2 * np.dot(X_norm, gpr.X_train.T)
        )
        K = gpr.signal_var * np.exp(-0.5 * sq_dist / (gpr.lengthscale**2))

        y_pred_norm = K @ gpr.alpha
        return y_pred_norm * gpr.y_std + gpr.y_mean

    def _sequences_to_recipes(
        self, sequences: list[list[str]]
    ) -> list[dict[str, float]]:
        """将层序列转换为配方"""
        recipes = []
        for seq in sequences:
            recipe = {}
            for layer in seq:
                recipe[layer] = recipe.get(layer, 0.0) + 1.0
            recipe["_layer_names"] = list(seq)
            recipes.append(recipe)
        return recipes

    def save(self, out_dir: Path) -> dict[str, Any]:
        """保存模型"""
        out_dir.mkdir(parents=True, exist_ok=True)
        npz_path = out_dir / "phys_gpr_model.npz"

        pack = {
            "optical_mu_a": self.optical.mu_a,
            "optical_mu_s": self.optical.mu_s,
            "optical_g": self.optical.g,
            "optical_n_layers": np.array([self.optical.n_layers], dtype=np.int32),
            "optical_k1": np.array([self.optical.k1], dtype=np.float32),
            "optical_k2": np.array([self.optical.k2], dtype=np.float32),
            "optical_backing": np.array([self.optical.backing], dtype=np.float32),
        }

        alpha = getattr(self.optical, "alpha", None)
        beta = getattr(self.optical, "beta", None)
        gamma = getattr(self.optical, "gamma", None)
        if alpha is not None and beta is not None and gamma is not None:
            alpha = np.asarray(alpha, dtype=np.float32)
            beta = np.asarray(beta, dtype=np.float32)
            gamma = np.asarray(gamma, dtype=np.float32)
            if alpha.size > 0 and beta.size > 0 and gamma.size > 0:
                pack["optical_alpha"] = alpha
                pack["optical_beta"] = beta
                pack["optical_gamma"] = gamma

        # 保存GPR模型
        if self.gpr_L:
            pack.update(self._pack_gpr("L", self.gpr_L))
        if self.gpr_a:
            pack.update(self._pack_gpr("a", self.gpr_a))
        if self.gpr_b:
            pack.update(self._pack_gpr("b", self.gpr_b))

        np.savez_compressed(npz_path, **pack)

        return {
            "model_type": "phys_gpr",
            "feature_names": self.feature_names,
            "material_keys": self.material_keys,
            "files": {"model": npz_path.name},
        }

    def _pack_gpr(self, prefix: str, gpr: GPRModel) -> dict:
        """打包GPR模型数据"""
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

    @classmethod
    def load(cls, model_dir: Path, metadata: dict[str, Any]) -> PhysGPRModelImpl:
        """加载模型"""
        npz_path = model_dir / metadata["files"]["model"]
        data = np.load(npz_path)

        material_keys = metadata["material_keys"]
        feature_names = metadata.get("feature_names", [])
        n_layers = int(data["optical_n_layers"][0])
        k1 = float(data["optical_k1"][0]) if "optical_k1" in data else 0.04
        k2 = float(data["optical_k2"][0]) if "optical_k2" in data else 0.6
        backing = (
            float(data["optical_backing"][0]) if "optical_backing" in data else 0.98
        )

        optical = OpticalParams(
            material_keys=material_keys,
            mu_a=data["optical_mu_a"],
            mu_s=data["optical_mu_s"],
            g=data["optical_g"],
            n_layers=n_layers,
            k1=k1,
            k2=k2,
            backing=backing,
        )

        if (
            "optical_alpha" in data
            and "optical_beta" in data
            and "optical_gamma" in data
        ):
            optical.alpha = np.asarray(data["optical_alpha"], dtype=np.float32)
            optical.beta = np.asarray(data["optical_beta"], dtype=np.float32)
            optical.gamma = np.asarray(data["optical_gamma"], dtype=np.float32)

        def _unpack_gpr(prefix: str) -> GPRModel | None:
            try:
                return GPRModel(
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
            except KeyError:
                return None

        gpr_L = _unpack_gpr("L")
        gpr_a = _unpack_gpr("a")
        gpr_b = _unpack_gpr("b")

        return cls(
            model_id=metadata.get("model_id", "phys_gpr_loaded"),
            material_keys=material_keys,
            n_layers=n_layers,
            optical=optical,
            gpr_L=gpr_L,
            gpr_a=gpr_a,
            gpr_b=gpr_b,
            feature_names=feature_names,
        )
