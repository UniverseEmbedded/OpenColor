"""
calib_color_model_fit - 颜色校准模型拟合与预测

提供颜色预测模型的训练、保存、加载和预测功能。
支持多种模型架构，包括物理+GPR模型和自定义模型。

主要接口:
    - ColorPredictionModel: 模型基类
    - create_model_from_checkpoint: 从检查点加载模型
    - train_phys_gpr: 训练物理+GPR模型
    
示例:
    # 加载模型
    from oc_proto.calib_color_model_fit import create_model_from_checkpoint
    model = create_model_from_checkpoint(Path("path/to/model"))
    
    # 预测
    sequences = [["White", "Red", "Red", "Red", "Red"]]
    result = model.predict_from_sequences(sequences)
    logger.info(result.rgb01)
"""

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

# 导入模型实现以触发注册
from . import models  # noqa: F401
from oc_xgb.model_base import (
    ColorPredictionModel,
    PredictionResult,
    ModelCapabilities,
    create_model_from_checkpoint,
)
from oc_xgb.model_io import save_model, load_model
# 保留旧版接口以兼容现有代码
from oc_xgb.xgb_fit import (
    PhysGPRModel,
    OpticalParams,
    GPRModel,
    PhysGPRConfig,
    train_phys_gpr,
    predict_phys_gpr_lab,
    predict_ad_rgb01,
    fit_optical_params,
)

__all__ = [
    # 新接口
    "ColorPredictionModel",
    "PredictionResult",
    "ModelCapabilities",
    "create_model_from_checkpoint",
    # 旧版接口（兼容）
    "PhysGPRModel",
    "OpticalParams",
    "GPRModel",
    "PhysGPRConfig",
    "train_phys_gpr",
    "predict_phys_gpr_lab",
    "predict_ad_rgb01",
    "fit_optical_params",
    "save_model",
    "load_model",
]
