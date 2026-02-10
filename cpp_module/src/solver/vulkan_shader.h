/**
 * @file vulkan_shader.h
 * @brief Vulkan Shader 编译接口
 *
 * 提供 RT slab shader 和 GPR shader 的编译功能
 */

#pragma once

#include <vector>
#include <cstdint>

namespace opencolor {
namespace solver {

/**
 * @brief 编译 RT slab shader
 * @return 编译后的 SPIR-V 字节码
 */
std::vector<std::uint32_t> compile_rt_slab_shader();

/**
 * @brief 编译 GPR shader
 * @return 编译后的 SPIR-V 字节码
 */
std::vector<std::uint32_t> compile_gpr_shader();

} // namespace solver
} // namespace opencolor
