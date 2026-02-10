/**
 * @file hill_climbing_rt_slab.cpp
 * @brief 爬山算法求解器 - RT Slab光学模型预测模块
 *
 * 本模块提供RT Slab光学模型的CPU和Vulkan实现
 */

#include "hill_climbing_solver.h"
#include "color_utils.h"
#include "vulkan_predictors.h"

#include <cmath>
#include <algorithm>
#include <iostream>
#include <vector>

namespace opencolor {
namespace solver {

/**
 * @brief RT Slab光学模型预测 - CPU实现
 * @param sequences 材料序列索引数组
 * @param n_seq 序列数量
 * @return 预测的RGB值数组
 */
std::vector<float> HillClimbingSolver::predict_rt_slab(const std::vector<int32_t>& sequences, int n_seq) {
    const int n_layers = config_.n_layers;
    std::vector<float> result(static_cast<std::size_t>(n_seq) * 3u, 0.0f);

    const auto& alpha = model_.optical.alpha;
    const auto& beta = model_.optical.beta;
    const auto& gamma = model_.optical.gamma;
    if (alpha.size() != static_cast<std::size_t>(num_materials_ * 3)
        || beta.size() != static_cast<std::size_t>(num_materials_ * 3)
        || gamma.size() != 3u) {
        std::fprintf(stderr, "[错误] RT slab 参数维度不匹配：alpha=%zu, beta=%zu, gamma=%zu, num_materials=%d\n",
                     alpha.size(), beta.size(), gamma.size(), num_materials_);
        std::fflush(stderr);
        return result;
    }

    auto clampf = [](float v, float lo, float hi) {
        return std::max(lo, std::min(hi, v));
    };
    auto sigmoidf = [&](float x) {
        x = clampf(x, -20.0f, 20.0f);
        return 1.0f / (1.0f + std::exp(-x));
    };
    auto linear_to_srgb = [&](float x) {
        if (x <= 0.0031308f) {
            return 12.92f * x;
        }
        float v = std::max(x, 0.0f);
        return 1.055f * std::pow(v, 1.0f / 2.4f) - 0.055f;
    };

    const bool input_is_bottom_first = (config_.layer_names_order == "bottom_first");
    for (int s = 0; s < n_seq; ++s) {
        for (int c = 0; c < 3; ++c) {
            float R = sigmoidf(gamma[static_cast<std::size_t>(c)]);
            for (int li = 0; li < n_layers; ++li) {
                int raw_l = input_is_bottom_first ? (n_layers - 1 - li) : li;
                int mat = sequences[s * n_layers + raw_l];
                if (mat < 0 || mat >= num_materials_) {
                    continue;
                }
                int base = mat * 3 + c;
                float r = sigmoidf(alpha[static_cast<std::size_t>(base)]);
                float t = sigmoidf(beta[static_cast<std::size_t>(base)]) * (1.0f - r);
                float denom = 1.0f - r * R;
                if (std::abs(denom) < 1e-6f) {
                    denom = (denom < 0.0f) ? -1e-6f : 1e-6f;
                }
                R = r + (t * t) * R / denom;
                R = clampf(R, 0.0f, 1.0f);
            }
            float srgb = linear_to_srgb(R);
            srgb = clampf(srgb, 0.0f, 1.0f);
            result[static_cast<std::size_t>(s) * 3u + static_cast<std::size_t>(c)] = srgb;
        }
    }
    return result;
}

std::vector<float> HillClimbingSolver::predict_rt_slab_vulkan(const std::vector<int32_t>& sequences, int n_seq) {
    return predict_rt_slab_vulkan_internal(
        sequences, n_seq, config_.n_layers, num_materials_,
        model_.optical, config_.layer_names_order, vk_state_.get()
    );
}

} // namespace solver
} // namespace opencolor