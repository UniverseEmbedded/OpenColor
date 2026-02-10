/**
 * @file hill_climbing_solver.cpp
 * @brief 爬山算法求解器实现 - 主程序入口
 *
 * 本文件实现了基于爬山算法的颜色配方求解器，支持：
 * - Four-Flux光学模型预测
 * - RT Slab光学模型预测
 * - GPR(高斯过程回归)特征构建和预测
 * - Vulkan GPU加速计算
 * - 多线程并行优化
 */

#include "hill_climbing_solver.h"
#include "color_utils.h"
#include "vulkan_context.h"
#include "vulkan_predictors.h"

#include <cmath>
#include <algorithm>
#include <random>
#include <cstring>
#include <iostream>
#include <chrono>
#include <iomanip>
#include <unordered_map>
#include <thread>
#include <atomic>

namespace opencolor {
namespace solver {

/**
 * @brief 析构函数 - 清理Vulkan资源
 */
HillClimbingSolver::~HillClimbingSolver() {
    vk_state_.reset();
    if (config_.use_vulkan) {
        const int prev = get_solver_vulkan_users().fetch_sub(1);
        if (prev == 1) {
            destroy_solver_vulkan_context();
        }
    }
}

/**
 * @brief 构造函数 - 初始化求解器
 * @param model 物理GPR模型
 * @param config 求解器配置
 */
HillClimbingSolver::HillClimbingSolver(const PhysGPRModel& model, const SolverConfig& config)
    : model_(model), config_(config), num_materials_(static_cast<int>(model.optical.material_keys.size())) {
    if (config_.use_vulkan) {
        init_solver_vulkan_context();
        get_solver_vulkan_users().fetch_add(1);
        vk_state_ = std::make_unique<HillClimbingSolverVulkanState>();
    }
}

/**
 * @brief 将秒数格式化为可读字符串
 * @param sec 秒数
 * @return 格式化后的时间字符串
 */
static std::string format_seconds(double sec) {
    if (sec < 60.0) {
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%.1fs", sec);
        return std::string(buf);
    }
    int m = static_cast<int>(sec / 60.0);
    double s = sec - m * 60.0;
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%dm%.1fs", m, s);
    return std::string(buf);
}

/**
 * @brief 求解最优配方 - 爬山算法主函数
 * @param target_rgb 目标RGB颜色值数组
 * @param n_targets 目标数量
 * @return 最优配方索引数组
 */
std::vector<int32_t> HillClimbingSolver::solve(const std::vector<float>& target_rgb, int n_targets) {
    int n_layers = config_.n_layers;
    int n_mats = num_materials_;

    std::vector<float> target_lab(n_targets * 3);
    for (int i = 0; i < n_targets; ++i) {
        opencolor::solver::rgb01_to_lab(&target_rgb[i * 3], &target_lab[i * 3]);
    }

    int n_candidates = config_.n_random_samples + n_mats;
    std::vector<int32_t> candidates(n_candidates * n_layers);

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, n_mats - 1);

    for (int i = 0; i < config_.n_random_samples; ++i) {
        for (int l = 0; l < n_layers; ++l) {
            candidates[i * n_layers + l] = dis(gen);
        }
    }

    for (int m = 0; m < n_mats; ++m) {
        for (int l = 0; l < n_layers; ++l) {
            candidates[(config_.n_random_samples + m) * n_layers + l] = m;
        }
    }

    std::cout << "[C++求解器] 预测 " << n_candidates << " 个候选配方..." << std::endl;
    std::vector<float> candidate_lab = predict_batch(candidates, n_candidates);

    std::vector<int32_t> best_indices(n_targets * n_layers);

    std::cout << "[C++求解器] 寻找初始候选..." << std::endl;

    auto t_find_start = std::chrono::steady_clock::now();
    auto t_find_next = t_find_start;
    auto print_find_progress = [&](int done) {
        if (n_targets <= 0) {
            return;
        }
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - t_find_start).count();
        double eta = 0.0;
        if (done > 0) {
            eta = elapsed * (static_cast<double>(n_targets - done) / static_cast<double>(done));
        }
        float pct = 100.0f * (static_cast<float>(done) / static_cast<float>(n_targets));
        std::cout
            << "[C++求解器] 初始候选进度 "
            << std::fixed << std::setprecision(1)
            << pct << "% (" << done << "/" << n_targets << ")"
            << "  已用=" << format_seconds(elapsed)
            << "  预计剩余=" << format_seconds(eta)
            << std::endl;
    };

