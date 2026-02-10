/**
 * 网格工具模块 - 提供网格清理、分析和导出功能
 * 包括顶点去重、退化面移除、STL导出等功能
 */

#include "mesh_utils.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <utility>
#include <vector>

namespace py = pybind11;

// 基础网格清理（无GIL版本）：移除无效顶点、越界面、退化面和重复面
std::tuple<py::array_t<double>, py::array_t<int32_t>, py::dict> mesh_clean_basic_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int64_t, py::array::c_style | py::array::forcecast> faces
) {
    if (vertices.ndim() != 2 || vertices.shape(1) != 3) {
        throw std::runtime_error("vertices 必须是 (N,3) 数组");
    }
    if (faces.ndim() != 2 || faces.shape(1) != 3) {
        throw std::runtime_error("faces 必须是 (M,3) 数组");
    }

    const int64_t v_count64 = vertices.shape(0);
    const int64_t f_count64 = faces.shape(0);
    if (v_count64 < 0 || f_count64 < 0) {
        throw std::runtime_error("非法的顶点/面数量");
    }
    if (v_count64 > static_cast<int64_t>(std::numeric_limits<uint32_t>::max())) {
        throw std::runtime_error("顶点数量过大，超过 uint32 范围");
    }
    if (f_count64 > static_cast<int64_t>(std::numeric_limits<uint32_t>::max())) {
        throw std::runtime_error("面数量过大，超过 uint32 范围");
    }

    const uint32_t v_count = static_cast<uint32_t>(v_count64);
    const uint32_t f_count = static_cast<uint32_t>(f_count64);

    py::dict rep;
    rep["vertices_in"] = static_cast<int64_t>(v_count);
    rep["faces_in"] = static_cast<int64_t>(f_count);

    if (v_count == 0 || f_count == 0) {
        py::array_t<double> v_out({0, 3});
        py::array_t<int32_t> f_out({0, 3});
        rep["vertices_out"] = static_cast<int64_t>(0);
        rep["faces_out"] = static_cast<int64_t>(0);
        rep["removed_oob_faces"] = static_cast<int64_t>(0);
        rep["removed_invalid_vertex_faces"] = static_cast<int64_t>(0);
        rep["removed_degenerate_faces"] = static_cast<int64_t>(0);
        rep["removed_duplicate_faces"] = static_cast<int64_t>(0);
        rep["removed_unreferenced_vertices"] = static_cast<int64_t>(0);
        return {v_out, f_out, rep};
    }

    const double* vptr = vertices.data();
    const int64_t* fptr = faces.data();

    std::vector<uint8_t> v_ok(v_count, 1);
    uint64_t invalid_vertices = 0;
    for (uint32_t i = 0; i < v_count; i++) {
        const double x = vptr[static_cast<size_t>(i) * 3 + 0];
        const double y = vptr[static_cast<size_t>(i) * 3 + 1];
        const double z = vptr[static_cast<size_t>(i) * 3 + 2];
        if (!(std::isfinite(x) && std::isfinite(y) && std::isfinite(z))) {
            v_ok[i] = 0;
            invalid_vertices++;
        }
    }

    auto tri_area2 = [&](uint32_t i0, uint32_t i1, uint32_t i2) -> double {
        const double* a = vptr + static_cast<size_t>(i0) * 3;
        const double* b = vptr + static_cast<size_t>(i1) * 3;
        const double* c = vptr + static_cast<size_t>(i2) * 3;
        const double abx = b[0] - a[0];
        const double aby = b[1] - a[1];
        const double abz = b[2] - a[2];
        const double acx = c[0] - a[0];
        const double acy = c[1] - a[1];
        const double acz = c[2] - a[2];
        const double cx = aby * acz - abz * acy;
        const double cy = abz * acx - abx * acz;
        const double cz = abx * acy - aby * acx;
        return cx * cx + cy * cy + cz * cz;
    };

    std::vector<FaceKeyWithFace> tmp;
    tmp.reserve(static_cast<size_t>(f_count));

    uint64_t removed_oob_faces = 0;
    uint64_t removed_invalid_vertex_faces = 0;
    uint64_t removed_degenerate_faces = 0;

    {
        py::gil_scoped_release release;
        for (uint32_t i = 0; i < f_count; i++) {
            const int64_t a64 = fptr[static_cast<size_t>(i) * 3 + 0];
            const int64_t b64 = fptr[static_cast<size_t>(i) * 3 + 1];
            const int64_t c64 = fptr[static_cast<size_t>(i) * 3 + 2];
            if (a64 < 0 || b64 < 0 || c64 < 0 || a64 >= v_count || b64 >= v_count || c64 >= v_count) {
                removed_oob_faces++;
                continue;
            }
            const uint32_t a = static_cast<uint32_t>(a64);
            const uint32_t b = static_cast<uint32_t>(b64);
            const uint32_t c = static_cast<uint32_t>(c64);

            if (!v_ok[a] || !v_ok[b] || !v_ok[c]) {
                removed_invalid_vertex_faces++;
                continue;
            }

            bool deg = false;
            if (a == b || b == c || a == c) {
                deg = true;
            } else {
                const double area2 = tri_area2(a, b, c);
                if (!(area2 > 1e-24)) {
                    deg = true;
                }
            }
            if (deg) {
                removed_degenerate_faces++;
                continue;
            }

            uint32_t sa = a;
            uint32_t sb = b;
            uint32_t sc = c;
            if (sa > sb) {
                std::swap(sa, sb);
            }
            if (sb > sc) {
                std::swap(sb, sc);
            }
            if (sa > sb) {
                std::swap(sa, sb);
            }

            FaceKeyWithFace it;
            it.k = FaceKey{sa, sb, sc};
            it.f = {static_cast<int32_t>(a), static_cast<int32_t>(b), static_cast<int32_t>(c)};
            tmp.push_back(it);
        }
    }

    if (tmp.empty()) {
        py::array_t<double> v_out({0, 3});
        py::array_t<int32_t> f_out({0, 3});
        rep["vertices_out"] = static_cast<int64_t>(0);
        rep["faces_out"] = static_cast<int64_t>(0);
        rep["invalid_vertices"] = static_cast<int64_t>(invalid_vertices);
        rep["removed_oob_faces"] = static_cast<int64_t>(removed_oob_faces);
        rep["removed_invalid_vertex_faces"] = static_cast<int64_t>(removed_invalid_vertex_faces);
        rep["removed_degenerate_faces"] = static_cast<int64_t>(removed_degenerate_faces);
        rep["removed_duplicate_faces"] = static_cast<int64_t>(0);
        rep["removed_unreferenced_vertices"] = static_cast<int64_t>(v_count);
        return {v_out, f_out, rep};
    }

    {
        py::gil_scoped_release release;
        std::sort(tmp.begin(), tmp.end(), [](const FaceKeyWithFace& x, const FaceKeyWithFace& y) {
            return std::tie(x.k.a, x.k.b, x.k.c) < std::tie(y.k.a, y.k.b, y.k.c);
        });
    }

    std::vector<std::array<int32_t, 3>> out_faces;
    out_faces.reserve(tmp.size());

    uint64_t removed_duplicate_faces = 0;
    {
        py::gil_scoped_release release;
        FaceKey prev = tmp.front().k;
        out_faces.push_back(tmp.front().f);
        for (size_t i = 1; i < tmp.size(); i++) {
            const FaceKey cur = tmp[i].k;
            if (cur.a == prev.a && cur.b == prev.b && cur.c == prev.c) {
                removed_duplicate_faces++;
                continue;
            }
            prev = cur;
            out_faces.push_back(tmp[i].f);
        }
    }

    std::vector<uint8_t> used(v_count, 0);
    {
        py::gil_scoped_release release;
        for (const auto& ff : out_faces) {
            used[static_cast<uint32_t>(ff[0])] = 1;
            used[static_cast<uint32_t>(ff[1])] = 1;
            used[static_cast<uint32_t>(ff[2])] = 1;
        }
    }

    std::vector<int32_t> remap(v_count, -1);
    uint32_t new_v_count = 0;
    {
        py::gil_scoped_release release;
        for (uint32_t i = 0; i < v_count; i++) {
            if (used[i]) {
                remap[i] = static_cast<int32_t>(new_v_count);
                new_v_count++;
            }
        }
    }

    py::array_t<double> v_out({static_cast<py::ssize_t>(new_v_count), static_cast<py::ssize_t>(3)});
    double* vdst = v_out.mutable_data();
    {
        py::gil_scoped_release release;
        for (uint32_t i = 0; i < v_count; i++) {
            const int32_t ni = remap[i];
            if (ni < 0) {
                continue;
            }
            const double x = vptr[static_cast<size_t>(i) * 3 + 0];
            const double y = vptr[static_cast<size_t>(i) * 3 + 1];
            const double z = vptr[static_cast<size_t>(i) * 3 + 2];
            vdst[static_cast<size_t>(ni) * 3 + 0] = x;
            vdst[static_cast<size_t>(ni) * 3 + 1] = y;
            vdst[static_cast<size_t>(ni) * 3 + 2] = z;
        }
    }

    py::array_t<int32_t> f_out({static_cast<py::ssize_t>(out_faces.size()), static_cast<py::ssize_t>(3)});
    int32_t* fdst = f_out.mutable_data();

    {
        py::gil_scoped_release release;
        for (size_t i = 0; i < out_faces.size(); i++) {
            const int32_t a0 = out_faces[i][0];
            const int32_t b0 = out_faces[i][1];
            const int32_t c0 = out_faces[i][2];
            const int32_t a1 = remap[static_cast<uint32_t>(a0)];
            const int32_t b1 = remap[static_cast<uint32_t>(b0)];
            const int32_t c1 = remap[static_cast<uint32_t>(c0)];
            if (a1 < 0 || b1 < 0 || c1 < 0) {
                throw std::runtime_error("内部错误：remap 失败");
            }
            fdst[i * 3 + 0] = a1;
            fdst[i * 3 + 1] = b1;
            fdst[i * 3 + 2] = c1;
        }
    }

    const int64_t removed_unreferenced_vertices = static_cast<int64_t>(v_count) - static_cast<int64_t>(new_v_count);

    rep["invalid_vertices"] = static_cast<int64_t>(invalid_vertices);
    rep["vertices_out"] = static_cast<int64_t>(new_v_count);
    rep["faces_out"] = static_cast<int64_t>(out_faces.size());
    rep["removed_oob_faces"] = static_cast<int64_t>(removed_oob_faces);
    rep["removed_invalid_vertex_faces"] = static_cast<int64_t>(removed_invalid_vertex_faces);
    rep["removed_degenerate_faces"] = static_cast<int64_t>(removed_degenerate_faces);
    rep["removed_duplicate_faces"] = static_cast<int64_t>(removed_duplicate_faces);
    rep["removed_unreferenced_vertices"] = removed_unreferenced_vertices;

    return {v_out, f_out, rep};
}

