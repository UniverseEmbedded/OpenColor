"""
模型模块
包含所有颜色预测模型的实现
"""

# 导入具体模型实现（这会触发注册）
from .phys_gpr_model import PhysGPRModelImpl

# 导入基类
from oc_xgb.model_base import (
    ColorPredictionModel,
    PredictionResult,
    ModelCapabilities,
    create_model_from_checkpoint,
)

__all__ = [
    "ColorPredictionModel",
    "PredictionResult",
    "ModelCapabilities",
    "create_model_from_checkpoint",
    "PhysGPRModelImpl",
]
