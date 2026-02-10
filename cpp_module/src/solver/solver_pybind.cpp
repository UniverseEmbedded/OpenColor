#include "hill_climbing_solver.h"
#include "icm_joint_optimizer.h"
#include "vulkan_recipe_map.h"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <cstring>

namespace py = pybind11;
using namespace opencolor::solver;

/**
 * 从Python字典加载GPR（高斯过程回归）参数
 * 
 * @param gpr_dict Python字典，包含GPR模型参数
 * @return 填充好的GPRParams结构体
 * 
 * GPR参数说明：
 * - X_train: 训练数据特征
 * - alpha: GPR模型的alpha系数
 * - x_mean/x_std: 输入特征的标准化参数
 * - y_mean/y_std: 输出目标的标准化参数
 * - lengthscale: 核函数的长度尺度参数
 * - signal_var: 信号方差
 * - noise: 噪声方差
 */
static GPRParams load_gpr_from_python(py::dict gpr_dict) {
    GPRParams gpr;
    
    // 从Python字典中提取numpy数组并转换为C++数组
    py::array_t<float> X_train = gpr_dict["X_train"].cast<py::array_t<float>>();
    py::array_t<float> alpha = gpr_dict["alpha"].cast<py::array_t<float>>();
    py::array_t<float> x_mean = gpr_dict["x_mean"].cast<py::array_t<float>>();
    py::array_t<float> x_std = gpr_dict["x_std"].cast<py::array_t<float>>();
    
    // 调整C++向量大小以容纳数据
    gpr.X_train.resize(X_train.size());
    gpr.alpha.resize(alpha.size());
    gpr.x_mean.resize(x_mean.size());
    gpr.x_std.resize(x_std.size());
    
    // 使用memcpy高效复制数据（比逐个元素复制更快）
    std::memcpy(gpr.X_train.data(), X_train.data(), sizeof(float) * X_train.size());
    std::memcpy(gpr.alpha.data(), alpha.data(), sizeof(float) * alpha.size());
    std::memcpy(gpr.x_mean.data(), x_mean.data(), sizeof(float) * x_mean.size());
    std::memcpy(gpr.x_std.data(), x_std.data(), sizeof(float) * x_std.size());
    
    // 提取标量参数
    gpr.y_mean = gpr_dict["y_mean"].cast<float>();
    gpr.y_std = gpr_dict["y_std"].cast<float>();
    gpr.lengthscale = gpr_dict["lengthscale"].cast<float>();
    gpr.signal_var = gpr_dict["signal_var"].cast<float>();
    gpr.noise = gpr_dict["noise"].cast<float>();
    
    return gpr;
}

/**
 * 从Python加载完整的物理GPR模型
 * 
 * @param optical_dict 光学参数字典（吸收系数、散射系数等）
 * @param gpr_L_dict L通道的GPR模型参数
 * @param gpr_a_dict a通道的GPR模型参数
 * @param gpr_b_dict b通道的GPR模型参数
 * @param feature_names 特征名称列表
 * @return 填充好的PhysGPRModel结构体
 * 
 * 光学参数说明：
 * - mu_a: 吸收系数（absorption coefficient）
 * - mu_s: 散射系数（scattering coefficient）
 * - g: 各向异性因子（anisotropy factor）
 * - alpha/beta/gamma: 可选的额外光学参数
 * - n_layers: 层数
 * - k1/k2: 光学模型常数
 * - backing: 背衬反射率
 * - material_keys: 材料键值列表
 */
