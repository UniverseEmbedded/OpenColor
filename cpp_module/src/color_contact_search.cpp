/* 颜色接触搜索模块 - 用于搜索满足颜色接触条件的最小网格布局
 * 
 * 该程序使用爬山算法搜索满足以下条件的最小网格布局：
 * - 网格中的每个格子被赋予一种颜色
 * - 任意两种不同颜色之间至少有一条边相邻
 * - 目标是找到满足条件的最小网格（格子数最少）
 */

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <utility>
#include <vector>

/* 解析命令行整数参数 */
static int parse_int_arg(int argc, char** argv, const char* key, int default_value)
{
    for (int i = 1; i < argc - 1; i++) {
        if (std::strcmp(argv[i], key) == 0) {
            return std::atoi(argv[i + 1]);
        }
    }
    return default_value;
}

/* 计算n种颜色的两两组合数：C(n,2) */
static int pair_count(int n)
{
    return n * (n - 1) / 2;
}

/* 计算满足接触条件的下界格子数
 * 理论下界：每种颜色对至少需要2条边（每种颜色各贡献1条）
 * 总边数至少为 n*(n-1)，每个格子最多贡献4条边
 * 因此格子数至少为 ceil(n*(n-1)/4)
 */
static int lower_bound_tiles(int n)
{
    const int v = n * (n - 1);
    return (v + 3) / 4;
}

/* 构建前缀和数组，用于快速计算颜色对在边列表中的索引 */
static std::vector<int> build_prefix(int n)
{
    std::vector<int> prefix;
    prefix.resize(static_cast<size_t>(n), 0);
    int sum = 0;
    for (int a = 0; a < n; a++) {
        prefix[static_cast<size_t>(a)] = sum;
        sum += (n - a - 1);
    }
    return prefix;
}

/* 计算颜色对(a,b)在边列表中的索引，要求a < b */
static int pair_index(int a, int b, const std::vector<int>& prefix)
{
    return prefix[static_cast<size_t>(a)] + (b - a - 1);
}

/* 获取v的所有因子对，按面积和宽度排序 */
static std::vector<std::pair<int, int>> grid_factors(int v)
{
    std::vector<std::pair<int, int>> out;
    const int limit = static_cast<int>(std::sqrt(static_cast<double>(v)));
    for (int h = 1; h <= limit; h++) {
        if (v % h == 0) {
            const int w = v / h;
            out.emplace_back(w, h);
            if (w != h) out.emplace_back(h, w);
        }
    }
    std::sort(out.begin(), out.end(), [](const auto& a, const auto& b) {
        const int aa = a.first * a.second;
        const int bb = b.first * b.second;
        if (aa != bb) return aa < bb;
        if (a.first != b.first) return a.first < b.first;
        return a.second < b.second;
    });
    return out;
}

/* 为w*h的网格构建边列表和邻接表
 * 边连接水平或垂直相邻的格子
 */
static void edges_for_grid(int w, int h, std::vector<std::pair<int, int>>& edges, std::vector<std::vector<int>>& neighbors)
{
    const int v = w * h;
    edges.clear();
    neighbors.clear();
    neighbors.resize(static_cast<size_t>(v));
    for (int y = 0; y < h; y++) {
        const int row = y * w;
        for (int x = 0; x < w; x++) {
            const int idx = row + x;
            // 水平边
            if (x + 1 < w) {
                const int j = idx + 1;
                edges.emplace_back(idx, j);
                neighbors[static_cast<size_t>(idx)].push_back(j);
                neighbors[static_cast<size_t>(j)].push_back(idx);
            }
            // 垂直边
            if (y + 1 < h) {
                const int j = idx + w;
                edges.emplace_back(idx, j);
                neighbors[static_cast<size_t>(idx)].push_back(j);
                neighbors[static_cast<size_t>(j)].push_back(idx);
            }
        }
    }
}

/* 计算当前网格布局的得分
 * 得分 = 网格中存在的不同颜色对的数量
 * 目标得分 = C(n,2)，即所有颜色对都至少出现一次
 */
