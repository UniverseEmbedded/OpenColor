/**
 * Clipper2几何操作模块 - 提供多边形布尔运算和偏移功能
 * 支持并集、差集、交集、异或等布尔运算，以及多边形膨胀/腐蚀操作
 */

#include "clipper_ops.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace py = pybind11;

// 默认缩放因子，用于将浮点坐标转换为整数以提高精度
double default_scale() {
    return 1000000.0;
}

// 判断两个int64是否相等（用于坐标比较）
bool nearly_equal_int64(int64_t a, int64_t b) {
    return a == b;
}

// 将Python环列表解析为Clipper2的Path64列表
std::vector<Clipper2Lib::Path64> parse_loops_as_paths64(const py::iterable& loops, double scale) {
    if (!(scale > 0.0)) {
        throw std::runtime_error("scale 必须为正数");
    }

    std::vector<Clipper2Lib::Path64> out;
    for (const py::handle& h : loops) {
        py::array arr = py::array::ensure(h);
        if (!arr) {
            continue;
        }
        if (arr.ndim() != 2 || arr.shape(1) != 2) {
            throw std::runtime_error("loop 必须是 (N,2) 数组");
        }
        py::array_t<double, py::array::c_style | py::array::forcecast> pts(arr);
        const auto n = static_cast<size_t>(pts.shape(0));
        if (n < 3) {
            continue;
        }
        const double* p = pts.data();
        Clipper2Lib::Path64 path;
        path.reserve(n);
        for (size_t i = 0; i < n; i++) {
            const double x = p[i * 2 + 0];
            const double y = p[i * 2 + 1];
            const int64_t xi = static_cast<int64_t>(std::llround(x * scale));
            const int64_t yi = static_cast<int64_t>(std::llround(y * scale));
            if (!path.empty()) {
                const auto& last = path.back();
                if (nearly_equal_int64(last.x, xi) && nearly_equal_int64(last.y, yi)) {
                    continue;
                }
            }
            path.push_back(Clipper2Lib::Point64{xi, yi});
        }
        if (path.size() >= 2) {
            const auto& first = path.front();
            const auto& last = path.back();
            if (nearly_equal_int64(first.x, last.x) && nearly_equal_int64(first.y, last.y)) {
                path.pop_back();
            }
        }
        if (path.size() >= 3) {
            out.push_back(std::move(path));
        }
    }
    return out;
}

// 将Clipper2的Path64列表转换为Python环列表
py::list paths64_to_loops(const std::vector<Clipper2Lib::Path64>& paths, double scale) {
    py::list out;
    for (const auto& path : paths) {
        const auto n = static_cast<py::ssize_t>(path.size());
        if (n < 3) {
            continue;
        }
        py::array_t<double> loop({n, static_cast<py::ssize_t>(2)});
        double* dst = loop.mutable_data();
        for (py::ssize_t i = 0; i < n; i++) {
            dst[i * 2 + 0] = static_cast<double>(path[static_cast<size_t>(i)].x) / scale;
            dst[i * 2 + 1] = static_cast<double>(path[static_cast<size_t>(i)].y) / scale;
        }
        out.append(std::move(loop));
    }
    return out;
}

// 将字符串操作类型转换为Clipper2的ClipType
Clipper2Lib::ClipType clip_type_from_string(const std::string& op) {
    if (op == "union") {
        return Clipper2Lib::ClipType::Union;
    }
    if (op == "difference") {
        return Clipper2Lib::ClipType::Difference;
    }
    if (op == "intersection") {
        return Clipper2Lib::ClipType::Intersection;
    }
    if (op == "xor") {
        return Clipper2Lib::ClipType::Xor;
    }
    throw std::runtime_error("未知布尔运算: " + op);
}

// 将字符串连接类型转换为Clipper2的JoinType
Clipper2Lib::JoinType join_type_from_string(const std::string& jt) {
    if (jt == "miter") {
        return Clipper2Lib::JoinType::Miter;
    }
    if (jt == "square") {
        return Clipper2Lib::JoinType::Square;
    }
    if (jt == "round") {
        return Clipper2Lib::JoinType::Round;
    }
    throw std::runtime_error("未知 join_type: " + jt);
}

// 将字符串端点类型转换为Clipper2的EndType
Clipper2Lib::EndType end_type_from_string(const std::string& et) {
    if (et == "polygon") {
        return Clipper2Lib::EndType::Polygon;
    }
    if (et == "joined") {
        return Clipper2Lib::EndType::Joined;
    }
    if (et == "butt") {
        return Clipper2Lib::EndType::Butt;
    }
    if (et == "square") {
        return Clipper2Lib::EndType::Square;
    }
    if (et == "round") {
        return Clipper2Lib::EndType::Round;
    }
    throw std::runtime_error("未知 end_type: " + et);
}

