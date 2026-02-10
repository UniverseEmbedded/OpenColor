#include "vulkan_app.h"
#include "vulkan_init.h"
#include "vulkan_helpers.h"

#include <cstdio>
#include <cstdlib>

/**
 * 清理交换链相关资源
 * 包括：帧缓冲区、渲染通道、图像视图、交换链本身
 */
void AppVulkan::cleanup_swapchain()
{
    // 销毁所有帧缓冲区
    for (auto fb : framebuffers) {
        vkDestroyFramebuffer(device, fb, nullptr);
    }
    framebuffers.clear();

    // 销毁渲染通道
    if (render_pass) {
        vkDestroyRenderPass(device, render_pass, nullptr);
        render_pass = VK_NULL_HANDLE;
    }

    // 销毁交换链图像视图
    for (auto v : swapchain_image_views) {
        vkDestroyImageView(device, v, nullptr);
    }
    swapchain_image_views.clear();
    swapchain_images.clear();

    // 销毁交换链
    if (swapchain) {
        vkDestroySwapchainKHR(device, swapchain, nullptr);
        swapchain = VK_NULL_HANDLE;
    }
}

/**
 * 清理所有 Vulkan 资源
 * 按依赖关系的逆序销毁：交换链 -> 描述符池 -> 命令池 -> 同步对象 -> 表面 -> 设备 -> 实例
 */
void AppVulkan::cleanup()
{
    cleanup_swapchain();

    // 销毁 ImGui 描述符池
    if (imgui_descriptor_pool) {
        vkDestroyDescriptorPool(device, imgui_descriptor_pool, nullptr);
        imgui_descriptor_pool = VK_NULL_HANDLE;
    }

    // 销毁命令池
    if (command_pool) {
        vkDestroyCommandPool(device, command_pool, nullptr);
        command_pool = VK_NULL_HANDLE;
    }

    // 销毁每帧的同步对象（信号量和栅栏）
    for (int i = 0; i < MaxFramesInFlight; i++) {
        // 图像获取信号量
        if (image_acquired_semaphores[i]) {
            vkDestroySemaphore(device, image_acquired_semaphores[i], nullptr);
            image_acquired_semaphores[i] = VK_NULL_HANDLE;
        }
        // 渲染完成信号量
        if (render_complete_semaphores[i]) {
            vkDestroySemaphore(device, render_complete_semaphores[i], nullptr);
            render_complete_semaphores[i] = VK_NULL_HANDLE;
        }
        // 飞行中栅栏
        if (in_flight_fences[i]) {
            vkDestroyFence(device, in_flight_fences[i], nullptr);
            in_flight_fences[i] = VK_NULL_HANDLE;
        }
    }

    // 销毁表面
    if (surface) {
        vkDestroySurfaceKHR(instance, surface, nullptr);
        surface = VK_NULL_HANDLE;
    }
    // 销毁逻辑设备
    if (device) {
        vkDestroyDevice(device, nullptr);
        device = VK_NULL_HANDLE;
    }
    // 销毁 Vulkan 实例
    if (instance) {
        vkDestroyInstance(instance, nullptr);
        instance = VK_NULL_HANDLE;
    }
}