static int compute_score(
    const std::vector<int>& grid,
    const std::vector<std::pair<int, int>>& edges,
    const std::vector<int>& prefix,
    std::vector<int>& pair_counts)
{
    std::fill(pair_counts.begin(), pair_counts.end(), 0);
    int score = 0;
    for (const auto& e : edges) {
        int a = grid[static_cast<size_t>(e.first)];
        int b = grid[static_cast<size_t>(e.second)];
        if (a == b) continue;
        if (a > b) std::swap(a, b);
        const int idx = pair_index(a, b, prefix);
        if (pair_counts[static_cast<size_t>(idx)] == 0) score++;
        pair_counts[static_cast<size_t>(idx)]++;
    }
    return score;
}

/* 应用颜色变更并增量更新得分
 * 只更新与变更格子相关的边的颜色对计数
 */
static int apply_change(
    int index,
    int old_color,
    int new_color,
    std::vector<int>& grid,
    const std::vector<std::vector<int>>& neighbors,
    const std::vector<int>& prefix,
    std::vector<int>& pair_counts,
    int score)
{
    if (old_color == new_color) return score;
    const auto& nb = neighbors[static_cast<size_t>(index)];
    for (int j : nb) {
        const int other = grid[static_cast<size_t>(j)];
        // 移除旧颜色产生的颜色对
        if (old_color != other) {
            int a = old_color;
            int b = other;
            if (a > b) std::swap(a, b);
            const int idx = pair_index(a, b, prefix);
            pair_counts[static_cast<size_t>(idx)]--;
            if (pair_counts[static_cast<size_t>(idx)] == 0) score--;
        }
        // 添加新颜色产生的颜色对
        if (new_color != other) {
            int a = new_color;
            int b = other;
            if (a > b) std::swap(a, b);
            const int idx = pair_index(a, b, prefix);
            if (pair_counts[static_cast<size_t>(idx)] == 0) score++;
            pair_counts[static_cast<size_t>(idx)]++;
        }
    }
    grid[static_cast<size_t>(index)] = new_color;
    return score;
}

/* 使用爬山算法搜索满足条件的网格布局
 * 
 * 参数:
 *   n: 颜色数量
 *   max_extra: 超出理论下界的最大额外格子数
 *   tries: 随机初始化的尝试次数
 *   steps: 每次尝试的最大迭代步数
 *   seed: 随机种子（0表示使用随机设备）
 *   out_grid: 输出网格布局
 *   out_w, out_h: 输出网格尺寸
 *   out_v: 输出格子总数
 */
