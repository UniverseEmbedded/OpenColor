#pragma once

#include <vector>
#include <cstdint>

namespace opencolor {
namespace solver {

/**
 * 编译配方映射着色器
 * 用于将像素级配方映射回唯一颜色级配方（众数统计）
 * 
 * @return SPIR-V字节码
 */
std::vector<std::uint32_t> compile_recipe_map_shader();

} // namespace solver
} // namespace opencolor
