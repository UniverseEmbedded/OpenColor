#include "vulkan_recipe_map.h"
#include "vulkan_recipe_map_shader.h"
#include "vulkan_context.h"
#include "vulkan_buffer.h"
#include <cstring>
#include <cstdio>
#include <stdexcept>

namespace opencolor {
namespace solver {

// 推送常量结构
struct RecipeMapPushConstants {
    int n_pixels;
    int n_colors;
    int n_layers;
    int n_slots;
};

VulkanRecipeMapper::VulkanRecipeMapper() {
    init_pipeline();
}

VulkanRecipeMapper::~VulkanRecipeMapper() {
    cleanup();
}

void VulkanRecipeMapper::init_pipeline() {
    if (!is_solver_vulkan_ready()) {
        throw std::runtime_error("Vulkan上下文未初始化");
    }
    
    auto& ctx = get_solver_vulkan_context();
    
    // 编译shader
    auto spv_code = compile_recipe_map_shader();
    
    // 创建shader模块
    VkShaderModuleCreateInfo shader_info{};
    shader_info.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
    shader_info.codeSize = spv_code.size() * sizeof(uint32_t);
    shader_info.pCode = spv_code.data();
    
    VkShaderModule shader_module = VK_NULL_HANDLE;
    VkResult result = vkCreateShaderModule(ctx.device, &shader_info, nullptr, &shader_module);
    if (result != VK_SUCCESS) {
        throw std::runtime_error("创建Recipe Map Shader模块失败");
    }
    
    // 创建描述符集布局
    VkDescriptorSetLayoutBinding bindings[3] = {};
    
    // recipes buffer (readonly)
    bindings[0].binding = 0;
    bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    bindings[0].descriptorCount = 1;
    bindings[0].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    
    // inverse buffer (readonly)
    bindings[1].binding = 1;
    bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    bindings[1].descriptorCount = 1;
    bindings[1].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    
    // output buffer (writeonly)
    bindings[2].binding = 2;
    bindings[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    bindings[2].descriptorCount = 1;
    bindings[2].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    
    VkDescriptorSetLayoutCreateInfo layout_info{};
    layout_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    layout_info.bindingCount = 3;
    layout_info.pBindings = bindings;
    
    result = vkCreateDescriptorSetLayout(ctx.device, &layout_info, nullptr, &desc_layout_);
    if (result != VK_SUCCESS) {
        vkDestroyShaderModule(ctx.device, shader_module, nullptr);
        throw std::runtime_error("创建Recipe Map描述符集布局失败");
    }
    
    // 创建pipeline布局（带推送常量）
    VkPushConstantRange push_range{};
    push_range.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
    push_range.offset = 0;
    push_range.size = sizeof(RecipeMapPushConstants);
    
    VkPipelineLayoutCreateInfo pipeline_layout_info{};
    pipeline_layout_info.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    pipeline_layout_info.setLayoutCount = 1;
    pipeline_layout_info.pSetLayouts = &desc_layout_;
    pipeline_layout_info.pushConstantRangeCount = 1;
    pipeline_layout_info.pPushConstantRanges = &push_range;
    
    result = vkCreatePipelineLayout(ctx.device, &pipeline_layout_info, nullptr, &pipeline_layout_);
    if (result != VK_SUCCESS) {
        vkDestroyDescriptorSetLayout(ctx.device, desc_layout_, nullptr);
        vkDestroyShaderModule(ctx.device, shader_module, nullptr);
        throw std::runtime_error("创建Recipe Map Pipeline布局失败");
    }
    
    // 创建compute pipeline
    VkPipelineShaderStageCreateInfo stage_info{};
    stage_info.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    stage_info.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    stage_info.module = shader_module;
    stage_info.pName = "main";
    
    VkComputePipelineCreateInfo pipeline_info{};
    pipeline_info.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
    pipeline_info.stage = stage_info;
    pipeline_info.layout = pipeline_layout_;
    
    result = vkCreateComputePipelines(ctx.device, VK_NULL_HANDLE, 1, &pipeline_info, nullptr, &pipeline_);
    
    // 销毁shader模块（pipeline创建后不再需要）
    vkDestroyShaderModule(ctx.device, shader_module, nullptr);
    
    if (result != VK_SUCCESS) {
        vkDestroyPipelineLayout(ctx.device, pipeline_layout_, nullptr);
        vkDestroyDescriptorSetLayout(ctx.device, desc_layout_, nullptr);
        throw std::runtime_error("创建Recipe Map Pipeline失败");
    }
    
    // 创建描述符池
    VkDescriptorPoolSize pool_size{};
    pool_size.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    pool_size.descriptorCount = 3;  // 3个buffer
    
    VkDescriptorPoolCreateInfo pool_info{};
    pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    pool_info.maxSets = 1;
    pool_info.poolSizeCount = 1;
    pool_info.pPoolSizes = &pool_size;
    
    result = vkCreateDescriptorPool(ctx.device, &pool_info, nullptr, &descriptor_pool_);
    if (result != VK_SUCCESS) {
        cleanup();
        throw std::runtime_error("创建Recipe Map描述符池失败");
    }
    
    // 分配描述符集
    VkDescriptorSetAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    alloc_info.descriptorPool = descriptor_pool_;
    alloc_info.descriptorSetCount = 1;
    alloc_info.pSetLayouts = &desc_layout_;
    
    result = vkAllocateDescriptorSets(ctx.device, &alloc_info, &descriptor_set_);
    if (result != VK_SUCCESS) {
        cleanup();
        throw std::runtime_error("分配Recipe Map描述符集失败");
    }
    
    initialized_ = true;
}

void VulkanRecipeMapper::cleanup() {
    if (!initialized_) return;
    
    // 检查Vulkan上下文是否仍然有效
    if (!is_solver_vulkan_ready()) {
        initialized_ = false;
        return;
    }
    
    auto& ctx = get_solver_vulkan_context();
    
    // 检查device是否有效
    if (ctx.device == VK_NULL_HANDLE) {
        initialized_ = false;
        return;
    }
    
    if (pipeline_ != VK_NULL_HANDLE) {
        vkDestroyPipeline(ctx.device, pipeline_, nullptr);
        pipeline_ = VK_NULL_HANDLE;
    }
    if (pipeline_layout_ != VK_NULL_HANDLE) {
        vkDestroyPipelineLayout(ctx.device, pipeline_layout_, nullptr);
        pipeline_layout_ = VK_NULL_HANDLE;
    }
    if (descriptor_pool_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorPool(ctx.device, descriptor_pool_, nullptr);
        descriptor_pool_ = VK_NULL_HANDLE;
    }
    if (desc_layout_ != VK_NULL_HANDLE) {
        vkDestroyDescriptorSetLayout(ctx.device, desc_layout_, nullptr);
        desc_layout_ = VK_NULL_HANDLE;
    }
    
    initialized_ = false;
}

// 辅助函数：复制数据到buffer
static void copy_to_buffer(VkDevice device, VulkanBuffer& buf, const void* data, size_t size) {
    void* mapped = nullptr;
    vkMapMemory(device, buf.memory, 0, size, 0, &mapped);
    std::memcpy(mapped, data, size);
    vkUnmapMemory(device, buf.memory);
}

// 辅助函数：从buffer复制数据
static void copy_from_buffer(VkDevice device, VulkanBuffer& buf, void* data, size_t size) {
    void* mapped = nullptr;
    vkMapMemory(device, buf.memory, 0, size, 0, &mapped);
    std::memcpy(data, mapped, size);
    vkUnmapMemory(device, buf.memory);
}

void VulkanRecipeMapper::map_recipes(
    const int32_t* recipes,
    const int32_t* inverse,
    int32_t* output,
    int n_pixels,
    int n_colors,
    int n_layers,
    int n_slots
) {
    if (!initialized_) {
        throw std::runtime_error("VulkanRecipeMapper未初始化");
    }
    
    auto& ctx = get_solver_vulkan_context();
    
    // 计算buffer大小
    size_t recipes_size = n_pixels * n_layers * sizeof(int32_t);
    size_t inverse_size = n_pixels * sizeof(int32_t);
    size_t output_size = n_colors * n_layers * sizeof(int32_t);
    
    // 创建staging buffer和device buffer
    ScopedVulkanBuffer recipes_staging(ctx.device, 
        create_buffer(ctx.device, ctx.physical_device, recipes_size, 
                      VK_BUFFER_USAGE_TRANSFER_SRC_BIT));
    ScopedVulkanBuffer recipes_device(ctx.device,
        create_buffer(ctx.device, ctx.physical_device, recipes_size,
                      VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT));
    
    ScopedVulkanBuffer inverse_staging(ctx.device,
        create_buffer(ctx.device, ctx.physical_device, inverse_size,
                      VK_BUFFER_USAGE_TRANSFER_SRC_BIT));
    ScopedVulkanBuffer inverse_device(ctx.device,
        create_buffer(ctx.device, ctx.physical_device, inverse_size,
                      VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT));
    
    ScopedVulkanBuffer output_device(ctx.device,
        create_buffer(ctx.device, ctx.physical_device, output_size,
                      VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT));
    ScopedVulkanBuffer output_staging(ctx.device,
        create_buffer(ctx.device, ctx.physical_device, output_size,
                      VK_BUFFER_USAGE_TRANSFER_DST_BIT));
    
    // 复制数据到staging buffer
    copy_to_buffer(ctx.device, recipes_staging.buf, recipes, recipes_size);
    copy_to_buffer(ctx.device, inverse_staging.buf, inverse, inverse_size);
    
    // 创建命令缓冲区
    VkCommandBufferAllocateInfo cmd_alloc{};
    cmd_alloc.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cmd_alloc.commandPool = ctx.command_pool;
    cmd_alloc.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cmd_alloc.commandBufferCount = 1;
    
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    vkAllocateCommandBuffers(ctx.device, &cmd_alloc, &cmd);
    
    // 开始记录命令
    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    vkBeginCommandBuffer(cmd, &begin_info);
    
    // 复制数据到device buffer
    VkBufferCopy copy_region{};
    copy_region.size = recipes_size;
    vkCmdCopyBuffer(cmd, recipes_staging.buf.buffer, recipes_device.buf.buffer, 1, &copy_region);
    
    copy_region.size = inverse_size;
    vkCmdCopyBuffer(cmd, inverse_staging.buf.buffer, inverse_device.buf.buffer, 1, &copy_region);
    
    // 内存屏障确保复制完成
    VkMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         0, 1, &barrier, 0, nullptr, 0, nullptr);
    
    // 绑定pipeline和描述符集
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline_);
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline_layout_,
                            0, 1, &descriptor_set_, 0, nullptr);
    
