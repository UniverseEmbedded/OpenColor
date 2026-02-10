/**
 * @file hill_climbing_four_flux.cpp
 * @brief 爬山算法求解器 - Four-Flux光学模型预测模块
 *
 * 本模块提供Four-Flux光学模型的CPU和Vulkan实现
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
 * @brief Four-Flux光学模型预测 - CPU实现
 * @param sequences 材料序列索引数组
 * @param n_seq 序列数量
 * @return 预测的RGB值数组
 */
std::vector<float> HillClimbingSolver::predict_four_flux(const std::vector<int32_t>& sequences, int n_seq) {
    int n_layers = config_.n_layers;
    std::vector<float> result(n_seq * 3);

    const auto& mu_a_raw = model_.optical.mu_a;
    const auto& mu_s_raw = model_.optical.mu_s;
    const auto& g_raw = model_.optical.g;

    float backing = model_.optical.backing;
    float k1 = model_.optical.k1;
    float k2 = model_.optical.k2;

    auto clampf = [](float v, float lo, float hi) {
        return std::max(lo, std::min(hi, v));
    };
    auto sigmoidf = [&](float x) {
        x = clampf(x, -20.0f, 20.0f);
        return 1.0f / (1.0f + std::exp(-x));
    };
    auto apply_saunderson = [&](float Ri) {
        if (k1 == 0.0f && k2 == 0.0f) {
            return Ri;
        }
        float denom = 1.0f - k2 * Ri + 1e-9f;
        return k1 + (1.0f - k1) * (1.0f - k2) * Ri / denom;
    };
    auto linear_to_srgb = [&](float x) {
        if (x <= 0.0031308f) {
            return 12.92f * x;
        }
        float v = std::max(x, 0.0f);
        return 1.055f * std::pow(v, 1.0f / 2.4f) - 0.055f;
    };

    const float dz = 1.6384f;
    const int total_mat = num_materials_ * 3;
    std::vector<float> rc(static_cast<std::size_t>(total_mat), 0.0f);
    std::vector<float> tc(static_cast<std::size_t>(total_mat), 0.0f);
    std::vector<float> rd(static_cast<std::size_t>(total_mat), 0.0f);
    std::vector<float> td(static_cast<std::size_t>(total_mat), 0.0f);

    for (int m = 0; m < num_materials_; ++m) {
        for (int c = 0; c < 3; ++c) {
            int idx = m * 3 + c;
            float k = std::exp(clampf(mu_a_raw[idx], -10.0f, 10.0f));
            float s = std::exp(clampf(mu_s_raw[idx], -10.0f, 10.0f));
            float g = 0.9f * sigmoidf(g_raw[idx]);

            float csum = k + s;
            float tc0 = std::exp(-(csum * dz));
            float rc0 = 0.0f;

            float K = 2.0f * k;
            float S = 2.0f * s * (1.0f - g);
            float tau_d = (K + S) * 1e-4f;
            float omega_d = S / (K + S + 1e-9f);
            float rd0 = 0.5f * omega_d * (1.0f - std::exp(-2.0f * tau_d));
            float td0 = std::exp(-tau_d) + rd0;

            float r = rd0;
            float t = td0;
            for (int i = 0; i < 14; ++i) {
                float denom = 1.0f - r * r;
                if (std::abs(denom) < 1e-6f) {
                    denom = 1e-6f;
                }
                float t_new = t * t / denom;
                float r_new = r + (t * r * t) / denom;
                r = r_new;
                t = t_new;
            }

            rc[static_cast<std::size_t>(idx)] = rc0;
            tc[static_cast<std::size_t>(idx)] = tc0;
            rd[static_cast<std::size_t>(idx)] = r;
            td[static_cast<std::size_t>(idx)] = t;
        }
    }

    const bool input_is_bottom_first = (config_.layer_names_order == "bottom_first");
    for (int s = 0; s < n_seq; ++s) {
        float Rc_s[3] = {0.0f, 0.0f, 0.0f};
        float Tc_s[3] = {1.0f, 1.0f, 1.0f};
        float Rd_s[3] = {0.0f, 0.0f, 0.0f};
        float Td_s[3] = {1.0f, 1.0f, 1.0f};

        for (int li = 0; li < n_layers; ++li) {
            int raw_l = input_is_bottom_first ? (n_layers - 1 - li) : li;
            int idx_mat = sequences[s * n_layers + raw_l];
            if (idx_mat < 0 || idx_mat >= num_materials_) {
                continue;
            }
            int base = idx_mat * 3;
            for (int c = 0; c < 3; ++c) {
                float Rc2 = rc[static_cast<std::size_t>(base + c)];
                float Tc2 = tc[static_cast<std::size_t>(base + c)];
                float Rd2 = rd[static_cast<std::size_t>(base + c)];
                float Td2 = td[static_cast<std::size_t>(base + c)];

                float denom_c = 1.0f - Rc_s[c] * Rc2 + 1e-9f;
                float Rc_new = Rc_s[c] + (Tc_s[c] * Rc2 * Tc_s[c]) / denom_c;
                float Tc_new = (Tc_s[c] * Tc2) / denom_c;

                float denom_d = 1.0f - Rd_s[c] * Rd2;
                if (std::abs(denom_d) < 1e-6f) {
                    denom_d = 1e-6f;
                }
                float Rd_new = Rd_s[c] + (Td_s[c] * Rd2 * Td_s[c]) / denom_d;
                float Td_new = (Td_s[c] * Td2) / denom_d;

                Rc_s[c] = Rc_new;
                Tc_s[c] = Tc_new;
                Rd_s[c] = Rd_new;
                Td_s[c] = Td_new;
            }
        }

        for (int c = 0; c < 3; ++c) {
            float denom_d = 1.0f - Rd_s[c] * backing;
            if (std::abs(denom_d) < 1e-6f) {
                denom_d = 1e-6f;
            }
            float R_internal = Rd_s[c] + (Td_s[c] * backing * Td_s[c]) / denom_d;
            float R_measured = apply_saunderson(R_internal);
            float srgb = linear_to_srgb(R_measured);
            srgb = clampf(srgb, 0.0f, 1.0f);
            result[s * 3 + c] = srgb;
        }
    }

    return result;
}

std::vector<float> HillClimbingSolver::predict_four_flux_vulkan(const std::vector<int32_t>& sequences, int n_seq) {
    if (model_.optical.alpha.empty() || model_.optical.beta.empty() || model_.optical.gamma.size() != 3) {
        throw std::runtime_error("当前求解器已切换到 RT slab stacking 的 Vulkan 路径，four-flux Vulkan 不再可用（缺少 alpha/beta/gamma 参数）");
    }
    return predict_rt_slab_vulkan(sequences, n_seq);
}

} // namespace solver
} // namespace opencolor