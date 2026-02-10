#pragma once

#include <vector>
#include <cstdint>
#include <string>
#include <memory>

namespace opencolor {
namespace solver {

struct HillClimbingSolverVulkanState;

// 光学参数结构
struct OpticalParams {
    std::vector<float> mu_a;      // 吸收系数 (M, 3)
    std::vector<float> mu_s;      // 散射系数 (M, 3)
    std::vector<float> g;         // 不对称因子 (M, 3)

    // RT slab stacking 参数（per material, per channel）
    // r = sigmoid(alpha), t = sigmoid(beta) * (1 - r)
    // backing_rb = sigmoid(gamma) （per channel）
    std::vector<float> alpha;     // (M, 3)
    std::vector<float> beta;      // (M, 3)
    std::vector<float> gamma;     // (3,)
    int n_layers = 5;             // 层数
    float k1 = 0.04f;             // Saunderson参数k1
    float k2 = 0.6f;              // Saunderson参数k2
    float backing = 0.98f;        // 背板反射率
    std::vector<std::string> material_keys; // 材料名称
};

// GPR模型参数
struct GPRParams {
    std::vector<float> X_train;   // 训练数据
    std::vector<float> alpha;     // GPR alpha
    std::vector<float> x_mean;    // 特征均值
    std::vector<float> x_std;     // 特征标准差
    float y_mean = 0.0f;          // 目标均值
    float y_std = 1.0f;           // 目标标准差
    float lengthscale = 0.1f;     // 长度尺度
    float signal_var = 1.0f;      // 信号方差
    float noise = 1e-7f;          // 噪声
};

// 完整的PhysGPR模型
struct PhysGPRModel {
    OpticalParams optical;
    GPRParams gpr_L;
    GPRParams gpr_a;
    GPRParams gpr_b;
    std::vector<std::string> feature_names;
};

// 求解配置
struct SolverConfig {
    int n_random_samples = 1000;  // 随机采样数量
    int hill_climb_iterations = 10; // 爬山迭代次数
    int n_layers = 5;             // 层数
    std::string layer_names_order = "bottom_first";
    bool use_vulkan = false;
};

// HillClimbingSolver 类
class HillClimbingSolver {
public:
    HillClimbingSolver(const PhysGPRModel& model, const SolverConfig& config);
    ~HillClimbingSolver();
    
    // 为多个目标颜色求解最优配方
    // target_rgb: (N, 3) RGB颜色值，范围[0, 1]
    // 返回: (N, n_layers) 材料索引
    std::vector<int32_t> solve(const std::vector<float>& target_rgb, int n_targets);
    
    // 批量预测配方颜色
    // recipe_indices: (N, n_layers) 材料索引
    // 返回: (N, 3) Lab颜色值
    std::vector<float> predict_batch(const std::vector<int32_t>& recipe_indices, int n_samples);
    
    // 获取材料数量
    int get_num_materials() const { return num_materials_; }
    
private:
    // 内部辅助函数
    std::vector<float> predict_four_flux(const std::vector<int32_t>& sequences, int n_seq);
    std::vector<float> predict_four_flux_vulkan(const std::vector<int32_t>& sequences, int n_seq);

    std::vector<float> predict_rt_slab(const std::vector<int32_t>& sequences, int n_seq);
    std::vector<float> predict_rt_slab_vulkan(const std::vector<int32_t>& sequences, int n_seq);
    std::vector<float> build_gpr_features(const std::vector<int32_t>& recipe_indices,
                                          int n_samples,
                                          const std::vector<float>& base_lab);
    std::vector<float> predict_gpr_vulkan3(const std::vector<float>& X, int n_samples);
    std::vector<float> predict_gpr(const GPRParams& gpr, const std::vector<float>& X);
    
    // RGB <-> Lab 转换
    void rgb01_to_lab(const float* rgb, float* lab) const;
    void lab_to_rgb01(const float* lab, float* rgb) const;
    
    // Sigmoid函数
    static float sigmoid(float x);
    
    PhysGPRModel model_;
    SolverConfig config_;
    int num_materials_;
    std::unique_ptr<HillClimbingSolverVulkanState> vk_state_;
};

// 创建求解器的工厂函数
std::unique_ptr<HillClimbingSolver> create_solver(const PhysGPRModel& model, 
                                                   const SolverConfig& config);

} // namespace solver
} // namespace opencolor