// 执行多边形布尔运算（并集、差集、交集、异或）
py::list clipper_boolean(const py::iterable& subject_loops, const py::iterable& clip_loops, const std::string& op, double scale) {
    auto subjects = parse_loops_as_paths64(subject_loops, scale);
    auto clips = parse_loops_as_paths64(clip_loops, scale);

    Clipper2Lib::Clipper64 c;
    c.AddSubject(subjects);
    c.AddClip(clips);

    std::vector<Clipper2Lib::Path64> solution;
    c.Execute(clip_type_from_string(op), Clipper2Lib::FillRule::EvenOdd, solution);
    return paths64_to_loops(solution, scale);
}

// 对多边形进行偏移操作（膨胀或腐蚀）
py::list clipper_offset(const py::iterable& loops, double delta, const std::string& join_type, const std::string& end_type, double miter_limit, double arc_tolerance, double scale) {
    auto paths = parse_loops_as_paths64(loops, scale);
    Clipper2Lib::ClipperOffset co;
    co.MiterLimit(miter_limit);
    co.ArcTolerance(arc_tolerance * scale);
    co.AddPaths(paths, join_type_from_string(join_type), end_type_from_string(end_type));

    std::vector<Clipper2Lib::Path64> solution;
    co.Execute(delta * scale, solution);
    return paths64_to_loops(solution, scale);
}

// 对所有多边形执行并集运算（无GIL版本，支持多线程）
py::list clipper_union_all_nogil(const py::iterable& loops, double scale) {
    auto paths = parse_loops_as_paths64(loops, scale);
    if (paths.empty()) {
        return py::list();
    }

    std::vector<Clipper2Lib::Path64> solution;
    {
        py::gil_scoped_release release;
        Clipper2Lib::Clipper64 c;
        c.AddSubject(paths);
        c.Execute(Clipper2Lib::ClipType::Union, Clipper2Lib::FillRule::EvenOdd, solution);
    }
    return paths64_to_loops(solution, scale);
}

py::array_t<double> path64_to_loop(const Clipper2Lib::Path64& path, double scale) {
    const auto n = static_cast<py::ssize_t>(path.size());
    py::array_t<double> loop({n, static_cast<py::ssize_t>(2)});
    double* dst = loop.mutable_data();
    for (py::ssize_t i = 0; i < n; i++) {
        dst[i * 2 + 0] = static_cast<double>(path[static_cast<size_t>(i)].x) / scale;
        dst[i * 2 + 1] = static_cast<double>(path[static_cast<size_t>(i)].y) / scale;
    }
    return loop;
}

void append_polygons_from_outer(const Clipper2Lib::PolyPath64& outer, double scale, py::list& out) {
    const auto& shell = outer.Polygon();
    if (shell.size() < 3) {
        return;
    }

    py::list holes;
    for (const auto& child_up : outer) {
        const auto* child = child_up.get();
        if (!child) {
            continue;
        }
        if (!child->IsHole()) {
            continue;
        }
        const auto& hole = child->Polygon();
        if (hole.size() < 3) {
            continue;
        }
        holes.append(path64_to_loop(hole, scale));
    }

    out.append(py::make_tuple(path64_to_loop(shell, scale), holes));

    for (const auto& child_up : outer) {
        const auto* child = child_up.get();
        if (!child) {
            continue;
        }
        if (child->IsHole()) {
            for (const auto& grand_up : *child) {
                const auto* grand = grand_up.get();
                if (!grand) {
                    continue;
                }
                if (!grand->IsHole()) {
                    append_polygons_from_outer(*grand, scale, out);
                }
            }
        } else {
            append_polygons_from_outer(*child, scale, out);
        }
    }
}

// 对所有多边形执行并集运算并保留孔洞结构（无GIL版本）
py::list clipper_union_all_to_polygons_nogil(const py::iterable& loops, double scale) {
    auto paths = parse_loops_as_paths64(loops, scale);
    if (paths.empty()) {
        return py::list();
    }

    Clipper2Lib::PolyTree64 tree;
    {
        py::gil_scoped_release release;
        Clipper2Lib::Clipper64 c;
        c.AddSubject(paths);
        c.Execute(Clipper2Lib::ClipType::Union, Clipper2Lib::FillRule::EvenOdd, tree);
    }

    py::list out;
    for (const auto& child_up : tree) {
        const auto* child = child_up.get();
        if (!child) {
            continue;
        }
        if (child->IsHole()) {
            for (const auto& grand_up : *child) {
                const auto* grand = grand_up.get();
                if (!grand) {
                    continue;
                }
                if (!grand->IsHole()) {
                    append_polygons_from_outer(*grand, scale, out);
                }
            }
            continue;
        }
        append_polygons_from_outer(*child, scale, out);
    }
    return out;
}

