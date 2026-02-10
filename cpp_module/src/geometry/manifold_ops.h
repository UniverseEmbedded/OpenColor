#pragma once

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <manifold/manifold.h>
#include <utility>

namespace py = pybind11;

// Manifold 网格转换
manifold::Manifold manifold_from_mesh(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> faces
);

std::pair<py::array_t<double>, py::array_t<int32_t>> mesh_from_manifold(const manifold::Manifold& m);

// Manifold 布尔运算
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_union(const py::iterable& meshes);
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_union_nogil(const py::iterable& meshes);

std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_difference(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
);

std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_difference_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
);

std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_intersection(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
);

std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_intersection_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
);

// 体积计算
double manifold_volume(
    py::array_t<double, py::array::c_style | py::array::forcecast> v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> f
);

double manifold_volume_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> f
);
