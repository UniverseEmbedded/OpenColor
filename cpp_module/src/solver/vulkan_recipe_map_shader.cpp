#include "vulkan_recipe_map_shader.h"
#include <shaderc/shaderc.hpp>
#include <stdexcept>
#include <cstdio>

namespace opencolor {
namespace solver {

/**
 * 编译配方映射着色器
 * 用于将像素级配方映射回唯一颜色级配方（众数统计）
 */
std::vector<std::uint32_t> compile_recipe_map_shader() {
    const char* shader_src = R"glsl(
#version 450
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

// 输入：像素级配方 (n_pixels, n_layers)
layout(set = 0, binding = 0) readonly buffer Recipes {
    int recipes[];  // 扁平化数组，shape: (n_pixels, n_layers)
};

// 输入：像素到颜色的映射
layout(set = 0, binding = 1) readonly buffer Inverse {
    int inverse[];  // shape: (n_pixels,)，每个像素对应的颜色ID
};

// 输出：颜色级配方 (n_colors, n_layers)
layout(set = 0, binding = 2) writeonly buffer OutputDigits {
    int recipe_digits[];  // 扁平化数组，shape: (n_colors, n_layers)
};

// 推送常量
layout(push_constant) uniform Push {
    int n_pixels;     // 像素总数
    int n_colors;     // 颜色总数
    int n_layers;     // 层数（通常为5）
    int n_slots;      // slot数量（通常为8）
} pc;

// 共享内存：用于workgroup内的局部直方图统计
shared int shared_hist[256][8];  // 最大256线程 × 8个slot

void main() {
    int color_id = int(gl_GlobalInvocationID.x);
    int local_id = int(gl_LocalInvocationID.x);
    
    // 检查边界
    if (color_id >= pc.n_colors) {
        return;
    }
    
    // 初始化共享内存直方图
    for (int s = 0; s < pc.n_slots; s++) {
        shared_hist[local_id][s] = 0;
    }
    
    barrier();
    
    // 第一层遍历：统计该颜色的所有像素
    // 每个线程处理部分像素，使用stride方式
    for (int k = local_id; k < pc.n_pixels; k += 256) {
        if (inverse[k] == color_id) {
            // 统计该像素的所有层
            for (int z = 0; z < pc.n_layers; z++) {
                int slot = recipes[k * pc.n_layers + z];
                if (slot >= 0 && slot < pc.n_slots) {
                    atomicAdd(shared_hist[local_id][slot], 1);
                }
            }
        }
    }
    
    barrier();
    
    // 归约：将所有线程的直方图合并到线程0
    if (local_id == 0) {
        int final_hist[8];
        for (int s = 0; s < pc.n_slots; s++) {
            final_hist[s] = 0;
        }
        
        // 累加所有线程的直方图
        for (int t = 0; t < 256; t++) {
            for (int s = 0; s < pc.n_slots; s++) {
                final_hist[s] += shared_hist[t][s];
            }
        }
        
        // 取众数并写入输出
        for (int z = 0; z < pc.n_layers; z++) {
            int max_count = -1;
            int max_slot = 0;
            
            // 重新统计该层的众数
            // 注意：上面的直方图是所有层的总和，需要重新按层统计
            int layer_hist[8];
            for (int s = 0; s < pc.n_slots; s++) {
                layer_hist[s] = 0;
            }
            
            // 重新遍历所有像素，只统计当前层
            for (int k = 0; k < pc.n_pixels; k++) {
                if (inverse[k] == color_id) {
                    int slot = recipes[k * pc.n_layers + z];
                    if (slot >= 0 && slot < pc.n_slots) {
                        layer_hist[slot]++;
                    }
                }
            }
            
            // 找众数
            for (int s = 0; s < pc.n_slots; s++) {
                if (layer_hist[s] > max_count) {
                    max_count = layer_hist[s];
                    max_slot = s;
                }
            }
            
            recipe_digits[color_id * pc.n_layers + z] = max_slot;
        }
    }
}
)glsl";

    shaderc::Compiler compiler;
    shaderc::CompileOptions options;
    options.SetTargetEnvironment(shaderc_target_env_vulkan, shaderc_env_version_vulkan_1_1);
    options.SetOptimizationLevel(shaderc_optimization_level_performance);

    shaderc::SpvCompilationResult result = compiler.CompileGlslToSpv(
        shader_src, shaderc_compute_shader, "recipe_map.comp", options
    );
    if (result.GetCompilationStatus() != shaderc_compilation_status_success) {
        std::string msg = result.GetErrorMessage();
        std::fprintf(stderr, "[错误] Recipe Map Shader 编译失败：%s\n", msg.c_str());
        std::fflush(stderr);
        throw std::runtime_error("Recipe Map Shader 编译失败");
    }

    return std::vector<std::uint32_t>(result.cbegin(), result.cend());
}

} // namespace solver
} // namespace opencolor
