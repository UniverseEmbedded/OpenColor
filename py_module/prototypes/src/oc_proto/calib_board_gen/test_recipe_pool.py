"""
测试配方生成算法
验证4色配置能生成1024个不重复的配方
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "src"))

from oc_proto.calib_board_gen.generate_board import build_recipe_pool, DEFAULT_LAYERS


def test_4color_recipes():
    """测试4色配置生成1024个不重复配方"""
    print("=" * 60)
    print("测试4色配置配方生成")
    print("=" * 60)

    n_colors = 4
    layers = DEFAULT_LAYERS  # 5层
    target_count = 1024  # 4^5 = 1024

    print(f"\n参数:")
    print(f"  颜色数: {n_colors}")
    print(f"  层数: {layers}")
    print(f"  目标配方数: {target_count}")
    print(f"  理论最大配方数: {n_colors ** layers}")

    # 生成配方
    recipes = build_recipe_pool(layers=layers, n_colors=n_colors, target_count=target_count)

    # 验证数量
    print(f"\n结果:")
    print(f"  实际生成配方数: {len(recipes)}")

    # 验证唯一性
    unique_recipes = set(tuple(r) for r in recipes)
    print(f"  唯一配方数: {len(unique_recipes)}")

    # 验证是否有重复
    if len(recipes) == len(unique_recipes):
        print(f"  ✓ 所有配方都是唯一的，没有重复！")
    else:
        print(f"  ✗ 发现重复配方: {len(recipes) - len(unique_recipes)} 个")

    # 统计各种配方类型
    color_counts = {}
    switch_counts = {}
    for r in recipes:
        unique_colors = len(set(r))
        color_counts[unique_colors] = color_counts.get(unique_colors, 0) + 1

        switches = sum(1 for i in range(1, len(r)) if r[i] != r[i-1])
        switch_counts[switches] = switch_counts.get(switches, 0) + 1

    print(f"\n配方类型分布（按颜色种类）:")
    for n in sorted(color_counts.keys()):
        print(f"  {n}色配方: {color_counts[n]}个")

    print(f"\n配方类型分布（按切换次数）:")
    for n in sorted(switch_counts.keys()):
        print(f"  切换{n}次: {switch_counts[n]}个")

    # 显示前10个和后10个配方
    print(f"\n前10个配方:")
    for i, r in enumerate(recipes[:10]):
        switches = sum(1 for j in range(1, len(r)) if r[j] != r[j-1])
        print(f"  {i+1}: {r} ({len(set(r))}色, {switches}次切换)")

    print(f"\n后10个配方:")
    for i, r in enumerate(recipes[-10:]):
        idx = len(recipes) - 10 + i
        switches = sum(1 for j in range(1, len(r)) if r[j] != r[j-1])
        print(f"  {idx+1}: {r} ({len(set(r))}色, {switches}次切换)")

    # 验收标准
    print("\n" + "=" * 60)
    if len(recipes) == 1024 and len(unique_recipes) == 1024:
        print("✓ 验收通过：生成1024个不重复的配方！")
    else:
        print(f"✗ 验收失败：期望1024个唯一配方，实际{len(unique_recipes)}个")
    print("=" * 60)


def test_3color_recipes():
    """测试3色配置生成243个不重复配方"""
    print("\n" + "=" * 60)
    print("测试3色配置配方生成")
    print("=" * 60)

    n_colors = 3
    layers = DEFAULT_LAYERS
    target_count = 243  # 3^5 = 243

    print(f"\n参数:")
    print(f"  颜色数: {n_colors}")
    print(f"  层数: {layers}")
    print(f"  目标配方数: {target_count}")
    print(f"  理论最大配方数: {n_colors ** layers}")

    recipes = build_recipe_pool(layers=layers, n_colors=n_colors, target_count=target_count)

    unique_recipes = set(tuple(r) for r in recipes)

    print(f"\n结果:")
    print(f"  实际生成配方数: {len(recipes)}")
    print(f"  唯一配方数: {len(unique_recipes)}")

    if len(recipes) == 243 and len(unique_recipes) == 243:
        print("✓ 验收通过：生成243个不重复的配方！")
    else:
        print(f"✗ 验收失败：期望243个唯一配方，实际{len(unique_recipes)}个")


def main():
    test_4color_recipes()
    test_3color_recipes()


if __name__ == "__main__":
    main()
