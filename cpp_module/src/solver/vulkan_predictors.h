#pragma once

#include <vector>
#include <cstdint>
#include <string>

namespace opencolor {
namespace solver {

// 前向声明
struct OpticalParams;
struct GPRParams;
struct HillClimbingSolverVulkanState;

// RT Slab Vulkan 预测器内部实现
std::vector<float> predict_rt_slab_vulkan_internal(
    const std::vector<int32_t>& sequences,
    int n_seq,
    int n_layers,
    int num_materials,
    const OpticalParams& optical,
    const std::string& layer_names_order,
    HillClimbingSolverVulkanState* vk_state
);

// GPR Vulkan 预测器内部实现
std::vector<float> predict_gpr_vulkan3_internal(
    const std::vector<float>& X,
    int n_samples,
    HillClimbingSolverVulkanState* vk_state,
    const GPRParams& gL,
    const GPRParams& ga,
    const GPRParams& gb
);

} // namespace solver
} // namespace opencolor
