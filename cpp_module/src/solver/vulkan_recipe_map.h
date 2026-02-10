#pragma once

#include <vulkan/vulkan.h>
#include <cstdint>

namespace opencolor {
namespace solver {

/**
 * Vulkan GPU配方映射器
 * 用于将像素级配方映射回唯一颜色级配方（众数统计）
 */
class VulkanRecipeMapper {
public:
    VulkanRecipeMapper();
    ~VulkanRecipeMapper();
    
    // 禁止拷贝
    VulkanRecipeMapper(const VulkanRecipeMapper&) = delete;
    VulkanRecipeMapper& operator=(const VulkanRecipeMapper&) = delete;
    
    /**
     * 执行配方映射
     * 
     * @param recipes 像素级配方数组，shape: (n_pixels, n_layers)
     * @param inverse 像素到颜色的映射，shape: (n_pixels,)
     * @param output 输出颜色级配方数组，shape: (n_colors, n_layers)
     * @param n_pixels 像素总数
     * @param n_colors 颜色总数
     * @param n_layers 层数
     * @param n_slots slot数量
     */
    void map_recipes(
        const int32_t* recipes,
        const int32_t* inverse,
        int32_t* output,
        int n_pixels,
        int n_colors,
        int n_layers,
        int n_slots
    );
    
    bool is_initialized() const { return initialized_; }

private:
    void init_pipeline();
    void cleanup();
    
    bool initialized_ = false;
    
    // Vulkan对象
    VkDescriptorSetLayout desc_layout_ = VK_NULL_HANDLE;
    VkPipelineLayout pipeline_layout_ = VK_NULL_HANDLE;
    VkPipeline pipeline_ = VK_NULL_HANDLE;
    VkDescriptorPool descriptor_pool_ = VK_NULL_HANDLE;
    VkDescriptorSet descriptor_set_ = VK_NULL_HANDLE;
};

} // namespace solver
} // namespace opencolor
