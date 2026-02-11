"""
规格适配器模块
用于解析和适配不同格式的色盘规格文件(board_spec.json)
提供统一的接口访问格子颜色、配方等信息
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, List

try:
    from oc_calib.board_spec import BoardSpec  # type: ignore
except Exception:
    BoardSpec = None  # type: ignore


class SpecAdapter:
    """色盘规格适配器类

    用于解析和适配不同格式的色盘规格文件，提供统一接口访问：
    - 格子目标RGB颜色
    - 格子配方信息
    - 格子层序列信息
    """

    def __init__(self, spec_path: Path):
        """初始化规格适配器

        参数:
            spec_path: 规格文件路径（JSON格式）
        """
        self.spec_path = Path(spec_path)
        self.raw: Dict[str, Any] = json.loads(
            self.spec_path.read_text(encoding="utf-8", errors="replace")
        )
        self.obj = None
        if BoardSpec is not None:
            try:
                self.obj = BoardSpec.load(self.spec_path)
            except Exception:
                self.obj = None

        self.name = (
            self.raw.get("name")
            or getattr(self.obj, "name", None)
            or self.spec_path.stem
        )
        self.rows, self.cols = self._infer_grid_shape()

    def _infer_grid_shape(self) -> Tuple[int, int]:
        """推断网格形状（行列数）

        优先从规格文件中读取真实的物理行列数（例如17x17），
        如果没有定义，则退回到默认的逻辑尺寸（15x15）

        返回:
            (行数, 列数) 元组
        """
        # 优先从规格文件中读取真实的物理行列数 (例如 17x17)
        r = self.raw.get("rows")
        c = self.raw.get("cols")
        if r and c:
            return int(r), int(c)

        # 如果没有定义，则退回到逻辑尺寸 (15x15)
        return 15, 15

    def get_cell_target_rgb(self, r: int, c: int) -> Optional[List[float]]:
        """获取指定格子的目标RGB颜色

        参数:
            r: 行索引
            c: 列索引

        返回:
            RGB颜色列表 [R, G, B]，如果未找到则返回None
        """
        if self.obj is not None and hasattr(self.obj, "get_cell_color"):
            try:
                col = self.obj.get_cell_color(r, c)
                if col is None:
                    return None
                return [float(x) for x in col]
            except Exception:
                pass
        # 从原始数据查找
        cell = self._get_cell_raw(r, c)
        if cell is None:
            return None
        for key in ["target_rgb", "rgb", "color_rgb", "target"]:
            if key in cell:
                v = cell[key]
                if isinstance(v, (list, tuple)) and len(v) == 3:
                    return [float(x) for x in v]
        # 有时在'color'字段下
        if "color" in cell and isinstance(cell["color"], dict):
            v = cell["color"].get("rgb")
            if isinstance(v, (list, tuple)) and len(v) == 3:
                return [float(x) for x in v]
        return None

    def get_cell_recipe(self, r: int, c: int) -> Dict[str, float]:
        """获取指定格子的配方信息

        返回材料名称到重量的映射字典（非负值）

        参数:
            r: 行索引
            c: 列索引

        返回:
            材料名称到重量的字典
        """
        # 返回材料到重量的扁平字典（非负值）
        if self.obj is not None:
            for meth in [
                "get_cell_recipe",
                "get_cell_mix",
                "get_cell_layers",
                "get_cell_params",
            ]:
                if hasattr(self.obj, meth):
                    try:
                        v = getattr(self.obj, meth)(r, c)
                        return _recipe_to_flat(v)
                    except Exception:
                        pass
        cell = self._get_cell_raw(r, c)
        if not cell:
            return {}

        # 处理特殊的"slot_names" + "layers"结构
        # 存在两种常见格式：
        #   (A) slot_names = 调色板（例如8个名称），layers = 每层对应的槽位索引（例如5个整数）
        #   (B) slot_names = 每层对应的名称（例如5个名称），layers = 每层对应的重量/厚度（例如5个浮点数）
        #   (C) slot_names = 每层对应的名称（例如5个名称），layers = 索引（但slot_names已解析为名称）
        if "slot_names" in cell and "layers" in cell:
            slots = cell.get("slot_names")
            layers = cell.get("layers")
            if (
                isinstance(slots, list)
                and isinstance(layers, list)
                and slots
                and layers
            ):
                # 启发式判断layers是否为整数索引
                is_int_like = True
                idx_vals = []
                for v in layers:
                    try:
                        fv = float(v)
                    except Exception:
                        is_int_like = False
                        break
                    iv = int(round(fv))
                    if abs(fv - iv) > 1e-6:
                        is_int_like = False
                        break
                    idx_vals.append(iv)

                # 情况1: len(slots) == len(layers) 且都是整数
                # 这通常表示 slots 已经是每层名称，layers 是索引（但不需要再解析）
                if len(slots) == len(layers) and is_int_like:
                    # slots 已经是每层名称，直接计数
                    out: Dict[str, float] = {}
                    for name in slots:
                        out[str(name)] = out.get(str(name), 0.0) + 1.0
                    return out

                # 情况2: layers 是指向调色板的索引（slots 长度 > layers 长度）
                if is_int_like and len(slots) > 0 and max(idx_vals + [0]) < len(slots):
                    out2: Dict[str, float] = {}
                    for iv in idx_vals:
                        if 0 <= iv < len(slots):
                            name = str(slots[iv])
                            out2[name] = out2.get(name, 0.0) + 1.0
                    return out2

                # 否则退回到将slots/layers解释为对齐的每层（名称，重量）
                out3: Dict[str, float] = {}
                for j in range(min(len(slots), len(layers))):
                    name = str(slots[j])
                    try:
                        w = float(layers[j])
                    except Exception:
                        w = 1.0
                    if w != 0:
                        out3[name] = out3.get(name, 0.0) + w
                return out3

        for key in ["recipe", "mix", "layers", "params", "stack"]:
            if key in cell:
                return _recipe_to_flat(cell[key])
        # 可能cell本身就是配方字典
        return {}

    def _get_cell_raw(self, r: int, c: int) -> Optional[Dict[str, Any]]:
        """获取指定格子的原始数据

        支持多种规格文件格式：
        - cell_map: 行列字符串键的字典
        - cells: 列表格式（二维列表或一维字典列表）
        - grid.cells: 嵌套结构

        同时处理active_range坐标映射（物理坐标到逻辑坐标的转换）

        参数:
            r: 行索引（物理坐标）
            c: 列索引（物理坐标）

        返回:
            格子的原始数据字典，如果未找到则返回None
        """
        # 0. 检查active_range进行坐标映射
        active = self.raw.get("active_range")
        if isinstance(active, dict):
            min_r = active.get("min_row", 0)
            max_r = active.get("max_row", self.rows - 1)
            min_c = active.get("min_col", 0)
            max_c = active.get("max_col", self.cols - 1)

            # 如果在有效范围外，返回None
            if not (min_r <= r <= max_r and min_c <= c <= max_c):
                return None

            # 将物理坐标(r,c)映射到逻辑坐标(lr, lc)用于cell_map查找
            # 假设cell_map的键"1,1"对应(min_r, min_c)
            lr = r - min_r
            lc = c - min_c
        else:
            lr = r
            lc = c

        # 1. 检查cell_map（行列字符串键）
        cell_map = self.raw.get("cell_map")
        if isinstance(cell_map, dict) and cell_map:
            # 检测cell_map使用的坐标格式
            # 通过采样前几个键来判断是0-based还是1-based
            sample_keys = list(cell_map.keys())[:5]
            has_0_based = any(
                key.startswith("0,") or ",0" in key for key in sample_keys
            )

            if has_0_based:
                # 0-based: 直接使用lr, lc
                key = f"{lr},{lc}"
                if key in cell_map:
                    return cell_map[key]
            else:
                # 1-based: 使用lr+1, lc+1
                key = f"{lr + 1},{lc + 1}"
                if key in cell_map:
                    return cell_map[key]

        # 2. 检查cells列表
        cells = self.raw.get("cells")
        if isinstance(cells, list) and cells:
            if isinstance(cells[0], list):
                try:
                    v = cells[lr][lc]
                    return v if isinstance(v, dict) else None
                except Exception:
                    return None
            # 一维列表
            for it in cells:
                if isinstance(it, dict) and it.get("row") == lr and it.get("col") == lc:
                    return it
        # 替代结构：grid->rows
        grid = self.raw.get("grid")
        if isinstance(grid, dict):
            g = grid.get("cells")
            if isinstance(g, list) and g and isinstance(g[0], list):
                try:
                    v = g[lr][lc]
                    return v if isinstance(v, dict) else None
                except Exception:
                    return None
        return None


def extract_layer_sequence(
    cell_raw: Optional[Dict[str, Any]],
) -> Tuple[List[str], List[int], List[str]]:
    """从规格单元格原始字典中提取每层材料名称

    支持两种常见格式：
      - slot_names: 调色板（长度>=8），layers: 索引（长度==n_layers）-> 将索引映射到名称
      - slot_names: 每层对应的名称（长度==n_layers）-> 直接使用

    参数:
        cell_raw: 单元格的原始数据字典

    返回:
        (调色板名称列表, 层索引列表, 层名称列表)
        如果某部分不可用，可能返回空列表或None
    """
    if not isinstance(cell_raw, dict):
        return [], [], []
    slots = cell_raw.get("slot_names")
    layers = cell_raw.get("layers")
    palette = [str(s) for s in slots] if isinstance(slots, list) else []
    if isinstance(slots, list) and isinstance(layers, list) and slots and layers:
        if len(slots) == len(layers) and len(slots) <= 16:
            return palette, [], palette
    idxs = []
    if isinstance(layers, list) and layers:
        int_like = True
        for v in layers:
            try:
                fv = float(v)
            except Exception:
                int_like = False
                break
            iv = int(round(fv))
            if abs(fv - iv) > 1e-6:
                int_like = False
                break
            idxs.append(iv)
        if int_like and palette and len(palette) > len(layers):
            min_idx = min(idxs) if idxs else 0
            max_idx = max(idxs) if idxs else 0
            is_one_based = min_idx >= 1 and max_idx <= len(palette)
            if is_one_based:
                names = [
                    palette[iv - 1] if 1 <= iv <= len(palette) else "" for iv in idxs
                ]
            else:
                names = [palette[iv] if 0 <= iv < len(palette) else "" for iv in idxs]
            return palette, idxs, names
    if isinstance(slots, list) and slots and len(slots) <= 16:
        return palette, [], palette
    return palette, [], []


def _recipe_to_flat(v: Any) -> Dict[str, float]:
    """将配方数据转换为扁平字典格式

    支持多种输入格式：
    - 字典：材料名称到重量的映射
    - 列表：层字典列表，每个层包含材料和重量信息

    参数:
        v: 配方数据（可以是字典、列表或其他格式）

    返回:
        材料名称到重量的扁平字典
    """
    out: Dict[str, float] = {}
    if v is None:
        return out
    # 如果是材料到重量的字典映射
    if isinstance(v, dict):
        for k, val in v.items():
            try:
                f = float(val)
            except Exception:
                continue
            if f != 0:
                out[str(k)] = out.get(str(k), 0.0) + f
        return out
    # 如果是层字典列表
    if isinstance(v, list):
        for it in v:
            if isinstance(it, dict):
                # 常见的材料名称键
                mat = (
                    it.get("material")
                    or it.get("slot")
                    or it.get("name")
                    or it.get("color")
                    or it.get("id")
                )
                # 常见的重量/数量键
                amt = (
                    it.get("amount")
                    or it.get("weight")
                    or it.get("w")
                    or it.get("ratio")
                    or it.get("thickness")
                    or it.get("value")
                )
                if mat is None:
                    # 可能字典本身就是材料到重量的映射
                    for k2, val2 in it.items():
                        try:
                            f = float(val2)
                        except Exception:
                            continue
                        if f != 0:
                            out[str(k2)] = out.get(str(k2), 0.0) + f
                    continue
                try:
                    f = float(amt) if amt is not None else 1.0
                except Exception:
                    f = 1.0
                out[str(mat)] = out.get(str(mat), 0.0) + f
        return out
    # 元组等其他类型
    return out
