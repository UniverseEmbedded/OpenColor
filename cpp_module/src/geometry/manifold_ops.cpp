/* Manifold几何操作模块 - 提供网格布尔运算和体积计算功能
 * 
 * 该模块基于manifold库实现，提供以下功能：
 * - 从顶点面片数据创建Manifold对象
 * - 网格布尔运算：并集、差集、交集
 * - 网格体积计算
 * 支持Python绑定，可在Python中调用
 */

#include "manifold_ops.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace py = pybind11;

/* 从顶点和面片数组创建Manifold对象
 * 
 * 参数:
 *   vertices: (N,3)形状的顶点数组
 *   faces: (M,3)形状的面片索引数组
 * 
 * 返回:
 *   Manifold对象
 * 
 * 注意：会自动检测并修正面片朝向，确保体积为正
 */
manifold::Manifold manifold_from_mesh(
    py::array_t<double, py::array::c_style | py::array::forcecast> vertices,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> faces
) {
    if (vertices.ndim() != 2 || vertices.shape(1) != 3) {
        throw std::runtime_error("vertices 必须是 (N,3) 数组");
    }
    if (faces.ndim() != 2 || faces.shape(1) != 3) {
        throw std::runtime_error("faces 必须是 (M,3) 数组");
    }
    const size_t n = static_cast<size_t>(vertices.shape(0));
    const size_t m = static_cast<size_t>(faces.shape(0));
    if (n > static_cast<size_t>(UINT32_MAX)) {
        throw std::runtime_error("顶点数量过大，超过 uint32 范围");
    }
    const double* vsrc = vertices.data();
    const int32_t* fsrc = faces.data();

    std::vector<uint8_t> v_ok(n, 1);
    uint64_t invalid_vertices = 0;
    for (size_t i = 0; i < n; i++) {
        const double x = vsrc[i * 3 + 0];
        const double y = vsrc[i * 3 + 1];
        const double z = vsrc[i * 3 + 2];
        if (!(std::isfinite(x) && std::isfinite(y) && std::isfinite(z))) {
            v_ok[i] = 0;
            invalid_vertices++;
        }
    }

    auto tri_area2 = [&](uint32_t i0, uint32_t i1, uint32_t i2) -> double {
        const double* a = vsrc + static_cast<size_t>(i0) * 3;
        const double* b = vsrc + static_cast<size_t>(i1) * 3;
        const double* c = vsrc + static_cast<size_t>(i2) * 3;
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

    std::vector<uint8_t> used(n, 0);
    std::vector<std::array<uint32_t, 3>> faces_ok;
    faces_ok.reserve(m);

    uint64_t removed_oob_faces = 0;
    uint64_t removed_invalid_vertex_faces = 0;
    uint64_t removed_degenerate_faces = 0;
    for (size_t i = 0; i < m; i++) {
        const int32_t a0 = fsrc[i * 3 + 0];
        const int32_t b0 = fsrc[i * 3 + 1];
        const int32_t c0 = fsrc[i * 3 + 2];
        if (a0 < 0 || b0 < 0 || c0 < 0 || static_cast<size_t>(a0) >= n || static_cast<size_t>(b0) >= n || static_cast<size_t>(c0) >= n) {
            removed_oob_faces++;
            continue;
        }
        const uint32_t a = static_cast<uint32_t>(a0);
        const uint32_t b = static_cast<uint32_t>(b0);
        const uint32_t c = static_cast<uint32_t>(c0);

        if (!v_ok[static_cast<size_t>(a)] || !v_ok[static_cast<size_t>(b)] || !v_ok[static_cast<size_t>(c)]) {
            removed_invalid_vertex_faces++;
            continue;
        }

        if (a == b || b == c || a == c) {
            removed_degenerate_faces++;
            continue;
        }

        used[static_cast<size_t>(a)] = 1;
        used[static_cast<size_t>(b)] = 1;
        used[static_cast<size_t>(c)] = 1;
        faces_ok.push_back({a, b, c});
    }

    if (faces_ok.empty()) {
        throw std::runtime_error(
            "输入网格没有有效三角形: vertices=" + std::to_string(n) +
            ", faces=" + std::to_string(m) +
            ", invalid_vertices=" + std::to_string(invalid_vertices) +
            ", removed_oob_faces=" + std::to_string(removed_oob_faces) +
            ", removed_invalid_vertex_faces=" + std::to_string(removed_invalid_vertex_faces) +
            ", removed_degenerate_faces=" + std::to_string(removed_degenerate_faces)
        );
    }

    std::vector<uint32_t> remap(n, UINT32_MAX);
    uint32_t new_n = 0;
    for (size_t i = 0; i < n; i++) {
        if (used[i]) {
            remap[i] = new_n;
            new_n++;
        }
    }

    // 计算有符号体积的6倍，用于判断面片朝向
    double vol6 = 0.0;
    for (const auto& tri : faces_ok) {
        const uint32_t ia = tri[0];
        const uint32_t ib = tri[1];
        const uint32_t ic = tri[2];

        const double ax = vsrc[static_cast<size_t>(ia) * 3 + 0];
        const double ay = vsrc[static_cast<size_t>(ia) * 3 + 1];
        const double az = vsrc[static_cast<size_t>(ia) * 3 + 2];
        const double bx = vsrc[static_cast<size_t>(ib) * 3 + 0];
        const double by = vsrc[static_cast<size_t>(ib) * 3 + 1];
        const double bz = vsrc[static_cast<size_t>(ib) * 3 + 2];
        const double cx = vsrc[static_cast<size_t>(ic) * 3 + 0];
        const double cy = vsrc[static_cast<size_t>(ic) * 3 + 1];
        const double cz = vsrc[static_cast<size_t>(ic) * 3 + 2];

        // 计算叉积 (b-a) x (c-a)
        const double x = by * cz - bz * cy;
        const double y = bz * cx - bx * cz;
        const double z = bx * cy - by * cx;
        vol6 += ax * x + ay * y + az * z;
    }
    const bool flip_winding = (vol6 < 0.0);

    // 构建MeshGL结构
    manifold::MeshGL mesh;
    mesh.vertProperties.reserve(static_cast<size_t>(new_n) * 3);
    for (size_t i = 0; i < n; i++) {
        const uint32_t ni = remap[i];
        if (ni == UINT32_MAX) {
            continue;
        }
        mesh.vertProperties.push_back(static_cast<float>(vsrc[i * 3 + 0]));
        mesh.vertProperties.push_back(static_cast<float>(vsrc[i * 3 + 1]));
        mesh.vertProperties.push_back(static_cast<float>(vsrc[i * 3 + 2]));
    }
    mesh.triVerts.reserve(faces_ok.size() * 3);
    for (const auto& tri : faces_ok) {
        const uint32_t a = remap[static_cast<size_t>(tri[0])];
        const uint32_t b = remap[static_cast<size_t>(tri[1])];
        const uint32_t c = remap[static_cast<size_t>(tri[2])];
        if (a == UINT32_MAX || b == UINT32_MAX || c == UINT32_MAX) {
            throw std::runtime_error("内部错误：remap 失败");
        }
        if (flip_winding) {
            mesh.triVerts.push_back(a);
            mesh.triVerts.push_back(c);
            mesh.triVerts.push_back(b);
        } else {
            mesh.triVerts.push_back(a);
            mesh.triVerts.push_back(b);
            mesh.triVerts.push_back(c);
        }
    }
    mesh.numProp = 3;
    manifold::Manifold out(mesh);
    if (out.NumTri() == 0) {
        throw std::runtime_error(
            "创建 Manifold 失败: vertices_in=" + std::to_string(n) +
            ", vertices_used=" + std::to_string(new_n) +
            ", faces_in=" + std::to_string(m) +
            ", faces_used=" + std::to_string(faces_ok.size()) +
            ", invalid_vertices=" + std::to_string(invalid_vertices) +
            ", removed_oob_faces=" + std::to_string(removed_oob_faces) +
            ", removed_invalid_vertex_faces=" + std::to_string(removed_invalid_vertex_faces) +
            ", removed_degenerate_faces=" + std::to_string(removed_degenerate_faces) +
            "（提示：网格可能非封闭/非流形/自相交）"
        );
    }
    return out;
}

/* 从Manifold对象提取顶点和面片数组
 * 
 * 参数:
 *   m: Manifold对象
 * 
 * 返回:
 *   (vertices, faces)元组，vertices为(N,3)数组，faces为(M,3)数组
 */
std::pair<py::array_t<double>, py::array_t<int32_t>> mesh_from_manifold(const manifold::Manifold& m) {
    const manifold::MeshGL mesh = m.GetMeshGL();
    const size_t n = mesh.NumVert();
    const size_t t = mesh.NumTri();

    py::array_t<double> verts({static_cast<py::ssize_t>(n), static_cast<py::ssize_t>(3)});
    double* vdst = verts.mutable_data();
    for (size_t i = 0; i < n; i++) {
        vdst[i * 3 + 0] = static_cast<double>(mesh.vertProperties[i * 3 + 0]);
        vdst[i * 3 + 1] = static_cast<double>(mesh.vertProperties[i * 3 + 1]);
        vdst[i * 3 + 2] = static_cast<double>(mesh.vertProperties[i * 3 + 2]);
    }

    py::array_t<int32_t> faces({static_cast<py::ssize_t>(t), static_cast<py::ssize_t>(3)});
    int32_t* fdst = faces.mutable_data();
    for (size_t i = 0; i < t; i++) {
        fdst[i * 3 + 0] = static_cast<int32_t>(mesh.triVerts[i * 3 + 0]);
        fdst[i * 3 + 1] = static_cast<int32_t>(mesh.triVerts[i * 3 + 1]);
        fdst[i * 3 + 2] = static_cast<int32_t>(mesh.triVerts[i * 3 + 2]);
    }
    return {verts, faces};
}

/* 计算多个网格的并集
 * 
 * 参数:
 *   meshes: 可迭代的(vertices, faces)元组列表
 * 
 * 返回:
 *   并集结果的(vertices, faces)元组
 */
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_union(const py::iterable& meshes) {
    bool first = true;
    manifold::Manifold acc;

    for (const py::handle& h : meshes) {
        py::tuple t = py::cast<py::tuple>(h);
        if (t.size() != 2) {
            throw std::runtime_error("mesh 必须是 (vertices, faces)");
        }
        auto v = py::cast<py::array>(t[0]);
        auto f = py::cast<py::array>(t[1]);
        manifold::Manifold m = manifold_from_mesh(
            py::array_t<double, py::array::c_style | py::array::forcecast>(v),
            py::array_t<int32_t, py::array::c_style | py::array::forcecast>(f)
        );
        if (first) {
            acc = m;
            first = false;
        } else {
            acc = acc + m;
        }
    }
    if (first) {
        py::array_t<double> v({0, 3});
        py::array_t<int32_t> f({0, 3});
        return {v, f};
    }
    return mesh_from_manifold(acc);
}

/* 计算多个网格的并集（释放GIL版本）
 * 
 * 在布尔运算期间释放Python GIL，允许其他线程执行
 */
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_union_nogil(const py::iterable& meshes) {
    std::vector<manifold::Manifold> ms;
    ms.reserve(8);
    size_t idx = 0;
    for (const py::handle& h : meshes) {
        py::tuple t = py::cast<py::tuple>(h);
        if (t.size() != 2) {
            throw std::runtime_error("mesh 必须是 (vertices, faces)");
        }
        auto v = py::cast<py::array>(t[0]);
        auto f = py::cast<py::array>(t[1]);
        manifold::Manifold m;
        try {
            m = manifold_from_mesh(
                py::array_t<double, py::array::c_style | py::array::forcecast>(v),
                py::array_t<int32_t, py::array::c_style | py::array::forcecast>(f)
            );
        } catch (const std::exception& e) {
            throw std::runtime_error("第 " + std::to_string(idx) + " 个输入网格创建 Manifold 失败: " + std::string(e.what()));
        }
        // 检查每个输入网格的有效性
        if (m.NumTri() == 0) {
            throw std::runtime_error("第 " + std::to_string(idx) + " 个输入网格创建 Manifold 后为空 (NumTri=0)");
        }
        ms.push_back(std::move(m));
        idx++;
    }

    if (ms.empty()) {
        py::array_t<double> v({0, 3});
        py::array_t<int32_t> f({0, 3});
        return {v, f};
    }

    struct Item {
        size_t tris;
        manifold::Manifold m;
    };
    auto cmp = [](const Item& a, const Item& b) {
        return a.tris > b.tris;
    };

    std::vector<Item> heap;
    heap.reserve(ms.size());
    for (auto& m : ms) {
        heap.push_back(Item{static_cast<size_t>(m.NumTri()), std::move(m)});
    }
    std::make_heap(heap.begin(), heap.end(), cmp);

    manifold::Manifold acc;
    {
        py::gil_scoped_release release;
        while (heap.size() >= 2) {
            std::pop_heap(heap.begin(), heap.end(), cmp);
            Item a = std::move(heap.back());
            heap.pop_back();

            std::pop_heap(heap.begin(), heap.end(), cmp);
            Item b = std::move(heap.back());
            heap.pop_back();

            manifold::Manifold u = a.m + b.m;
            if (u.NumTri() == 0) {
                throw std::runtime_error("布尔运算后结果为空 (NumTri=0)");
            }
            heap.push_back(Item{static_cast<size_t>(u.NumTri()), std::move(u)});
            std::push_heap(heap.begin(), heap.end(), cmp);
        }
        acc = std::move(heap.front().m);
    }

    if (acc.NumTri() == 0) {
        throw std::runtime_error("最终并集结果为空 (NumTri=0)");
    }
    return mesh_from_manifold(acc);
}

/* 计算两个网格的差集 (A - B)
 * 
 * 参数:
 *   a_v, a_f: 网格A的顶点和面片
 *   b_v, b_f: 网格B的顶点和面片
 * 
 * 返回:
 *   差集结果的(vertices, faces)元组
 */
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_difference(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
) {
    manifold::Manifold A = manifold_from_mesh(a_v, a_f);
    manifold::Manifold B = manifold_from_mesh(b_v, b_f);
    manifold::Manifold C = A - B;
    return mesh_from_manifold(C);
}

/* 计算两个网格的差集（释放GIL版本） */
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_difference_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
) {
    manifold::Manifold A = manifold_from_mesh(a_v, a_f);
    manifold::Manifold B = manifold_from_mesh(b_v, b_f);
    manifold::Manifold C;
    {
        py::gil_scoped_release release;
        C = A - B;
    }
    return mesh_from_manifold(C);
}

