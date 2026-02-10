#pragma once

/**
 * OpenColor 颜色预测模型模块
 * 
 * 提供统一的模型接口和多种预测模型实现
 */

#include "model_base.h"

namespace opencolor {
namespace models {

/**
 * 初始化模型模块
 * 自动注册所有内置模型
 */
void initialize_models();

/**
 * 获取模块版本信息
 */
const char* get_models_version();

} // namespace models
} // namespace opencolor
