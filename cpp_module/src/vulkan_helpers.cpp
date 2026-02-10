/**
 * @file vulkan_helpers.cpp
 * @brief Vulkan 辅助工具函数
 *
 * 提供 Vulkan 错误检查和计时工具函数
 */

#include "vulkan_helpers.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>

/**
 * @brief 检查 Vulkan 调用结果，出错时输出错误信息并终止程序
 * @param err Vulkan 调用返回的结果码
 * @param what 发生错误时的描述信息
 */
void vk_check(VkResult err, const char* what)
{
    if (err == VK_SUCCESS) {
        return;
    }
    std::fprintf(stderr, "[错误] Vulkan 调用失败：%s (VkResult=%d)\n", what, static_cast<int>(err));
    std::fflush(stderr);
    std::abort();
}

/**
 * @brief 获取当前时间戳（毫秒）
 * @return 自系统启动以来的毫秒数
 */
std::uint64_t now_ms()
{
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}
