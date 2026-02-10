#pragma once

#include <vulkan/vulkan.h>
#include <cstdint>
#include <mutex>
#include <atomic>
#include "vulkan_buffer.h"

namespace opencolor {
namespace solver {

// 求解器 Vulkan 上下文结构
struct SolverVulkanContext {
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical_device = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkQueue queue = VK_NULL_HANDLE;
    std::uint32_t queue_family = 0;
    VkCommandPool command_pool = VK_NULL_HANDLE;
    
    // RT slab pipeline
    VkDescriptorSetLayout desc_layout = VK_NULL_HANDLE;
    VkPipelineLayout pipeline_layout = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
    VkDescriptorPool descriptor_pool = VK_NULL_HANDLE;
    VkDescriptorSet descriptor_set = VK_NULL_HANDLE;
    
    // GPR pipeline
    VkDescriptorSetLayout gpr_desc_layout = VK_NULL_HANDLE;
    VkPipelineLayout gpr_pipeline_layout = VK_NULL_HANDLE;
    VkPipeline gpr_pipeline = VK_NULL_HANDLE;
    VkDescriptorPool gpr_descriptor_pool = VK_NULL_HANDLE;
    VkDescriptorSet gpr_descriptor_set = VK_NULL_HANDLE;
};

// 获取全局 Vulkan 上下文
SolverVulkanContext& get_solver_vulkan_context();

// 获取全局 Vulkan 互斥锁
std::mutex& get_solver_vulkan_mutex();

// 获取 Vulkan 就绪状态
bool is_solver_vulkan_ready();

// 获取 Vulkan 用户计数
std::atomic<int>& get_solver_vulkan_users();

// 初始化求解器 Vulkan 上下文
void init_solver_vulkan_context();

// 销毁求解器 Vulkan 上下文
void destroy_solver_vulkan_context();

// HillClimbingSolver 的 Vulkan 状态
struct HillClimbingSolverVulkanState {
    // RT slab 数据
    VulkanBuffer alpha;
    VulkanBuffer beta;
    VulkanBuffer gamma;
    std::size_t alpha_bytes = 0;
    std::size_t beta_bytes = 0;
    std::size_t gamma_bytes = 0;
    std::uint32_t num_mats = 0;
    bool uploaded_rts = false;
    
    // GPR 数据
    VulkanBuffer gpr_X_train;
    VulkanBuffer gpr_alpha_L;
    VulkanBuffer gpr_alpha_a;
    VulkanBuffer gpr_alpha_b;
    std::size_t gpr_X_train_bytes = 0;
    std::size_t gpr_alpha_bytes = 0;
    std::uint32_t gpr_n_train = 0;
    std::uint32_t gpr_n_features = 0;
    bool uploaded_gpr = false;
    
    ~HillClimbingSolverVulkanState();
};

} // namespace solver
} // namespace opencolor
