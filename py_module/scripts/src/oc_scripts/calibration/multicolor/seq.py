#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


def sequence_index_to_digits(
    base: int, length: int, idx: int, *, lsb_first: bool = True
) -> List[int]:
    """将序列索引转换为数字列表（按指定进制）

    Args:
        base: 进制基数
        length: 序列长度
        idx: 索引值
        lsb_first: 是否最低位在前

    Returns:
        数字列表
    """
    digits = [0] * length
    x = idx
    if lsb_first:
        for pos in range(0, length):
            digits[pos] = x % base
            x //= base
    else:
        for pos in range(length - 1, -1, -1):
            digits[pos] = x % base
            x //= base
    return digits


def interleave_from_counts(counts: Sequence[int]) -> List[int]:
    """根据计数交错排列序列

    将不同类别的元素按计数交错排列，避免相邻相同元素。

    Args:
        counts: 各类别的计数列表

    Returns:
        交错后的序列
    """
    rem = [int(x) for x in counts]
    K = len(rem)
    seq: List[int] = []
    last = -1
    while sum(rem) > 0:
        order = sorted(range(K), key=lambda i: rem[i], reverse=True)
        pick = None
        for i in order:
            if rem[i] <= 0:
                continue
            if i != last:
                pick = i
                break
        if pick is None:
            pick = order[0]
        seq.append(pick)
        rem[pick] -= 1
        last = pick
    return seq


def prioritized_sequences(K: int, L: int, *, max_items: int) -> Iterable[List[int]]:
    """生成优先级的序列组合

    按优先级顺序生成材料序列：
    1. 单一材料序列
    2. 单点变异序列
    3. 双材料平衡序列
    4. 多材料组合序列
    5. 剩余随机序列

    Args:
        K: 材料种类数
        L: 序列长度
        max_items: 最大生成数量

    Yields:
        材料索引序列
    """
    seen: set[Tuple[int, ...]] = set()

    def emit(seq: List[int]):
        t = tuple(seq)
        if t in seen:
            return
        seen.add(t)
        yield seq

    produced = 0

    # 1. 单一材料序列
    for mi in range(K):
        for s in emit([mi] * L):
            yield s
            produced += 1
            if produced >= max_items:
                return

    # 2. 单点变异序列
    for base in range(K):
        for alt in range(K):
            if alt == base:
                continue
            for pos in range(L):
                seq = [base] * L
                seq[pos] = alt
                for s in emit(seq):
                    yield s
                    produced += 1
                    if produced >= max_items:
                        return

    # 3. 双材料平衡序列
    for a in range(K):
        for b in range(a + 1, K):
            for ca in range(2, L - 1):
                cb = L - ca
                counts = [0] * K
                counts[a] = ca
                counts[b] = cb
                seq = interleave_from_counts(counts)
                for s in emit(seq):
                    yield s
                    produced += 1
                    if produced >= max_items:
                        return

    # 4. 多材料组合序列
    for m_used in range(3, min(K, 6) + 1):
        idxs = list(range(K))

        def combs(
            pool: List[int], r: int, start: int = 0, cur: List[int] | None = None
        ):
            nonlocal produced
            if cur is None:
                cur = []
            if len(cur) == r:
                yield cur
                return
            for i in range(start, len(pool)):
                yield from combs(pool, r, i + 1, cur + [pool[i]])

        for subset in combs(idxs, m_used):
            comps = compositions_k(L, m_used, limit=64)
            for comp in comps:
                counts = [0] * K
                for j, mi in enumerate(subset):
                    counts[mi] = int(comp[j])
                if sum(counts) != L:
                    continue
                if sum(1 for x in counts if x > 0) < 3:
                    continue
                seq = interleave_from_counts(counts)
                for s in emit(seq):
                    yield s
                    produced += 1
                    if produced >= max_items:
                        return

    # 5. 剩余随机序列
    idx = 0
    while produced < max_items:
        seq = sequence_index_to_digits(base=K, length=L, idx=idx, lsb_first=True)
        idx += 1
        t = tuple(seq)
        if t in seen:
            continue
        seen.add(t)
        yield seq
        produced += 1


def compositions_k(n: int, k: int, limit: int | None = None) -> List[Tuple[int, ...]]:
    """生成 n 的 k 部分组合

    将整数 n 分解为 k 个非负整数之和的所有组合。

    Args:
        n: 目标整数
        k: 部分数
        limit: 最大返回数量限制

    Returns:
        组合列表
    """
    out: List[Tuple[int, ...]] = []

    def rec(prefix: List[int], remain: int, kk: int) -> None:
        if limit is not None and len(out) >= limit:
            return
        if kk == 1:
            out.append(tuple(prefix + [remain]))
            return
        for a in range(remain, -1, -1):
            rec(prefix + [a], remain - a, kk - 1)
            if limit is not None and len(out) >= limit:
                return

    rec([], int(n), int(k))
    return out
