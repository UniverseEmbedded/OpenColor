#pragma once

#include "model_base.h"

namespace opencolor {
namespace models {

/**
 * 新模型模板
 * 
 * 这是一个示例模板，展示如何实现一个新的颜色预测模型。
 * 复制此文件并重命名，然后按照注释修改即可。
 * 
 * 步骤：
 * 1. 复制此文件和对应的 .cpp 文件
 * 2. 重命名类名（如 MyNewModel）
 * 3. 修改 REGISTER_COLOR_MODEL 中的模型类型标识符
 * 4. 实现所有纯虚函数
 * 5. 添加模型特有的方法和参数
 * 6. 在 CMakeLists.txt 中添加新文件
 * 7. 重新编译
 */
class NewModelTemplate : public ColorPredictionModel {
public:
    NewModelTemplate();
    ~NewModelTemplate() override;
    
    // 禁用拷贝和赋值
    NewModelTemplate(const NewModelTemplate&) = delete;
    NewModelTemplate& operator=(const NewModelTemplate&) = delete;
    
    // ==================== 必须实现的接口 ====================
    
    /**
     * 获取模型类型标识符
     * 返回一个唯一的字符串标识符，如 "my_new_model"
     */
    std::string get_type() const override;
    
    /**
     * 获取模型能力描述
     * 描述模型的能力和限制
     */
    ModelCapabilities get_capabilities() const override;
    
    /**
     * 执行颜色预测
     * 这是模型的核心功能
     * 
     * @param input 包含所有输入参数的结构体
     * @return 每个序列的预测结果数组
     */
    std::vector<PredictionResult> predict(const PredictionInput& input) override;
    
    /**
     * 初始化模型
     * 
     * @param config 配置字符串（可以是JSON格式）
     * @return 初始化是否成功
     */
    bool initialize(const std::string& config = "") override;
    
    /**
     * 释放模型资源
     * 清理所有分配的资源
     */
    void release() override;
    
    /**
     * 检查模型是否已初始化
     */
    bool is_initialized() const override;
    
    /**
     * 获取模型特定的参数信息
     * 返回JSON格式的参数描述
     */
    std::string get_parameter_info() const override;
    
    // ==================== 可选：模型特定的方法和参数 ====================
    
    // 示例：设置是否使用GPU
    void set_use_gpu(bool use_gpu);
    bool get_use_gpu() const;
    
    // 示例：设置模型特定参数
    void set_custom_param(float param) { custom_param_ = param; }
    float get_custom_param() const { return custom_param_; }
    
private:
    // CPU实现
    std::vector<PredictionResult> predict_cpu(const PredictionInput& input);
    
    // GPU实现（如果需要）
    std::vector<PredictionResult> predict_gpu(const PredictionInput& input);
    
    // RGB转Lab辅助函数
    void rgb_to_lab(const float rgb[3], float lab[3]) const;
    
    // 内部状态
    bool initialized_ = false;
    bool use_gpu_ = false;
    
    // 模型特定参数
    float custom_param_ = 1.0f;
    
    // 可以添加更多内部状态...
};

} // namespace models
} // namespace opencolor
