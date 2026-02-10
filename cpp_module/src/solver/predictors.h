/**
 * @file predictors.h
 * @brief 预测器函数声明
 *
 * 提供 Four-flux、RT slab、GPR 等模型的 CPU 和 Vulkan GPU 预测接口
 */

#pragma once

#include "hill_climbing_solver.h"
#include <vector>
#include <cstdint>

namespace opencolor {
namespace solver {

/**
 * @brief Four-flux 预测（CPU 版本）
 * @param sequences 材料序列索引数组
 * @param n_seq 序列数量
 * @param n_layers 层数
 * @param num_materials 材料数量
 * @param optical 光学参数
 * @return 预测结果数组
 */
std::vector<float> predict_four_flux(
    const std::vector<int32_t>& sequences,
    int n_seq,
    int n_layers,
    int num_materials,
    const OpticalParams& optical
);

/**
 * @brief Four-flux 预测（Vulkan GPU 版本）
 * @param sequences 材料序列索引数组
 * @param n_seq 序列数量
 * @param vk_state Vulkan 状态对象
 * @param optical 光学参数
 * @param n_layers 层数
 * @param num_materials 材料数量
 * @return 预测结果数组
 */
std::vector<float> predict_four_flux_vulkan(
    const std::vector<int32_t>& sequences,
    int n_seq,
    HillClimbingSolverVulkanState* vk_state,
    const OpticalParams& optical,
    int n_layers,
    int num_materials
);

/**
 * @brief RT slab 预测（CPU 版本）
 * @param sequences 材料序列索引数组
 * @param n_seq 序列数量
 * @param n_layers 层数
 * @param num_materials 材料数量
 * @param optical 光学参数
 * @param layer_names_order 层名称顺序
 * @return 预测结果数组
 */
std::vector<float> predict_rt_slab(
    const std::vector<int32_t>& sequences,
    int n_seq,
    int n_layers,
    int num_materials,
    const OpticalParams& optical,
    const std::string& layer_names_order
);

/**
 * @brief RT slab 预测（Vulkan GPU 版本）
 * @param sequences 材料序列索引数组
 * @param n_seq 序列数量
 * @param n_layers 层数
 * @param num_materials 材料数量
 * @param optical 光学参数
 * @param layer_names_order 层名称顺序
 * @param vk_state Vulkan 状态对象引用
 * @return 预测结果数组
 */
std::vector<float> predict_rt_slab_vulkan(
    const std::vector<int32_t>& sequences,
    int n_seq,
    int n_layers,
    int num_materials,
    const OpticalParams& optical,
    const std::string& layer_names_order,
    HillClimbingSolverVulkanState*& vk_state
);

/**
 * @brief GPR 特征构建
 * @param recipe_indices 配方索引数组
 * @param n_samples 样本数量
 * @param n_layers 层数
 * @param num_materials 材料数量
 * @param base_lab 基础 Lab 颜色值
 * @param optical 光学参数
 * @param layer_names_order 层名称顺序
 * @return 构建的特征数组
 */
std::vector<float> build_gpr_features(
    const std::vector<int32_t>& recipe_indices,
    int n_samples,
    int n_layers,
    int num_materials,
    const std::vector<float>& base_lab,
    const OpticalParams& optical,
    const std::string& layer_names_order
);

/**
 * @brief GPR 预测（Vulkan GPU 版本）
 * @param X 特征数组
 * @param n_samples 样本数量
 * @param vk_state Vulkan 状态对象
 * @param gL L 通道的 GPR 参数
 * @param ga a 通道的 GPR 参数
 * @param gb b 通道的 GPR 参数
 * @return 预测结果数组
 */
std::vector<float> predict_gpr_vulkan3(
    const std::vector<float>& X,
    int n_samples,
    HillClimbingSolverVulkanState* vk_state,
    const GPRParams& gL,
    const GPRParams& ga,
    const GPRParams& gb
);

/**
 * @brief GPR 预测（CPU 版本）
 * @param gpr GPR 参数
 * @param X 特征数组
 * @return 预测结果数组
 */
std::vector<float> predict_gpr(const GPRParams& gpr, const std::vector<float>& X);

} // namespace solver
} // namespace opencolor
