/**
 * @file hill_climbing_gpr.cpp
 * @brief 爬山算法求解器 - GPR特征构建和预测模块
 *
 * 本模块提供GPR(高斯过程回归)特征构建和预测功能
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
 * @brief 构建GPR(高斯过程回归)特征向量
 * @param recipe_indices 配方索引数组
 * @param n_samples 样本数量
 * @param base_lab 基础LAB颜色值
 * @return 特征向量数组
 */
std::vector<float> HillClimbingSolver::build_gpr_features(
    const std::vector<int32_t>& recipe_indices,
    int n_samples,
    const std::vector<float>& base_lab
) {
    int n_mats = num_materials_;
    int n_layers = config_.n_layers;
    int n_classes = n_mats + 1;
    int empty_idx = n_mats;

    int seq_feat_dim = n_layers * n_classes + n_classes * n_classes + 2 + n_classes;
    int n_features = n_mats + 1 + 1 + 1 + 3 + seq_feat_dim + 3;

    std::vector<float> X(n_samples * n_features, 0.0f);

    std::vector<float> depth_weights(n_layers);
    float weight_sum = 0.0f;
    for (int l = 0; l < n_layers; ++l) {
        depth_weights[l] = static_cast<float>(l + 1);
        weight_sum += depth_weights[l];
    }
    for (int l = 0; l < n_layers; ++l) {
        depth_weights[l] /= weight_sum;
    }

    bool input_is_bottom_first = (config_.layer_names_order == "bottom_first");

    for (int i = 0; i < n_samples; ++i) {
        int feat_idx = 0;

        std::vector<float> recipe(static_cast<std::size_t>(n_mats), 0.0f);
        for (int l = 0; l < n_layers; ++l) {
            int mat_idx = recipe_indices[i * n_layers + l];
            if (mat_idx >= 0 && mat_idx < n_mats) {
                recipe[static_cast<std::size_t>(mat_idx)] += 1.0f;
            }
        }

        float sum = 0.0f;
        for (float v : recipe) {
            sum += v;
        }
        float eps = 1e-8f;

        for (int j = 0; j < n_mats; ++j) {
            X[i * n_features + feat_idx++] = recipe[j] / (sum + eps);
        }

        X[i * n_features + feat_idx++] = sum;

        float max_val = 0.0f;
        for (float v : recipe) max_val = std::max(max_val, v);
        X[i * n_features + feat_idx++] = max_val;

        float nz = 0.0f;
        for (float v : recipe) if (v > 0) nz += 1.0f;
        X[i * n_features + feat_idx++] = nz;

        X[i * n_features + feat_idx++] = base_lab[i * 3 + 0];
        X[i * n_features + feat_idx++] = base_lab[i * 3 + 1];
        X[i * n_features + feat_idx++] = base_lab[i * 3 + 2];

        std::vector<int32_t> seq(n_layers, empty_idx);
        for (int l = 0; l < n_layers; ++l) {
            int src_l = input_is_bottom_first ? (n_layers - 1 - l) : l;
            int mat_idx = recipe_indices[i * n_layers + src_l];
            if (mat_idx >= 0 && mat_idx < n_mats) {
                seq[l] = mat_idx;
            } else {
                seq[l] = empty_idx;
            }
        }

        int pos_offset = feat_idx;
        for (int l = 0; l < n_layers; ++l) {
            int mat_idx = seq[l];
            if (mat_idx >= 0 && mat_idx < n_classes) {
                X[i * n_features + pos_offset + l * n_classes + mat_idx] = 1.0f;
            }
        }
        feat_idx += n_layers * n_classes;

        int pair_offset = feat_idx;
        for (int l = 0; l < n_layers - 1; ++l) {
            int a = seq[l];
            int b = seq[l + 1];
            if (a >= 0 && a < n_classes && b >= 0 && b < n_classes) {
                X[i * n_features + pair_offset + a * n_classes + b] += 1.0f;
            }
        }
        feat_idx += n_classes * n_classes;

        float run_first = 1.0f;
        for (int l = 1; l < n_layers; ++l) {
            if (seq[l] == seq[0]) {
                run_first += 1.0f;
            } else {
                break;
            }
        }

        float run_last = 1.0f;
        for (int l = n_layers - 2; l >= 0; --l) {
            if (seq[l] == seq[n_layers - 1]) {
                run_last += 1.0f;
            } else {
                break;
            }
        }

        X[i * n_features + feat_idx++] = run_first / static_cast<float>(n_layers);
        X[i * n_features + feat_idx++] = run_last / static_cast<float>(n_layers);

        int depth_w_offset = feat_idx;
        for (int l = 0; l < n_layers; ++l) {
            int mat_idx = seq[l];
            if (mat_idx >= 0 && mat_idx < n_classes) {
                X[i * n_features + depth_w_offset + mat_idx] += depth_weights[l];
            }
        }
        feat_idx += n_classes;

        X[i * n_features + feat_idx++] = model_.optical.k1;
        X[i * n_features + feat_idx++] = model_.optical.k2;
        X[i * n_features + feat_idx++] = model_.optical.backing;
    }

    return X;
}

