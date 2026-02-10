/**
 * Earcut三角剖分模块 - 使用mapbox/earcut库进行多边形三角剖分
 * 支持2D多边形带孔洞的三角化，并提供拉伸生成为3D网格的功能
 */

#include "earcut_triangulation.h"
#include <mapbox/earcut.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <tuple>
#include <utility>

#include <manifold/manifold.h>

namespace py = pybind11;

namespace {

struct MeshEdgeStats {
    uint64_t boundary_edges = 0;
    uint64_t nonmanifold_edges = 0;
    uint64_t degenerate_tris = 0;
    uint64_t nonmanifold_edge_key = 0;
    uint32_t nonmanifold_edge_count = 0;
    uint64_t boundary_edge_key = 0;
};

struct DirectedEdge {
    uint32_t u = 0;
    uint32_t v = 0;
};

static inline uint64_t edge_key(uint32_t a, uint32_t b) {
    const uint32_t lo = (a < b) ? a : b;
    const uint32_t hi = (a < b) ? b : a;
    return (static_cast<uint64_t>(lo) << 32) | static_cast<uint64_t>(hi);
}

static MeshEdgeStats compute_edge_stats(const std::vector<int32_t>& faces, size_t vert_count) {
    MeshEdgeStats stats;
    if (faces.size() % 3 != 0) {
        return stats;
    }
    std::unordered_map<uint64_t, uint32_t> edge_counts;
    edge_counts.reserve(faces.size());

    for (size_t i = 0; i < faces.size(); i += 3) {
        const int32_t a0 = faces[i + 0];
        const int32_t b0 = faces[i + 1];
        const int32_t c0 = faces[i + 2];
        if (a0 < 0 || b0 < 0 || c0 < 0) {
            stats.degenerate_tris++;
            continue;
        }
        const uint32_t a = static_cast<uint32_t>(a0);
        const uint32_t b = static_cast<uint32_t>(b0);
        const uint32_t c = static_cast<uint32_t>(c0);
        if (static_cast<size_t>(a) >= vert_count || static_cast<size_t>(b) >= vert_count || static_cast<size_t>(c) >= vert_count) {
            stats.degenerate_tris++;
            continue;
        }
        if (a == b || b == c || a == c) {
            stats.degenerate_tris++;
            continue;
        }
        edge_counts[edge_key(a, b)] += 1;
        edge_counts[edge_key(b, c)] += 1;
        edge_counts[edge_key(c, a)] += 1;
    }

    for (const auto& kv : edge_counts) {
        if (kv.second == 1) {
            stats.boundary_edges++;
            if (stats.boundary_edges == 1) {
                stats.boundary_edge_key = kv.first;
            }
        } else if (kv.second > 2) {
            stats.nonmanifold_edges++;
            if (stats.nonmanifold_edge_count == 0) {
                stats.nonmanifold_edge_key = kv.first;
                stats.nonmanifold_edge_count = kv.second;
            }
        }
    }
    return stats;
}

static std::vector<DirectedEdge> compute_boundary_directed_edges_from_tris(
    const uint32_t* tri_verts,
    size_t tri_count
) {
    std::unordered_map<uint64_t, uint32_t> edge_counts;
    std::unordered_map<uint64_t, DirectedEdge> edge_dir;
    edge_counts.reserve(tri_count * 3);
    edge_dir.reserve(tri_count * 3);

    auto add_edge = [&](uint32_t a, uint32_t b) {
        const uint64_t k = edge_key(a, b);
        auto it = edge_counts.find(k);
        if (it == edge_counts.end()) {
            edge_counts.emplace(k, 1);
            edge_dir.emplace(k, DirectedEdge{a, b});
        } else {
            it->second += 1;
        }
    };

    for (size_t i = 0; i < tri_count; i++) {
        const uint32_t a = tri_verts[i * 3 + 0];
        const uint32_t b = tri_verts[i * 3 + 1];
        const uint32_t c = tri_verts[i * 3 + 2];
        add_edge(a, b);
        add_edge(b, c);
        add_edge(c, a);
    }

    std::vector<DirectedEdge> boundary;
    boundary.reserve(edge_counts.size());
    for (const auto& kv : edge_counts) {
        if (kv.second == 1) {
            const auto it = edge_dir.find(kv.first);
            if (it != edge_dir.end()) {
                boundary.push_back(it->second);
            }
        }
    }
    return boundary;
}

static std::vector<std::vector<uint32_t>> compute_boundary_loops_from_tris(
    const uint32_t* tri_verts,
    size_t tri_count,
    const std::vector<EarcutPoint>& verts2d
) {
    std::unordered_map<uint64_t, uint32_t> edge_counts;
    std::unordered_map<uint64_t, DirectedEdge> edge_dir;
    edge_counts.reserve(tri_count * 3);
    edge_dir.reserve(tri_count * 3);

    auto add_edge = [&](uint32_t a, uint32_t b) {
        const uint64_t k = edge_key(a, b);
        auto it = edge_counts.find(k);
        if (it == edge_counts.end()) {
            edge_counts.emplace(k, 1);
            edge_dir.emplace(k, DirectedEdge{a, b});
        } else {
            it->second += 1;
        }
    };

    for (size_t i = 0; i < tri_count; i++) {
        const uint32_t a = tri_verts[i * 3 + 0];
        const uint32_t b = tri_verts[i * 3 + 1];
        const uint32_t c = tri_verts[i * 3 + 2];
        add_edge(a, b);
        add_edge(b, c);
        add_edge(c, a);
    }

    std::unordered_map<uint32_t, std::vector<uint32_t>> adj;
    adj.reserve(edge_counts.size());
    std::vector<DirectedEdge> boundary;
    boundary.reserve(edge_counts.size());
    for (const auto& kv : edge_counts) {
        if (kv.second != 1) {
            continue;
        }
        const auto it = edge_dir.find(kv.first);
        if (it == edge_dir.end()) {
            continue;
        }
        boundary.push_back(it->second);
        adj[it->second.u].push_back(it->second.v);
        adj[it->second.v].push_back(it->second.u);
    }

    auto angle_score = [&](uint32_t a, uint32_t b, uint32_t c) -> double {
        const auto& pa = verts2d[a];
        const auto& pb = verts2d[b];
        const auto& pc = verts2d[c];
        const double inx = pb[0] - pa[0];
        const double iny = pb[1] - pa[1];
        const double outx = pc[0] - pb[0];
        const double outy = pc[1] - pb[1];
        const double cross = inx * outy - iny * outx;
        const double dot = inx * outx + iny * outy;
        return std::atan2(cross, dot);
    };

    std::unordered_map<uint64_t, uint8_t> used;
    used.reserve(boundary.size());

    std::vector<std::vector<uint32_t>> loops;
    loops.reserve(8);

    for (const auto& e0 : boundary) {
        const uint64_t k0 = edge_key(e0.u, e0.v);
        if (used.find(k0) != used.end()) {
            continue;
        }

        const uint32_t start_u = e0.u;
        uint32_t prev = e0.u;
        uint32_t cur = e0.v;

        std::vector<uint32_t> loop;
        loop.reserve(128);
        loop.push_back(start_u);

        size_t guard = 0;
        while (true) {
            guard += 1;
            if (guard > boundary.size() + 8) {
                throw std::runtime_error("边界拓扑异常: 环遍历超限");
            }

            loop.push_back(cur);
            used.emplace(edge_key(prev, cur), 1);

            if (cur == start_u) {
                break;
            }

            const auto it = adj.find(cur);
            if (it == adj.end() || it->second.empty()) {
                throw std::runtime_error("边界拓扑异常: 找不到相邻边界点");
            }

            double best_score = -1e100;
            bool has = false;
            uint32_t best_next = 0;

            for (uint32_t cand : it->second) {
                if (cand == prev) {
                    continue;
                }
                const uint64_t kc = edge_key(cur, cand);
                if (used.find(kc) != used.end()) {
                    continue;
                }
                const double sc = angle_score(prev, cur, cand);
                if ((!has) || sc > best_score) {
                    has = true;
                    best_score = sc;
                    best_next = cand;
                }
            }

            if (!has) {
                bool can_close = false;
                for (uint32_t cand : it->second) {
                    if (cand == start_u) {
                        const uint64_t kc = edge_key(cur, cand);
                        if (used.find(kc) == used.end()) {
                            best_next = cand;
                            can_close = true;
                            break;
                        }
                    }
                }
                if (!can_close) {
                    throw std::runtime_error("边界拓扑异常: 无法闭合边界环");
                }
            }

            const uint32_t next = best_next;
            prev = cur;
            cur = next;
        }

        if (loop.size() < 4 || loop.front() != loop.back()) {
            throw std::runtime_error("边界拓扑异常: 未形成闭环");
        }

        loop.pop_back();
        loops.push_back(std::move(loop));
    }

    return loops;
}

static void validate_manifold_mesh_or_throw(
    const std::vector<double>& verts,
    const std::vector<int32_t>& faces,
    const std::string& ctx
) {
    if (verts.size() % 3 != 0 || faces.size() % 3 != 0) {
        throw std::runtime_error(ctx + ": 顶点/面片数组长度非法");
    }
    const size_t vert_count = verts.size() / 3;
    const size_t tri_count = faces.size() / 3;
    if (vert_count == 0 || tri_count == 0) {
        throw std::runtime_error(ctx + ": 空网格");
    }

    const MeshEdgeStats stats = compute_edge_stats(faces, vert_count);
    
    // 如果存在边界边（开口），那是肯定不能转 Manifold 的，直接报错
    if (stats.boundary_edges > 0) {
        std::string msg = ctx;
        msg += ": 输出网格非封闭 (boundary_edges=";
        msg += std::to_string(stats.boundary_edges);
        msg += ", verts=";
        msg += std::to_string(vert_count);
        msg += ", tris=";
        msg += std::to_string(tri_count);
        if (stats.boundary_edges > 0) {
            const uint32_t lo = static_cast<uint32_t>(stats.boundary_edge_key >> 32);
            const uint32_t hi = static_cast<uint32_t>(stats.boundary_edge_key & 0xffffffffULL);
            msg += ", sample_boundary_edge=(";
            msg += std::to_string(lo);
            msg += ",";
            msg += std::to_string(hi);
            msg += ")";

            if (lo < vert_count && hi < vert_count) {
                const double ax = verts[static_cast<size_t>(lo) * 3 + 0];
                const double ay = verts[static_cast<size_t>(lo) * 3 + 1];
                const double az = verts[static_cast<size_t>(lo) * 3 + 2];
                const double bx = verts[static_cast<size_t>(hi) * 3 + 0];
                const double by = verts[static_cast<size_t>(hi) * 3 + 1];
                const double bz = verts[static_cast<size_t>(hi) * 3 + 2];
                msg += ", pos_a=(";
                msg += std::to_string(ax);
                msg += ",";
                msg += std::to_string(ay);
                msg += ",";
                msg += std::to_string(az);
                msg += "), pos_b=(";
                msg += std::to_string(bx);
                msg += ",";
                msg += std::to_string(by);
                msg += ",";
                msg += std::to_string(bz);
                msg += ")";
            }
        }
        msg += ")";
        throw std::runtime_error(msg);
    }

    manifold::MeshGL mesh;
    mesh.numProp = 3;
    mesh.vertProperties.reserve(vert_count * 3);
    for (size_t i = 0; i < vert_count * 3; i++) {
        mesh.vertProperties.push_back(static_cast<float>(verts[i]));
    }
    mesh.triVerts.reserve(tri_count * 3);
    for (size_t i = 0; i < faces.size(); i++) {
        const int32_t idx = faces[i];
        if (idx < 0 || static_cast<size_t>(idx) >= vert_count) {
            throw std::runtime_error(ctx + ": 面片索引越界");
        }
        mesh.triVerts.push_back(static_cast<uint32_t>(idx));
    }

    manifold::Manifold m(mesh);
    const auto st = m.Status();
    
    // 如果 Manifold 创建失败，或者虽然没有 boundary 但我们检测到了 nonmanifold_edges 且 Manifold 状态不对
    if (st != manifold::Manifold::Error::NoError || m.NumTri() == 0) {
        std::string msg = ctx;
        msg += ": 创建 Manifold 失败";
        msg += " (status=";
        msg += std::to_string(static_cast<int>(st));
        msg += ", verts=";
        msg += std::to_string(vert_count);
        msg += ", tris=";
        msg += std::to_string(m.NumTri());
        if (stats.nonmanifold_edges > 0) {
            msg += ", nonmanifold_edges=";
            msg += std::to_string(stats.nonmanifold_edges);
            if (stats.nonmanifold_edge_count > 0) {
                const uint32_t lo = static_cast<uint32_t>(stats.nonmanifold_edge_key >> 32);
                const uint32_t hi = static_cast<uint32_t>(stats.nonmanifold_edge_key & 0xffffffffULL);
                msg += ", sample_nonmanifold_edge=(";
                msg += std::to_string(lo);
                msg += ",";
                msg += std::to_string(hi);
                msg += ",count=";
                msg += std::to_string(stats.nonmanifold_edge_count);
                msg += ")";
            }
        }
        msg += ")";
        throw std::runtime_error(msg);
    }
}

}  // namespace

