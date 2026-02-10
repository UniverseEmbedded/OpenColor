#pragma once

// 导入标准整数类型
#include <cstdint>

// 导入 Vulkan 核心头文件
#include <vulkan/vulkan.h>

// 检查 Vulkan 结果并处理错误
void vk_check(VkResult err, const char* what);

// 获取当前时间（毫秒）
std::uint64_t now_ms();
