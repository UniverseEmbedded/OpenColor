#include "model_base.h"

#include <mutex>

namespace opencolor {
namespace models {

// ColorPredictionModel 默认批量预测实现
std::vector<std::vector<PredictionResult>> ColorPredictionModel::predict_batch(
    const std::vector<PredictionInput>& inputs)
{
    std::vector<std::vector<PredictionResult>> results;
    results.reserve(inputs.size());
    
    // 逐个调用单条预测并收集结果
    for (const auto& input : inputs) {
        results.push_back(predict(input));
    }
    
    return results;
}

// ModelRegistry 实现
static std::mutex& get_registry_mutex() {
    // 使用静态局部变量确保线程安全的单例模式
    static std::mutex mutex;
    return mutex;
}

std::unordered_map<std::string, ModelRegistry::RegistryEntry>& ModelRegistry::get_registry() {
    // 使用静态局部变量存储模型注册表
    static std::unordered_map<std::string, RegistryEntry> registry;
    return registry;
}

bool ModelRegistry::register_model(
    const std::string& type,
    ModelCreateFunc create_func,
    const ModelCapabilities& capabilities)
{
    std::lock_guard<std::mutex> lock(get_registry_mutex());
    
    auto& registry = get_registry();
    if (registry.find(type) != registry.end()) {
        // 模型类型已存在，执行覆盖注册
        registry[type] = {create_func, capabilities};
        return true;
    }
    
    // 新模型类型，执行首次注册
    registry.emplace(type, RegistryEntry{create_func, capabilities});
    return true;
}

std::unique_ptr<ColorPredictionModel> ModelRegistry::create(const std::string& type)
{
    std::lock_guard<std::mutex> lock(get_registry_mutex());
    
    auto& registry = get_registry();
    auto it = registry.find(type);
    if (it == registry.end()) {
        // 未找到指定类型的模型，返回空指针
        return nullptr;
    }
    
    // 调用工厂函数创建模型实例
    return it->second.create_func();
}

bool ModelRegistry::is_registered(const std::string& type)
{
    std::lock_guard<std::mutex> lock(get_registry_mutex());
    
    auto& registry = get_registry();
    // 检查指定类型的模型是否已注册
    return registry.find(type) != registry.end();
}

std::vector<std::string> ModelRegistry::get_registered_types()
{
    std::lock_guard<std::mutex> lock(get_registry_mutex());
    
    auto& registry = get_registry();
    std::vector<std::string> types;
    types.reserve(registry.size());
    
    // 收集所有已注册的模型类型名称
    for (const auto& [type, _] : registry) {
        types.push_back(type);
    }
    
    return types;
}

ModelCapabilities ModelRegistry::get_capabilities(const std::string& type)
{
    std::lock_guard<std::mutex> lock(get_registry_mutex());
    
    auto& registry = get_registry();
    auto it = registry.find(type);
    if (it == registry.end()) {
        // 未找到指定类型，返回默认空能力对象
        return ModelCapabilities();
    }
    
    // 返回该类型模型的能力描述
    return it->second.capabilities;
}

bool ModelRegistry::unregister_model(const std::string& type)
{
    std::lock_guard<std::mutex> lock(get_registry_mutex());
    
    auto& registry = get_registry();
    auto it = registry.find(type);
    if (it == registry.end()) {
        // 未找到指定类型，注销失败
        return false;
    }
    
    // 从注册表中移除该模型类型
    registry.erase(it);
    return true;
}

} // namespace models
} // namespace opencolor