// 基础网格分析（无GIL版本）：统计顶点数、面数、非流形边、边界边等信息
py::dict mesh_analyze_basic_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int64_t, py::array::c_style | py::array::forcecast> faces
) {
    if (vertices.ndim() != 2 || vertices.shape(1) != 3) {
        throw std::runtime_error("vertices 必须是 (N,3) 数组");
    }
    if (faces.ndim() != 2 || faces.shape(1) != 3) {
        throw std::runtime_error("faces 必须是 (M,3) 数组");
    }

    const auto v_count = static_cast<uint32_t>(vertices.shape(0));
    const auto f_count = static_cast<uint32_t>(faces.shape(0));
    if (v_count == 0 || f_count == 0) {
        py::dict out;
        out["vertices"] = static_cast<int64_t>(v_count);
        out["faces"] = static_cast<int64_t>(f_count);
        out["non_manifold_edges"] = static_cast<int64_t>(0);
        out["boundary_edges"] = static_cast<int64_t>(0);
        out["degenerate_faces"] = static_cast<int64_t>(0);
        out["duplicate_faces"] = static_cast<int64_t>(0);
        out["watertight"] = false;
        return out;
    }

    const double* vptr = vertices.data();
    const int64_t* fptr = faces.data();

    uint64_t degenerate_faces = 0;

    std::vector<uint64_t> packed_edges;
    packed_edges.reserve(static_cast<size_t>(f_count) * 3);

    std::vector<FaceKey> face_keys;
    face_keys.reserve(static_cast<size_t>(f_count));

    auto pack_edge = [](uint32_t u, uint32_t v) -> uint64_t {
        if (u > v) {
            std::swap(u, v);
        }
        return (static_cast<uint64_t>(u) << 32) | static_cast<uint64_t>(v);
    };

    auto tri_area2 = [&](uint32_t i0, uint32_t i1, uint32_t i2) -> double {
        const double* a = vptr + static_cast<size_t>(i0) * 3;
        const double* b = vptr + static_cast<size_t>(i1) * 3;
        const double* c = vptr + static_cast<size_t>(i2) * 3;
        const double abx = b[0] - a[0];
        const double aby = b[1] - a[1];
        const double abz = b[2] - a[2];
        const double acx = c[0] - a[0];
        const double acy = c[1] - a[1];
        const double acz = c[2] - a[2];
        const double cx = aby * acz - abz * acy;
        const double cy = abz * acx - abx * acz;
        const double cz = abx * acy - aby * acx;
        return cx * cx + cy * cy + cz * cz;
    };

    uint64_t non_manifold_edges = 0;
    uint64_t boundary_edges = 0;
    uint64_t duplicate_faces = 0;

    {
        py::gil_scoped_release release;

        for (uint32_t i = 0; i < f_count; i++) {
            const int64_t a64 = fptr[static_cast<size_t>(i) * 3 + 0];
            const int64_t b64 = fptr[static_cast<size_t>(i) * 3 + 1];
            const int64_t c64 = fptr[static_cast<size_t>(i) * 3 + 2];
            if (a64 < 0 || b64 < 0 || c64 < 0 || a64 >= v_count || b64 >= v_count || c64 >= v_count) {
                throw std::runtime_error("faces 存在越界索引");
            }
            const uint32_t a = static_cast<uint32_t>(a64);
            const uint32_t b = static_cast<uint32_t>(b64);
            const uint32_t c = static_cast<uint32_t>(c64);

            uint32_t sa = a;
            uint32_t sb = b;
            uint32_t sc = c;
            if (sa > sb) {
                std::swap(sa, sb);
            }
            if (sb > sc) {
                std::swap(sb, sc);
            }
            if (sa > sb) {
                std::swap(sa, sb);
            }
            face_keys.push_back(FaceKey{sa, sb, sc});

            bool deg = false;
            if (a == b || b == c || a == c) {
                deg = true;
            } else {
                const double area2 = tri_area2(a, b, c);
                if (!(area2 > 1e-24)) {
                    deg = true;
                }
            }
            if (deg) {
                degenerate_faces++;
                continue;
            }

            packed_edges.push_back(pack_edge(a, b));
            packed_edges.push_back(pack_edge(b, c));
            packed_edges.push_back(pack_edge(c, a));
        }

        std::sort(face_keys.begin(), face_keys.end(), [](const FaceKey& x, const FaceKey& y) {
            return std::tie(x.a, x.b, x.c) < std::tie(y.a, y.b, y.c);
        });

        for (size_t i = 1; i < face_keys.size(); i++) {
            const auto& prev = face_keys[i - 1];
            const auto& cur = face_keys[i];
            if (prev.a == cur.a && prev.b == cur.b && prev.c == cur.c) {
                duplicate_faces++;
            }
        }

        std::sort(packed_edges.begin(), packed_edges.end());
        for (size_t i = 0; i < packed_edges.size();) {
            const uint64_t e = packed_edges[i];
            size_t j = i + 1;
            while (j < packed_edges.size() && packed_edges[j] == e) {
                j++;
            }
            const size_t cnt = j - i;
            if (cnt == 1) {
                boundary_edges++;
            } else if (cnt > 2) {
                non_manifold_edges++;
            }
            i = j;
        }
    }

    const bool watertight = (boundary_edges == 0 && non_manifold_edges == 0);

    py::dict out;
    out["vertices"] = static_cast<int64_t>(v_count);
    out["faces"] = static_cast<int64_t>(f_count);
    out["non_manifold_edges"] = static_cast<int64_t>(non_manifold_edges);
    out["boundary_edges"] = static_cast<int64_t>(boundary_edges);
    out["degenerate_faces"] = static_cast<int64_t>(degenerate_faces);
    out["duplicate_faces"] = static_cast<int64_t>(duplicate_faces);
    out["watertight"] = watertight;
    return out;
}

