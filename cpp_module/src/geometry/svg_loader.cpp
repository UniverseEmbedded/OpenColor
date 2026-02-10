/**
 * SVG 加载器实现 - 使用 NanoSVG 库
 */

#include "svg_loader.h"

#include <fstream>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <stdexcept>

// NanoSVG - 单文件 SVG 解析库
#define NANOSVG_IMPLEMENTATION
#include <nanosvg.h>

namespace opencolor {

// 空间索引节点（简单网格划分）
struct SpatialIndex {
    struct Cell {
        std::vector<size_t> indices;
    };
    
    double min_x, min_y, max_x, max_y;
    double cell_size;
    size_t grid_width, grid_height;
    std::vector<Cell> cells;
    const std::vector<Ring>* rings;
    
    SpatialIndex(const std::vector<Ring>& r, double cell_sz = 10.0) 
        : rings(&r), cell_size(cell_sz) {
        // 计算边界框
        min_x = min_y = std::numeric_limits<double>::max();
        max_x = max_y = std::numeric_limits<double>::lowest();
        
        for (const auto& ring : r) {
            for (const auto& p : ring) {
                min_x = std::min(min_x, p.x);
                min_y = std::min(min_y, p.y);
                max_x = std::max(max_x, p.x);
                max_y = std::max(max_y, p.y);
            }
        }
        
        // 添加一些边距
        double padding = cell_size;
        min_x -= padding;
        min_y -= padding;
        max_x += padding;
        max_y += padding;
        
        // 计算网格尺寸
        grid_width = static_cast<size_t>(std::ceil((max_x - min_x) / cell_size)) + 1;
        grid_height = static_cast<size_t>(std::ceil((max_y - min_y) / cell_size)) + 1;
        cells.resize(grid_width * grid_height);
        
        // 插入所有环
        for (size_t i = 0; i < r.size(); ++i) {
            insert_ring(i, r[i]);
        }
    }
    
    void insert_ring(size_t idx, const Ring& ring) {
        // 计算环的边界框
        double rmin_x = std::numeric_limits<double>::max();
        double rmin_y = std::numeric_limits<double>::max();
        double rmax_x = std::numeric_limits<double>::lowest();
        double rmax_y = std::numeric_limits<double>::lowest();
        
        for (const auto& p : ring) {
            rmin_x = std::min(rmin_x, p.x);
            rmin_y = std::min(rmin_y, p.y);
            rmax_x = std::max(rmax_x, p.x);
            rmax_y = std::max(rmax_y, p.y);
        }
        
        // 计算覆盖的网格单元
        size_t x0 = static_cast<size_t>(std::max(0.0, (rmin_x - min_x) / cell_size));
        size_t y0 = static_cast<size_t>(std::max(0.0, (rmin_y - min_y) / cell_size));
        size_t x1 = static_cast<size_t>(std::min(static_cast<double>(grid_width - 1), 
                                                  (rmax_x - min_x) / cell_size));
        size_t y1 = static_cast<size_t>(std::min(static_cast<double>(grid_height - 1), 
                                                  (rmax_y - min_y) / cell_size));
        
        // 插入到所有覆盖的单元
        for (size_t y = y0; y <= y1; ++y) {
            for (size_t x = x0; x <= x1; ++x) {
                cells[y * grid_width + x].indices.push_back(idx);
            }
        }
    }
    
