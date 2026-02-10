#include "vulkan_buffer.h"
#include "vulkan_utils.h"
#include <cstring>

namespace opencolor {
namespace solver {

/**
 * 查找符合要求的 Vulkan 内存类型
 *
 * @param phys 物理设备
 * @param type_bits 内存类型位掩码
 * @param props 所需的内存属性标志
 * @return 找到的内存类型索引
 * @throws std::runtime_error 如果未找到合适的内存类型
 */
std::uint32_t find_memory_type(VkPhysicalDevice phys, std::uint32_t type_bits, VkMemoryPropertyFlags props) {
    VkPhysicalDeviceMemoryProperties mem_props{};
    vkGetPhysicalDeviceMemoryProperties(phys, &mem_props);
    for (std::uint32_t i = 0; i < mem_props.memoryTypeCount; i++) {
        if ((type_bits & (1u << i)) && (mem_props.memoryTypes[i].propertyFlags & props) == props) {
            return i;
        }
    }
    throw std::runtime_error("未找到合适的 Vulkan 内存类型");
}

/**
 * 创建 Vulkan 缓冲区
 *
 * @param device 逻辑设备
 * @param phys 物理设备
 * @param size 缓冲区大小
 * @param usage 缓冲区使用标志
 * @return 创建的 VulkanBuffer 对象
 */
VulkanBuffer create_buffer(VkDevice device, VkPhysicalDevice phys, VkDeviceSize size, VkBufferUsageFlags usage) {
    VulkanBuffer buf;
    buf.size = size;

    VkBufferCreateInfo bci{};
    bci.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bci.size = size;
    bci.usage = usage;
    bci.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    vk_check(vkCreateBuffer(device, &bci, nullptr, &buf.buffer), "vkCreateBuffer");

    VkMemoryRequirements req{};
    vkGetBufferMemoryRequirements(device, buf.buffer, &req);

    VkMemoryAllocateInfo mai{};
    mai.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    mai.allocationSize = req.size;
    mai.memoryTypeIndex = find_memory_type(phys, req.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    vk_check(vkAllocateMemory(device, &mai, nullptr, &buf.memory), "vkAllocateMemory");
    vk_check(vkBindBufferMemory(device, buf.buffer, buf.memory, 0), "vkBindBufferMemory");
    return buf;
}

/**
 * 销毁 Vulkan 缓冲区
 *
 * @param device 逻辑设备
 * @param buf 要销毁的 VulkanBuffer 对象
 */
void destroy_buffer(VkDevice device, VulkanBuffer& buf) {
    if (buf.buffer) {
        vkDestroyBuffer(device, buf.buffer, nullptr);
        buf.buffer = VK_NULL_HANDLE;
    }
    if (buf.memory) {
        vkFreeMemory(device, buf.memory, nullptr);
        buf.memory = VK_NULL_HANDLE;
    }
    buf.size = 0;
}

// ScopedVulkanBuffer 实现 - 提供 RAII 管理的 Vulkan 缓冲区
ScopedVulkanBuffer::ScopedVulkanBuffer(VkDevice d, VulkanBuffer b)
    : device(d), buf(b) {}

ScopedVulkanBuffer::ScopedVulkanBuffer(ScopedVulkanBuffer&& other) noexcept {
    device = other.device;
    buf = other.buf;
    other.device = VK_NULL_HANDLE;
    other.buf = VulkanBuffer{};
}

ScopedVulkanBuffer& ScopedVulkanBuffer::operator=(ScopedVulkanBuffer&& other) noexcept {
    if (this == &other) {
        return *this;
    }
    cleanup();
    device = other.device;
    buf = other.buf;
    other.device = VK_NULL_HANDLE;
    other.buf = VulkanBuffer{};
    return *this;
}

ScopedVulkanBuffer::~ScopedVulkanBuffer() {
    cleanup();
}

void ScopedVulkanBuffer::cleanup() {
    if (device && (buf.buffer || buf.memory)) {
        destroy_buffer(device, buf);
    }
    device = VK_NULL_HANDLE;
    buf = VulkanBuffer{};
}

// ScopedCommandBuffer 实现 - 提供 RAII 管理的命令缓冲区
ScopedCommandBuffer::ScopedCommandBuffer(VkDevice d, VkCommandPool p, VkCommandBuffer c)
    : device(d), pool(p), cb(c) {}

ScopedCommandBuffer::ScopedCommandBuffer(ScopedCommandBuffer&& other) noexcept {
    device = other.device;
    pool = other.pool;
    cb = other.cb;
    other.device = VK_NULL_HANDLE;
    other.pool = VK_NULL_HANDLE;
    other.cb = VK_NULL_HANDLE;
}

ScopedCommandBuffer& ScopedCommandBuffer::operator=(ScopedCommandBuffer&& other) noexcept {
    if (this == &other) {
        return *this;
    }
    cleanup();
    device = other.device;
    pool = other.pool;
    cb = other.cb;
    other.device = VK_NULL_HANDLE;
    other.pool = VK_NULL_HANDLE;
    other.cb = VK_NULL_HANDLE;
    return *this;
}

ScopedCommandBuffer::~ScopedCommandBuffer() {
    cleanup();
}

void ScopedCommandBuffer::cleanup() {
    if (device && pool && cb) {
        vkFreeCommandBuffers(device, pool, 1, &cb);
    }
    device = VK_NULL_HANDLE;
    pool = VK_NULL_HANDLE;
    cb = VK_NULL_HANDLE;
}

} // namespace solver
} // namespace opencolor