// 将网格写入二进制STL文件（无GIL版本）
void write_binary_stl_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int64_t, py::array::c_style | py::array::forcecast> faces,
    const std::string& file_path
) {
    if (vertices.ndim() != 2 || vertices.shape(1) != 3) {
        throw std::runtime_error("vertices 必须是 (N,3) 数组");
    }
    if (faces.ndim() != 2 || faces.shape(1) != 3) {
        throw std::runtime_error("faces 必须是 (M,3) 数组");
    }

    const int64_t v_count = vertices.shape(0);
    const int64_t f_count = faces.shape(0);
    if (v_count < 0 || f_count < 0) {
        throw std::runtime_error("非法的顶点/面数量");
    }

    const double* v = vertices.data();
    const int64_t* f = faces.data();

    py::gil_scoped_release release;

    std::ofstream out(file_path, std::ios::binary);
    if (!out) {
        throw std::runtime_error("无法打开 STL 文件: " + file_path);
    }

    std::array<char, 80> header{};
    const std::string name = "OpenColor";
    std::memcpy(header.data(), name.data(), std::min<size_t>(name.size(), header.size()));
    out.write(header.data(), static_cast<std::streamsize>(header.size()));

    const uint32_t tri_count = (f_count > static_cast<int64_t>(std::numeric_limits<uint32_t>::max()))
        ? std::numeric_limits<uint32_t>::max()
        : static_cast<uint32_t>(f_count);
    out.write(reinterpret_cast<const char*>(&tri_count), static_cast<std::streamsize>(sizeof(uint32_t)));

    for (int64_t i = 0; i < f_count; i++) {
        const int64_t i0 = f[i * 3 + 0];
        const int64_t i1 = f[i * 3 + 1];
        const int64_t i2 = f[i * 3 + 2];
        if (i0 < 0 || i1 < 0 || i2 < 0 || i0 >= v_count || i1 >= v_count || i2 >= v_count) {
            throw std::runtime_error("faces 含有越界索引");
        }

        const double ax = v[i0 * 3 + 0];
        const double ay = v[i0 * 3 + 1];
        const double az = v[i0 * 3 + 2];
        const double bx = v[i1 * 3 + 0];
        const double by = v[i1 * 3 + 1];
        const double bz = v[i1 * 3 + 2];
        const double cx = v[i2 * 3 + 0];
        const double cy = v[i2 * 3 + 1];
        const double cz = v[i2 * 3 + 2];

        const double ux = bx - ax;
        const double uy = by - ay;
        const double uz = bz - az;
        const double vx = cx - ax;
        const double vy = cy - ay;
        const double vz = cz - az;

        double nx = uy * vz - uz * vy;
        double ny = uz * vx - ux * vz;
        double nz = ux * vy - uy * vx;

        const double n2 = nx * nx + ny * ny + nz * nz;
        if (n2 > 0.0) {
            const double inv = 1.0 / std::sqrt(n2);
            nx *= inv;
            ny *= inv;
            nz *= inv;
        } else {
            nx = 0.0;
            ny = 0.0;
            nz = 0.0;
        }

        const float nxf = static_cast<float>(nx);
        const float nyf = static_cast<float>(ny);
        const float nzf = static_cast<float>(nz);
        const float axf = static_cast<float>(ax);
        const float ayf = static_cast<float>(ay);
        const float azf = static_cast<float>(az);
        const float bxf = static_cast<float>(bx);
        const float byf = static_cast<float>(by);
        const float bzf = static_cast<float>(bz);
        const float cxf = static_cast<float>(cx);
        const float cyf = static_cast<float>(cy);
        const float czf = static_cast<float>(cz);

        out.write(reinterpret_cast<const char*>(&nxf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&nyf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&nzf), static_cast<std::streamsize>(sizeof(float)));

        out.write(reinterpret_cast<const char*>(&axf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&ayf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&azf), static_cast<std::streamsize>(sizeof(float)));

        out.write(reinterpret_cast<const char*>(&bxf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&byf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&bzf), static_cast<std::streamsize>(sizeof(float)));

        out.write(reinterpret_cast<const char*>(&cxf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&cyf), static_cast<std::streamsize>(sizeof(float)));
        out.write(reinterpret_cast<const char*>(&czf), static_cast<std::streamsize>(sizeof(float)));

        const uint16_t attr = 0;
        out.write(reinterpret_cast<const char*>(&attr), static_cast<std::streamsize>(sizeof(uint16_t)));
    }

    if (!out.good()) {
        throw std::runtime_error("写入 STL 失败: " + file_path);
    }
}
