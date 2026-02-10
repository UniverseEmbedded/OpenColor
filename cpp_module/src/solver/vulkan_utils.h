#pragma once

#include <vulkan/vulkan.h>
#include <cstdio>
#include <stdexcept>

namespace opencolor {
namespace solver {

// Vulkan 错误检查
inline void vk_check(VkResult res, const char* msg) {
    if (res == VK_SUCCESS) {
        return;
    }
    std::fprintf(stderr, "[错误] Vulkan 调用失败：%s (VkResult=%d)\n", msg, static_cast<int>(res));
    std::fflush(stderr);
    throw std::runtime_error("Vulkan 调用失败");
}

// 格式化秒数为可读字符串
inline std::string format_seconds(double sec) {
    if (sec < 0.0) sec = 0.0;
    auto total = static_cast<long long>(sec + 0.5);
    long long h = total / 3600;
    long long m = (total % 3600) / 60;
    long long s = total % 60;
    char buf[64];
    if (h > 0) {
        std::snprintf(buf, sizeof(buf), "%lld:%02lld:%02lld", h, m, s);
    } else {
        std::snprintf(buf, sizeof(buf), "%02lld:%02lld", m, s);
    }
    return std::string(buf);
}

} // namespace solver
} // namespace opencolor