/* 计算两个网格的交集 (A ^ B)
 * 
 * 参数:
 *   a_v, a_f: 网格A的顶点和面片
 *   b_v, b_f: 网格B的顶点和面片
 * 
 * 返回:
 *   交集结果的(vertices, faces)元组
 */
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_intersection(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
) {
    manifold::Manifold A = manifold_from_mesh(a_v, a_f);
    manifold::Manifold B = manifold_from_mesh(b_v, b_f);
    manifold::Manifold C = A ^ B;
    return mesh_from_manifold(C);
}

/* 计算两个网格的交集（释放GIL版本） */
std::pair<py::array_t<double>, py::array_t<int32_t>> manifold_intersection_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> a_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> a_f,
    py::array_t<double, py::array::c_style | py::array::forcecast> b_v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> b_f
) {
    manifold::Manifold A = manifold_from_mesh(a_v, a_f);
    manifold::Manifold B = manifold_from_mesh(b_v, b_f);
    manifold::Manifold C;
    {
        py::gil_scoped_release release;
        C = A ^ B;
    }
    return mesh_from_manifold(C);
}

/* 计算网格的体积
 * 
 * 参数:
 *   v: 顶点数组
 *   f: 面片数组
 * 
 * 返回:
 *   网格的绝对体积值
 */
double manifold_volume(
    py::array_t<double, py::array::c_style | py::array::forcecast> v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> f
) {
    manifold::Manifold m = manifold_from_mesh(v, f);
    return std::abs(static_cast<double>(m.Volume()));
}

/* 计算网格的体积（释放GIL版本） */
double manifold_volume_nogil(
    py::array_t<double, py::array::c_style | py::array::forcecast> v,
    py::array_t<int32_t, py::array::c_style | py::array::forcecast> f
) {
    manifold::Manifold m = manifold_from_mesh(v, f);
    double vol = 0.0;
    {
        py::gil_scoped_release release;
        vol = std::abs(static_cast<double>(m.Volume()));
    }
    return vol;
}
