#pragma once

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <clipper2/clipper.h>
#include <string>
#include <vector>

namespace py = pybind11;

// 默认缩放因子
double default_scale();

// 工具函数
bool nearly_equal_int64(int64_t a, int64_t b);

// 路径转换函数
std::vector<Clipper2Lib::Path64> parse_loops_as_paths64(const py::iterable& loops, double scale);
py::list paths64_to_loops(const std::vector<Clipper2Lib::Path64>& paths, double scale);

// 类型转换
Clipper2Lib::ClipType clip_type_from_string(const std::string& op);
Clipper2Lib::JoinType join_type_from_string(const std::string& jt);
Clipper2Lib::EndType end_type_from_string(const std::string& et);

// Clipper 操作
py::list clipper_boolean(const py::iterable& subject_loops, const py::iterable& clip_loops, const std::string& op, double scale);
py::list clipper_offset(const py::iterable& loops, double delta, const std::string& join_type, const std::string& end_type, double miter_limit, double arc_tolerance, double scale);
py::list clipper_union_all_nogil(const py::iterable& loops, double scale);
py::list clipper_union_all_to_polygons_nogil(const py::iterable& loops, double scale);
py::list clipper_make_exclusive_nogil(const py::iterable& slots_loops, double scale);
std::tuple<double, double, double> clipper_layer_overlap_gap_areas_nogil(const py::iterable& slots_loops, const py::iterable& full_loops, double scale);

// 辅助函数
py::array_t<double> path64_to_loop(const Clipper2Lib::Path64& path, double scale);
void append_polygons_from_outer(const Clipper2Lib::PolyPath64& outer, double scale, py::list& out);
double signed_area_paths64(const std::vector<Clipper2Lib::Path64>& paths);
