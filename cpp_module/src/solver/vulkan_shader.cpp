#include "vulkan_shader.h"
#include <shaderc/shaderc.hpp>
#include <stdexcept>
#include <cstdio>

namespace opencolor {
namespace solver {

/**
 * 编译实时 slab 着色器
 * 用于计算多层材料叠加后的 RGB 输出
 */
std::vector<std::uint32_t> compile_rt_slab_shader() {
    const char* shader_src = R"glsl(
#version 450
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0) readonly buffer Alpha { float alpha[]; };
layout(set = 0, binding = 1) readonly buffer Beta { float beta[]; };
layout(set = 0, binding = 2) readonly buffer Gamma { float gamma_rb[]; };
layout(set = 0, binding = 3) readonly buffer Seq { int seq_indices[]; };
layout(set = 0, binding = 4) writeonly buffer OutRgb { float out_rgb[]; };

layout(push_constant) uniform Push {
    uint num_seq;
    uint n_layers;
    uint layer_order;
    uint num_mats;
    float pad0;
    float pad1;
    float pad2;
} pc;

float clampf(float v, float lo, float hi)
{
    return min(max(v, lo), hi);
}

float sigmoidf(float x)
{
    x = clampf(x, -20.0, 20.0);
    return 1.0 / (1.0 + exp(-x));
}

float linear_to_srgb(float x)
{
    if (x <= 0.0031308) {
        return 12.92 * x;
    }
    return 1.055 * pow(max(x, 0.0), 1.0 / 2.4) - 0.055;
}

void main()
{
    uint idx = gl_GlobalInvocationID.x;
    uint total = pc.num_seq * 3u;
    if (idx >= total) {
        return;
    }

    uint seq = idx / 3u;
    uint ch = idx - seq * 3u;

    float rb = sigmoidf(gamma_rb[int(ch)]);
    float R = rb;
    for (uint l = 0u; l < pc.n_layers; ++l) {
        uint li = (pc.layer_order == 0u) ? (pc.n_layers - 1u - l) : l;
        int mat = seq_indices[int(seq * pc.n_layers + li)];
        if (mat < 0 || uint(mat) >= pc.num_mats) {
            continue;
        }
        uint base = uint(mat) * 3u + ch;
        float r = sigmoidf(alpha[base]);
        float t = sigmoidf(beta[base]) * (1.0 - r);
        float denom = 1.0 - r * R;
        if (abs(denom) < 1e-6) {
            denom = (denom < 0.0) ? -1e-6 : 1e-6;
        }
        R = r + (t * t) * R / denom;
    }

    float srgb = linear_to_srgb(R);
    srgb = clampf(srgb, 0.0, 1.0);
    out_rgb[idx] = srgb;
}
)glsl";

    shaderc::Compiler compiler;
    shaderc::CompileOptions options;
    options.SetTargetEnvironment(shaderc_target_env_vulkan, shaderc_env_version_vulkan_1_1);
    options.SetOptimizationLevel(shaderc_optimization_level_performance);

    shaderc::SpvCompilationResult result = compiler.CompileGlslToSpv(
        shader_src, shaderc_compute_shader, "solver_rt_slab.comp", options
    );
    if (result.GetCompilationStatus() != shaderc_compilation_status_success) {
        std::string msg = result.GetErrorMessage();
        std::fprintf(stderr, "[错误] Shader 编译失败：%s\n", msg.c_str());
        std::fflush(stderr);
        throw std::runtime_error("Shader 编译失败");
    }
    return std::vector<std::uint32_t>(result.cbegin(), result.cend());
}

/**
 * 编译高斯过程回归 (GPR) 着色器
 * 用于计算残差预测
 */
std::vector<std::uint32_t> compile_gpr_shader() {
    const char* shader_src = R"glsl(
#version 450
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0) readonly buffer XsBuf { float Xs[]; };
layout(set = 0, binding = 1) readonly buffer XTrainBuf { float X_train[]; };
layout(set = 0, binding = 2) readonly buffer AlphaLBuf { float alpha_L[]; };
layout(set = 0, binding = 3) readonly buffer AlphaABuf { float alpha_a[]; };
layout(set = 0, binding = 4) readonly buffer AlphaBBuf { float alpha_b[]; };
layout(set = 0, binding = 5) writeonly buffer OutBuf { float out_residuals[]; };

layout(push_constant) uniform Push {
    uint n_samples;
    uint n_train;
    uint n_features;
    uint pad0;
    vec4 lengthscale;
    vec4 signal_var;
    vec4 y_mean;
    vec4 y_std;
} pc;

float clampf(float v, float lo, float hi)
{
    return min(max(v, lo), hi);
}

void main()
{
    uint idx = gl_GlobalInvocationID.x;
    uint total = pc.n_samples * 3u;
    if (idx >= total) {
        return;
    }

    uint i = idx / 3u;
    uint ch = idx - i * 3u;

    float ls = (ch == 0u) ? pc.lengthscale.x : ((ch == 1u) ? pc.lengthscale.y : pc.lengthscale.z);
    float sv = (ch == 0u) ? pc.signal_var.x : ((ch == 1u) ? pc.signal_var.y : pc.signal_var.z);
    float ym = (ch == 0u) ? pc.y_mean.x : ((ch == 1u) ? pc.y_mean.y : pc.y_mean.z);
    float ys = (ch == 0u) ? pc.y_std.x : ((ch == 1u) ? pc.y_std.y : pc.y_std.z);

    float ls2 = max(ls * ls, 1e-12);
    float y_pred = 0.0;
    float max_k = 0.0;
    for (uint j = 0u; j < pc.n_train; ++j) {
        float dist_sq = 0.0;
        uint base_train = j * pc.n_features;
        uint base_x = i * pc.n_features;
        for (uint k = 0u; k < pc.n_features; ++k) {
            float diff = X_train[base_train + k] - Xs[base_x + k];
            dist_sq += diff * diff;
        }
        float k_star = sv * exp(-0.5 * dist_sq / ls2);
        if (k_star > max_k) {
            max_k = k_star;
        }
        float a = (ch == 0u) ? alpha_L[j] : ((ch == 1u) ? alpha_a[j] : alpha_b[j]);
        y_pred += k_star * a;
    }

    float denom = (sv > 1e-12) ? sv : 1.0;
    float w = clampf(max_k / denom, 0.0, 1.0);
    out_residuals[idx] = y_pred * ys + ym * w;
}
)glsl";

    shaderc::Compiler compiler;
    shaderc::CompileOptions options;
    options.SetTargetEnvironment(shaderc_target_env_vulkan, shaderc_env_version_vulkan_1_1);
    options.SetOptimizationLevel(shaderc_optimization_level_performance);

    shaderc::SpvCompilationResult result = compiler.CompileGlslToSpv(
        shader_src, shaderc_compute_shader, "solver_gpr.comp", options
    );
    if (result.GetCompilationStatus() != shaderc_compilation_status_success) {
        std::string msg = result.GetErrorMessage();
        std::fprintf(stderr, "[错误] Shader 编译失败：%s\n", msg.c_str());
        std::fflush(stderr);
        throw std::runtime_error("Shader 编译失败");
    }
    return std::vector<std::uint32_t>(result.cbegin(), result.cend());
}

} // namespace solver
} // namespace opencolor
