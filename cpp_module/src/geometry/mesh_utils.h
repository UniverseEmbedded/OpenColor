#pragma once

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <cstdint>
#include <string>
#include <tuple>
#include <utility>

namespace py = pybind11;

// 面键值结构
struct FaceKey {
    uint32_t a;
    uint32_t b;
    uint32_t c;
};

struct FaceKeyWithFace {
    FaceKey k;
    std::array<int32_t, 3> f;
};

// 网格清理
std::tuple<py::array_t<double>, py::array_t<int32_t>, py::dict> mesh_clean_basic_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int64_t, py::array::c_style | py::array::forcecast> faces
);

// 网格分析
py::dict mesh_analyze_basic_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int64_t, py::array::c_style | py::array::forcecast> faces
);

// STL 导出
void write_binary_stl_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int64_t, py::array::c_style | py::array::forcecast> faces,
    const std::string& file_path
);
