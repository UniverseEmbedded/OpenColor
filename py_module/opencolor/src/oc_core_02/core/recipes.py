from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class StackRecipe:
    """
    一个单元格/像素的堆叠配方。

    `layers` 的长度为 N（默认 5）。每个条目是一个 0..3 的整数，
    引用 ColorSystem.slot_names 中对应的插槽。
    第 0 层是底层；第 N-1 层是顶层。
    """

    layers: List[int]

    def as_base4_int(self) -> int:
        """
        将层配方转换为四进制整数表示

        @return: 四进制整数
        """
        v = 0
        for d in self.layers:
            v = v * 4 + int(d)
        return v


def int_to_recipe(idx: int, n_layers: int) -> StackRecipe:
    """
    将四进制整数转换为层配方

    @param idx: 四进制整数索引
    @param n_layers: 层数
    @return: 堆叠配方对象
    @raises ValueError: 索引超出范围时抛出
    """
    if idx < 0 or idx >= (4**n_layers):
        raise ValueError(f"idx 超出 {n_layers} 层的范围：{idx}")
    digits = [0] * n_layers
    x = idx
    # 从低位到高位逐位计算
    for i in range(n_layers - 1, -1, -1):
        digits[i] = x % 4
        x //= 4
    return StackRecipe(digits)


def recipe_to_int(recipe: StackRecipe) -> int:
    """
    将层配方转换为四进制整数

    @param recipe: 堆叠配方对象
    @return: 四进制整数
    """
    return recipe.as_base4_int()