    std::atomic<int> find_done(0);
    int n_workers_find = static_cast<int>(std::thread::hardware_concurrency());
    if (n_workers_find <= 0) n_workers_find = 1;
    if (n_targets > 0) {
        n_workers_find = std::min(n_workers_find, n_targets);
    }
    std::vector<std::thread> workers_find;
    workers_find.reserve(static_cast<std::size_t>(n_workers_find));
    // 辅助函数：计算配方复杂度（不同材料的数量）
    auto recipe_complexity = [&](int candidate_idx) -> int {
        int base = candidate_idx * n_layers;
        int unique_count = 1;
        for (int l = 1; l < n_layers; ++l) {
            bool found = false;
            for (int k = 0; k < l; ++k) {
                if (candidates[base + l] == candidates[base + k]) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                unique_count++;
            }
        }
        return unique_count;
    };

    for (int w = 0; w < n_workers_find; ++w) {
        int begin = (n_targets * w) / n_workers_find;
        int end = (n_targets * (w + 1)) / n_workers_find;
        workers_find.emplace_back([&, begin, end]() {
            for (int i = begin; i < end; ++i) {
                float min_dist = 1e10f;
                int best_idx = 0;
                int best_complexity = n_layers;
                for (int j = 0; j < n_candidates; ++j) {
                    float dist = 0.0f;
                    for (int c = 0; c < 3; ++c) {
                        float diff = candidate_lab[j * 3 + c] - target_lab[i * 3 + c];
                        dist += diff * diff;
                    }
                    dist = std::sqrt(dist);
                    int complexity = recipe_complexity(j);
                    
                    if (dist < min_dist - 1e-3f) {
                        min_dist = dist;
                        best_idx = j;
                        best_complexity = complexity;
                    } else if (std::abs(dist - min_dist) <= 1e-3f) {
                        if (complexity < best_complexity) {
                            best_idx = j;
                            best_complexity = complexity;
                        }
                    }
                }
                for (int l = 0; l < n_layers; ++l) {
                    best_indices[i * n_layers + l] = candidates[best_idx * n_layers + l];
                }
                find_done.fetch_add(1, std::memory_order_relaxed);
            }
        });
    }

