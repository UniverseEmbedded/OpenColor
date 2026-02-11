"""
特征工程模块
为物理模型和GPR残差模型构建训练特征
保留层顺序信息，避免不同层序列产生特征冲突
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np


def infer_material_keys(recipes: Sequence[Dict[str, float]]) -> List[str]:
    """从配方字典中推断数值材料键（排除元数据键）"""
    mats = set()
    for rec in recipes:
        if not rec:
            continue
        for k, v in rec.items():
            if str(k).startswith("_"):
                continue
            try:
                float(v)
            except Exception:
                continue
            mats.add(str(k))
    return sorted(mats)


def _make_layer_sequence(fractions: Dict[str, float], total_layers: int) -> List[str]:
    """从配方数值构建层序列，与RTS模型的逻辑保持一致。

    策略：按数值降序排序，将数值四舍五入作为重复次数，简单重复材料名。
    注意：不使用交替分布策略，确保与 _rts_build_seq_from_recipe 保持一致。
    """
    # 过滤并排序配方项（按数值降序，数值相同则按名称升序）
    items: List[Tuple[str, float]] = []
    for k, v in fractions.items():
        if str(k).startswith("_"):
            continue
        try:
            fv = float(v)
            if fv > 0:
                items.append((str(k).upper(), fv))
        except Exception:
            continue

    if not items:
        return ["WHITE"] * total_layers

    # 按数值降序排序（数值相同则按名称升序）
    items.sort(key=lambda kv: (-kv[1], kv[0]))

    # 构建序列：将数值四舍五入作为重复次数
    seq: List[str] = []
    for k, v in items:
        n = int(round(v))
        if n <= 0:
            continue
        seq.extend([k] * n)
        if len(seq) >= total_layers:
            break

    # 截断或填充
    if len(seq) > total_layers:
        seq = seq[:total_layers]
    elif len(seq) < total_layers:
        seq = seq + ["WHITE"] * (total_layers - len(seq))

    return seq


def build_layer_sequences(
    recipes: Sequence[Dict[str, float]],
    material_keys: Sequence[str],
    n_layers: int,
    layer_names_order: str = "bottom_first",
) -> List[List[str]]:
    """返回每个样本的层名称序列，保留顺序

    优先级：
    1) 如果存在，使用显式的recipe['_layer_names']（已排序）
    2) 否则从数值分数派生有序序列
    """
    order = str(layer_names_order).strip().lower()
    if order not in {"bottom_first", "top_first"}:
        raise ValueError(
            f"未知的层序方向: {layer_names_order}，仅支持 bottom_first 或 top_first"
        )

    out: List[List[str]] = []
    for r in recipes:
        if not r:
            out.append(["WHITE"] * n_layers)
            continue

        # 优先使用显式层顺序（如果提供）
        ln = r.get("_layer_names", r.get("layer_names", None))
        if isinstance(ln, list) and len(ln) > 0:
            seq = [str(name).upper() for name in ln]
            if len(seq) < n_layers:
                seq = seq + ["WHITE"] * (n_layers - len(seq))
            seq = seq[:n_layers]
            if order == "bottom_first":
                seq = list(reversed(seq))
            out.append(seq)
            continue

        fr: Dict[str, float] = {}
        # 不区分大小写的材料映射
        recipe_upper = {str(k).upper(): v for k, v in r.items()}
        for k in material_keys:
            v = recipe_upper.get(str(k).upper(), 0.0)
            try:
                fr[str(k).upper()] = float(v)
            except Exception:
                fr[str(k).upper()] = 0.0
        seq = _make_layer_sequence(fr, n_layers)
        if order == "bottom_first":
            seq = list(reversed(seq))
        out.append(seq)
    return out


def _encode_sequence_features(
    sequences: Sequence[Sequence[str]],
    material_keys: Sequence[str],
    n_layers: int,
) -> Tuple[np.ndarray, List[str]]:
    """将有序层序列编码为抗冲突特征

    包含：
    - 位置独热编码：(n_layers * (M+1))，带额外的EMPTY桶
    - 相邻有序对计数：((M+1)^2)
    - 从首尾位置的连续长度 (2)
    - 每材料的深度加权计数 (M+1)

    这使得不同序列（即使每材料计数相同）也能区分开
    """
    m = len(material_keys)
    empty_idx = m
    n_classes = m + 1

    key_to_idx = {str(k).upper(): i for i, k in enumerate(material_keys)}

    n = len(sequences)
    pos = np.zeros((n, n_layers * n_classes), dtype=np.float32)
    pair = np.zeros((n, n_classes * n_classes), dtype=np.float32)
    run = np.zeros((n, 2), dtype=np.float32)  # run_first, run_last
    depth_w = np.zeros((n, n_classes), dtype=np.float32)

    # 从1到n_layers归一化的权重（捕获"上层更重要"而不假设方向）
    weights = np.arange(1, n_layers + 1, dtype=np.float32)
    weights = weights / float(weights.sum())

    for i, seq in enumerate(sequences):
        # 归一化序列长度
        s = list(seq[:n_layers]) + ["EMPTY"] * max(0, n_layers - len(seq))
        idxs = []
        for p, name in enumerate(s):
            idx = key_to_idx.get(str(name).upper(), empty_idx)
            idxs.append(idx)
            pos[i, p * n_classes + idx] = 1.0
            depth_w[i, idx] += weights[p]

        # 有序相邻对
        for p in range(n_layers - 1):
            a = idxs[p]
            b = idxs[p + 1]
            pair[i, a * n_classes + b] += 1.0

        # 从首位置开始的连续长度
        rf = 1
        for p in range(1, n_layers):
            if idxs[p] == idxs[0]:
                rf += 1
            else:
                break
        # 从尾位置开始的连续长度
        rl = 1
        for p in range(n_layers - 2, -1, -1):
            if idxs[p] == idxs[-1]:
                rl += 1
            else:
                break
        run[i, 0] = rf / float(n_layers)
        run[i, 1] = rl / float(n_layers)

    names: List[str] = []
    # 位置独热编码名称
    for p in range(n_layers):
        for c in range(n_classes):
            cname = "EMPTY" if c == empty_idx else str(material_keys[c])
            names.append(f"pos{p + 1}:{cname}")
    # 对名称
    for a in range(n_classes):
        an = "EMPTY" if a == empty_idx else str(material_keys[a])
        for b in range(n_classes):
            bn = "EMPTY" if b == empty_idx else str(material_keys[b])
            names.append(f"pair:{an}->{bn}")
    names += ["run_first", "run_last"]
    for c in range(n_classes):
        cname = "EMPTY" if c == empty_idx else str(material_keys[c])
        names.append(f"depth_w:{cname}")

    feats = np.concatenate([pos, pair, run, depth_w], axis=1).astype(np.float32)
    return feats, names


def build_gpr_features(
    recipes: Sequence[Dict[str, float]],
    material_keys: Sequence[str],
    base_pred_lab: np.ndarray,
    n_layers: int = 5,
    layer_names_order: str = "bottom_first",
    k1: float | None = None,
    k2: float | None = None,
    backing: float | None = None,
) -> Tuple[np.ndarray, List[str]]:
    """为GPR残差模型构建训练特征

    说明：
    - 保留原始连续配方特征（绝对/相对数量）
    - 添加保留层顺序的序列特征以避免冲突
    - 可选添加物理参数（k1, k2, backing）以帮助跨调色板外推
    """
    n = len(recipes)
    m = len(material_keys)

    X_main = np.zeros((n, m), dtype=np.float32)
    for j, k in enumerate(material_keys):
        k_upper = str(k).upper()
        vals = []
        for r in recipes:
            if not r:
                vals.append(0.0)
                continue
            # 不区分大小写查找
            recipe_upper = {str(rk).upper(): rv for rk, rv in r.items()}
            vals.append(float(recipe_upper.get(k_upper, 0.0)))
        X_main[:, j] = np.array(vals, dtype=np.float32)

    s = X_main.sum(axis=1, keepdims=True)
    eps = 1e-8
    rel_X = X_main / (s + eps) if m > 0 else X_main
    mx = (
        X_main.max(axis=1, keepdims=True)
        if m > 0
        else np.zeros((n, 1), dtype=np.float32)
    )
    nz = (X_main > 0).sum(axis=1, keepdims=True).astype(np.float32)

    # 有序序列
    seqs = build_layer_sequences(
        recipes, material_keys, n_layers=n_layers, layer_names_order=layer_names_order
    )
    seq_feats, seq_names = _encode_sequence_features(
        seqs, material_keys, n_layers=n_layers
    )

    feats = [rel_X, s, mx, nz, base_pred_lab.astype(np.float32), seq_feats]
    names = (
        [f"rel[{k}]" for k in material_keys]
        + ["sum_amount", "max_amount", "nonzero_count", "base_L", "base_a", "base_b"]
        + seq_names
    )

    if k1 is not None:
        feats.append(np.full((n, 1), float(k1), dtype=np.float32))
        names.append("k1")
    if k2 is not None:
        feats.append(np.full((n, 1), float(k2), dtype=np.float32))
        names.append("k2")
    if backing is not None:
        feats.append(np.full((n, 1), float(backing), dtype=np.float32))
        names.append("backing")

    X = np.concatenate(feats, axis=1).astype(np.float32)
    return X, names