// 将多个槽位的多边形转换为互斥区域（无GIL版本）
py::list clipper_make_exclusive_nogil(const py::iterable& slots_loops, double scale) {
    std::vector<std::vector<Clipper2Lib::Path64>> slots;
    slots.reserve(16);
    for (const py::handle& h : slots_loops) {
        slots.push_back(parse_loops_as_paths64(py::cast<py::iterable>(h), scale));
    }
    if (slots.empty()) {
        return py::list();
    }

    std::vector<std::vector<Clipper2Lib::Path64>> out(slots.size());
    std::vector<Clipper2Lib::Path64> occupied;

    {
        py::gil_scoped_release release;
        for (size_t i = 0; i < slots.size(); i++) {
            std::vector<Clipper2Lib::Path64> current = slots[i];
            if (!occupied.empty() && !current.empty()) {
                Clipper2Lib::Clipper64 c;
                c.AddSubject(current);
                c.AddClip(occupied);
                std::vector<Clipper2Lib::Path64> diff;
                c.Execute(Clipper2Lib::ClipType::Difference, Clipper2Lib::FillRule::EvenOdd, diff);
                current.swap(diff);
            }
            out[i] = current;

            if (!current.empty()) {
                std::vector<Clipper2Lib::Path64> merged = occupied;
                merged.insert(merged.end(), current.begin(), current.end());

                Clipper2Lib::Clipper64 u;
                u.AddSubject(merged);
                std::vector<Clipper2Lib::Path64> uni;
                u.Execute(Clipper2Lib::ClipType::Union, Clipper2Lib::FillRule::EvenOdd, uni);
                occupied.swap(uni);
            }
        }
    }

    py::list out_py;
    for (const auto& paths : out) {
        out_py.append(paths64_to_loops(paths, scale));
    }
    return out_py;
}

// 计算Path64列表的总有符号面积
double signed_area_paths64(const std::vector<Clipper2Lib::Path64>& paths) {
    double s = 0.0;
    for (const auto& p : paths) {
        s += Clipper2Lib::Area(p);
    }
    return s;
}

std::tuple<double, double, double> clipper_layer_overlap_gap_areas_nogil(
    const py::iterable& slots_loops,
    const py::iterable& full_loops,
    double scale
) {
    if (!(scale > 0.0)) {
        throw std::runtime_error("scale 必须为正数");
    }

    auto full_paths = parse_loops_as_paths64(full_loops, scale);
    if (full_paths.empty()) {
        return {0.0, 0.0, 0.0};
    }

    std::vector<std::vector<Clipper2Lib::Path64>> slots;
    slots.reserve(16);
    for (const py::handle& h : slots_loops) {
        slots.push_back(parse_loops_as_paths64(py::cast<py::iterable>(h), scale));
    }

    std::vector<Clipper2Lib::Path64> occupied;
    double overlap_area_i2 = 0.0;

    {
        py::gil_scoped_release release;
        for (size_t i = 0; i < slots.size(); i++) {
            const auto& current = slots[i];
            if (current.empty()) {
                continue;
            }

            if (!occupied.empty()) {
                Clipper2Lib::Clipper64 ci;
                ci.AddSubject(current);
                ci.AddClip(occupied);
                std::vector<Clipper2Lib::Path64> inter;
                ci.Execute(Clipper2Lib::ClipType::Intersection, Clipper2Lib::FillRule::EvenOdd, inter);
                overlap_area_i2 += signed_area_paths64(inter);
            }

            std::vector<Clipper2Lib::Path64> merged = occupied;
            merged.insert(merged.end(), current.begin(), current.end());

            Clipper2Lib::Clipper64 u;
            u.AddSubject(merged);
            std::vector<Clipper2Lib::Path64> uni;
            u.Execute(Clipper2Lib::ClipType::Union, Clipper2Lib::FillRule::EvenOdd, uni);
            occupied.swap(uni);
        }
    }

    const double union_area_i2 = signed_area_paths64(occupied);
    double gap_area_i2 = 0.0;
    {
        py::gil_scoped_release release;
        Clipper2Lib::Clipper64 cd;
        cd.AddSubject(full_paths);
        cd.AddClip(occupied);
        std::vector<Clipper2Lib::Path64> diff;
        cd.Execute(Clipper2Lib::ClipType::Difference, Clipper2Lib::FillRule::EvenOdd, diff);
        gap_area_i2 = signed_area_paths64(diff);
    }

    const double denom = scale * scale;
    const double union_area_mm2 = std::abs(union_area_i2) / denom;
    const double overlap_area_mm2 = std::abs(overlap_area_i2) / denom;
    const double gap_area_mm2 = std::abs(gap_area_i2) / denom;
    return {union_area_mm2, overlap_area_mm2, gap_area_mm2};
}
