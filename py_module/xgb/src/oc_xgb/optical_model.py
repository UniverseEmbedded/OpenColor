"""\
【已废弃】本文件中的 FourFlux（四通量）/TMM 相关实现已废弃，仅保留用于历史对照与回溯；新流程请勿依赖。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OpticalParams:
    mu_a: np.ndarray
    mu_s: np.ndarray
    g: np.ndarray
    backing: float = 0.98
    k1: float = 0.0
    k2: float = 0.0

    def to_raw(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """返回原始参数元组 (mu_a, mu_s, g)"""
        return self.mu_a, self.mu_s, self.g


class OpticalModel(ABC):
    """光学模型抽象基类"""

    @abstractmethod
    def predict_rgb(
        self,
        sequences: list[list[str]],
        material_keys: list[str],
        params: OpticalParams,
        backing: float = 0.98,
        k1: float = 0.0,
        k2: float = 0.0,
    ) -> np.ndarray:
        """预测给定序列的 RGB"""
        pass

    @abstractmethod
    def fit(
        self,
        sequences: list[list[str]],
        y_lab: np.ndarray,
        material_keys: list[str],
        initial_params: OpticalParams,
        **kwargs,
    ) -> OpticalParams:
        """根据实验数据拟合光学参数"""
        pass


class NumpyFourFluxModel(OpticalModel):
    """基于 NumPy 的四通量模型实现 (CPU)"""

    def _sigmoid(self, x):
        x = np.asarray(x, dtype=np.float32)
        return np.float32(1.0) / (
            np.float32(1.0) + np.exp(-np.clip(x, np.float32(-20.0), np.float32(20.0)))
        )

    def _params_to_four_flux(self, mu_a_raw, mu_s_raw, g_raw):
        mu_a_raw = np.asarray(mu_a_raw, dtype=np.float32)
        mu_s_raw = np.asarray(mu_s_raw, dtype=np.float32)
        g_raw = np.asarray(g_raw, dtype=np.float32)

        k = np.exp(np.clip(mu_a_raw, np.float32(-10.0), np.float32(10.0))).astype(
            np.float32
        )
        s = np.exp(np.clip(mu_s_raw, np.float32(-10.0), np.float32(10.0))).astype(
            np.float32
        )
        g = (np.float32(0.9) * self._sigmoid(g_raw)).astype(np.float32)

        dz = np.float32(1.6384)
        c = (k + s).astype(np.float32)
        tc = np.exp(-(c * dz)).astype(np.float32)
        rc = np.zeros_like(tc, dtype=np.float32)

        K = (np.float32(2.0) * k).astype(np.float32)
        S = (np.float32(2.0) * s * (np.float32(1.0) - g)).astype(np.float32)

        dz_thin = np.float32(1e-4)
        tau_d = ((K + S) * dz_thin).astype(np.float32)
        omega_d = (S / (K + S + np.float32(1e-9))).astype(np.float32)

        rd = (
            np.float32(0.5)
            * omega_d
            * (np.float32(1.0) - np.exp(-(np.float32(2.0) * tau_d)))
        ).astype(np.float32)
        td = (np.exp(-tau_d).astype(np.float32) + rd).astype(np.float32)

        for _ in range(14):
            denom = (np.float32(1.0) - rd * rd).astype(np.float32)
            denom = np.where(
                np.abs(denom) < np.float32(1e-6), np.float32(1e-6), denom
            ).astype(np.float32)
            td_new = (td * td / denom).astype(np.float32)
            rd_new = (rd + (td * rd * td) / denom).astype(np.float32)
            rd, td = rd_new, td_new

        return (
            rc.astype(np.float32),
            tc.astype(np.float32),
            rd.astype(np.float32),
            td.astype(np.float32),
        )

    def _stack_four_flux(self, Rc1, Tc1, Rd1, Td1, Rc2, Tc2, Rd2, Td2):
        Rc1 = np.asarray(Rc1, dtype=np.float32)
        Tc1 = np.asarray(Tc1, dtype=np.float32)
        Rd1 = np.asarray(Rd1, dtype=np.float32)
        Td1 = np.asarray(Td1, dtype=np.float32)
        Rc2 = np.asarray(Rc2, dtype=np.float32)
        Tc2 = np.asarray(Tc2, dtype=np.float32)
        Rd2 = np.asarray(Rd2, dtype=np.float32)
        Td2 = np.asarray(Td2, dtype=np.float32)

        denom_c = (np.float32(1.0) - Rc1 * Rc2 + np.float32(1e-9)).astype(np.float32)
        Rc = (Rc1 + (Tc1 * Rc2 * Tc1) / denom_c).astype(np.float32)
        Tc = ((Tc1 * Tc2) / denom_c).astype(np.float32)

        denom = (np.float32(1.0) - Rd1 * Rd2).astype(np.float32)
        denom = np.where(
            np.abs(denom) < np.float32(1e-6), np.float32(1e-6), denom
        ).astype(np.float32)

        Rd = (Rd1 + (Td1 * Rd2 * Td1) / denom).astype(np.float32)
        Td = ((Td1 * Td2) / denom).astype(np.float32)
        return Rc, Tc, Rd, Td

    def _apply_backing_four_flux(self, Rd, Td, Rc, Tc, backing):
        Rd = np.asarray(Rd, dtype=np.float32)
        Td = np.asarray(Td, dtype=np.float32)
        Rb = np.array([backing, backing, backing], dtype=np.float32)
        denom_d = (np.float32(1.0) - Rd * Rb).astype(np.float32)
        denom_d = np.where(
            np.abs(denom_d) < np.float32(1e-6), np.float32(1e-6), denom_d
        ).astype(np.float32)
        # 只使用扩散分量，避免与平行的准直分量叠加导致能量翻倍
        # 在标准的 d/8 或类似测量中，我们主要观测扩散反射
        R_total = (Rd + (Td * Rb * Td) / denom_d).astype(np.float32)
        return R_total

    def _apply_saunderson(self, Ri, k1, k2):
        """应用 Saunderson 修正：Ri 是内部反射率，Rm 是可观测反射率"""
        Ri = np.asarray(Ri, dtype=np.float32)
        k1_f = np.float32(k1)
        k2_f = np.float32(k2)
        if float(k1_f) == 0.0 and float(k2_f) == 0.0:
            return Ri
        return (
            k1_f
            + (np.float32(1.0) - k1_f)
            * (np.float32(1.0) - k2_f)
            * Ri
            / (np.float32(1.0) - k2_f * Ri + np.float32(1e-9))
        ).astype(np.float32)

    def predict_rgb(
        self, sequences, material_keys, params, backing=0.98, k1=0.0, k2=0.0
    ):
        from .color_space import linear01_to_srgb01

        key_to_idx = {k.upper(): i for i, k in enumerate(material_keys)}
        Rc, Tc, Rd, Td = self._params_to_four_flux(params.mu_a, params.mu_s, params.g)

        n_seq = len(sequences)
        if n_seq == 0:
            return np.zeros((0, 3), dtype=np.float32)
        max_len = max(len(s) for s in sequences)

        R_c_stack = np.zeros((n_seq, 3), dtype=np.float32)
        T_c_stack = np.ones((n_seq, 3), dtype=np.float32)
        R_d_stack = np.zeros((n_seq, 3), dtype=np.float32)
        T_d_stack = np.ones((n_seq, 3), dtype=np.float32)

        for layer_idx in range(max_len):
            indices = []
            for s in sequences:
                if layer_idx < len(s):
                    indices.append(key_to_idx.get(str(s[layer_idx]).upper(), -1))
                else:
                    indices.append(-1)

            indices = np.array(indices)
            valid_mask = indices >= 0
            if not np.any(valid_mask):
                continue

            valid_idx = indices[valid_mask]
            n_Rc, n_Tc, n_Rd, n_Td = self._stack_four_flux(
                R_c_stack[valid_mask],
                T_c_stack[valid_mask],
                R_d_stack[valid_mask],
                T_d_stack[valid_mask],
                Rc[valid_idx],
                Tc[valid_idx],
                Rd[valid_idx],
                Td[valid_idx],
            )
            (
                R_c_stack[valid_mask],
                T_c_stack[valid_mask],
                R_d_stack[valid_mask],
                T_d_stack[valid_mask],
            ) = n_Rc, n_Tc, n_Rd, n_Td

        rgb_lin_internal = self._apply_backing_four_flux(
            R_d_stack, T_d_stack, R_c_stack, T_c_stack, backing
        )
        rgb_lin_measured = self._apply_saunderson(rgb_lin_internal, k1, k2)
        return np.clip(linear01_to_srgb01(rgb_lin_measured), 0.0, 1.0).astype(
            np.float32
        )

    def fit(self, sequences, y_lab, material_keys, initial_params, **kwargs):
        from scipy.optimize import minimize
        from .color_space import rgb01_to_lab

        # 获取参数
        k1_val = float(kwargs.get("k1", 0.04))
        k2_val = float(kwargs.get("k2", 0.6))
        backing_val = float(kwargs.get("backing", 0.98))
        reg_val = float(kwargs.get("reg", 1e-4))
        optimize_k = kwargs.get("optimize_k", False)
        sample_weight = kwargs.get("sample_weight", None)

        n_mat = len(material_keys)
        if sample_weight is None or len(sample_weight) != len(y_lab):
            sample_weight = np.ones(len(y_lab), dtype=np.float32)
        else:
            sample_weight = np.asarray(sample_weight, dtype=np.float32)

        def _loss(x):
            mu_a = x[: n_mat * 3].reshape((n_mat, 3))
            mu_s = x[n_mat * 3 : n_mat * 6].reshape((n_mat, 3))
            g = x[n_mat * 6 : n_mat * 9].reshape((n_mat, 3))

            if optimize_k:
                k1 = np.clip(x[n_mat * 9], 0.0, 0.2)
                k2 = np.clip(x[n_mat * 9 + 1], 0.0, 1.0)
            else:
                k1, k2 = k1_val, k2_val

            p = OpticalParams(mu_a=mu_a, mu_s=mu_s, g=g)
            pred_rgb = self.predict_rgb(
                sequences, material_keys, p, backing=backing_val, k1=k1, k2=k2
            )
            pred_lab = rgb01_to_lab(pred_rgb)
            sample_loss = np.mean(np.square(pred_lab - y_lab), axis=1)
            data_loss = float(
                np.sum(sample_weight * sample_loss) / (np.sum(sample_weight) + 1e-9)
            )
            reg_loss = reg_val * (
                np.sum(np.square(mu_a)) + np.sum(np.square(mu_s)) + np.sum(np.square(g))
            )
            return data_loss + reg_loss

        x0_list = [
            initial_params.mu_a.flatten(),
            initial_params.mu_s.flatten(),
            initial_params.g.flatten(),
        ]
        if optimize_k:
            x0_list.append(np.array([k1_val, k2_val]))
        x0 = np.concatenate(x0_list)

        bounds = [(-6.0, 6.0)] * (n_mat * 9)
        if optimize_k:
            bounds += [(0.0, 0.2), (0.0, 1.0)]

        res = minimize(
            _loss,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": kwargs.get("maxiter", 50), "disp": True},
        )
        fitted_k1, fitted_k2 = k1_val, k2_val
        if optimize_k:
            fitted_k1 = float(np.clip(res.x[n_mat * 9], 0.0, 0.2))
            fitted_k2 = float(np.clip(res.x[n_mat * 9 + 1], 0.0, 1.0))
            logger.info(
                f"[NumpyModel] 拟合得到的 Saunderson 参数: k1={fitted_k1:.4f}, k2={fitted_k2:.4f}"
            )

        return (
            OpticalParams(
                mu_a=res.x[: n_mat * 3].reshape((n_mat, 3)),
                mu_s=res.x[n_mat * 3 : n_mat * 6].reshape((n_mat, 3)),
                g=res.x[n_mat * 6 : n_mat * 9].reshape((n_mat, 3)),
            ),
            fitted_k1,
            fitted_k2,
        )


class VulkanFourFluxModel(OpticalModel):
    """基于 Vulkan 的四通量模型实现"""

    def __init__(self):
        from oc_core_02.utils.bin_loader import import_cpp_extension

        try:
            self._mcrt = import_cpp_extension("opencolor_mcrt")
            if not hasattr(self._mcrt, "predict_four_flux_vulkan"):
                raise RuntimeError("未找到 Vulkan 四通量接口")
        except Exception as e:
            logger.error(f"[VulkanModel] 初始化失败: {e}")
            raise

    def _apply_saunderson(self, Ri, k1, k2):
        """应用 Saunderson 修正"""
        if k1 == 0 and k2 == 0:
            return Ri
        return k1 + (1.0 - k1) * (1.0 - k2) * Ri / (1.0 - k2 * Ri + 1e-9)

    def _sigmoid(self, x):
        return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))

    def predict_rgb(
        self, sequences, material_keys, params, backing=0.98, k1=0.04, k2=0.6
    ):
        key_to_idx = {k.upper(): i for i, k in enumerate(material_keys)}
        n_seq = len(sequences)
        if n_seq == 0:
            return np.zeros((0, 3), dtype=np.float32)
        max_len = max(len(s) for s in sequences)
        seq_indices = np.full((n_seq, max_len), -1, dtype=np.int32)
        for i, s in enumerate(sequences):
            for j, name in enumerate(s):
                seq_indices[i, j] = key_to_idx.get(str(name).upper(), -1)

        # Vulkan Shader 内部会进行 exp 转换，所以这里直接传递原始 log 空间参数
        mu_a = np.ascontiguousarray(params.mu_a.astype(np.float32))
        mu_s = np.ascontiguousarray(params.mu_s.astype(np.float32))
        g = np.ascontiguousarray(params.g.astype(np.float32))
        seq_indices = np.ascontiguousarray(seq_indices, dtype=np.int32)

        try:
            out_srgb = self._mcrt.predict_four_flux_vulkan(
                mu_a, mu_s, g, seq_indices, float(backing), float(k1), float(k2)
            )
            return np.asarray(out_srgb, dtype=np.float32).reshape((n_seq, 3))
        except TypeError:
            out_srgb_raw = self._mcrt.predict_four_flux_vulkan(
                mu_a, mu_s, g, seq_indices, float(backing)
            )
            from .color_space import srgb_to_linear01, linear01_to_srgb01

            out_srgb_arr = np.asarray(out_srgb_raw, dtype=np.float32).reshape(
                (n_seq, 3)
            )
            out_lin = srgb_to_linear01(out_srgb_arr)
            out_lin_corr = self._apply_saunderson(out_lin, k1, k2)
            return np.clip(linear01_to_srgb01(out_lin_corr), 0.0, 1.0).astype(
                np.float32
            )

    def fit(self, sequences, y_lab, material_keys, initial_params, **kwargs):
        from scipy.optimize import minimize
        from .color_space import rgb01_to_lab

        # 获取 Saunderson 参数和正则化系数
        k1_val = float(kwargs.get("k1", 0.04))
        k2_val = float(kwargs.get("k2", 0.6))
        backing_val = float(kwargs.get("backing", 0.98))
        reg_val = float(kwargs.get("reg", 1e-4))
        optimize_k = kwargs.get("optimize_k", False)
        sample_weight = kwargs.get("sample_weight", None)

        n_mat = len(material_keys)
        if sample_weight is None or len(sample_weight) != len(y_lab):
            sample_weight = np.ones(len(y_lab), dtype=np.float32)
        else:
            sample_weight = np.asarray(sample_weight, dtype=np.float32)

        def _loss(x):
            mu_a = x[: n_mat * 3].reshape((n_mat, 3))
            mu_s = x[n_mat * 3 : n_mat * 6].reshape((n_mat, 3))
            g = x[n_mat * 6 : n_mat * 9].reshape((n_mat, 3))

            if optimize_k:
                k1 = np.clip(x[n_mat * 9], 0.0, 0.2)
                k2 = np.clip(x[n_mat * 9 + 1], 0.0, 1.0)
            else:
                k1, k2 = k1_val, k2_val

            p = OpticalParams(mu_a=mu_a, mu_s=mu_s, g=g)
            pred_rgb = self.predict_rgb(
                sequences, material_keys, p, backing=backing_val, k1=k1, k2=k2
            )
            pred_lab = rgb01_to_lab(pred_rgb)
            sample_loss = np.mean(np.square(pred_lab - y_lab), axis=1)
            data_loss = float(
                np.sum(sample_weight * sample_loss) / (np.sum(sample_weight) + 1e-9)
            )
            reg_loss = reg_val * (
                np.sum(np.square(mu_a)) + np.sum(np.square(mu_s)) + np.sum(np.square(g))
            )
            return data_loss + reg_loss

        x0_list = [
            initial_params.mu_a.flatten(),
            initial_params.mu_s.flatten(),
            initial_params.g.flatten(),
        ]
        if optimize_k:
            x0_list.append(np.array([k1_val, k2_val]))
        x0 = np.concatenate(x0_list)

        bounds = [(-6.0, 6.0)] * (n_mat * 9)
        if optimize_k:
            bounds += [(0.0, 0.2), (0.0, 1.0)]

        res = minimize(
            _loss,
            x0,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": kwargs.get("maxiter", 50), "disp": True},
        )
        fitted_k1, fitted_k2 = k1_val, k2_val
        if optimize_k:
            fitted_k1 = float(np.clip(res.x[n_mat * 9], 0.0, 0.2))
            fitted_k2 = float(np.clip(res.x[n_mat * 9 + 1], 0.0, 1.0))
            logger.info(
                f"[VulkanModel] 拟合得到的 Saunderson 参数: k1={fitted_k1:.4f}, k2={fitted_k2:.4f}"
            )

        return (
            OpticalParams(
                mu_a=res.x[: n_mat * 3].reshape((n_mat, 3)),
                mu_s=res.x[n_mat * 3 : n_mat * 6].reshape((n_mat, 3)),
                g=res.x[n_mat * 6 : n_mat * 9].reshape((n_mat, 3)),
            ),
            fitted_k1,
            fitted_k2,
        )
