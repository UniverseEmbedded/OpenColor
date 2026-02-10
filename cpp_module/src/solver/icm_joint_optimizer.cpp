#include "icm_joint_optimizer.h"
#include "hill_climbing_solver.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <random>
#include <queue>

namespace opencolor {
namespace solver {

// 颜色转换常量
static const float D65_X = 0.95047f;
static const float D65_Y = 1.00000f;
static const float D65_Z = 1.08883f;

// RGB to XYZ矩阵
static const float RGB_TO_XYZ[3][3] = {
    {0.4124564f, 0.3575761f, 0.1804375f},
    {0.2126729f, 0.7151522f, 0.0721750f},
    {0.0193339f, 0.1191920f, 0.9503041f}
};

ICMJointOptimizer::ICMJointOptimizer(HillClimbingSolver* solver,
                                     int n_slots,
                                     int n_layers,
                                     int h, int w,
                                     const ICMJointOptimizerConfig& config)
    : solver_(solver),
      n_slots_(n_slots),
      n_layers_(n_layers),
      h_(h),
      w_(w),
      n_pixels_(h * w),
      config_(config) {
    
    // 初始化位置映射
    pos_to_k_.resize(h_ * w_, -1);
    
    std::cout << "[ICM] 优化器已创建: n_slots=" << n_slots_ << ", n_layers=" << n_layers_ 
              << ", size=" << h_ << "x" << w_ << std::endl;
}

ICMJointOptimizer::~ICMJointOptimizer() {
}

void ICMJointOptimizer::optimize(std::vector<int32_t>& recipes,
                                 const std::vector<int32_t>& ys,
                                 const std::vector<int32_t>& xs,
                                 const std::vector<float>& pix_rgb01,
                                 const std::vector<float>& guidance_gray01,
                                 const std::vector<uint8_t>& full_mask,
                                 int layer_start,
                                 int layer_end) {
    
    if (layer_end < 0) {
        layer_end = n_layers_;
    }
    
    // 保存像素坐标
    ys_ = ys;
    xs_ = xs;
    
    // 构建位置映射
    std::fill(pos_to_k_.begin(), pos_to_k_.end(), -1);
    for (int k = 0; k < (int)ys.size(); ++k) {
        int idx = ys[k] * w_ + xs[k];
        if (idx >= 0 && idx < (int)pos_to_k_.size()) {
            pos_to_k_[idx] = k;
        }
    }
    
    // 小连通域剔除（前置）
    if (config_.remove_islands_max_area_px > 0 && config_.remove_islands_passes > 0) {
        std::cout << "[ICM] 小连通域剔除（前置）" << std::endl;
        for (int z = layer_start; z < layer_end; ++z) {
            std::vector<int32_t> layer_labels(n_pixels_, -1);
            for (int k = 0; k < (int)ys.size(); ++k) {
                layer_labels[ys[k] * w_ + xs[k]] = recipes[k * n_layers_ + z];
            }
            remove_small_components(layer_labels, full_mask);
            for (int k = 0; k < (int)ys.size(); ++k) {
                recipes[k * n_layers_ + z] = layer_labels[ys[k] * w_ + xs[k]];
            }
        }
    }
    
    // 计算边缘强度（结构保护）
    if (config_.structure_protect) {
        edge_strength_.resize(h_ * w_);
        compute_edge_strength(guidance_gray01, edge_strength_);
    }
    
    // 主优化循环
    int total_layers = layer_end - layer_start;
    int current_layer = 0;
    
    for (int z = layer_start; z < layer_end; ++z) {
        float layer_progress = 100.0f * current_layer / total_layers;
        std::cout << "[ICM] 优化层 " << z << " (" << current_layer + 1 << "/" << total_layers 
                  << ", " << std::fixed << std::setprecision(1) << layer_progress << "%)" << std::endl;
        
        // 提取当前层标签
        std::vector<int32_t> current_labels(n_pixels_, -1);
        for (int k = 0; k < (int)ys.size(); ++k) {
            current_labels[ys[k] * w_ + xs[k]] = recipes[k * n_layers_ + z];
        }
        
        for (int pass = 0; pass < config_.passes; ++pass) {
            std::cout << "[ICM]   第 " << pass + 1 << "/" << config_.passes << " 轮开始..." << std::endl;
            
            // 生成候选提案
            std::vector<int32_t> proposals(n_pixels_);
            generate_proposals_cpu(current_labels, proposals, guidance_gray01, full_mask);
            
            // 找到候选像素
            std::vector<int32_t> candidate_idx;
            for (int k = 0; k < (int)ys.size(); ++k) {
                int idx = ys[k] * w_ + xs[k];
                if (proposals[idx] != current_labels[idx] && proposals[idx] >= 0) {
                    candidate_idx.push_back(k);
                }
            }
            
            if (candidate_idx.empty()) {
                std::cout << "[ICM]   第 " << pass + 1 << " 轮无候选" << std::endl;
                break;
            }
            
            std::cout << "[ICM]   候选数: " << candidate_idx.size() << std::endl;
            
            // 限制候选数
            if (config_.max_candidates > 0 && (int)candidate_idx.size() > config_.max_candidates) {
                std::shuffle(candidate_idx.begin(), candidate_idx.end(), 
                           std::default_random_engine(12345 + z * 100 + pass));
                candidate_idx.resize(config_.max_candidates);
                std::cout << "[ICM]   限制候选数至: " << candidate_idx.size() << std::endl;
            }
            
            // 获取当前预测
            std::cout << "[ICM]   预测当前颜色..." << std::endl;
            int n_samples = recipes.size() / n_layers_;
            std::vector<float> pred_lab_current = solver_->predict_batch(recipes, n_samples);
            
            // ===== 批量预测优化 =====
            // 1. 收集所有候选的测试配方
            std::cout << "[ICM]   批量收集测试配方..." << std::endl;
            int total_candidates = (int)candidate_idx.size();
            std::vector<int32_t> all_test_recipes;
            all_test_recipes.reserve(total_candidates * n_layers_);
            
            for (int i = 0; i < total_candidates; ++i) {
                int k = candidate_idx[i];
                // 复制当前配方
                for (int l = 0; l < n_layers_; ++l) {
                    all_test_recipes.push_back(recipes[k * n_layers_ + l]);
                }
                // 修改当前层的标签为候选标签
                int pixel_idx = ys_[k] * w_ + xs_[k];
                all_test_recipes[all_test_recipes.size() - n_layers_ + z] = proposals[pixel_idx];
            }
            
            // 2. 一次性批量预测所有新颜色
            std::cout << "[ICM]   批量预测新颜色 (" << total_candidates << " 个)..." << std::endl;
            std::vector<float> all_pred_new = solver_->predict_batch(all_test_recipes, total_candidates);
            
            // 3. 逐个评估是否接受（使用预计算的颜色）
            std::cout << "[ICM]   顺序评估候选..." << std::endl;
            int moved = 0;
            int report_interval = std::max(1, total_candidates / 20);  // 每5%报告一次
            
            for (int i = 0; i < total_candidates; ++i) {
                if (i % report_interval == 0 || i == total_candidates - 1) {
                    float progress = 100.0f * (i + 1) / total_candidates;
                    std::cout << "[ICM]     进度: " << i + 1 << "/" << total_candidates 
                              << " (" << std::fixed << std::setprecision(1) << progress << "%)\r" << std::flush;
                }
                
                int k = candidate_idx[i];
                int pixel_idx = ys_[k] * w_ + xs_[k];
                int new_label = proposals[pixel_idx];
                int old_label = current_labels[pixel_idx];
                
                if (new_label == old_label) continue;
                
                // 结构保护
                float lambda_eff = config_.lambda_smooth;
                if (config_.structure_protect && !edge_strength_.empty()) {
                    lambda_eff *= (1.0f - config_.structure_protect_strength * edge_strength_[pixel_idx]);
                }
                
                // 计算边长代价
                float cur_cost = 0.0f, new_cost = 0.0f;
                int y = ys_[k], x = xs_[k];
                const int dy[4] = {0, 0, 1, -1};
                const int dx[4] = {1, -1, 0, 0};
                
                for (int j = 0; j < 4; ++j) {
                    int ny = y + dy[j], nx = x + dx[j];
                    if (ny < 0 || ny >= h_ || nx < 0 || nx >= w_) continue;
                    int nidx = ny * w_ + nx;
                    int nb_k = pos_to_k_[nidx];
                    if (nb_k < 0) continue;
                    
                    int nb_label = current_labels[nidx];
                    float w_edge = std::exp(-config_.edge_beta * 
                                  std::abs(guidance_gray01[pixel_idx] - guidance_gray01[nidx]));
                    cur_cost += w_edge * (old_label != nb_label);
                    new_cost += w_edge * (new_label != nb_label);
                }
                
                // 使用预计算的批量预测结果
                const float* pred_new = &all_pred_new[i * 3];
                const float* pred_cur = &pred_lab_current[k * 3];
                const float* tgt_rgb = &pix_rgb01[k * 3];
                float tgt_lab[3], pred_cur_lab[3] = {pred_cur[0], pred_cur[1], pred_cur[2]};
                rgb01_to_lab(tgt_rgb, tgt_lab);
                
                float de_cur = delta_e_cie76(tgt_lab, pred_cur_lab);
                float de_new = delta_e_cie76(tgt_lab, pred_new);
                
                bool ok_slack = de_new <= (de_cur + config_.slack_de76);
                float delta = config_.color_weight * (de_new - de_cur) + lambda_eff * (new_cost - cur_cost);
                
                if (ok_slack && delta < 0.0f) {
                    recipes[k * n_layers_ + z] = new_label;
                    current_labels[pixel_idx] = new_label;
                    moved++;
                }
            }
            std::cout << std::endl;  // 换行结束进度显示
            
            std::cout << "[ICM]   第 " << pass + 1 << " 轮完成，移动=" << moved << std::endl;
        }
        
        current_layer++;
    }
    
    std::cout << "[ICM] 优化完成 (100%)" << std::endl;
}

// CPU版本的候选生成（引导滤波简化版）
void ICMJointOptimizer::generate_proposals_cpu(const std::vector<int32_t>& current_labels,
                                               std::vector<int32_t>& proposals,
                                               const std::vector<float>& guidance_gray01,
                                               const std::vector<uint8_t>& full_mask) {
    int r = config_.proposal_radius;
    float eps = config_.proposal_eps;
    
    proposals = current_labels;
    
    for (int y = 0; y < h_; ++y) {
        for (int x = 0; x < w_; ++x) {
            int idx = y * w_ + x;
            if (!full_mask[idx] || current_labels[idx] < 0) continue;
            
            float I_mean = 0.0f, I_sq_mean = 0.0f;
            std::vector<int> neighbor_labels;
            
            for (int dy = -r; dy <= r; ++dy) {
                for (int dx = -r; dx <= r; ++dx) {
                    int ny = y + dy, nx = x + dx;
                    if (ny < 0 || ny >= h_ || nx < 0 || nx >= w_) continue;
                    int nidx = ny * w_ + nx;
                    if (!full_mask[nidx] || current_labels[nidx] < 0) continue;
                    
                    float I = guidance_gray01[nidx];
                    I_mean += I;
                    I_sq_mean += I * I;
                    neighbor_labels.push_back(current_labels[nidx]);
                }
            }
            
            if (neighbor_labels.empty()) continue;
            
            int n = (int)neighbor_labels.size();
            I_mean /= n;
            I_sq_mean /= n;
            float var = I_sq_mean - I_mean * I_mean;
            
            float a = var / (var + eps);
            
            std::vector<int> label_counts(n_slots_, 0);
            for (int label : neighbor_labels) {
                if (label >= 0 && label < n_slots_) label_counts[label]++;
            }
            
            int best_label = current_labels[idx];
            int max_count = 0;
            for (int i = 0; i < n_slots_; ++i) {
                if (label_counts[i] > max_count) {
                    max_count = label_counts[i];
                    best_label = i;
                }
            }
            
            if (max_count >= (int)(config_.proposal_min_soft_margin * n)) {
                proposals[idx] = best_label;
            }
        }
    }
}

void ICMJointOptimizer::icm_update_layer(std::vector<int32_t>& recipes,
                                          std::vector<int32_t>& current_labels,
                                          const std::vector<int32_t>& proposals,
                                          const std::vector<int32_t>& candidate_idx,
                                          const std::vector<float>& pred_lab_current,
                                          const std::vector<float>& pix_rgb01,
                                          const std::vector<float>& guidance_gray01,
                                          int z,
                                          int& moved_out) {
    moved_out = 0;
    
    // 按边缘强度排序候选（先处理非边缘区域）
    std::vector<int> sorted_idx = candidate_idx;
    if (config_.structure_protect && !edge_strength_.empty()) {
        std::sort(sorted_idx.begin(), sorted_idx.end(), [&](int a, int b) {
            int idx_a = ys_[a] * w_ + xs_[a];
            int idx_b = ys_[b] * w_ + xs_[b];
            return edge_strength_[idx_a] < edge_strength_[idx_b];
        });
    }
    
    // 逐个处理候选
    for (int k : sorted_idx) {
        int pixel_idx = ys_[k] * w_ + xs_[k];
        int new_label = proposals[pixel_idx];
        int old_label = current_labels[pixel_idx];
        
        if (new_label == old_label) continue;
        
        // 结构保护
        float lambda_eff = config_.lambda_smooth;
        if (config_.structure_protect && !edge_strength_.empty()) {
            lambda_eff *= (1.0f - config_.structure_protect_strength * edge_strength_[pixel_idx]);
        }
        
        // 计算边长代价
        float cur_cost = 0.0f, new_cost = 0.0f;
        int y = ys_[k], x = xs_[k];
        const int dy[4] = {0, 0, 1, -1};
        const int dx[4] = {1, -1, 0, 0};
        
        for (int i = 0; i < 4; ++i) {
            int ny = y + dy[i], nx = x + dx[i];
            if (ny < 0 || ny >= h_ || nx < 0 || nx >= w_) continue;
            int nidx = ny * w_ + nx;
            int nb_k = pos_to_k_[nidx];
            if (nb_k < 0) continue;
            
            int nb_label = current_labels[nidx];
            float w_edge = std::exp(-config_.edge_beta * 
                          std::abs(guidance_gray01[pixel_idx] - guidance_gray01[nidx]));
            cur_cost += w_edge * (old_label != nb_label);
            new_cost += w_edge * (new_label != nb_label);
        }
        
        // 预测新颜色
        std::vector<int32_t> test_recipe(recipes.begin() + k * n_layers_, 
                                        recipes.begin() + (k + 1) * n_layers_);
        test_recipe[z] = new_label;
        std::vector<float> pred_new = solver_->predict_batch(test_recipe, 1);
        
        // 计算色差
        const float* pred_cur = &pred_lab_current[k * 3];
        const float* tgt_rgb = &pix_rgb01[k * 3];
        
        float tgt_lab[3], pred_cur_lab[3] = {pred_cur[0], pred_cur[1], pred_cur[2]};
        rgb01_to_lab(tgt_rgb, tgt_lab);
        
        float de_cur = delta_e_cie76(tgt_lab, pred_cur_lab);
        float de_new = delta_e_cie76(tgt_lab, &pred_new[0]);
        
        bool ok_slack = de_new <= (de_cur + config_.slack_de76);
        float delta = config_.color_weight * (de_new - de_cur) + lambda_eff * (new_cost - cur_cost);
        
        if (ok_slack && delta < 0.0f) {
            recipes[k * n_layers_ + z] = new_label;
            current_labels[pixel_idx] = new_label;
            moved_out++;
        }
    }
}

void ICMJointOptimizer::compute_edge_strength(const std::vector<float>& guidance_gray01,
                                              std::vector<float>& edge_strength) {
    edge_strength.resize(h_ * w_);
    
    for (int y = 1; y < h_ - 1; ++y) {
        for (int x = 1; x < w_ - 1; ++x) {
            int idx = y * w_ + x;
            
            float sobel_x = -guidance_gray01[(y-1)*w_+(x-1)] + guidance_gray01[(y-1)*w_+(x+1)]
                          -2*guidance_gray01[y*w_+(x-1)]     + 2*guidance_gray01[y*w_+(x+1)]
                          -guidance_gray01[(y+1)*w_+(x-1)] + guidance_gray01[(y+1)*w_+(x+1)];
            
            float sobel_y = -guidance_gray01[(y-1)*w_+(x-1)] - 2*guidance_gray01[(y-1)*w_+x] 
                          - guidance_gray01[(y-1)*w_+(x+1)]
                          + guidance_gray01[(y+1)*w_+(x-1)] + 2*guidance_gray01[(y+1)*w_+x] 
                          + guidance_gray01[(y+1)*w_+(x+1)];
            
            edge_strength[idx] = std::sqrt(sobel_x * sobel_x + sobel_y * sobel_y);
        }
    }
    
    float max_val = *std::max_element(edge_strength.begin(), edge_strength.end());
    if (max_val > 0) {
        for (auto& v : edge_strength) {
            v /= max_val;
        }
    }
}

void ICMJointOptimizer::remove_small_components(std::vector<int32_t>& labels,
                                                const std::vector<uint8_t>& full_mask) {
    std::vector<bool> visited(n_pixels_, false);
    std::vector<int> component;
    const int dys[4] = {0, 0, 1, -1};
    const int dxs[4] = {1, -1, 0, 0};
    
    for (int y = 0; y < h_; ++y) {
        for (int x = 0; x < w_; ++x) {
            int idx = y * w_ + x;
            if (!full_mask[idx] || visited[idx] || labels[idx] < 0) continue;
            
            int label = labels[idx];
            component.clear();
            std::vector<int> stack = {idx};
            visited[idx] = true;
            
            while (!stack.empty()) {
                int cur = stack.back();
                stack.pop_back();
                component.push_back(cur);
                
                int cy = cur / w_, cx = cur % w_;
                for (int i = 0; i < 4; i++) {
                    int ny = cy + dys[i], nx = cx + dxs[i];
                    if (ny < 0 || ny >= h_ || nx < 0 || nx >= w_) continue;
                    int nidx = ny * w_ + nx;
                    if (!full_mask[nidx] || visited[nidx] || labels[nidx] != label) continue;
                    visited[nidx] = true;
                    stack.push_back(nidx);
                }
            }
            
            if ((int)component.size() <= config_.remove_islands_max_area_px) {
                std::vector<int> neighbor_counts(n_slots_, 0);
                for (int cid : component) {
                    int cy = cid / w_, cx = cid % w_;
                    for (int i = 0; i < 4; i++) {
                        int ny = cy + dys[i], nx = cx + dxs[i];
                        if (ny < 0 || ny >= h_ || nx < 0 || nx >= w_) continue;
                        int nidx = ny * w_ + nx;
                        if (!full_mask[nidx]) continue;
                        int nb = labels[nidx];
                        if (nb >= 0 && nb < n_slots_ && nb != label) {
                            neighbor_counts[nb]++;
                        }
                    }
                }
                
                int best_nb = label;
                int max_count = 0;
                for (int i = 0; i < n_slots_; i++) {
                    if (neighbor_counts[i] > max_count) {
                        max_count = neighbor_counts[i];
                        best_nb = i;
                    }
                }
                
                for (int cid : component) {
                    labels[cid] = best_nb;
                }
            }
        }
    }
}

float ICMJointOptimizer::delta_e_cie76(const float* lab1, const float* lab2) {
    float dl = lab1[0] - lab2[0];
    float da = lab1[1] - lab2[1];
    float db = lab1[2] - lab2[2];
    return std::sqrt(dl*dl + da*da + db*db);
}

void ICMJointOptimizer::rgb01_to_lab(const float* rgb, float* lab) {
    float xyz[3] = {0, 0, 0};
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            xyz[i] += RGB_TO_XYZ[i][j] * rgb[j];
        }
    }
    
    auto f = [](float t) {
        const float delta = 6.0f / 29.0f;
        if (t > delta * delta * delta) {
            return std::cbrt(t);
        } else {
            return t / (3.0f * delta * delta) + 4.0f / 29.0f;
        }
    };
    
    float fx = f(xyz[0] / D65_X);
    float fy = f(xyz[1] / D65_Y);
    float fz = f(xyz[2] / D65_Z);
    
    lab[0] = 116.0f * fy - 16.0f;
    lab[1] = 500.0f * (fx - fy);
    lab[2] = 200.0f * (fy - fz);
}

std::unique_ptr<ICMJointOptimizer> create_icm_optimizer(
    HillClimbingSolver* solver,
    int n_slots,
    int n_layers,
    int h, int w,
    const ICMJointOptimizerConfig& config) {
    
    return std::make_unique<ICMJointOptimizer>(solver, n_slots, n_layers, h, w, config);
}

} // namespace solver
} // namespace opencolor
