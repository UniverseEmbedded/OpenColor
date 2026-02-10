#pragma once

#include "vulkan_app.h"
#include "vulkan_helpers.h"

#include <vector>
#include <cstdio>
#include <cstdlib>

/**
 * 从可用格式中选择合适的表面格式
 * @param formats 可用的表面格式列表
 * @return 选定的表面格式
 */
VkFormat choose_surface_format(const std::vector<VkSurfaceFormatKHR>& formats);

/**
 * 从可用模式中选择合适的呈现模式
 * @param modes 可用的呈现模式列表
 * @return 选定的呈现模式
 */
VkPresentModeKHR choose_present_mode(const std::vector<VkPresentModeKHR>& modes);

/**
 * 将请求的扩展限制在表面能力范围内
 * @param caps 表面能力
 * @param w 请求的宽度
 * @param h 请求的高度
 * @return 限制后的扩展
 */
VkExtent2D clamp_extent(const VkSurfaceCapabilitiesKHR& caps, std::uint32_t w, std::uint32_t h);

/**
 * 创建 Vulkan 实例
 * @param app Vulkan 应用对象
 */
void create_instance(AppVulkan& app);

/**
 * 创建窗口表面
 * @param app Vulkan 应用对象
 */
void create_surface(AppVulkan& app);

/**
 * 选择物理设备和队列族
 * @param app Vulkan 应用对象
 */
void pick_physical_device_and_queue(AppVulkan& app);

/**
 * 创建逻辑设备
 * @param app Vulkan 应用对象
 */
void create_device(AppVulkan& app);

/**
 * 创建交换链
 * @param app Vulkan 应用对象
 */
void create_swapchain(AppVulkan& app);

/**
 * 创建渲染通道
 * @param app Vulkan 应用对象
 */
void create_render_pass(AppVulkan& app);

/**
 * 创建帧缓冲区
 * @param app Vulkan 应用对象
 */
void create_framebuffers(AppVulkan& app);

/**
 * 创建命令池和命令缓冲区
 * @param app Vulkan 应用对象
 */
void create_command_pool_and_buffers(AppVulkan& app);

/**
 * 创建同步对象（信号量和栅栏）
 * @param app Vulkan 应用对象
 */
void create_sync_objects(AppVulkan& app);

/**
 * 创建 ImGui 描述符池
 * @param app Vulkan 应用对象
 */
void create_imgui_descriptor_pool(AppVulkan& app);

/**
 * 开始一次性命令缓冲区记录
 * @param app Vulkan 应用对象
 * @return 命令缓冲区
 */
VkCommandBuffer begin_one_time_commands(AppVulkan& app);

/**
 * 结束并提交一次性命令缓冲区
 * @param app Vulkan 应用对象
 * @param cmd 命令缓冲区
 */
void end_one_time_commands(AppVulkan& app, VkCommandBuffer cmd);