// 获取默认缩放因子（用于将浮点坐标转换为整数以提高精度）
double earcut_default_scale() {
    return 1000000.0;
}

// 计算两点间距离的平方
double earcut_dist2(const EarcutPoint& a, const EarcutPoint& b) {
    const double dx = a[0] - b[0];
    const double dy = a[1] - b[1];
    return dx * dx + dy * dy;
}

// 计算多边形环的有符号面积（正值为逆时针，负值为顺时针）
double earcut_signed_area(const std::vector<EarcutPoint>& ring) {
    const size_t n = ring.size();
    if (n < 3) {
        return 0.0;
    }
    double s = 0.0;
    for (size_t i = 0; i < n; i++) {
        const auto& a = ring[i];
        const auto& b = ring[(i + 1) % n];
        s += a[0] * b[1] - b[0] * a[1];
    }
    return 0.5 * s;
}

// 清理多边形环：移除重复点、共线点，并进行量化去重
std::vector<EarcutPoint> clean_ring_cpp(std::vector<EarcutPoint> coords, double eps, double scale, bool remove_global_duplicates) {
    if (coords.size() < 3) {
        return coords;
    }

    const double eps2 = eps * eps;

    if (coords.size() >= 2 && earcut_dist2(coords.front(), coords.back()) <= eps2) {
        coords.pop_back();
    }
    if (coords.size() < 3) {
        return coords;
    }

    {
        std::vector<EarcutPoint> out;
        out.reserve(coords.size());
        out.push_back(coords.front());
        for (size_t i = 1; i < coords.size(); i++) {
            if (earcut_dist2(coords[i], out.back()) > eps2) {
                out.push_back(coords[i]);
            }
        }
        coords.swap(out);
    }
    if (coords.size() < 3) {
        return coords;
    }

    if (remove_global_duplicates) {
        std::unordered_set<QuantKey, QuantKeyHash, QuantKeyEq> seen;
        seen.reserve(coords.size());
        std::vector<EarcutPoint> out;
        out.reserve(coords.size());
        for (const auto& p : coords) {
            const int64_t qx = static_cast<int64_t>(std::llround(p[0] / eps));
            const int64_t qy = static_cast<int64_t>(std::llround(p[1] / eps));
            QuantKey key{qx, qy};
            if (seen.find(key) != seen.end()) {
                continue;
            }
            seen.insert(key);
            out.push_back(p);
        }
        coords.swap(out);
        if (coords.size() < 3) {
            return coords;
        }
    }

    {
        bool changed = true;
        while (changed && coords.size() >= 3) {
            changed = false;
            const size_t n = coords.size();
            std::vector<EarcutPoint> keep;
            keep.reserve(n);
            for (size_t i = 0; i < n; i++) {
                const auto& prev = coords[(i + n - 1) % n];
                const auto& cur = coords[i];
                const auto& nxt = coords[(i + 1) % n];
                if (earcut_dist2(cur, prev) <= eps2 && earcut_dist2(nxt, cur) <= eps2) {
                    changed = true;
                    continue;
                }
                keep.push_back(cur);
            }
            coords.swap(keep);
        }
    }
    if (coords.size() < 3) {
        return coords;
    }

    {
        const double col_thresh = 1e-12 * (scale * scale);
        const size_t n = coords.size();
        std::vector<EarcutPoint> keep;
        keep.reserve(n);
        for (size_t i = 0; i < n; i++) {
            const auto& a = coords[(i + n - 1) % n];
            const auto& b = coords[i];
            const auto& c = coords[(i + 1) % n];
            const double abx = b[0] - a[0];
            const double aby = b[1] - a[1];
            const double bcx = c[0] - b[0];
            const double bcy = c[1] - b[1];
            const double cross = std::abs(abx * bcy - aby * bcx);
            if (cross <= col_thresh) {
                continue;
            }
            keep.push_back(b);
        }
        coords.swap(keep);
    }

    return coords;
}