static PhysGPRModel load_model_from_python(
    py::dict optical_dict,
    py::dict gpr_L_dict,
    py::dict gpr_a_dict,
    py::dict gpr_b_dict,
    std::vector<std::string> feature_names
) {
    PhysGPRModel model;
    
    // 加载光学参数
    py::array_t<float> mu_a = optical_dict["mu_a"].cast<py::array_t<float>>();
    py::array_t<float> mu_s = optical_dict["mu_s"].cast<py::array_t<float>>();
    py::array_t<float> g = optical_dict["g"].cast<py::array_t<float>>();
    
    // 调整向量大小并复制数据
    model.optical.mu_a.resize(mu_a.size());
    model.optical.mu_s.resize(mu_s.size());
    model.optical.g.resize(g.size());
    
    std::memcpy(model.optical.mu_a.data(), mu_a.data(), sizeof(float) * mu_a.size());
    std::memcpy(model.optical.mu_s.data(), mu_s.data(), sizeof(float) * mu_s.size());
    std::memcpy(model.optical.g.data(), g.data(), sizeof(float) * g.size());

    // 如果存在alpha/beta/gamma参数，也一并加载
    if (optical_dict.contains("alpha") && optical_dict.contains("beta") && optical_dict.contains("gamma")) {
        py::array_t<float> alpha = optical_dict["alpha"].cast<py::array_t<float>>();
        py::array_t<float> beta = optical_dict["beta"].cast<py::array_t<float>>();
        py::array_t<float> gamma = optical_dict["gamma"].cast<py::array_t<float>>();

        model.optical.alpha.resize(alpha.size());
        model.optical.beta.resize(beta.size());
        model.optical.gamma.resize(gamma.size());

        std::memcpy(model.optical.alpha.data(), alpha.data(), sizeof(float) * alpha.size());
        std::memcpy(model.optical.beta.data(), beta.data(), sizeof(float) * beta.size());
        std::memcpy(model.optical.gamma.data(), gamma.data(), sizeof(float) * gamma.size());
    }
    
    // 加载其他光学参数
    model.optical.n_layers = optical_dict["n_layers"].cast<int>();
    model.optical.k1 = optical_dict["k1"].cast<float>();
    model.optical.k2 = optical_dict["k2"].cast<float>();
    model.optical.backing = optical_dict["backing"].cast<float>();
    model.optical.material_keys = optical_dict["material_keys"].cast<std::vector<std::string>>();
    
    // 加载三个颜色通道（Lab）的GPR模型
    model.gpr_L = load_gpr_from_python(gpr_L_dict);  // L通道（亮度）
    model.gpr_a = load_gpr_from_python(gpr_a_dict);  // a通道（红绿）
    model.gpr_b = load_gpr_from_python(gpr_b_dict);  // b通道（黄蓝）
    
    model.feature_names = feature_names;
    
    return model;
}

/**
 * Python包装类：为C++求解器提供Python接口
 * 
 * 这个类作为Python和C++之间的桥梁，处理：
 * 1. Python数据类型到C++数据类型的转换
 * 2. GIL（全局解释器锁）的管理
 * 3. 异常处理和错误检查
 */
class HillClimbingSolverPy {
public:
    /**
     * 构造函数：从Python参数创建求解器
     * 
     * @param optical_dict 光学参数字典
     * @param gpr_L_dict L通道GPR参数
     * @param gpr_a_dict a通道GPR参数
     * @param gpr_b_dict b通道GPR参数
     * @param feature_names 特征名称列表
     * @param n_random_samples 随机采样数量（初始搜索）
     * @param hill_climb_iterations 爬山算法迭代次数
     * @param n_layers 层数
     * @param layer_names_order 层顺序（"bottom_first"或"top_first"）
     * @param use_vulkan 是否使用Vulkan GPU加速
     */
    HillClimbingSolverPy(
        py::dict optical_dict,
        py::dict gpr_L_dict,
        py::dict gpr_a_dict,
        py::dict gpr_b_dict,
        std::vector<std::string> feature_names,
        int n_random_samples,
        int hill_climb_iterations,
        int n_layers,
        std::string layer_names_order,
        bool use_vulkan
    ) {
        // 加载模型数据
        PhysGPRModel model = load_model_from_python(
            optical_dict, gpr_L_dict, gpr_a_dict, gpr_b_dict, feature_names
        );
        
        // 配置求解器参数
        SolverConfig config;
        config.n_random_samples = n_random_samples;           // 随机采样数
        config.hill_climb_iterations = hill_climb_iterations; // 爬山迭代次数
        config.n_layers = n_layers;                           // 层数
        config.layer_names_order = layer_names_order;         // 层顺序
        config.use_vulkan = use_vulkan;                       // 是否使用GPU

        config_n_layers_ = n_layers;
        
        // 创建实际的C++求解器实例
        solver_ = create_solver(model, config);
    }
    
