"""
模型基类与注册机制
提供统一的模型接口，支持多种预测模型并存
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar

import numpy as np


@dataclass
class PredictionResult:
    """预测结果容器"""

    rgb01: np.ndarray  # (N, 3) RGB值，范围[0, 1]
    lab: np.ndarray | None = None  # (N, 3) Lab值，可选
    confidence: np.ndarray | None = None  # (N,) 置信度，可选
    metadata: dict[str, Any] | None = None  # 额外元数据


@dataclass
class ModelCapabilities:
    """模型能力描述"""

    supports_uncertainty: bool = False  # 是否支持不确定性估计
    supports_batch_prediction: bool = True  # 是否支持批量预测
    requires_layer_sequence: bool = True  # 是否需要层序列输入
    supports_recipe_input: bool = True  # 是否支持配方输入
    description: str = ""  # 模型描述


class ColorPredictionModel(ABC):
    """颜色预测模型抽象基类

    所有预测模型必须继承此类并实现抽象方法。
    通过 register_model 装饰器注册到模型工厂。
    """

    # 类级别的模型注册表
    _registry: ClassVar[dict[str, type[ColorPredictionModel]]] = {}
    _metadata: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, model_id: str, material_keys: list[str], n_layers: int):
        self.model_id = model_id
        self.material_keys = material_keys
        self.n_layers = n_layers
        self._capabilities = ModelCapabilities()

    @property
    def capabilities(self) -> ModelCapabilities:
        """返回模型能力描述"""
        return self._capabilities

    @abstractmethod
    def predict_from_sequences(self, sequences: list[list[str]]) -> PredictionResult:
        """从层序列预测颜色

        Args:
            sequences: 层序列列表，每个序列是材质名称的列表

        Returns:
            PredictionResult: 预测结果
        """
        pass

    def predict_from_recipes(self, recipes: list[dict[str, float]]) -> PredictionResult:
        """从配方预测颜色（可选实现）

        默认实现将配方转换为层序列后调用 predict_from_sequences
        子类可以覆盖此方法以提供更高效的实现

        Args:
            recipes: 配方列表，每个配方是 {材质名: 层数} 的字典

        Returns:
            PredictionResult: 预测结果
        """
        sequences = self._recipes_to_sequences(recipes)
        return self.predict_from_sequences(sequences)

    def _recipes_to_sequences(self, recipes: list[dict[str, float]]) -> list[list[str]]:
        """将配方转换为层序列"""
        sequences = []
        for recipe in recipes:
            seq = []
            for mat_key in self.material_keys:
                count = int(recipe.get(mat_key, 0))
                seq.extend([mat_key] * count)
            # 填充或截断到固定层数
            if len(seq) < self.n_layers:
                seq.extend(["White"] * (self.n_layers - len(seq)))  # 默认填充White
            elif len(seq) > self.n_layers:
                seq = seq[: self.n_layers]
            sequences.append(seq)
        return sequences

    @abstractmethod
    def save(self, out_dir: Path) -> dict[str, Any]:
        """保存模型到目录

        Args:
            out_dir: 输出目录

        Returns:
            dict: 模型元数据，将被写入 color_model.json
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls, model_dir: Path, metadata: dict[str, Any]) -> ColorPredictionModel:
        """从目录加载模型

        Args:
            model_dir: 模型目录
            metadata: 从 color_model.json 读取的元数据

        Returns:
            ColorPredictionModel: 加载的模型实例
        """
        pass

    @classmethod
    def register(
        cls, model_type: str, description: str = "", **capabilities
    ) -> Callable[[type[ColorPredictionModel]], type[ColorPredictionModel]]:
        """注册模型到工厂的装饰器

        Args:
            model_type: 模型类型标识符
            description: 模型描述
            **capabilities: 模型能力标志

        Example:
            @ColorPredictionModel.register("phys_gpr", description="物理+GPR模型")
            class PhysGPRModel(ColorPredictionModel):
                ...
        """

        def decorator(
            model_class: type[ColorPredictionModel],
        ) -> type[ColorPredictionModel]:
            cls._registry[model_type] = model_class
            cls._metadata[model_type] = {
                "description": description,
                "capabilities": capabilities,
            }
            return model_class

        return decorator

    @classmethod
    def create(cls, model_type: str, **kwargs) -> ColorPredictionModel:
        """工厂方法：创建模型实例

        Args:
            model_type: 模型类型标识符
            **kwargs: 传递给模型构造函数的参数

        Returns:
            ColorPredictionModel: 模型实例

        Raises:
            ValueError: 如果模型类型未注册
        """
        if model_type not in cls._registry:
            raise ValueError(
                f"未知的模型类型: {model_type}. 可用类型: {list(cls._registry.keys())}"
            )
        return cls._registry[model_type](**kwargs)

    @classmethod
    def load_from_dir(cls, model_dir: Path) -> "ColorPredictionModel":
        """从目录加载模型（自动识别类型）

        Args:
            model_dir: 模型目录

        Returns:
            ColorPredictionModel: 加载的模型实例
        """
        import json

        # 尝试查找模型元数据文件
        meta_path = model_dir / "color_model.json"
        rts_meta_path = model_dir / "rts_model.json"

        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            model_type = metadata.get("model_type", "phys_gpr")  # 默认兼容旧模型
        elif rts_meta_path.exists():
            metadata = json.loads(rts_meta_path.read_text(encoding="utf-8"))
            model_type = metadata.get("model_type", "rts")
        else:
            raise FileNotFoundError(f"找不到模型元数据: {meta_path} 或 {rts_meta_path}")

        if model_type not in cls._registry:
            raise ValueError(
                f"未知的模型类型: {model_type}. 可用类型: {list(cls._registry.keys())}"
            )

        return cls._registry[model_type].load(model_dir, metadata)

    @classmethod
    def list_registered_models(cls) -> dict[str, dict[str, Any]]:
        """列出所有已注册的模型"""
        return dict(cls._metadata)


def create_model_from_checkpoint(model_dir: Path) -> ColorPredictionModel:
    """便捷的模型加载函数

    Args:
        model_dir: 模型检查点目录

    Returns:
        ColorPredictionModel: 加载的模型
    """
    return ColorPredictionModel.load_from_dir(model_dir)