// 解析多个环为Earcut多边形格式，返回顶点列表和环结束索引
std::vector<EarcutPoint> parse_rings_to_earcut_polygon(const py::iterable& rings, std::vector<uint32_t>& ring_end_indices) {
    std::vector<std::vector<EarcutPoint>> poly;
    ring_end_indices.clear();

    uint32_t cum = 0;
    for (const py::handle& h : rings) {
        py::array arr = py::array::ensure(h);
        if (!arr) {
            continue;
        }
        if (arr.ndim() != 2 || arr.shape(1) != 2) {
            throw std::runtime_error("ring 必须是 (N,2) 数组");
        }
        py::array_t<double, py::array::c_style | py::array::forcecast> pts(arr);
        const auto n = static_cast<size_t>(pts.shape(0));
        if (n < 3) {
            continue;
        }
        const double* p = pts.data();
        std::vector<EarcutPoint> ring;
        ring.reserve(n);

        for (size_t i = 0; i < n; i++) {
            const double x = p[i * 2 + 0];
            const double y = p[i * 2 + 1];
            if (!ring.empty()) {
                const auto& last = ring.back();
                if (last[0] == x && last[1] == y) {
                    continue;
                }
            }
            ring.push_back(EarcutPoint{x, y});
        }
        if (ring.size() >= 2) {
            const auto& first = ring.front();
            const auto& last = ring.back();
            if (first[0] == last[0] && first[1] == last[1]) {
                ring.pop_back();
            }
        }
        if (ring.size() < 3) {
            continue;
        }
        cum += static_cast<uint32_t>(ring.size());
        ring_end_indices.push_back(cum);
        poly.push_back(std::move(ring));
    }

    std::vector<EarcutPoint> vertices;
    vertices.reserve(ring_end_indices.empty() ? 0 : ring_end_indices.back());
    for (const auto& ring : poly) {
        for (const auto& pt : ring) {
            vertices.push_back(pt);
        }
    }
    return vertices;
}