static bool search_layout(
    int n,
    int max_extra,
    int tries,
    int steps,
    int seed,
    std::vector<int>& out_grid,
    int& out_w,
    int& out_h,
    int& out_v)
{
    if (n <= 0) {
        std::fprintf(stderr, "[错误] 颜色数量必须大于0\n");
        return false;
    }
    if (n == 1) {
        out_grid = {0};
        out_w = 1;
        out_h = 1;
        out_v = 1;
        return true;
    }

    const int target = pair_count(n);
    const int v0 = lower_bound_tiles(n);
    std::mt19937 rng;
    if (seed == 0) {
        std::random_device rd;
        rng.seed(rd());
    } else {
        rng.seed(static_cast<std::uint32_t>(seed));
    }
    std::uniform_int_distribution<int> pick_color(0, n - 1);

    const auto prefix = build_prefix(n);
    // 遍历可能的格子数
    for (int v = v0; v <= v0 + max_extra; v++) {
        auto factors = grid_factors(v);
        // 遍历所有可能的网格尺寸
        for (const auto& wh : factors) {
            const int w = wh.first;
            const int h = wh.second;
            std::vector<std::pair<int, int>> edges;
            std::vector<std::vector<int>> neighbors;
            edges_for_grid(w, h, edges, neighbors);

            const int pc = pair_count(n);
            std::vector<int> pair_counts(static_cast<size_t>(pc), 0);

            std::vector<int> best_grid;
            int best_score = -1;

            // 多次随机初始化尝试
            for (int t = 0; t < tries; t++) {
                std::vector<int> grid;
                grid.resize(static_cast<size_t>(v));
                for (int i = 0; i < v; i++) grid[static_cast<size_t>(i)] = pick_color(rng);

                int score = compute_score(grid, edges, prefix, pair_counts);
                if (score > best_score) {
                    best_score = score;
                    best_grid = grid;
                }
                if (score == target) {
                    out_grid = grid;
                    out_w = w;
                    out_h = h;
                    out_v = v;
                    return true;
                }

                // 爬山算法迭代优化
                std::uniform_int_distribution<int> pick_idx(0, v - 1);
                for (int s = 0; s < steps; s++) {
                    if (score == target) {
                        out_grid = grid;
                        out_w = w;
                        out_h = h;
                        out_v = v;
                        return true;
                    }
                    // 随机选择操作：变色或交换
                    if ((rng() & 1u) == 0u) {
                        // 变色操作
                        const int i = pick_idx(rng);
                        const int old_c = grid[static_cast<size_t>(i)];
                        int new_c = pick_color(rng);
                        if (new_c == old_c) continue;
                        const int new_score = apply_change(i, old_c, new_c, grid, neighbors, prefix, pair_counts, score);
                        if (new_score >= score) {
                            score = new_score;
                        } else {
                            // 不接受劣化，回滚
                            score = apply_change(i, new_c, old_c, grid, neighbors, prefix, pair_counts, new_score);
                        }
                    } else {
                        // 交换操作
                        const int i = pick_idx(rng);
                        const int j = pick_idx(rng);
                        if (i == j) continue;
                        const int ci = grid[static_cast<size_t>(i)];
                        const int cj = grid[static_cast<size_t>(j)];
                        if (ci == cj) continue;
                        int new_score = apply_change(i, ci, cj, grid, neighbors, prefix, pair_counts, score);
                        new_score = apply_change(j, cj, ci, grid, neighbors, prefix, pair_counts, new_score);
                        if (new_score >= score) {
                            score = new_score;
                        } else {
                            // 不接受劣化，回滚
                            new_score = apply_change(j, ci, cj, grid, neighbors, prefix, pair_counts, new_score);
                            score = apply_change(i, cj, ci, grid, neighbors, prefix, pair_counts, new_score);
                        }
                    }
                }
                if (score > best_score) {
                    best_score = score;
                    best_grid = grid;
                }
            }
            if (best_score == target) {
                out_grid = best_grid;
                out_w = w;
                out_h = h;
                out_v = v;
                return true;
            }
        }
    }
    return false;
}

/* 以JSON格式输出网格布局结果 */
static void print_json(const std::vector<int>& grid, int w, int h, int v)
{
    std::printf("{\"grid\":[");
    for (size_t i = 0; i < grid.size(); i++) {
        if (i) std::printf(",");
        std::printf("%d", grid[i]);
    }
    std::printf("],\"w\":%d,\"h\":%d,\"v\":%d}\n", w, h, v);
}

int main(int argc, char** argv)
{
    // 解析命令行参数
    const int colors = parse_int_arg(argc, argv, "--colors", -1);
    const int max_extra = parse_int_arg(argc, argv, "--max-extra", 8);
    const int tries = parse_int_arg(argc, argv, "--tries", 60);
    const int steps = parse_int_arg(argc, argv, "--steps", 8000);
    const int seed = parse_int_arg(argc, argv, "--seed", 0);

    if (colors <= 0) {
        std::fprintf(stderr, "[错误] 参数 --colors 必须大于0\n");
        return 2;
    }
    if (max_extra < 0 || tries <= 0 || steps <= 0) {
        std::fprintf(stderr, "[错误] 参数 max-extra/tries/steps 无效\n");
        return 2;
    }

    std::vector<int> grid;
    int w = 0;
    int h = 0;
    int v = 0;
    const bool ok = search_layout(colors, max_extra, tries, steps, seed, grid, w, h, v);
    if (!ok) {
        std::fprintf(stderr, "[错误] 未能在限制范围内找到满足全部接触条件的最小布局\n");
        return 3;
    }
    print_json(grid, w, h, v);
    return 0;
}
