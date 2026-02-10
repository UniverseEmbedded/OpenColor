/**
 * OpenColor几何模块Python绑定
 * 提供C++加速的几何操作功能
 */

#include <pybind11/numpy.h>
#include <pybind11/gil.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "clipper_ops.h"
#include "earcut_triangulation.h"
#include "manifold_ops.h"
#include "mesh_utils.h"
#include "svg_loader.h"

namespace py = pybind11;

/**
 * 测试函数，返回模块状态信息
 */
static std::string ping() {
    return "pong from opencolor_geometry (C++)";
}

/**
 * 模块定义
 * 将C++几何操作函数暴露给Python
 */
PYBIND11_MODULE(opencolor_geometry, m) {
    m.doc() = "OpenColor 几何 C++加速模块";
    m.def("ping", &ping, "测试函数，返回模块状态");

    // STL文件写入（无GIL版本，支持多线程）
    m.def(
        "write_binary_stl_nogil",
        &write_binary_stl_nogil,
        py::arg("vertices"),
        py::arg("faces"),
        py::arg("file_path"),
        "写入二进制STL文件（无GIL）"
    );

    // Clipper布尔运算
    m.def("clipper_boolean", &clipper_boolean,
          py::arg("subject_loops"), py::arg("clip_loops"), py::arg("op"), py::arg("scale") = default_scale(),
          "执行Clipper布尔运算");
    m.def("clipper_offset", &clipper_offset,
          py::arg("loops"), py::arg("delta"),
          py::arg("join_type") = "miter", py::arg("end_type") = "polygon",
          py::arg("miter_limit") = 2.0, py::arg("arc_tolerance") = 0.25,
          py::arg("scale") = default_scale(),
          "执行Clipper偏移操作");

    // Clipper并集操作（无GIL版本）
    m.def("clipper_union_all_nogil", &clipper_union_all_nogil,
          py::arg("loops"), py::arg("scale") = default_scale(),
          "对所有环路执行并集操作（无GIL）");

    m.def("clipper_union_all_to_polygons_nogil", &clipper_union_all_to_polygons_nogil,
          py::arg("loops"), py::arg("scale") = default_scale(),
          "对所有环路执行并集操作并返回多边形（无GIL）");

    // 排他性Clipper操作（无GIL版本）
    m.def("clipper_make_exclusive_nogil", &clipper_make_exclusive_nogil,
          py::arg("slots_loops"), py::arg("scale") = default_scale(),
          "生成排他性槽位（无GIL）");

    // 层重叠间隙区域计算（无GIL版本）
    m.def("clipper_layer_overlap_gap_areas_nogil", &clipper_layer_overlap_gap_areas_nogil,
          py::arg("slots_loops"), py::arg("full_loops"), py::arg("scale") = default_scale(),
          "计算层重叠间隙区域（无GIL）");

    // Earcut三角化
    m.def("earcut_triangulate_rings", &earcut_triangulate_rings, py::arg("rings"),
          "使用Earcut算法对环进行三角化");

    // 拉伸操作
    m.def("extrude_triangulation", &extrude_triangulation,
          py::arg("verts_2d"), py::arg("faces"), py::arg("ring_end_indices"), py::arg("z_start"), py::arg("z_end"),
          "拉伸三角化网格");
    m.def("extrude_rings", &extrude_rings, py::arg("rings"), py::arg("z_start"), py::arg("z_end"),
          "拉伸环生成3D网格");
    m.def("extrude_rings_nogil", &extrude_rings_nogil, py::arg("rings"), py::arg("z_start"), py::arg("z_end"),
          "拉伸环生成3D网格（无GIL）");

    // Manifold布尔运算
    m.def("manifold_union", &manifold_union, py::arg("meshes"),
          "执行Manifold并集操作");
    m.def("manifold_union_nogil", &manifold_union_nogil, py::arg("meshes"),
          "执行Manifold并集操作（无GIL）");
    m.def("manifold_difference", &manifold_difference,
          py::arg("a_vertices"), py::arg("a_faces"), py::arg("b_vertices"), py::arg("b_faces"),
          "执行Manifold差集操作");
    m.def("manifold_difference_nogil", &manifold_difference_nogil,
          py::arg("a_vertices"), py::arg("a_faces"), py::arg("b_vertices"), py::arg("b_faces"),
          "执行Manifold差集操作（无GIL）");
    m.def("manifold_intersection", &manifold_intersection,
          py::arg("a_vertices"), py::arg("a_faces"), py::arg("b_vertices"), py::arg("b_faces"),
          "执行Manifold交集操作");
    m.def("manifold_intersection_nogil", &manifold_intersection_nogil,
          py::arg("a_vertices"), py::arg("a_faces"), py::arg("b_vertices"), py::arg("b_faces"),
          "执行Manifold交集操作（无GIL）");
    m.def("manifold_volume", &manifold_volume, py::arg("vertices"), py::arg("faces"),
          "计算Manifold体积");
    m.def("manifold_volume_nogil", &manifold_volume_nogil, py::arg("vertices"), py::arg("faces"),
          "计算Manifold体积（无GIL）");

    // 网格分析（无GIL版本）
    m.def("mesh_analyze_basic_nogil", &mesh_analyze_basic_nogil, py::arg("vertices"), py::arg("faces"),
          "基础网格分析（无GIL）");

    // 网格清理（无GIL版本）
    m.def("mesh_clean_basic_nogil", &mesh_clean_basic_nogil, py::arg("vertices"), py::arg("faces"),
          "基础网格清理（无GIL）");

    // SVG 加载 - 使用包装函数转换为Python友好格式
    m.def("load_svg_polygons", 
          [](const std::string& svg_path) -> std::vector<std::pair<std::vector<std::pair<double, double>>, std::vector<std::vector<std::pair<double, double>>>>> {
              auto result = opencolor::load_svg_polygons(svg_path);
              std::vector<std::pair<std::vector<std::pair<double, double>>, std::vector<std::vector<std::pair<double, double>>>>> py_result;
              for (const auto& poly : result) {
                  std::vector<std::pair<double, double>> exterior;
                  for (const auto& p : poly.first) {
                      exterior.emplace_back(p.x, p.y);
                  }
                  std::vector<std::vector<std::pair<double, double>>> holes;
                  for (const auto& hole : poly.second) {
                      std::vector<std::pair<double, double>> hole_pts;
                      for (const auto& p : hole) {
                          hole_pts.emplace_back(p.x, p.y);
                      }
                      holes.push_back(hole_pts);
                  }
                  py_result.emplace_back(exterior, holes);
              }
              return py_result;
          }, 
          py::arg("svg_path"),
          "从SVG文件加载多边形（高性能C++实现），返回 [(外轮廓, [孔洞列表]), ...]");
    
    m.def("load_svg_polygons_from_string", 
          [](const std::string& svg_content, double height_mm) -> std::vector<std::pair<std::vector<std::pair<double, double>>, std::vector<std::vector<std::pair<double, double>>>>> {
              auto result = opencolor::load_svg_polygons_from_string(svg_content, height_mm);
              std::vector<std::pair<std::vector<std::pair<double, double>>, std::vector<std::vector<std::pair<double, double>>>>> py_result;
              for (const auto& poly : result) {
                  std::vector<std::pair<double, double>> exterior;
                  for (const auto& p : poly.first) {
                      exterior.emplace_back(p.x, p.y);
                  }
                  std::vector<std::vector<std::pair<double, double>>> holes;
                  for (const auto& hole : poly.second) {
                      std::vector<std::pair<double, double>> hole_pts;
                      for (const auto& p : hole) {
                          hole_pts.emplace_back(p.x, p.y);
                      }
                      holes.push_back(hole_pts);
                  }
                  py_result.emplace_back(exterior, holes);
              }
              return py_result;
          }, 
          py::arg("svg_content"), py::arg("height_mm"),
          "从SVG字符串加载多边形（高性能C++实现），返回 [(外轮廓, [孔洞列表]), ...]");
}