// 对多个环进行三角剖分，返回顶点、面片、环结束索引和三角形总面积
std::tuple<py::array_t<double>, py::array_t<uint32_t>, std::vector<uint32_t>, double> earcut_triangulate_rings(const py::iterable& rings) {
    std::vector<uint32_t> ring_end_indices;

    double minx = std::numeric_limits<double>::infinity();
    double miny = std::numeric_limits<double>::infinity();
    double maxx = -std::numeric_limits<double>::infinity();
    double maxy = -std::numeric_limits<double>::infinity();

    std::vector<std::vector<EarcutPoint>> raw;
    for (const py::handle& h : rings) {
        py::array arr = py::array::ensure(h);
        if (!arr) {
            continue;
        }
        if (arr.ndim() != 2 || arr.shape(1) != 2) {
            throw std::runtime_error("ring 必须是 (N,2) 数组");
        }
        py::array_t<double, py::array::c_style | py::array::forcecast> pts(arr);
        const auto n = static_cast<size_t>(pts.shape(0));
        if (n < 3) {
            continue;
        }
        const double* p = pts.data();
        std::vector<EarcutPoint> ring;
        ring.reserve(n);
        for (size_t i = 0; i < n; i++) {
            const double x = p[i * 2 + 0];
            const double y = p[i * 2 + 1];
            ring.push_back(EarcutPoint{x, y});
            minx = std::min(minx, x);
            miny = std::min(miny, y);
            maxx = std::max(maxx, x);
            maxy = std::max(maxy, y);
        }
        raw.push_back(std::move(ring));
    }

    if (raw.empty()) {
        py::array_t<double> v({0, 2});
        py::array_t<uint32_t> f({0, 3});
        return {v, f, std::vector<uint32_t>{}, 0.0};
    }

    const double dx = maxx - minx;
    const double dy = maxy - miny;
    const double scale = std::max(1.0, std::max(dx, dy));
    const double eps = 1e-7 * scale;

    std::vector<std::vector<EarcutPoint>> poly;
    poly.reserve(raw.size());
    bool first_ring = true;
    for (auto ring : raw) {
        ring = clean_ring_cpp(std::move(ring), eps, scale);
        if (ring.size() < 3) {
            continue;
        }
        const double a = earcut_signed_area(ring);
        if (first_ring) {
            if (a < 0.0) {
                std::reverse(ring.begin(), ring.end());
            }
            first_ring = false;
        } else {
            if (a > 0.0) {
                std::reverse(ring.begin(), ring.end());
            }
        }
        poly.push_back(std::move(ring));
    }

    if (poly.empty()) {
        py::array_t<double> v({0, 2});
        py::array_t<uint32_t> f({0, 3});
        return {v, f, std::vector<uint32_t>{}, 0.0};
    }

    ring_end_indices.reserve(poly.size());
    uint32_t cum = 0;
    for (const auto& ring : poly) {
        cum += static_cast<uint32_t>(ring.size());
        ring_end_indices.push_back(cum);
    }

    std::vector<EarcutPoint> vertices;
    vertices.reserve(cum);
    for (const auto& ring : poly) {
        for (const auto& pt : ring) {
            vertices.push_back(pt);
        }
    }

    const std::vector<uint32_t> indices = mapbox::earcut<uint32_t>(poly);
    const size_t tri_count = indices.size() / 3;

    py::array_t<double> verts_out({static_cast<py::ssize_t>(vertices.size()), static_cast<py::ssize_t>(2)});
    double* vdst = verts_out.mutable_data();
    for (size_t i = 0; i < vertices.size(); i++) {
        vdst[i * 2 + 0] = vertices[i][0];
        vdst[i * 2 + 1] = vertices[i][1];
    }

    py::array_t<uint32_t> faces_out({static_cast<py::ssize_t>(tri_count), static_cast<py::ssize_t>(3)});
    uint32_t* fdst = faces_out.mutable_data();
    for (size_t i = 0; i < tri_count; i++) {
        fdst[i * 3 + 0] = indices[i * 3 + 0];
        fdst[i * 3 + 1] = indices[i * 3 + 1];
        fdst[i * 3 + 2] = indices[i * 3 + 2];
    }

    double tri_area = 0.0;
    for (size_t i = 0; i < tri_count; i++) {
        const auto i0 = indices[i * 3 + 0];
        const auto i1 = indices[i * 3 + 1];
        const auto i2 = indices[i * 3 + 2];
        const auto& a = vertices[i0];
        const auto& b = vertices[i1];
        const auto& c = vertices[i2];
        const double cross = std::abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
        tri_area += 0.5 * cross;
    }

    return {verts_out, faces_out, ring_end_indices, tri_area};
}

