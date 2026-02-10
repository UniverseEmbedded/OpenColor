#pragma once

#include <vector>
#include <cstdint>
#include <memory>

namespace opencolor {
namespace solver {

// 前向声明
class HillClimbingSolver;

// ICM联合优化配置
struct ICMJointOptimizerConfig {
    int passes = 1;                    // 迭代次数
    float lambda_smooth = 0.05f;       // 平滑权重
    float color_weight = 3.0f;         // 色准权重
    float slack_de76 = 0.15f;          // 色差松弛
    float edge_beta = 0.0f;            // 边缘保护系数
    int max_candidates = 0;            // 最大候选数（0=无限制）
    int proposal_radius = 4;           // 引导滤波半径
    float proposal_eps = 0.001f;       // 引导滤波eps
    float proposal_min_soft_margin = 0.02f;  // 最小软边距
    int proposal_despickle_iters = 1;  // 去噪迭代
    float mix_sigma = 2.5f;            // 混色高斯sigma
    float mix_weight = 6.0f;           // 混色权重
    float mix_max_increase_de76 = 0.0f;      // 混色最大增加
    float mix_base_slack_de76 = 0.0f;        // 混色基线松弛
    float island_weight = 0.35f;       // 岛屿权重
    float island_alpha = 1.0f;         // 岛屿面积指数
    int remove_islands_max_area_px = 0;      // 剔除小连通域面积
    int remove_islands_connectivity = 8;     // 连通性
    int remove_islands_passes = 1;           // 剔除迭代次数
    bool structure_protect = true;           // 结构保护
    float structure_protect_strength = 0.8f; // 保护强度
};

// ICM联合优化器
class ICMJointOptimizer {
public:
    ICMJointOptimizer(HillClimbingSolver* solver,
                      int n_slots,
                      int n_layers,
                      int h, int w,
                      const ICMJointOptimizerConfig& config);
    
    ~ICMJointOptimizer();
    
    // 执行ICM优化
    void optimize(std::vector<int32_t>& recipes,
                  const std::vector<int32_t>& ys,
                  const std::vector<int32_t>& xs,
                  const std::vector<float>& pix_rgb01,
                  const std::vector<float>& guidance_gray01,
                  const std::vector<uint8_t>& full_mask,
                  int layer_start = 0,
                  int layer_end = -1);
    
private:
    // CPU版本的候选生成（引导滤波）
    void generate_proposals_cpu(const std::vector<int32_t>& current_labels,
                                std::vector<int32_t>& proposals,
                                const std::vector<float>& guidance_gray01,
                                const std::vector<uint8_t>& full_mask);
    
    // ICM顺序更新（CPU串行）
    void icm_update_layer(std::vector<int32_t>& recipes,
                          std::vector<int32_t>& current_labels,
                          const std::vector<int32_t>& proposals,
                          const std::vector<int32_t>& candidate_idx,
                          const std::vector<float>& pred_lab_current,
                          const std::vector<float>& pix_rgb01,
                          const std::vector<float>& guidance_gray01,
                          int z,
                          int& moved_out);
    
    // 结构保护：计算边缘强度
    void compute_edge_strength(const std::vector<float>& guidance_gray01,
                               std::vector<float>& edge_strength);
    
    // 小连通域剔除
    void remove_small_components(std::vector<int32_t>& labels,
                                 const std::vector<uint8_t>& full_mask);
    
    // 辅助函数
    float delta_e_cie76(const float* lab1, const float* lab2);
    void rgb01_to_lab(const float* rgb, float* lab);
    
    HillClimbingSolver* solver_;
    int n_slots_;
    int n_layers_;
    int h_, w_;
    int n_pixels_;
    ICMJointOptimizerConfig config_;
    
    // 位置映射: (y, x) -> pixel_idx
    std::vector<int32_t> pos_to_k_;
    
    // 像素坐标（用于ICM更新）
    std::vector<int32_t> ys_;
    std::vector<int32_t> xs_;
    
    // 边缘强度
    std::vector<float> edge_strength_;
};

// 创建优化器的工厂函数
std::unique_ptr<ICMJointOptimizer> create_icm_optimizer(
    HillClimbingSolver* solver,
    int n_slots,
    int n_layers,
    int h, int w,
    const ICMJointOptimizerConfig& config);

} // namespace solver
} // namespace opencolor