    /**
     * 求解最优配方
     * 
     * @param target_rgb 目标RGB颜色数组，形状为(N, 3)
     * @return 配方索引数组，形状为(N, n_layers)
     * 
     * 算法流程：
     * 1. 验证输入数组形状
     * 2. 复制数据到C++向量
     * 3. 释放GIL，允许Python其他线程运行
     * 4. 调用C++求解器进行计算
     * 5. 重新获取GIL，返回结果
     */
    py::array_t<int32_t> solve(py::array_t<float, py::array::c_style | py::array::forcecast> target_rgb) {
        // 验证输入数组维度：必须是(N, 3)的二维数组
        if (target_rgb.ndim() != 2 || target_rgb.shape(1) != 3) {
            throw std::runtime_error("target_rgb必须是(N, 3)的数组");
        }
        
        // 获取目标颜色数量
        int n_targets = static_cast<int>(target_rgb.shape(0));
        // 复制数据到C++向量
        std::vector<float> target(target_rgb.size());
        std::memcpy(target.data(), target_rgb.data(), sizeof(float) * target.size());

        // 调用求解器
        std::vector<int32_t> result;
        {
            // 释放GIL（全局解释器锁），允许Python其他线程执行
            // 这在长时间计算时非常重要，可以避免阻塞Python解释器
            py::gil_scoped_release release;
            result = solver_->solve(target, n_targets);
        }
        // GIL在这里自动重新获取

        // 将结果转换为Python numpy数组
        const py::ssize_t n_layers = static_cast<py::ssize_t>(config_n_layers_);
        py::array_t<int32_t> out({static_cast<py::ssize_t>(n_targets), n_layers});
        std::memcpy(out.mutable_data(), result.data(), sizeof(int32_t) * result.size());
        return out;
    }
    
    /**
     * 批量预测颜色
     * 
     * @param recipe_indices 配方索引数组，形状为(N, n_layers)
     * @return 预测的RGB颜色数组，形状为(N, 3)
     * 
     * 用于根据配方索引预测最终颜色，可用于验证求解结果
     */
    py::array_t<float> predict_batch(py::array_t<int32_t, py::array::c_style | py::array::forcecast> recipe_indices) {
        // 验证输入必须是二维数组
        if (recipe_indices.ndim() != 2) {
            throw std::runtime_error("recipe_indices必须是二维数组");
        }
        
        // 获取样本数量
        int n_samples = static_cast<int>(recipe_indices.shape(0));
        // 复制数据到C++向量
        std::vector<int32_t> indices(recipe_indices.size());
        std::memcpy(indices.data(), recipe_indices.data(), sizeof(int32_t) * indices.size());

        // 调用预测函数
        std::vector<float> result;
        {
            // 释放GIL，允许并行执行
            py::gil_scoped_release release;
            result = solver_->predict_batch(indices, n_samples);
        }

        // 转换为Python数组，形状为(N, 3)表示RGB三个通道
        py::array_t<float> out({static_cast<py::ssize_t>(n_samples), static_cast<py::ssize_t>(3)});
        std::memcpy(out.mutable_data(), result.data(), sizeof(float) * result.size());
        return out;
    }
    
public:
    std::unique_ptr<HillClimbingSolver> solver_;  // C++求解器实例
    int config_n_layers_ = 5;                     // 保存层数配置，用于输出形状
};

/**
 * 测试函数：检查模块是否正确加载
 * @return 测试字符串
 */
static std::string ping() {
    return "pong from opencolor_solver (C++)";
}

/**
 * 模块定义：使用pybind11导出Python模块
 * 
 * 导出的Python接口：
 * - opencolor_solver.ping(): 测试函数
 * - opencolor_solver.HillClimbingSolver: 主求解器类
 *   - __init__(...): 构造函数，接受模型参数和配置
 *   - solve(target_rgb): 求解最优配方
 *   - predict_batch(recipe_indices): 批量预测颜色
 */