// 将2D三角剖分结果拉伸为3D网格，生成顶面和侧面
std::pair<py::array_t<double>, py::array_t<int32_t>> extrude_triangulation(
    py::array_t<double, py::array::c_style | py::array::forcecast> verts_2d,
    py::array_t<uint32_t, py::array::c_style | py::array::forcecast> faces,
    const std::vector<uint32_t>& ring_end_indices,
    double z_start,
    double z_end
) {
    if (verts_2d.ndim() != 2 || verts_2d.shape(1) != 2) {
        throw std::runtime_error("verts_2d 必须是 (N,2) 数组");
    }
    if (faces.ndim() != 2 || faces.shape(1) != 3) {
        throw std::runtime_error("faces 必须是 (M,3) 数组");
    }
    const int64_t n2 = verts_2d.shape(0);
    const int64_t m = faces.shape(0);
    if (n2 <= 0 || m <= 0) {
        py::array_t<double> v3({0, 3});
        py::array_t<int32_t> f3({0, 3});
        return {v3, f3};
    }

    py::array_t<double> verts_3d({n2 * 2, static_cast<py::ssize_t>(3)});
    double* vdst = verts_3d.mutable_data();
    const double* vsrc = verts_2d.data();
    for (int64_t i = 0; i < n2; i++) {
        const double x = vsrc[i * 2 + 0];
        const double y = vsrc[i * 2 + 1];
        vdst[i * 3 + 0] = x;
        vdst[i * 3 + 1] = y;
        vdst[i * 3 + 2] = z_start;
        vdst[(i + n2) * 3 + 0] = x;
        vdst[(i + n2) * 3 + 1] = y;
        vdst[(i + n2) * 3 + 2] = z_end;
    }

    std::vector<std::array<int32_t, 3>> out_faces;
    out_faces.reserve(static_cast<size_t>(m) * 2 + static_cast<size_t>(n2) * 4);

    const uint32_t* fsrc = faces.data();
    for (int64_t i = 0; i < m; i++) {
        const uint32_t a = fsrc[i * 3 + 0];
        const uint32_t b = fsrc[i * 3 + 1];
        const uint32_t c = fsrc[i * 3 + 2];
        out_faces.push_back({static_cast<int32_t>(c), static_cast<int32_t>(b), static_cast<int32_t>(a)});
        out_faces.push_back({static_cast<int32_t>(a + n2), static_cast<int32_t>(b + n2), static_cast<int32_t>(c + n2)});
    }

    uint32_t start = 0;
    for (uint32_t end : ring_end_indices) {
        if (end <= start) {
            continue;
        }
        const uint32_t n = end - start;
        if (n < 3) {
            start = end;
            continue;
        }
        for (uint32_t i = 0; i < n; i++) {
            const uint32_t u0 = start + i;
            const uint32_t v0 = start + (i + 1) % n;
            const int32_t u = static_cast<int32_t>(u0);
            const int32_t v = static_cast<int32_t>(v0);
            const int32_t u2 = u + static_cast<int32_t>(n2);
            const int32_t v2 = v + static_cast<int32_t>(n2);
            out_faces.push_back({u, v, v2});
            out_faces.push_back({u, v2, u2});
        }
        start = end;
    }

    std::vector<double> verts_tmp;
    verts_tmp.resize(static_cast<size_t>(n2) * 2 * 3);
    std::memcpy(verts_tmp.data(), verts_3d.data(), verts_tmp.size() * sizeof(double));

    std::vector<int32_t> faces_tmp_flat;
    faces_tmp_flat.resize(out_faces.size() * 3);
    for (size_t i = 0; i < out_faces.size(); i++) {
        faces_tmp_flat[i * 3 + 0] = out_faces[i][0];
        faces_tmp_flat[i * 3 + 1] = out_faces[i][1];
        faces_tmp_flat[i * 3 + 2] = out_faces[i][2];
    }
    py::array_t<int32_t> faces_3d({static_cast<py::ssize_t>(out_faces.size()), static_cast<py::ssize_t>(3)});
    int32_t* fdst = faces_3d.mutable_data();
    for (size_t i = 0; i < out_faces.size(); i++) {
        fdst[i * 3 + 0] = out_faces[i][0];
        fdst[i * 3 + 1] = out_faces[i][1];
        fdst[i * 3 + 2] = out_faces[i][2];
    }
    return {verts_3d, faces_3d};
}