std::vector<float> HillClimbingSolver::predict_gpr_vulkan3(const std::vector<float>& X, int n_samples) {
    return predict_gpr_vulkan3_internal(X, n_samples, vk_state_.get(), model_.gpr_L, model_.gpr_a, model_.gpr_b);
}

std::vector<float> HillClimbingSolver::predict_gpr(const GPRParams& gpr, const std::vector<float>& X) {
    if (gpr.x_mean.empty() || gpr.x_std.empty() || gpr.X_train.empty() || gpr.alpha.empty()) {
        std::cerr << "[错误] GPR参数为空" << std::endl;
        return std::vector<float>();
    }

    int n_features = static_cast<int>(gpr.x_mean.size());
    if (n_features == 0) {
        std::cerr << "[错误] n_features为0" << std::endl;
        return std::vector<float>();
    }

    if (static_cast<int>(X.size()) % n_features != 0) {
        std::cerr << "[错误] X大小不是n_features的整数倍: " << X.size() << " % " << n_features << std::endl;
        return std::vector<float>();
    }

    int n_samples = static_cast<int>(X.size()) / n_features;
    int n_train = static_cast<int>(gpr.X_train.size()) / n_features;

    if (n_train == 0) {
        std::cerr << "[错误] n_train为0" << std::endl;
        return std::vector<float>(n_samples, 0.0f);
    }

    if (static_cast<int>(gpr.alpha.size()) != n_train) {
        std::cerr << "[错误] alpha大小不匹配: " << gpr.alpha.size() << " vs " << n_train << std::endl;
        return std::vector<float>(n_samples, 0.0f);
    }

    if (static_cast<int>(gpr.X_train.size()) != n_train * n_features) {
        std::cerr << "[错误] X_train大小不匹配: " << gpr.X_train.size() << " vs " << n_train * n_features << std::endl;
        return std::vector<float>(n_samples, 0.0f);
    }

    std::vector<float> result(n_samples, 0.0f);

    for (int i = 0; i < n_samples; ++i) {
        std::vector<float> x_norm(n_features);
        for (int j = 0; j < n_features; ++j) {
            float x_val = X[i * n_features + j];
            float mean = gpr.x_mean[j];
            float std = gpr.x_std[j] + 1e-9f;
            x_norm[j] = (x_val - mean) / std;
        }

        float lengthscale_sq = gpr.lengthscale * gpr.lengthscale;

        float y_pred = 0.0f;
        float max_k = 0.0f;
        for (int j = 0; j < n_train; ++j) {
            float dist_sq = 0.0f;
            for (int k = 0; k < n_features; ++k) {
                float diff = gpr.X_train[j * n_features + k] - x_norm[k];
                dist_sq += diff * diff;
            }
            float k_star = gpr.signal_var * std::exp(-0.5f * dist_sq / lengthscale_sq);
            if (k_star > max_k) {
                max_k = k_star;
            }
            y_pred += k_star * gpr.alpha[j];
        }

        float denom = (gpr.signal_var > 1e-12f) ? gpr.signal_var : 1.0f;
        float w = std::max(0.0f, std::min(1.0f, max_k / denom));

        result[i] = y_pred * gpr.y_std + gpr.y_mean * w;
    }

    return result;
}

