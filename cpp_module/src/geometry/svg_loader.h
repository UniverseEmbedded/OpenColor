/**
 * SVG 加载器头文件
 * 提供高性能的 SVG 多边形加载功能
 */

#pragma once

#include <string>
#include <vector>
#include <tuple>

namespace opencolor {

/**
 * 表示一个二维点
 */
struct Point2D {
    double x;
    double y;
    
    Point2D(double x = 0.0, double y = 0.0) : x(x), y(y) {}
};

/**
 * 表示一个多边形环（外轮廓或孔洞）
 */
using Ring = std::vector<Point2D>;

/**
 * 表示一个带孔洞的多边形
 * first: 外轮廓环
 * second: 孔洞环列表
 */
using PolygonWithHoles = std::pair<Ring, std::vector<Ring>>;

/**
 * 从 SVG 文件加载多边形
 * 
 * @param svg_path SVG 文件路径
 * @return 多边形列表（每个多边形包含外轮廓和孔洞）
 * @throws std::runtime_error 当加载失败时抛出
 */
std::vector<PolygonWithHoles> load_svg_polygons(const std::string& svg_path);

/**
 * 从 SVG 字符串加载多边形
 * 
 * @param svg_content SVG 内容字符串
 * @param height_mm 画布高度（用于Y轴翻转）
 * @return 多边形列表
 */
std::vector<PolygonWithHoles> load_svg_polygons_from_string(
    const std::string& svg_content, 
    double height_mm
);

} // namespace opencolor