PYBIND11_MODULE(opencolor_solver, m) {
    m.doc() = "OpenColor HillClimbingSolver C++加速模块\n"
              "\n"
              "该模块提供了基于爬山算法的颜色配方求解器，\n"
              "使用C++实现以获得更高的计算性能。\n"
              "支持CPU和Vulkan GPU加速。";
    
    // 导出测试函数
    m.def("ping", &ping, "测试模块是否正常工作，返回'pong'表示成功");
    
    // 导出HillClimbingSolver类
    py::class_<HillClimbingSolverPy>(m, "HillClimbingSolver")
        .def(py::init<py::dict, py::dict, py::dict, py::dict, std::vector<std::string>,
                      int, int, int, std::string, bool>(),
             py::arg("optical"),           // 光学参数字典
             py::arg("gpr_L"),             // L通道GPR模型
             py::arg("gpr_a"),             // a通道GPR模型
             py::arg("gpr_b"),             // b通道GPR模型
             py::arg("feature_names"),     // 特征名称列表
             py::arg("n_random_samples") = 1000,      // 随机采样数（默认1000）
             py::arg("hill_climb_iterations") = 10,   // 爬山迭代次数（默认10）
             py::arg("n_layers") = 5,                 // 层数（默认5）
             py::arg("layer_names_order") = "bottom_first",  // 层顺序
             py::arg("use_vulkan") = false)           // 是否使用GPU（默认否）
        .def("solve", &HillClimbingSolverPy::solve, 
             "求解最优配方\n"
             "\n"
             "参数:\n"
             "  target_rgb: numpy数组，形状为(N, 3)，表示N个目标RGB颜色\n"
             "\n"
             "返回:\n"
             "  numpy数组，形状为(N, n_layers)，表示最优配方索引",
             py::arg("target_rgb"))
        .def("predict_batch", &HillClimbingSolverPy::predict_batch, 
             "批量预测颜色\n"
             "\n"
             "参数:\n"
             "  recipe_indices: numpy数组，形状为(N, n_layers)，表示N个配方\n"
             "\n"
             "返回:\n"
             "  numpy数组，形状为(N, 3)，表示预测的RGB颜色",
             py::arg("recipe_indices"));
    
    // ICM联合优化器Python包装类
    class ICMJointOptimizerPy {
    public:
        ICMJointOptimizerPy(HillClimbingSolverPy* solver,
                            int n_slots,
                            int n_layers,
                            int h, int w,
                            py::dict config_dict) {
            // 从Python字典加载配置
            ICMJointOptimizerConfig config;
            if (config_dict.contains("passes")) config.passes = config_dict["passes"].cast<int>();
            if (config_dict.contains("lambda_smooth")) config.lambda_smooth = config_dict["lambda_smooth"].cast<float>();
            if (config_dict.contains("color_weight")) config.color_weight = config_dict["color_weight"].cast<float>();
            if (config_dict.contains("slack_de76")) config.slack_de76 = config_dict["slack_de76"].cast<float>();
            if (config_dict.contains("edge_beta")) config.edge_beta = config_dict["edge_beta"].cast<float>();
            if (config_dict.contains("max_candidates")) config.max_candidates = config_dict["max_candidates"].cast<int>();
            if (config_dict.contains("proposal_radius")) config.proposal_radius = config_dict["proposal_radius"].cast<int>();
            if (config_dict.contains("proposal_eps")) config.proposal_eps = config_dict["proposal_eps"].cast<float>();
            if (config_dict.contains("proposal_min_soft_margin")) config.proposal_min_soft_margin = config_dict["proposal_min_soft_margin"].cast<float>();
            if (config_dict.contains("proposal_despickle_iters")) config.proposal_despickle_iters = config_dict["proposal_despickle_iters"].cast<int>();
            if (config_dict.contains("mix_sigma")) config.mix_sigma = config_dict["mix_sigma"].cast<float>();
            if (config_dict.contains("mix_weight")) config.mix_weight = config_dict["mix_weight"].cast<float>();
            if (config_dict.contains("mix_max_increase_de76")) config.mix_max_increase_de76 = config_dict["mix_max_increase_de76"].cast<float>();
            if (config_dict.contains("mix_base_slack_de76")) config.mix_base_slack_de76 = config_dict["mix_base_slack_de76"].cast<float>();
            if (config_dict.contains("island_weight")) config.island_weight = config_dict["island_weight"].cast<float>();
            if (config_dict.contains("island_alpha")) config.island_alpha = config_dict["island_alpha"].cast<float>();
            if (config_dict.contains("remove_islands_max_area_px")) config.remove_islands_max_area_px = config_dict["remove_islands_max_area_px"].cast<int>();
            if (config_dict.contains("remove_islands_connectivity")) config.remove_islands_connectivity = config_dict["remove_islands_connectivity"].cast<int>();
            if (config_dict.contains("remove_islands_passes")) config.remove_islands_passes = config_dict["remove_islands_passes"].cast<int>();
            if (config_dict.contains("structure_protect")) config.structure_protect = config_dict["structure_protect"].cast<bool>();
            if (config_dict.contains("structure_protect_strength")) config.structure_protect_strength = config_dict["structure_protect_strength"].cast<float>();
            
            // 创建优化器
            optimizer_ = create_icm_optimizer(solver->solver_.get(), n_slots, n_layers, h, w, config);
        }
        
        py::array_t<int32_t> optimize(py::array_t<int32_t, py::array::c_style | py::array::forcecast> recipes,
                                      py::array_t<int32_t, py::array::c_style | py::array::forcecast> ys,
                                      py::array_t<int32_t, py::array::c_style | py::array::forcecast> xs,
                                      py::array_t<float, py::array::c_style | py::array::forcecast> pix_rgb01,
                                      py::array_t<float, py::array::c_style | py::array::forcecast> guidance_gray01,
                                      py::array_t<uint8_t, py::array::c_style | py::array::forcecast> full_mask,
                                      int layer_start = 0,
                                      int layer_end = -1) {
            // 验证输入
            if (recipes.ndim() != 2) throw std::runtime_error("recipes必须是二维数组");
            if (ys.ndim() != 1 || xs.ndim() != 1) throw std::runtime_error("ys和xs必须是一维数组");
            if (pix_rgb01.ndim() != 2 || pix_rgb01.shape(1) != 3) throw std::runtime_error("pix_rgb01必须是(N, 3)的数组");
            if (guidance_gray01.ndim() != 2) throw std::runtime_error("guidance_gray01必须是二维数组");
            if (full_mask.ndim() != 2) throw std::runtime_error("full_mask必须是二维数组");
            
            // 复制数据到C++向量
            std::vector<int32_t> recipes_vec(recipes.size());
            std::vector<int32_t> ys_vec(ys.size());
            std::vector<int32_t> xs_vec(xs.size());
            std::vector<float> pix_rgb01_vec(pix_rgb01.size());
            std::vector<float> guidance_gray01_vec(guidance_gray01.size());
            std::vector<uint8_t> full_mask_vec(full_mask.size());
            
            std::memcpy(recipes_vec.data(), recipes.data(), sizeof(int32_t) * recipes.size());
            std::memcpy(ys_vec.data(), ys.data(), sizeof(int32_t) * ys.size());
            std::memcpy(xs_vec.data(), xs.data(), sizeof(int32_t) * xs.size());
            std::memcpy(pix_rgb01_vec.data(), pix_rgb01.data(), sizeof(float) * pix_rgb01.size());
            std::memcpy(guidance_gray01_vec.data(), guidance_gray01.data(), sizeof(float) * guidance_gray01.size());
            std::memcpy(full_mask_vec.data(), full_mask.data(), sizeof(uint8_t) * full_mask.size());
            
            // 执行优化
            {
                py::gil_scoped_release release;
                optimizer_->optimize(recipes_vec, ys_vec, xs_vec, pix_rgb01_vec, 
                                    guidance_gray01_vec, full_mask_vec, layer_start, layer_end);
            }
            
            // 返回结果
            py::array_t<int32_t> out({static_cast<py::ssize_t>(recipes.shape(0)), 
                                      static_cast<py::ssize_t>(recipes.shape(1))});
            std::memcpy(out.mutable_data(), recipes_vec.data(), sizeof(int32_t) * recipes_vec.size());
            return out;
        }
        
    private:
        std::unique_ptr<ICMJointOptimizer> optimizer_;
    };
    
    // 导出ICMJointOptimizer类
    py::class_<ICMJointOptimizerPy>(m, "ICMJointOptimizer")
        .def(py::init<HillClimbingSolverPy*, int, int, int, int, py::dict>(),
             py::arg("solver"),
             py::arg("n_slots"),
             py::arg("n_layers"),
             py::arg("h"),
             py::arg("w"),
             py::arg("config"))
        .def("optimize", &ICMJointOptimizerPy::optimize,
             "执行ICM联合优化\n"
             "\n"
             "参数:\n"
             "  recipes: numpy数组，形状为(N, n_layers)，表示配方\n"
             "  ys: numpy数组，形状为(N,)，表示y坐标\n"
             "  xs: numpy数组，形状为(N,)，表示x坐标\n"
             "  pix_rgb01: numpy数组，形状为(N, 3)，表示目标RGB颜色\n"
             "  guidance_gray01: numpy数组，形状为(h, w)，表示引导图像\n"
             "  full_mask: numpy数组，形状为(h, w)，表示ROI掩码\n"
             "  layer_start: 起始层索引（默认0）\n"
             "  layer_end: 结束层索引（默认-1表示所有层）\n"
             "\n"
             "返回:\n"
             "  numpy数组，形状为(N, n_layers)，表示优化后的配方",
             py::arg("recipes"),
             py::arg("ys"),
             py::arg("xs"),
             py::arg("pix_rgb01"),
             py::arg("guidance_gray01"),
             py::arg("full_mask"),
             py::arg("layer_start") = 0,
             py::arg("layer_end") = -1);
    
    // VulkanRecipeMapper Python包装类
    class VulkanRecipeMapperPy {
    public:
        VulkanRecipeMapperPy() {
            mapper_ = std::make_unique<VulkanRecipeMapper>();
        }
        
        py::array_t<int32_t> map_recipes(
            py::array_t<int32_t, py::array::c_style | py::array::forcecast> recipes,
            py::array_t<int32_t, py::array::c_style | py::array::forcecast> inverse,
            int n_colors,
            int n_slots = 8
        ) {
            // 验证输入
            if (recipes.ndim() != 2) throw std::runtime_error("recipes必须是二维数组");
            if (inverse.ndim() != 1) throw std::runtime_error("inverse必须是一维数组");
            
            int n_pixels = static_cast<int>(recipes.shape(0));
            int n_layers = static_cast<int>(recipes.shape(1));
            
            if (inverse.shape(0) != n_pixels) {
                throw std::runtime_error("inverse长度必须与recipes行数相同");
            }
            
            // 创建输出数组
            py::array_t<int32_t> output({n_colors, n_layers});
            
            // 执行GPU映射
            mapper_->map_recipes(
                static_cast<const int32_t*>(recipes.data()),
                static_cast<const int32_t*>(inverse.data()),
                static_cast<int32_t*>(output.mutable_data()),
                n_pixels,
                n_colors,
                n_layers,
                n_slots
            );
            
            return output;
        }
        
    private:
        std::unique_ptr<VulkanRecipeMapper> mapper_;
    };
    
    // 导出VulkanRecipeMapper类
    py::class_<VulkanRecipeMapperPy>(m, "VulkanRecipeMapper")
        .def(py::init<>(),
             "创建Vulkan配方映射器\n"
             "\n"
             "需要Vulkan GPU支持")
        .def("map_recipes", &VulkanRecipeMapperPy::map_recipes,
             "执行GPU加速的配方映射\n"
             "\n"
             "参数:\n"
             "  recipes: numpy数组，形状为(n_pixels, n_layers)，像素级配方\n"
             "  inverse: numpy数组，形状为(n_pixels,)，像素到颜色的映射\n"
             "  n_colors: 颜色总数\n"
             "  n_slots: slot数量（默认8）\n"
             "\n"
             "返回:\n"
             "  numpy数组，形状为(n_colors, n_layers)，颜色级配方",
             py::arg("recipes"),
             py::arg("inverse"),
             py::arg("n_colors"),
             py::arg("n_slots") = 8);
}
