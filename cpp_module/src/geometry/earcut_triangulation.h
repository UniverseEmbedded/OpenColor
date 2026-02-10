#pragma once

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <array>
#include <cstdint>
#include <unordered_set>
#include <vector>

namespace py = pybind11;

using EarcutPoint = std::array<double, 2>;

// 量化键值结构（用于去重）
struct QuantKey {
    int64_t x;
    int64_t y;
};

struct QuantKeyHash {
    size_t operator()(const QuantKey& k) const noexcept {
        const auto h1 = std::hash<int64_t>{}(k.x);
        const auto h2 = std::hash<int64_t>{}(k.y);
        return h1 ^ (h2 + 0x9e3779b97f4a7c15ULL + (h1 << 6) + (h1 >> 2));
    }
};

struct QuantKeyEq {
    bool operator()(const QuantKey& a, const QuantKey& b) const noexcept {
        return a.x == b.x && a.y == b.y;
    }
};

// 基础几何计算
double earcut_dist2(const EarcutPoint& a, const EarcutPoint& b);
double earcut_signed_area(const std::vector<EarcutPoint>& ring);

// 环清洗
double earcut_default_scale();
std::vector<EarcutPoint> clean_ring_cpp(std::vector<EarcutPoint> coords, double eps, double scale, bool remove_global_duplicates = true);

// 三角剖分
std::vector<EarcutPoint> parse_rings_to_earcut_polygon(const py::iterable& rings, std::vector<uint32_t>& ring_end_indices);
std::tuple<py::array_t<double>, py::array_t<uint32_t>, std::vector<uint32_t>, double> earcut_triangulate_rings(const py::iterable& rings);

// 挤出操作
std::pair<py::array_t<double>, py::array_t<int32_t>> extrude_triangulation(
    py::array_t<double, py::array::c_style | py::array::forcecast> verts_2d,
    py::array_t<uint32_t, py::array::c_style | py::array::forcecast> faces,
    const std::vector<uint32_t>& ring_end_indices,
    double z_start,
    double z_end
);
std::tuple<py::array_t<double>, py::array_t<int32_t>, double> extrude_rings(
    const py::iterable& rings,
    double z_start,
    double z_end
);
std::tuple<py::array_t<double>, py::array_t<int32_t>, double> extrude_rings_nogil(
    const py::iterable& rings,
    double z_start,
    double z_end
);
