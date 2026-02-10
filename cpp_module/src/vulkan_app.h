#pragma once

// 导入标准整数类型
#include <cstdint>
// 导入标准向量容器
#include <vector>

// 导入 Vulkan 头文件
#include <vulkan/vulkan.h>

// Vulkan 应用结构体
struct AppVulkan
{
    // Vulkan 实例
    VkInstance instance{};
    // 物理设备
    VkPhysicalDevice physical_device{};
    // 逻辑设备
    VkDevice device{};
    // 队列族索引
    std::uint32_t queue_family = 0;
    // 队列
    VkQueue queue{};

    // Vulkan 表面
    VkSurfaceKHR surface{};
    // 交换链
    VkSwapchainKHR swapchain{};
    // 交换链格式
    VkFormat swapchain_format = VK_FORMAT_UNDEFINED;
    // 交换链尺寸
    VkExtent2D swapchain_extent{};
    // 交换链图像向量
    std::vector<VkImage> swapchain_images;
    // 交换链图像视图向量
    std::vector<VkImageView> swapchain_image_views;
    // 渲染通道
    VkRenderPass render_pass{};
    // 帧缓冲区向量
    std::vector<VkFramebuffer> framebuffers;

    // 命令池
    VkCommandPool command_pool{};
    // 命令缓冲区向量
    std::vector<VkCommandBuffer> command_buffers;

    // ImGui 描述符池
    VkDescriptorPool imgui_descriptor_pool{};

    // 最大飞行帧数
    static constexpr int MaxFramesInFlight = 2;
    // 图像获取信号量数组
    VkSemaphore image_acquired_semaphores[MaxFramesInFlight]{};
    // 渲染完成信号量数组
    VkSemaphore render_complete_semaphores[MaxFramesInFlight]{};
    // 飞行栅栏数组
    VkFence in_flight_fences[MaxFramesInFlight]{};
    // 当前帧索引
    int frame_index = 0;

    // 清理交换链
    void cleanup_swapchain();
    // 清理所有资源
    void cleanup();
};

// 选择表面格式
VkFormat choose_surface_format(const std::vector<VkSurfaceFormatKHR>& formats);

// 选择呈现模式
VkPresentModeKHR choose_present_mode(const std::vector<VkPresentModeKHR>& modes);

// 限制范围
VkExtent2D clamp_extent(const VkSurfaceCapabilitiesKHR& caps, std::uint32_t w, std::uint32_t h);

// 创建 Vulkan 实例
void create_instance(AppVulkan& app);

// 创建 Vulkan 表面
void create_surface(AppVulkan& app);

// 选择物理设备和队列
void pick_physical_device_and_queue(AppVulkan& app);

// 创建逻辑设备
void create_device(AppVulkan& app);

// 创建交换链
void create_swapchain(AppVulkan& app);

// 创建渲染通道
void create_render_pass(AppVulkan& app);

// 创建帧缓冲区
void create_framebuffers(AppVulkan& app);

// 创建命令池和缓冲区
void create_command_pool_and_buffers(AppVulkan& app);

// 创建同步对象
void create_sync_objects(AppVulkan& app);

// 创建 ImGui 描述符池
void create_imgui_descriptor_pool(AppVulkan& app);

// 开始一次性命令
VkCommandBuffer begin_one_time_commands(AppVulkan& app);

// 结束一次性命令
void end_one_time_commands(AppVulkan& app, VkCommandBuffer cmd);