    // 查询包含某点的所有环
    std::vector<size_t> query_point(double x, double y) const {
        size_t gx = static_cast<size_t>((x - min_x) / cell_size);
        size_t gy = static_cast<size_t>((y - min_y) / cell_size);
        
        if (gx >= grid_width || gy >= grid_height) {
            return {};
        }
        
        return cells[gy * grid_width + gx].indices;
    }
};

// 计算多边形面积（带符号）
static double ring_area(const Ring& ring) {
    double area = 0.0;
    size_t n = ring.size();
    for (size_t i = 0; i < n; ++i) {
        size_t j = (i + 1) % n;
        area += ring[i].x * ring[j].y;
        area -= ring[j].x * ring[i].y;
    }
    return area * 0.5;
}

// 计算绝对面积
double ring_area_abs(const Ring& ring) {
    return std::abs(ring_area(ring));
}

// 判断点是否在多边形内（射线法）
static bool point_in_ring(double x, double y, const Ring& ring) {
    bool inside = false;
    size_t n = ring.size();
    
    for (size_t i = 0, j = n - 1; i < n; j = i++) {
        const auto& pi = ring[i];
        const auto& pj = ring[j];
        
        // 检查边是否与射线相交
        if (((pi.y > y) != (pj.y > y)) &&
            (x < (pj.x - pi.x) * (y - pi.y) / (pj.y - pi.y) + pi.x)) {
            inside = !inside;
        }
    }
    
    return inside;
}

// 从 NanoSVG 路径构建环
static std::vector<Ring> extract_rings_from_nanosvg(NSVGimage* image, double height_mm) {
    std::vector<Ring> rings;
    
    if (!image) return rings;
    
    // 遍历所有形状
    for (NSVGshape* shape = image->shapes; shape != nullptr; shape = shape->next) {
        // 遍历所有路径
        for (NSVGpath* path = shape->paths; path != nullptr; path = path->next) {
            Ring ring;
            
            // NanoSVG 路径点是平铺的: x,y,x,y,...
            for (int i = 0; i < path->npts; ++i) {
                double x = path->pts[i * 2];
                double y_svg = path->pts[i * 2 + 1];
                double y = height_mm - y_svg;  // Y轴翻转
                ring.emplace_back(x, y);
            }
            
            if (ring.size() >= 3) {
                rings.push_back(ring);
            }
        }
    }
    
    return rings;
}

// 构建包含树（使用空间索引优化）
static std::vector<PolygonWithHoles> build_polygons_with_holes(
    const std::vector<Ring>& rings) {
    
    if (rings.empty()) return {};
    
    size_t n = rings.size();
    
    // 计算面积和质心
    std::vector<double> areas(n);
    std::vector<Point2D> centroids(n);
    
    for (size_t i = 0; i < n; ++i) {
        areas[i] = ring_area_abs(rings[i]);
        
        // 计算质心（简单平均）
        double cx = 0, cy = 0;
        for (const auto& p : rings[i]) {
            cx += p.x;
            cy += p.y;
        }
        centroids[i] = Point2D(cx / rings[i].size(), cy / rings[i].size());
    }
    
    // 按面积从大到小排序
    std::vector<size_t> sorted_indices(n);
    for (size_t i = 0; i < n; ++i) sorted_indices[i] = i;
    std::sort(sorted_indices.begin(), sorted_indices.end(),
              [&areas](size_t a, size_t b) { return areas[a] > areas[b]; });
    
    // 构建空间索引
    SpatialIndex index(rings, 20.0);  // 20mm 单元格
    
    // 父节点数组
    std::vector<int> parent(n, -1);
    std::vector<std::vector<size_t>> children(n);
    
    // 逐步处理（从大到小）
    std::vector<size_t> processed;
    
    for (size_t idx : sorted_indices) {
        const auto& centroid = centroids[idx];
        
        // 查询可能包含当前质心的候选
        auto candidates = index.query_point(centroid.x, centroid.y);
        
        // 找到真正包含当前质心的最小父节点
        int best_parent = -1;
        double best_area = std::numeric_limits<double>::max();
        
        for (size_t cidx : candidates) {
            // 只考虑已处理的（面积更大的）
            if (areas[cidx] <= areas[idx]) continue;
            
            if (point_in_ring(centroid.x, centroid.y, rings[cidx])) {
                if (areas[cidx] < best_area) {
                    best_parent = static_cast<int>(cidx);
                    best_area = areas[cidx];
                }
            }
        }
        
        if (best_parent >= 0) {
            parent[idx] = best_parent;
            children[best_parent].push_back(idx);
        }
        
        processed.push_back(idx);
    }
    
    // 计算深度
    std::vector<int> depth(n, 0);
    for (size_t i = 0; i < n; ++i) {
        int d = 0;
        int k = static_cast<int>(i);
        while (parent[k] != -1) {
            d++;
            k = parent[k];
        }
        depth[i] = d;
    }
    
    // 构建输出多边形
    std::vector<PolygonWithHoles> result;
    
    for (size_t i = 0; i < n; ++i) {
        // 只处理偶数深度的（外轮廓）
        if (depth[i] % 2 != 0) continue;
        
        PolygonWithHoles poly;
        poly.first = rings[i];
        
        // 收集直接子节点（孔洞）
        for (size_t c : children[i]) {
            if (depth[c] == depth[i] + 1) {
                poly.second.push_back(rings[c]);
            }
        }
        
        result.push_back(poly);
    }
    
    return result;
}

std::vector<PolygonWithHoles> load_svg_polygons_from_string(
    const std::string& svg_content, 
    double height_mm) {
    
    // 使用 NanoSVG 解析
    NSVGimage* image = nsvgParse(const_cast<char*>(svg_content.c_str()), "mm", 96.0f);
    
    if (!image) {
        throw std::runtime_error("Failed to parse SVG");
    }
    
    // 提取所有环
    auto rings = extract_rings_from_nanosvg(image, height_mm);
    
    // 释放 NanoSVG 资源
    nsvgDelete(image);
    
    // 构建带孔洞的多边形
    return build_polygons_with_holes(rings);
}

std::vector<PolygonWithHoles> load_svg_polygons(const std::string& svg_path) {
    // 读取文件
    std::ifstream file(svg_path);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + svg_path);
    }
    
    std::string content((std::istreambuf_iterator<char>(file)),
                        std::istreambuf_iterator<char>());
    
    // 解析高度（从 SVG 内容中提取）
    // NanoSVG 会自动处理单位和尺寸
    
    return load_svg_polygons_from_string(content, 100.0);  // 默认高度 100mm
}

} // namespace opencolor