/**
 * @brief 批量预测颜色值
 * @param recipe_indices 配方索引数组
 * @param n_samples 样本数量
 * @return 预测的LAB颜色值数组
 */
std::vector<float> HillClimbingSolver::predict_batch(const std::vector<int32_t>& recipe_indices, int n_samples) {
    int n_layers = config_.n_layers;

    std::vector<float> base_rgb;
    const bool has_rts = (model_.optical.alpha.size() == static_cast<std::size_t>(num_materials_ * 3))
        && (model_.optical.beta.size() == static_cast<std::size_t>(num_materials_ * 3))
        && (model_.optical.gamma.size() == 3u);

    if (has_rts) {
        if (config_.use_vulkan) {
            base_rgb = predict_rt_slab_vulkan(recipe_indices, n_samples);
        } else {
            base_rgb = predict_rt_slab(recipe_indices, n_samples);
        }
    } else {
        base_rgb = predict_four_flux(recipe_indices, n_samples);
    }

    std::vector<float> base_lab(n_samples * 3);
    for (int i = 0; i < n_samples; ++i) {
        opencolor::solver::rgb01_to_lab(&base_rgb[i * 3], &base_lab[i * 3]);
    }

    std::vector<float> X = build_gpr_features(recipe_indices, n_samples, base_lab);

    int n_features_expected = static_cast<int>(model_.gpr_L.x_mean.size());
    int n_features_actual = static_cast<int>(X.size()) / n_samples;

    if (n_features_actual != n_features_expected) {
        std::cerr << "[错误] 特征维度不匹配: 实际=" << n_features_actual << ", 期望=" << n_features_expected << std::endl;
        return base_lab;
    }

    std::vector<float> pred_L;
    std::vector<float> pred_a;
    std::vector<float> pred_b;
    if (config_.use_vulkan) {
        std::vector<float> pred3 = predict_gpr_vulkan3(X, n_samples);
        if (pred3.size() != static_cast<std::size_t>(n_samples) * 3u) {
            throw std::runtime_error("GPR GPU 输出维度不匹配");
        }
        pred_L.resize(n_samples);
        pred_a.resize(n_samples);
        pred_b.resize(n_samples);
        for (int i = 0; i < n_samples; ++i) {
            pred_L[i] = pred3[static_cast<std::size_t>(i) * 3u + 0u];
            pred_a[i] = pred3[static_cast<std::size_t>(i) * 3u + 1u];
            pred_b[i] = pred3[static_cast<std::size_t>(i) * 3u + 2u];
        }
    } else {
        pred_L = predict_gpr(model_.gpr_L, X);
        pred_a = predict_gpr(model_.gpr_a, X);
        pred_b = predict_gpr(model_.gpr_b, X);
    }

    if (pred_L.empty() || pred_a.empty() || pred_b.empty()) {
        std::cerr << "[警告] GPR 预测失败，返回基础预测" << std::endl;
        return base_lab;
    }

    std::vector<float> result(n_samples * 3);
    for (int i = 0; i < n_samples; ++i) {
        result[i * 3 + 0] = base_lab[i * 3 + 0] + pred_L[i];
        result[i * 3 + 1] = base_lab[i * 3 + 1] + pred_a[i];
        result[i * 3 + 2] = base_lab[i * 3 + 2] + pred_b[i];
    }

    return result;
}

} // namespace solver
} // namespace opencolor