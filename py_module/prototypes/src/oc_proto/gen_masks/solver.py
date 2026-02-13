"""
爬山求解器模块
基于训练好的物理GPR模型，使用爬山算法为目标RGB颜色求解最优配方
"""

import random

import numpy as np
from tqdm import tqdm

from ..calib_color_rts.color_space import rgb01_to_lab
from oc_xgb.xgb_features import build_gpr_features
from oc_proto.calib_color_rts.models.ml_residual_model import MLResidualModel
from oc_xgb.xgb_fit import PhysGPRModel, predict_phys_gpr_lab, predict_ad_rgb01


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


class HillClimbingSolver:
    def __init__(self, model: PhysGPRModel):
        self.model = model
        self.material_keys = model.optical.material_keys
        self.n_layers = model.optical.n_layers
        self.m = len(self.material_keys)

    def _align_features(self, X: np.ndarray, names: list[str]) -> np.ndarray:
        model_names = list(getattr(self.model, "feature_names", []) or [])
        if not model_names:
            return X
        if X.shape[1] == len(model_names) and names == model_names:
            return X

        if len(model_names) < X.shape[1] and names[: len(model_names)] == model_names:
            logger.info(
                f"[Solver] 特征维度不一致，执行前缀裁剪: {X.shape[1]} -> {len(model_names)}"
            )
            return X[:, : len(model_names)]

        name_to_idx = {n: i for i, n in enumerate(names)}
        X_aligned = np.zeros((X.shape[0], len(model_names)), dtype=np.float32)
        missing: list[str] = []
        for j, n in enumerate(model_names):
            i = name_to_idx.get(n)
            if i is None:
                missing.append(n)
            else:
                X_aligned[:, j] = X[:, i]

        extra = [n for n in names if n not in set(model_names)]
        if missing:
            logger.info(f"[Solver] 特征缺失数量: {len(missing)}")
            logger.info(f"[Solver] 缺失特征示例: {missing[:12]}")
        if extra:
            logger.info(f"[Solver] 额外特征数量: {len(extra)}")
            logger.info(f"[Solver] 额外特征示例: {extra[:12]}")
        logger.info(f"[Solver] 已按模型特征名对齐: {X.shape} -> {X_aligned.shape}")
        return X_aligned

    def _predict_batch(self, recipe_indices_list: np.ndarray) -> np.ndarray:
        """批量预测一组配方索引的 Lab 颜色

        recipe_indices_list: (N, n_layers) int array
        """
        n = len(recipe_indices_list)
        if n == 0:
            return np.zeros((0, 3), dtype=np.float32)

        recipes = []
        sequences_top_first = []
        for i in range(n):
            indices = recipe_indices_list[i]
            indices = np.asarray(indices, dtype=np.int32).reshape(-1)

            layer_names_bottom_first = [
                self.material_keys[int(idx)] for idx in indices.tolist()
            ]
            seq_top_first = list(reversed(layer_names_bottom_first))
            sequences_top_first.append(seq_top_first)

            # 转换为配方字典
            recipe = {}
            for idx in indices:
                m_key = self.material_keys[idx]
                recipe[m_key] = recipe.get(m_key, 0.0) + 1.0
            recipe["_layer_names"] = layer_names_bottom_first
            recipes.append(recipe)

        # 基础物理模型预测
        base_rgb01 = predict_ad_rgb01(
            sequences_top_first,
            self.material_keys,
            self.model.optical,
            k1=self.model.optical.k1,
            k2=self.model.optical.k2,
            backing=self.model.optical.backing,
        )
        base_lab = rgb01_to_lab(base_rgb01)

        # GPR 残差修正
        X, feat_names = build_gpr_features(
            recipes,
            self.material_keys,
            base_lab,
            n_layers=self.n_layers,
            layer_names_order="bottom_first",
            k1=self.model.optical.k1,
            k2=self.model.optical.k2,
            backing=self.model.optical.backing,
        )
        X = self._align_features(X, feat_names)
        return predict_phys_gpr_lab(self.model, sequences_top_first, X)


