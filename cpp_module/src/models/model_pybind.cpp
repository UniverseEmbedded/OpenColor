#include "models.h"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

namespace py = pybind11;
using namespace opencolor::models;

// 获取所有注册的模型类型
static py::list get_registered_model_types() {
    py::list types;
    for (const auto& type : ModelRegistry::get_registered_types()) {
        types.append(type);
    }
    return types;
}

// 获取模型能力
static py::dict get_model_capabilities(const std::string& type) {
    auto caps = ModelRegistry::get_capabilities(type);
    py::dict dict;
    dict["supports_gpu"] = caps.supports_gpu;
    dict["supports_cpu"] = caps.supports_cpu;
    dict["supports_batch"] = caps.supports_batch;
    dict["requires_training"] = caps.requires_training;
    dict["max_sequence_length"] = caps.max_sequence_length;
    dict["max_materials"] = caps.max_materials;
    dict["description"] = caps.description;
    dict["version"] = caps.version;
    return dict;
}

PYBIND11_MODULE(opencolor_models, m) {
    m.doc() = "OpenColor 颜色预测模型模块";
    
    // 版本信息
    m.def("get_version", &get_models_version, "获取模块版本");
    m.def("initialize", &initialize_models, "初始化模型模块");
    
    // 模型注册表接口
    m.def("list_models", &get_registered_model_types, "获取所有已注册的模型类型");
    m.def("has_model", &ModelRegistry::is_registered, "检查模型类型是否已注册",
          py::arg("model_type"));
    m.def("get_capabilities", &get_model_capabilities, "获取模型能力描述",
          py::arg("model_type"));
    
    // ModelCapabilities结构体
    py::class_<ModelCapabilities>(m, "ModelCapabilities")
        .def_readonly("supports_gpu", &ModelCapabilities::supports_gpu, "是否支持GPU加速")
        .def_readonly("supports_cpu", &ModelCapabilities::supports_cpu, "是否支持CPU计算")
        .def_readonly("supports_batch", &ModelCapabilities::supports_batch, "是否支持批量预测")
        .def_readonly("requires_training", &ModelCapabilities::requires_training, "是否需要训练")
        .def_readonly("max_sequence_length", &ModelCapabilities::max_sequence_length, "最大支持的序列长度")
        .def_readonly("max_materials", &ModelCapabilities::max_materials, "最大支持的材料数量")
        .def_readonly("description", &ModelCapabilities::description, "模型描述")
        .def_readonly("version", &ModelCapabilities::version, "模型版本");
    
    // 模型基类
    py::class_<ColorPredictionModel, std::unique_ptr<ColorPredictionModel>>(m, "ColorPredictionModel")
        .def("get_type", &ColorPredictionModel::get_type, "获取模型类型")
        .def("get_capabilities", &ColorPredictionModel::get_capabilities, "获取模型能力")
        .def("initialize", &ColorPredictionModel::initialize, "初始化模型", py::arg("config") = "")
        .def("release", &ColorPredictionModel::release, "释放模型资源")
        .def("is_initialized", &ColorPredictionModel::is_initialized, "检查是否已初始化")
        .def("get_parameter_info", &ColorPredictionModel::get_parameter_info, "获取参数信息");
    
    // 工厂函数
    m.def("create_model", [](const std::string& type) -> std::unique_ptr<ColorPredictionModel> {
        auto model = ModelRegistry::create(type);
        if (!model) {
            throw std::runtime_error("未知的模型类型: " + type);
        }
        return model;
    }, "创建模型实例", py::arg("model_type"));
}
