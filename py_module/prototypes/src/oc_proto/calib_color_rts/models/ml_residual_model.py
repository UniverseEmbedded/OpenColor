"""
ML残差模型
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from oc_core_02.utils.logger import get_logger
from oc_xgb.color_space import rgb01_to_lab
from oc_xgb.xgb_model import require_xgboost

logger = get_logger(__name__)


@dataclass
class MLResidualModel:
    rts_alpha: np.ndarray
    rts_beta: np.ndarray
    rts_gamma: np.ndarray
    material_keys: list[str]
    n_layers: int
    layer_names_order: str
    model_L: object
    model_a: object
    model_b: object
    feature_names: list[str]

    def predict(self, sequences: list[list[str]], X_features: np.ndarray) -> np.ndarray:
        base_lab = self._rts_predict_lab(sequences)
        residual_L = self.model_L.predict(X_features)
        residual_a = self.model_a.predict(X_features)
        residual_b = self.model_b.predict(X_features)
        residual_lab = np.column_stack([residual_L, residual_a, residual_b])
        return base_lab + residual_lab

    def _rts_predict_lab(self, sequences: list[list[str]]) -> np.ndarray:
        seqs = [self._normalize_seq(s) for s in sequences]
        idx = self._idx_mat(seqs)
        pred_lin = self._rts_predict_linear_idx(
            idx, self.rts_alpha, self.rts_beta, self.rts_gamma
        )
        pred_srgb01 = self._linear01_to_srgb01(pred_lin).astype(np.float32)
        return rgb01_to_lab(pred_srgb01)

    def _normalize_seq(self, seq: list[str]) -> list[str]:
        out = [str(x).upper() for x in (seq or []) if str(x).strip()]
        if len(out) < self.n_layers:
            out += ["EMPTY"] * (self.n_layers - len(out))
        else:
            out = out[: self.n_layers]
        return out

    def _idx_mat(self, seqs: list[list[str]]) -> np.ndarray:
        mat2idx = {str(m).upper(): i for i, m in enumerate(self.material_keys)}
        empty_idx = mat2idx.get("EMPTY", 0)
        n = len(seqs)
        l = len(seqs[0]) if seqs else 0
        idx = np.full((n, l), empty_idx, dtype=np.int32)
        for i, seq in enumerate(seqs):
            for j, m in enumerate(seq[:l]):
                idx[i, j] = mat2idx.get(str(m).upper(), empty_idx)
        if self.layer_names_order == "bottom_first":
            idx = idx[:, ::-1]
        return idx

    def _rts_predict_linear_idx(
        self, idx_mat: np.ndarray, alpha: np.ndarray, beta: np.ndarray, gamma: np.ndarray
    ) -> np.ndarray:
        r = self._sigmoid(alpha)
        t = self._sigmoid(beta) * (1.0 - r)
        r[0, :] = 0.0
        t[0, :] = 1.0

        R = np.repeat(self._sigmoid(gamma)[None, :], repeats=idx_mat.shape[0], axis=0)
        for j in range(idx_mat.shape[1]):
            midx = idx_mat[:, j]
            r1 = r[midx, :]
            t1 = t[midx, :]
            denom = np.clip(1.0 - r1 * R, 1e-6, 1e9)
            R = r1 + (t1 * t1) * R / denom
            R = np.clip(R, 0.0, 1.0)
        return np.clip(R, 0.0, 1.0)

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        x = np.clip(np.asarray(x, dtype=np.float64), -20.0, 20.0)
        return 1.0 / (1.0 + np.exp(-x))

    def _linear01_to_srgb01(self, lin01: np.ndarray) -> np.ndarray:
        a = 0.055
        x = np.clip(np.asarray(lin01, dtype=np.float64), 0.0, 1.0)
        return np.where(x <= 0.0031308, x * 12.92, (1 + a) * (x ** (1 / 2.4)) - a)

    def save(self, out_dir: Path, train_stats: dict | None = None) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        require_xgboost()

        model_paths = {
            "model_L": out_dir / "ml_residual_xgb_L.json",
            "model_a": out_dir / "ml_residual_xgb_a.json",
            "model_b": out_dir / "ml_residual_xgb_b.json",
        }
        self.model_L.save_model(str(model_paths["model_L"]))
        self.model_a.save_model(str(model_paths["model_a"]))
        self.model_b.save_model(str(model_paths["model_b"]))

        meta = {
            "model_type": "ml_residual",
            "rts_params": {
                "alpha": np.asarray(self.rts_alpha, dtype=np.float64).tolist(),
                "beta": np.asarray(self.rts_beta, dtype=np.float64).tolist(),
                "gamma": np.asarray(self.rts_gamma, dtype=np.float64).tolist(),
                "material_keys": list(self.material_keys),
                "n_layers": int(self.n_layers),
                "layer_names_order": str(self.layer_names_order),
            },
            "feature_names": list(self.feature_names or []),
            "files": {k: v.name for k, v in model_paths.items()},
            "train_stats": dict(train_stats or {}),
        }
        meta_path = out_dir / "ml_residual_model.json"
        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"[ML残差] 模型已保存: {meta_path}")
        return meta

    @classmethod
    def load(cls, model_dir: Path) -> "MLResidualModel":
        meta_path = model_dir / "ml_residual_model.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"找不到ML残差模型元数据: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        params = meta.get("rts_params")
        if not isinstance(params, dict):
            raise KeyError("ml_residual_model.json 缺少 rts_params")

        require_xgboost()
        import xgboost as xgb

        files = meta.get("files", {})
        mL = xgb.XGBRegressor()
        mA = xgb.XGBRegressor()
        mB = xgb.XGBRegressor()
        mL.load_model(str(model_dir / files["model_L"]))
        mA.load_model(str(model_dir / files["model_a"]))
        mB.load_model(str(model_dir / files["model_b"]))

        return cls(
            rts_alpha=np.asarray(params["alpha"], dtype=np.float64),
            rts_beta=np.asarray(params["beta"], dtype=np.float64),
            rts_gamma=np.asarray(params["gamma"], dtype=np.float64),
            material_keys=list(params["material_keys"]),
            n_layers=int(params["n_layers"]),
            layer_names_order=str(params["layer_names_order"]),
            model_L=mL,
            model_a=mA,
            model_b=mB,
            feature_names=list(meta.get("feature_names", []) or []),
        )