class HillClimbingSolverML:
    def __init__(self, model: MLResidualModel):
        self.model = model
        self.material_keys = list(model.material_keys)
        self.n_layers = int(model.n_layers)
        self.m = len(self.material_keys)

    def _align_features(self, X: np.ndarray, names: list[str]) -> np.ndarray:
        model_names = list(getattr(self.model, "feature_names", []) or [])
        if not model_names:
            return X
        if X.shape[1] == len(model_names) and names == model_names:
            return X

        if len(model_names) < X.shape[1] and names[: len(model_names)] == model_names:
            logger.info(
                f"[Solver] 特征维度不一致，执行前缀裁剪: {X.shape[1]} -> {len(model_names)}"
            )
            return X[:, : len(model_names)]

        name_to_idx = {n: i for i, n in enumerate(names)}
        X_aligned = np.zeros((X.shape[0], len(model_names)), dtype=np.float32)
        missing: list[str] = []
        for j, n in enumerate(model_names):
            i = name_to_idx.get(n)
            if i is None:
                missing.append(n)
            else:
                X_aligned[:, j] = X[:, i]

        extra = [n for n in names if n not in set(model_names)]
        if missing:
            logger.info(f"[Solver] 特征缺失数量: {len(missing)}")
            logger.info(f"[Solver] 缺失特征示例: {missing[:12]}")
        if extra:
            logger.info(f"[Solver] 额外特征数量: {len(extra)}")
            logger.info(f"[Solver] 额外特征示例: {extra[:12]}")
        logger.info(f"[Solver] 已按模型特征名对齐: {X.shape} -> {X_aligned.shape}")
        return X_aligned

    def _predict_batch(self, recipe_indices_list: np.ndarray) -> np.ndarray:
        n = len(recipe_indices_list)
        if n == 0:
            return np.zeros((0, 3), dtype=np.float32)

        recipes = []
        sequences_top_first = []
        for i in range(n):
            indices = recipe_indices_list[i]
            indices = np.asarray(indices, dtype=np.int32).reshape(-1)

            layer_names_bottom_first = [
                self.material_keys[int(idx)] for idx in indices.tolist()
            ]
            seq_top_first = list(reversed(layer_names_bottom_first))
            sequences_top_first.append(seq_top_first)

            recipe = {}
            for idx in indices:
                m_key = self.material_keys[idx]
                recipe[m_key] = recipe.get(m_key, 0.0) + 1.0
            recipe["_layer_names"] = layer_names_bottom_first
            recipes.append(recipe)

        base_lab = self.model._rts_predict_lab(sequences_top_first)
        X, feat_names = build_gpr_features(
            recipes,
            self.material_keys,
            base_lab,
            n_layers=self.n_layers,
            layer_names_order=self.model.layer_names_order,
        )
        X = self._align_features(X, feat_names)
        pred_lab = self.model.predict(sequences_top_first, X)
        return pred_lab.astype(np.float32)

    def solve(self, target_rgb_list: np.ndarray, n_random_samples=1000) -> np.ndarray:
        n_targets = len(target_rgb_list)
        if n_targets == 0:
            return np.zeros((0, self.n_layers), dtype=np.int32)

        target_labs = rgb01_to_lab(target_rgb_list)

        random_indices = np.random.randint(
            0, self.m, size=(n_random_samples, self.n_layers)
        )
        pure_recipes = []
        for i in range(self.m):
            pure_recipes.append([i] * self.n_layers)
        random_indices = np.concatenate(
            [random_indices, np.array(pure_recipes)], axis=0
        )

        candidate_labs = self._predict_batch(random_indices)

        best_indices = np.zeros((n_targets, self.n_layers), dtype=np.int32)

        logger.info(f"[Solver] 正在为 {n_targets} 个唯一颜色寻找初始候选...")
        for i in tqdm(range(n_targets), desc="寻找初始候选", unit="color"):
            dists = np.linalg.norm(candidate_labs - target_labs[i], axis=1)
            best_idx = np.argmin(dists)
            best_indices[i] = random_indices[best_idx]

        logger.info(f"[Solver] 正在进行局部爬山优化...")
        for i in tqdm(range(n_targets), desc="爬山优化", unit="color"):
            curr_indices = best_indices[i].copy()
            curr_lab = self._predict_batch(curr_indices[None, :])[0]
            curr_dist = np.linalg.norm(curr_lab - target_labs[i])

            for _ in range(10):
                layer_to_change = random.randint(0, self.n_layers - 1)
                new_m = random.randint(0, self.m - 1)
                if new_m == curr_indices[layer_to_change]:
                    continue

                next_indices = curr_indices.copy()
                next_indices[layer_to_change] = new_m
                next_lab = self._predict_batch(next_indices[None, :])[0]
                next_dist = np.linalg.norm(next_lab - target_labs[i])

                if next_dist < curr_dist:
                    curr_dist = next_dist
                    curr_indices = next_indices

            best_indices[i] = curr_indices

        return best_indices

    def solve(self, target_rgb_list: np.ndarray, n_random_samples=1000) -> np.ndarray:
        """为一组 RGB 颜色实时求解最优配方

        target_rgb_list: (N, 3) 0..1 float
        返回: (N, n_layers) int array，表示每层的材料索引
        """
        n_targets = len(target_rgb_list)
        if n_targets == 0:
            return np.zeros((0, self.n_layers), dtype=np.int32)

        target_labs = rgb01_to_lab(target_rgb_list)

        # 1. 随机采样候选空间 (实时计算，非预置库)
        # 我们采样一部分空间来获得一个好的初始值
        random_indices = np.random.randint(
            0, self.m, size=(n_random_samples, self.n_layers)
        )
        # 补充一些纯色配方
        pure_recipes = []
        for i in range(self.m):
            pure_recipes.append([i] * self.n_layers)
        random_indices = np.concatenate(
            [random_indices, np.array(pure_recipes)], axis=0
        )

        # 预测候选集颜色
        candidate_labs = self._predict_batch(random_indices)

        # 2. 为每个目标颜色找到最近的初始候选
        best_indices = np.zeros((n_targets, self.n_layers), dtype=np.int32)

        logger.info(f"[Solver] 正在为 {n_targets} 个唯一颜色寻找初始候选...")
        for i in tqdm(range(n_targets), desc="寻找初始候选", unit="color"):
            dists = np.linalg.norm(candidate_labs - target_labs[i], axis=1)
            best_idx = np.argmin(dists)
            best_indices[i] = random_indices[best_idx]

        # 3. 局部爬山优化 (可选，为了更高精度)
        # 为了速度，我们这里只对每个目标做少量迭代
        logger.info(f"[Solver] 正在进行局部爬山优化...")
        for i in tqdm(range(n_targets), desc="爬山优化", unit="color"):
            curr_indices = best_indices[i].copy()
            curr_lab = self._predict_batch(curr_indices[None, :])[0]
            curr_dist = np.linalg.norm(curr_lab - target_labs[i])

            # 尝试随机改变某一层
            for _ in range(10):
                layer_to_change = random.randint(0, self.n_layers - 1)
                new_m = random.randint(0, self.m - 1)
                if new_m == curr_indices[layer_to_change]:
                    continue

                next_indices = curr_indices.copy()
                next_indices[layer_to_change] = new_m
                next_lab = self._predict_batch(next_indices[None, :])[0]
                next_dist = np.linalg.norm(next_lab - target_labs[i])

                if next_dist < curr_dist:
                    curr_dist = next_dist
                    curr_indices = next_indices

            best_indices[i] = curr_indices

        return best_indices
