"""
新模型模板
展示如何实现一个新的颜色预测模型

使用说明：
1. 复制此文件并重命名（如 my_model.py）
2. 修改类名和 model_type
3. 实现抽象方法
4. 在 __init__.py 中导入新模型模块以触发注册
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from oc_core_02.utils.logger import get_logger
from oc_xgb.model_base import ColorPredictionModel
from oc_xgb.model_base import PredictionResult, ModelCapabilities

logger = get_logger(__name__)


# 使用装饰器注册模型
# model_type: 模型的唯一标识符
# description: 模型描述
# 其他参数: 模型能力标志
@ColorPredictionModel.register(
    "my_new_model",  # 修改为你的模型类型标识符
    description="新模型描述：基于XXX的颜色预测",
    supports_uncertainty=False,  # 是否支持不确定性估计
    supports_batch_prediction=True,  # 是否支持批量预测
)
class MyNewModel(ColorPredictionModel):
    """我的新颜色预测模型
    
    在这里添加详细的模型描述文档
    
    Attributes:
        model_id: 模型唯一标识
        material_keys: 支持的耗材列表
        n_layers: 层数
        # 添加你的自定义属性
    """

    def __init__(
            self,
            model_id: str,
            material_keys: list[str],
            n_layers: int,
            # 添加你的自定义参数
            my_param: float = 1.0,
    ):
        """初始化模型
        
        Args:
            model_id: 模型唯一标识
            material_keys: 耗材列表
            n_layers: 层数
            my_param: 示例参数
        """
        super().__init__(model_id, material_keys, n_layers)

        # 保存自定义参数
        self.my_param = my_param

        # 设置模型能力
        self._capabilities = ModelCapabilities(
            supports_uncertainty=False,
            supports_batch_prediction=True,
            requires_layer_sequence=True,
            supports_recipe_input=True,
            description="新模型描述：基于XXX的颜色预测",
        )

        # 初始化你的模型组件
        self._init_model()

    def _init_model(self):
        """初始化模型内部组件"""
        # 在这里加载或初始化你的模型
        pass

    def predict_from_sequences(
            self,
            sequences: list[list[str]]
    ) -> PredictionResult:
        """从层序列预测颜色（必须实现）
        
        Args:
            sequences: 层序列列表，每个序列是材质名称的列表
                例如: [["White", "Red", "Red", "Red", "Red"], ...]
                
        Returns:
            PredictionResult: 预测结果，包含:
                - rgb01: (N, 3) RGB值，范围[0, 1]
                - lab: (可选) Lab值
                - confidence: (可选) 置信度
                - metadata: (可选) 额外元数据
        """
        n_samples = len(sequences)

        # TODO: 实现你的预测逻辑
        # 这里只是一个示例，返回灰色
        rgb01 = np.ones((n_samples, 3), dtype=np.float32) * 0.5

        # 返回预测结果
        return PredictionResult(
            rgb01=rgb01,
            lab=None,  # 可选
            confidence=None,  # 可选
            metadata={"my_param_used": self.my_param},  # 可选
        )

    # 可选：覆盖此方法以提供更高效的配方预测
    # def predict_from_recipes(
    #     self,
    #     recipes: list[dict[str, float]]
    # ) -> PredictionResult:
    #     """从配方预测颜色（可选覆盖）"""
    #     # 你的高效实现
    #     pass

    def save(self, out_dir: Path) -> dict[str, Any]:
        """保存模型到目录（必须实现）
        
        Args:
            out_dir: 输出目录路径
            
        Returns:
            dict: 模型元数据，将被写入 color_model.json
                  必须包含 "model_type" 字段
        """
        out_dir.mkdir(parents=True, exist_ok=True)

        # TODO: 保存你的模型参数
        # 示例：保存 NumPy 数组
        model_data = {
            "my_param": np.array([self.my_param], dtype=np.float32),
            # 添加你的模型参数...
        }

        # 保存到文件
        npz_path = out_dir / "my_new_model.npz"
        np.savez_compressed(npz_path, **model_data)

        # 返回元数据
        return {
            "model_type": "my_new_model",  # 必须与注册时一致
            "model_id": self.model_id,
            "material_keys": self.material_keys,
            "n_layers": self.n_layers,
            "files": {
                "model": npz_path.name,
            },
            # 添加其他元数据...
        }

    @classmethod
    def load(cls, model_dir: Path, metadata: dict[str, Any]) -> MyNewModel:
        """从目录加载模型（必须实现）
        
        Args:
            model_dir: 模型目录路径
            metadata: 从 color_model.json 读取的元数据
            
        Returns:
            MyNewModel: 加载的模型实例
        """
        # 加载模型数据
        npz_path = model_dir / metadata["files"]["model"]
        data = np.load(npz_path)

        # 提取参数
        material_keys = metadata["material_keys"]
        n_layers = metadata["n_layers"]
        my_param = float(data["my_param"][0])

        # 创建模型实例
        return cls(
            model_id=metadata.get("model_id", "loaded_model"),
            material_keys=material_keys,
            n_layers=n_layers,
            my_param=my_param,
        )

    # 可选：添加你的自定义方法
    def get_model_info(self) -> dict[str, Any]:
        """获取模型信息（自定义方法示例）"""
        return {
            "model_type": "my_new_model",
            "model_id": self.model_id,
            "material_keys": self.material_keys,
            "n_layers": self.n_layers,
            "my_param": self.my_param,
        }


# 使用示例（可以删除）
if __name__ == "__main__":
    # 创建模型
    model = MyNewModel(
        model_id="test_model",
        material_keys=["White", "Black", "Red", "Green", "Blue"],
        n_layers=5,
        my_param=0.5,
    )

    # 预测
    sequences = [
        ["White"] * 5,
        ["Red"] * 5,
        ["Blue", "Blue", "White", "White", "White"],
    ]
    result = model.predict_from_sequences(sequences)

    logger.info("预测结果 RGB:")
    logger.info(result.rgb01)

    # 列出所有注册的模型
    logger.info("\n已注册的模型:")
    for name, info in ColorPredictionModel.list_registered_models().items():
        logger.info(f"  - {name}: {info}")
