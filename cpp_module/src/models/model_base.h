#pragma once

#include <vector>
#include <string>
#include <memory>
#include <functional>
#include <unordered_map>
#include <cstdint>

namespace opencolor {
namespace models {

/**
 * 预测结果结构体
 * 包含RGB和Lab颜色空间的预测结果
 */
struct PredictionResult {
    // RGB颜色值 [0, 1] 范围
    float rgb[3];
    // Lab颜色值
    float lab[3];
    // 可选的额外信息（如置信度、不确定性等）
    float metadata[4];
    
    PredictionResult() : rgb{0.0f, 0.0f, 0.0f}, lab{0.0f, 0.0f, 0.0f}, metadata{0.0f, 0.0f, 0.0f, 0.0f} {}
};

/**
 * 输入参数结构体
 * 包含模型预测所需的所有输入数据
 */
struct PredictionInput {
    // 材料参数（每个材料3个通道RGB）
    std::vector<float> mu_a;      // 吸收系数 (num_materials * 3)
    std::vector<float> mu_s;      // 散射系数 (num_materials * 3)
    std::vector<float> g;         // 各向异性参数 (num_materials * 3)
    
    // 序列索引 (num_sequences * max_length)
    std::vector<std::int32_t> sequences;
    int num_sequences = 0;
    int max_sequence_length = 0;
    int num_materials = 0;
    
    // 背板和表面修正参数
    float backing_reflectance = 0.98f;
    float k1 = 0.0f;  // Saunderson修正参数1
    float k2 = 0.0f;  // Saunderson修正参数2
    
    // 可选的额外参数
    std::unordered_map<std::string, float> extra_params;
};

/**
 * 模型能力描述
 */
struct ModelCapabilities {
    bool supports_gpu = false;           // 是否支持GPU加速
    bool supports_cpu = true;            // 是否支持CPU计算
    bool supports_batch = true;          // 是否支持批量预测
    bool requires_training = false;      // 是否需要训练
    int max_sequence_length = 64;        // 最大支持的序列长度
    int max_materials = 256;             // 最大支持的材料数量
    std::string description;             // 模型描述
    std::string version = "1.0.0";       // 模型版本
};

/**
 * 颜色预测模型基类
 * 
 * 所有具体的预测模型都需要继承此类并实现纯虚函数
 * 使用示例：
 *   auto model = ModelRegistry::create("four_flux");
 *   auto result = model->predict(input);
 */
class ColorPredictionModel {
public:
    virtual ~ColorPredictionModel() = default;
    
    /**
     * 获取模型类型标识符
     */
    virtual std::string get_type() const = 0;
    
    /**
     * 获取模型能力描述
     */
    virtual ModelCapabilities get_capabilities() const = 0;
    
    /**
     * 执行颜色预测
     * 
     * @param input 输入参数
     * @return 预测结果数组（大小为 num_sequences）
     */
    virtual std::vector<PredictionResult> predict(const PredictionInput& input) = 0;
    
    /**
     * 批量预测（默认实现为逐个调用predict，子类可重写以优化性能）
     * 
     * @param inputs 输入参数数组
     * @return 预测结果数组
     */
    virtual std::vector<std::vector<PredictionResult>> predict_batch(
        const std::vector<PredictionInput>& inputs);
    
    /**
     * 初始化模型
     * 
     * @param config 配置参数字符串（JSON格式或其他）
     * @return 是否初始化成功
     */
    virtual bool initialize(const std::string& config = "") = 0;
    
    /**
     * 释放模型资源
     */
    virtual void release() = 0;
    
    /**
     * 检查模型是否已初始化
     */
    virtual bool is_initialized() const = 0;
    
    /**
     * 获取模型特定的参数信息
     * 返回参数名称、类型、默认值等元信息
     */
    virtual std::string get_parameter_info() const = 0;
};

/**
 * 模型创建函数类型
 */
using ModelCreateFunc = std::function<std::unique_ptr<ColorPredictionModel>()>;

/**
 * 模型注册表
 * 
 * 使用工厂模式管理所有模型的创建
 * 支持运行时动态注册和创建模型
 */
class ModelRegistry {
public:
    /**
     * 注册模型类型
     * 
     * @param type 模型类型标识符
     * @param create_func 模型创建函数
     * @param capabilities 模型能力描述
     * @return 是否注册成功
     */
    static bool register_model(
        const std::string& type,
        ModelCreateFunc create_func,
        const ModelCapabilities& capabilities = ModelCapabilities()
    );
    
    /**
     * 创建模型实例
     * 
     * @param type 模型类型标识符
     * @return 模型实例指针（失败返回nullptr）
     */
    static std::unique_ptr<ColorPredictionModel> create(const std::string& type);
    
    /**
     * 检查模型类型是否已注册
     */
    static bool is_registered(const std::string& type);
    
    /**
     * 获取所有已注册的模型类型
     */
    static std::vector<std::string> get_registered_types();
    
    /**
     * 获取模型的能力描述
     */
    static ModelCapabilities get_capabilities(const std::string& type);
    
    /**
     * 注销模型类型
     */
    static bool unregister_model(const std::string& type);
    
private:
    struct RegistryEntry {
        ModelCreateFunc create_func;
        ModelCapabilities capabilities;
    };
    
    static std::unordered_map<std::string, RegistryEntry>& get_registry();
};

/**
 * 模型注册辅助宏
 * 用于简化模型注册过程
 */
#define REGISTER_COLOR_MODEL(ModelClass, type_id, ...) \
    namespace { \
        struct ModelClass##Registrar { \
            ModelClass##Registrar() { \
                opencolor::models::ModelCapabilities caps{__VA_ARGS__}; \
                opencolor::models::ModelRegistry::register_model( \
                    type_id, \
                    []() -> std::unique_ptr<opencolor::models::ColorPredictionModel> { \
                        return std::make_unique<ModelClass>(); \
                    }, \
                    caps \
                ); \
            } \
        }; \
        static ModelClass##Registrar g_##ModelClass##_registrar; \
    }

} // namespace models
} // namespace opencolor