// 对多个环进行三角剖分并拉伸为3D网格，返回3D顶点、面片和三角形总面积
std::tuple<py::array_t<double>, py::array_t<int32_t>, double> extrude_rings(
    const py::iterable& rings,
    double z_start,
    double z_end
) {
    auto tri = earcut_triangulate_rings(rings);
    py::array_t<double> verts_2d = std::get<0>(tri);
    py::array_t<uint32_t> faces = std::get<1>(tri);
    std::vector<uint32_t> ring_end = std::get<2>(tri);
    double tri_area = std::get<3>(tri);
    auto extr = extrude_triangulation(verts_2d, faces, ring_end, z_start, z_end);
    return {extr.first, extr.second, tri_area};
}

// 无GIL版本的环拉伸函数，支持多线程并发
std::tuple<py::array_t<double>, py::array_t<int32_t>, double> extrude_rings_nogil(
    const py::iterable& rings,
    double z_start,
    double z_end
) {
    double minx = std::numeric_limits<double>::infinity();
    double miny = std::numeric_limits<double>::infinity();
    double maxx = -std::numeric_limits<double>::infinity();
    double maxy = -std::numeric_limits<double>::infinity();

    std::vector<std::vector<EarcutPoint>> raw;
    raw.reserve(8);
    for (const py::handle& h : rings) {
        py::array arr = py::array::ensure(h);
        if (!arr) {
            continue;
        }
        if (arr.ndim() != 2 || arr.shape(1) != 2) {
            throw std::runtime_error("ring 必须是 (N,2) 数组");
        }
        py::array_t<double, py::array::c_style | py::array::forcecast> pts(arr);
        const auto n = static_cast<size_t>(pts.shape(0));
        if (n < 3) {
            continue;
        }
        const double* p = pts.data();
        std::vector<EarcutPoint> ring;
        ring.reserve(n);
        for (size_t i = 0; i < n; i++) {
            const double x = p[i * 2 + 0];
            const double y = p[i * 2 + 1];
            ring.push_back(EarcutPoint{x, y});
            minx = std::min(minx, x);
            miny = std::min(miny, y);
            maxx = std::max(maxx, x);
            maxy = std::max(maxy, y);
        }
        raw.push_back(std::move(ring));
    }

    if (raw.empty()) {
        py::array_t<double> v3({0, 3});
        py::array_t<int32_t> f3({0, 3});
        return {v3, f3, 0.0};
    }

    const double dx = maxx - minx;
    const double dy = maxy - miny;
    const double scale = std::max(1.0, std::max(dx, dy));
    const double eps = 1e-7 * scale;

    std::vector<double> out_verts;
    std::vector<int32_t> out_faces;
    double tri_area = 0.0;

    {
        py::gil_scoped_release release;

        std::vector<std::vector<EarcutPoint>> poly;
        poly.reserve(raw.size());
        bool first_ring = true;
        for (auto ring : raw) {
            if (ring.size() < 3) {
                continue;
            }
            const double a = earcut_signed_area(ring);
            if (first_ring) {
                if (a < 0.0) {
                    std::reverse(ring.begin(), ring.end());
                }
                first_ring = false;
            } else {
                if (a > 0.0) {
                    std::reverse(ring.begin(), ring.end());
                }
            }
            poly.push_back(std::move(ring));
        }

        if (!poly.empty()) {
            std::vector<EarcutPoint> vertices;
            vertices.reserve(256);
            uint32_t cum = 0;
            for (const auto& ring : poly) {
                cum += static_cast<uint32_t>(ring.size());
            }
            vertices.reserve(cum);
            std::vector<uint32_t> ring_end_indices;
            ring_end_indices.reserve(poly.size());
            for (const auto& ring : poly) {
                for (const auto& pt : ring) {
                    vertices.push_back(pt);
                }
                ring_end_indices.push_back(static_cast<uint32_t>(vertices.size()));
            }

            const std::vector<uint32_t> indices = mapbox::earcut<uint32_t>(poly);
            const size_t tri_count = indices.size() / 3;

            for (size_t i = 0; i < tri_count; i++) {
                const auto i0 = indices[i * 3 + 0];
                const auto i1 = indices[i * 3 + 1];
                const auto i2 = indices[i * 3 + 2];
                const auto& a = vertices[i0];
                const auto& b = vertices[i1];
                const auto& c = vertices[i2];
                const double cross = std::abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
                tri_area += 0.5 * cross;
            }

            const size_t n2 = vertices.size();
            if (n2 > 0 && tri_count > 0) {
                out_verts.resize(n2 * 2 * 3);
                for (size_t i = 0; i < n2; i++) {
                    const double x = vertices[i][0];
                    const double y = vertices[i][1];
                    out_verts[i * 3 + 0] = x;
                    out_verts[i * 3 + 1] = y;
                    out_verts[i * 3 + 2] = z_start;
                    out_verts[(i + n2) * 3 + 0] = x;
                    out_verts[(i + n2) * 3 + 1] = y;
                    out_verts[(i + n2) * 3 + 2] = z_end;
                }

                std::vector<std::array<int32_t, 3>> faces_tmp;
                faces_tmp.reserve(tri_count * 2 + n2 * 4);
                for (size_t i = 0; i < tri_count; i++) {
                    const uint32_t a = indices[i * 3 + 0];
                    const uint32_t b = indices[i * 3 + 1];
                    const uint32_t c = indices[i * 3 + 2];
                    faces_tmp.push_back({static_cast<int32_t>(c), static_cast<int32_t>(b), static_cast<int32_t>(a)});
                    faces_tmp.push_back({static_cast<int32_t>(a + n2), static_cast<int32_t>(b + n2), static_cast<int32_t>(c + n2)});
                }

                struct EdgeEntry {
                    uint32_t count = 0;
                    uint32_t u = 0;
                    uint32_t v = 0;
                    uint32_t w = 0;
                };

                auto edge_key = [](uint32_t a, uint32_t b) -> uint64_t {
                    const uint32_t lo = (a < b) ? a : b;
                    const uint32_t hi = (a < b) ? b : a;
                    return (static_cast<uint64_t>(lo) << 32) | static_cast<uint64_t>(hi);
                };

                std::unordered_map<uint64_t, EdgeEntry> edge_map;
                edge_map.reserve(indices.size());

                auto add_edge = [&](uint32_t u, uint32_t v, uint32_t w) {
                    const uint64_t key = edge_key(u, v);
                    auto it = edge_map.find(key);
                    if (it == edge_map.end()) {
                        EdgeEntry e;
                        e.count = 1;
                        e.u = u;
                        e.v = v;
                        e.w = w;
                        edge_map.emplace(key, e);
                    } else {
                        it->second.count += 1;
                    }
                };

                for (size_t i = 0; i < tri_count; i++) {
                    const uint32_t a = indices[i * 3 + 0];
                    const uint32_t b = indices[i * 3 + 1];
                    const uint32_t c = indices[i * 3 + 2];
                    add_edge(a, b, c);
                    add_edge(b, c, a);
                    add_edge(c, a, b);
                }

                for (const auto& kv : edge_map) {
                    const EdgeEntry& e = kv.second;
                    if (e.count != 1) {
                        continue;
                    }
                    uint32_t u = e.u;
                    uint32_t v = e.v;
                    const uint32_t w = e.w;

                    const double ux = vertices[u][0];
                    const double uy = vertices[u][1];
                    const double vx = vertices[v][0];
                    const double vy = vertices[v][1];
                    const double wx = vertices[w][0];
                    const double wy = vertices[w][1];
                    const double cross = (vx - ux) * (wy - uy) - (vy - uy) * (wx - ux);
                    if (cross < 0.0) {
                        std::swap(u, v);
                    }

                    const int32_t u_i = static_cast<int32_t>(u);
                    const int32_t v_i = static_cast<int32_t>(v);
                    const int32_t u2 = u_i + static_cast<int32_t>(n2);
                    const int32_t v2 = v_i + static_cast<int32_t>(n2);
                    faces_tmp.push_back({u_i, v_i, v2});
                    faces_tmp.push_back({u_i, v2, u2});
                }

                out_faces.resize(faces_tmp.size() * 3);
                for (size_t i = 0; i < faces_tmp.size(); i++) {
                    out_faces[i * 3 + 0] = faces_tmp[i][0];
                    out_faces[i * 3 + 1] = faces_tmp[i][1];
                    out_faces[i * 3 + 2] = faces_tmp[i][2];
                }
            }
        }
    }

    if (out_verts.empty() || out_faces.empty()) {
        py::array_t<double> v3({0, 3});
        py::array_t<int32_t> f3({0, 3});
        return {v3, f3, tri_area};
    }

    const py::ssize_t n3 = static_cast<py::ssize_t>(out_verts.size() / 3);
    const py::ssize_t t3 = static_cast<py::ssize_t>(out_faces.size() / 3);
    py::array_t<double> v3({n3, static_cast<py::ssize_t>(3)});
    std::memcpy(v3.mutable_data(), out_verts.data(), out_verts.size() * sizeof(double));

    py::array_t<int32_t> f3({t3, static_cast<py::ssize_t>(3)});
    std::memcpy(f3.mutable_data(), out_faces.data(), out_faces.size() * sizeof(int32_t));

    return {v3, f3, tri_area};
}