    while (find_done.load(std::memory_order_relaxed) < n_targets) {
        auto now = std::chrono::steady_clock::now();
        if (now >= t_find_next) {
            print_find_progress(find_done.load(std::memory_order_relaxed));
            t_find_next = now + std::chrono::milliseconds(500);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    for (auto& th : workers_find) {
        th.join();
    }
    print_find_progress(n_targets);

    std::cout << "[C++求解器] 爬山优化..." << std::endl;

    std::vector<float> curr_dist(n_targets, 0.0f);
    std::cout << "[C++求解器] 计算当前误差(整批)..." << std::endl;
    std::vector<float> best_lab = predict_batch(best_indices, n_targets);
    int n_workers_dist = static_cast<int>(std::thread::hardware_concurrency());
    if (n_workers_dist <= 0) n_workers_dist = 1;
    if (n_targets > 0) {
        n_workers_dist = std::min(n_workers_dist, n_targets);
    }
    std::vector<std::thread> workers_dist;
    workers_dist.reserve(static_cast<std::size_t>(n_workers_dist));
    for (int w = 0; w < n_workers_dist; ++w) {
        int begin = (n_targets * w) / n_workers_dist;
        int end = (n_targets * (w + 1)) / n_workers_dist;
        workers_dist.emplace_back([&, begin, end]() {
            for (int i = begin; i < end; ++i) {
                float dist = 0.0f;
                for (int c = 0; c < 3; ++c) {
                    float diff = best_lab[i * 3 + c] - target_lab[i * 3 + c];
                    dist += diff * diff;
                }
                curr_dist[i] = std::sqrt(dist);
            }
        });
    }
    for (auto& th : workers_dist) {
        th.join();
    }

    std::uniform_int_distribution<> dis_layer(0, n_layers - 1);
    std::uniform_int_distribution<> dis_mat(0, n_mats - 1);
    std::vector<int> layer_choice(n_targets, 0);
    std::vector<int32_t> mat_choice(n_targets, 0);
    std::vector<std::uint8_t> changed(n_targets, 0);

    const int total_iters = std::max(0, config_.hill_climb_iterations);
    auto t_start = std::chrono::steady_clock::now();
    auto t_next = t_start;

    auto print_progress = [&](int iter_done, double iter_sec) {
        if (total_iters <= 0) {
            return;
        }
        float dmin = 1e30f;
        float dmax = 0.0f;
        double dsum = 0.0;
        for (int i = 0; i < n_targets; ++i) {
            float d = curr_dist[i];
            dsum += static_cast<double>(d);
            if (d < dmin) dmin = d;
            if (d > dmax) dmax = d;
        }
        double mean = (n_targets > 0) ? (dsum / static_cast<double>(n_targets)) : 0.0;
        float pct = 100.0f * (static_cast<float>(iter_done) / static_cast<float>(total_iters));

        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - t_start).count();
        double eta = 0.0;
        if (iter_done > 0) {
            double avg = elapsed / static_cast<double>(iter_done);
            eta = avg * static_cast<double>(total_iters - iter_done);
        }

        std::cout
            << "[C++求解器] 爬山进度 "
            << std::fixed << std::setprecision(1)
            << pct << "% (" << iter_done << "/" << total_iters << ")"
            << "  本轮=" << std::setprecision(2) << iter_sec << "s"
            << "  已用=" << format_seconds(elapsed)
            << "  预计剩余=" << format_seconds(eta)
            << "  平均=" << std::setprecision(3) << static_cast<float>(mean)
            << "  最小=" << dmin
            << "  最大=" << dmax
            << std::endl;
    };

    if (total_iters > 0) {
        print_progress(0, 0.0);
    }

    for (int iter = 0; iter < total_iters; ++iter) {
        auto iter_start = std::chrono::steady_clock::now();
        std::vector<int32_t> proposed = best_indices;

        for (int i = 0; i < n_targets; ++i) {
            int layer_to_change = dis_layer(gen);
            int32_t new_mat = static_cast<int32_t>(dis_mat(gen));
            layer_choice[i] = layer_to_change;
            mat_choice[i] = new_mat;

            int32_t curr_mat = best_indices[i * n_layers + layer_to_change];
            if (new_mat == curr_mat) {
                changed[i] = 0;
                continue;
            }
            changed[i] = 1;
            proposed[i * n_layers + layer_to_change] = new_mat;
        }

        std::vector<float> lab_all = predict_batch(proposed, n_targets);
        int n_workers_update = static_cast<int>(std::thread::hardware_concurrency());
        if (n_workers_update <= 0) n_workers_update = 1;
        if (n_targets > 0) {
            n_workers_update = std::min(n_workers_update, n_targets);
        }
        std::vector<std::thread> workers_update;
        workers_update.reserve(static_cast<std::size_t>(n_workers_update));
        for (int w = 0; w < n_workers_update; ++w) {
            int begin = (n_targets * w) / n_workers_update;
            int end = (n_targets * (w + 1)) / n_workers_update;
            workers_update.emplace_back([&, begin, end]() {
                for (int gi = begin; gi < end; ++gi) {
                    if (!changed[gi]) {
                        continue;
                    }
                    float dist = 0.0f;
                    for (int c = 0; c < 3; ++c) {
                        float diff = lab_all[gi * 3 + c] - target_lab[gi * 3 + c];
                        dist += diff * diff;
                    }
                    dist = std::sqrt(dist);
                    if (dist < curr_dist[gi]) {
                        best_indices[gi * n_layers + layer_choice[gi]] = mat_choice[gi];
                        curr_dist[gi] = dist;
                    }
                }
            });
        }
        for (auto& th : workers_update) {
            th.join();
        }

        auto iter_end = std::chrono::steady_clock::now();
        double iter_sec = std::chrono::duration<double>(iter_end - iter_start).count();
        auto now = std::chrono::steady_clock::now();
        if (now >= t_next || (iter + 1) == total_iters) {
            print_progress(iter + 1, iter_sec);
            t_next = now + std::chrono::milliseconds(500);
        }
    }

    if (total_iters > 0) {
        auto t_end = std::chrono::steady_clock::now();
        double sec = std::chrono::duration<double>(t_end - t_start).count();
        std::cout << "\n[C++求解器] 爬山优化完成，用时 " << std::fixed << std::setprecision(2) << sec << " 秒" << std::endl;
    }

    return best_indices;
}

/**
 * @brief 创建求解器实例的工厂函数
 * @param model 物理GPR模型
 * @param config 求解器配置
 * @return 求解器唯一指针
 */
std::unique_ptr<HillClimbingSolver> create_solver(const PhysGPRModel& model,
                                                   const SolverConfig& config) {
    return std::make_unique<HillClimbingSolver>(model, config);
}

} // namespace solver
} // namespace opencolor