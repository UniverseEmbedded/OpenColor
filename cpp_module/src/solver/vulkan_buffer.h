#pragma once

#include <vulkan/vulkan.h>
#include <cstdint>
#include <cstdio>
#include <stdexcept>

namespace opencolor {
namespace solver {

// Vulkan 缓冲区结构
struct VulkanBuffer {
    VkBuffer buffer = VK_NULL_HANDLE;
    VkDeviceMemory memory = VK_NULL_HANDLE;
    VkDeviceSize size = 0;
};

// 查找 Vulkan 内存类型
std::uint32_t find_memory_type(VkPhysicalDevice phys, std::uint32_t type_bits, VkMemoryPropertyFlags props);

// 创建 Vulkan 缓冲区
VulkanBuffer create_buffer(VkDevice device, VkPhysicalDevice phys, VkDeviceSize size, VkBufferUsageFlags usage);

// 销毁 Vulkan 缓冲区
void destroy_buffer(VkDevice device, VulkanBuffer& buf);

// RAII 封装的 Vulkan 缓冲区
struct ScopedVulkanBuffer {
    VkDevice device = VK_NULL_HANDLE;
    VulkanBuffer buf;

    ScopedVulkanBuffer() = default;
    ScopedVulkanBuffer(VkDevice d, VulkanBuffer b);
    
    ScopedVulkanBuffer(const ScopedVulkanBuffer&) = delete;
    ScopedVulkanBuffer& operator=(const ScopedVulkanBuffer&) = delete;
    
    ScopedVulkanBuffer(ScopedVulkanBuffer&& other) noexcept;
    ScopedVulkanBuffer& operator=(ScopedVulkanBuffer&& other) noexcept;
    
    ~ScopedVulkanBuffer();
    
    void cleanup();
};

// RAII 封装的命令缓冲区
struct ScopedCommandBuffer {
    VkDevice device = VK_NULL_HANDLE;
    VkCommandPool pool = VK_NULL_HANDLE;
    VkCommandBuffer cb = VK_NULL_HANDLE;

    ScopedCommandBuffer() = default;
    ScopedCommandBuffer(VkDevice d, VkCommandPool p, VkCommandBuffer c);
    
    ScopedCommandBuffer(const ScopedCommandBuffer&) = delete;
    ScopedCommandBuffer& operator=(const ScopedCommandBuffer&) = delete;
    
    ScopedCommandBuffer(ScopedCommandBuffer&& other) noexcept;
    ScopedCommandBuffer& operator=(ScopedCommandBuffer&& other) noexcept;
    
    ~ScopedCommandBuffer();
    
    void cleanup();
};

} // namespace solver
} // namespace opencolor