    // 更新描述符集
    VkDescriptorBufferInfo recipes_info{};
    recipes_info.buffer = recipes_device.buf.buffer;
    recipes_info.offset = 0;
    recipes_info.range = recipes_size;
    
    VkDescriptorBufferInfo inverse_info{};
    inverse_info.buffer = inverse_device.buf.buffer;
    inverse_info.offset = 0;
    inverse_info.range = inverse_size;
    
    VkDescriptorBufferInfo output_info{};
    output_info.buffer = output_device.buf.buffer;
    output_info.offset = 0;
    output_info.range = output_size;
    
    VkWriteDescriptorSet writes[3] = {};
    
    writes[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[0].dstSet = descriptor_set_;
    writes[0].dstBinding = 0;
    writes[0].descriptorCount = 1;
    writes[0].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[0].pBufferInfo = &recipes_info;
    
    writes[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[1].dstSet = descriptor_set_;
    writes[1].dstBinding = 1;
    writes[1].descriptorCount = 1;
    writes[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[1].pBufferInfo = &inverse_info;
    
    writes[2].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    writes[2].dstSet = descriptor_set_;
    writes[2].dstBinding = 2;
    writes[2].descriptorCount = 1;
    writes[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    writes[2].pBufferInfo = &output_info;
    
    vkUpdateDescriptorSets(ctx.device, 3, writes, 0, nullptr);
    
    // 推送常量
    RecipeMapPushConstants push{};
    push.n_pixels = n_pixels;
    push.n_colors = n_colors;
    push.n_layers = n_layers;
    push.n_slots = n_slots;
    vkCmdPushConstants(cmd, pipeline_layout_, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(push), &push);
    
    // 调度compute shader
    uint32_t group_count = (n_colors + 255) / 256;
    vkCmdDispatch(cmd, group_count, 1, 1);
    
    // 内存屏障确保shader写入完成
    barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
                         0, 1, &barrier, 0, nullptr, 0, nullptr);
    
    // 复制结果回staging buffer
    copy_region.size = output_size;
    vkCmdCopyBuffer(cmd, output_device.buf.buffer, output_staging.buf.buffer, 1, &copy_region);
    
    // 结束命令记录
    vkEndCommandBuffer(cmd);
    
    // 提交命令
    VkSubmitInfo submit_info{};
    submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit_info.commandBufferCount = 1;
    submit_info.pCommandBuffers = &cmd;
    
    VkFenceCreateInfo fence_info{};
    fence_info.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
    VkFence fence = VK_NULL_HANDLE;
    vkCreateFence(ctx.device, &fence_info, nullptr, &fence);
    
    vkQueueSubmit(ctx.queue, 1, &submit_info, fence);
    vkWaitForFences(ctx.device, 1, &fence, VK_TRUE, UINT64_MAX);
    
    // 复制结果到输出
    copy_from_buffer(ctx.device, output_staging.buf, output, output_size);
    
    // 清理
    vkDestroyFence(ctx.device, fence, nullptr);
    vkFreeCommandBuffers(ctx.device, ctx.command_pool, 1, &cmd);
}

} // namespace solver
} // namespace opencolor
