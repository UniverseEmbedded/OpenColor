"""
颜色配置验证脚本
验证 ColorProfile 与 generate_board 的集成是否正确
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "src"))

from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager,
    ColorProfile,
    DEFAULT_COLOR_PROFILES,
)
from oc_proto.calib_board_gen.generate_board import (
    build_recipe_pool,
    build_board_spec,
    DEFAULT_LAYERS,
    DATA_ROWS,
    DATA_COLS,
)


def test_color_mapping():
    """测试颜色索引映射是否正确"""
    print("=" * 60)
    print("测试1: 颜色索引映射验证")
    print("=" * 60)

    manager = get_profile_manager()

    for profile_id in ["rgb", "rybw", "rgbw", "rgbwk", "full_8"]:
        profile = manager.get_profile(profile_id)
        print(f"\n配置: {profile_id} ({profile.name})")
        print(f"  颜色数量: {profile.num_colors}")
        print(f"  颜色列表: {profile.color_names}")
        print(f"  颜色索引映射:")
        for i, name in enumerate(profile.color_names):
            rgba = profile.get_color_rgba(name)
            print(f"    索引 {i} -> {name} -> RGBA{rgba}")
        print(f"  标记颜色: {profile.marker_colors}")


def test_recipe_pool_generation():
    """测试配方生成是否适应不同颜色数量"""
    print("\n" + "=" * 60)
    print("测试2: 配方生成验证")
    print("=" * 60)

    manager = get_profile_manager()
    num_cells = DATA_ROWS * DATA_COLS  # 225个格子

    for profile_id in ["rgb", "rybw", "full_8"]:
        profile = manager.get_profile(profile_id)
        n_colors = profile.num_colors

        # 生成配方池
        recipes = build_recipe_pool(
            layers=DEFAULT_LAYERS,
            n_colors=n_colors,
            target_count=num_cells,
        )

        print(f"\n配置: {profile_id} ({n_colors}色)")
        print(f"  需要配方数: {num_cells}")
        print(f"  实际生成配方数: {len(recipes)}")

        # 验证所有配方中的颜色索引都在有效范围内
        max_idx = max(max(r) for r in recipes) if recipes else -1
        min_idx = min(min(r) for r in recipes) if recipes else -1
        print(f"  配方中颜色索引范围: {min_idx} ~ {max_idx}")

        if max_idx >= n_colors:
            print(f"  [错误] 存在越界索引！最大应为 {n_colors - 1}")
        else:
            print(f"  [通过] 所有索引都在有效范围内")

        # 统计各种配方类型
        color_counts = {}
        for r in recipes:
            unique_colors = len(set(r))
            color_counts[unique_colors] = color_counts.get(unique_colors, 0) + 1

        print(f"  配方类型分布:")
        for n in sorted(color_counts.keys()):
            print(f"    {n}色配方: {color_counts[n]}个")


def test_board_spec_color_names():
    """测试 BoardSpec 中的颜色名映射是否正确"""
    print("\n" + "=" * 60)
    print("测试3: BoardSpec 颜色名映射验证")
    print("=" * 60)

    manager = get_profile_manager()
    num_cells = DATA_ROWS * DATA_COLS

    for profile_id in ["rybw", "full_8"]:
        profile = manager.get_profile(profile_id)
        n_colors = profile.num_colors

        # 生成配方
        recipes = build_recipe_pool(
            layers=DEFAULT_LAYERS,
            n_colors=n_colors,
            target_count=num_cells,
        )

        # 构建 BoardSpec
        spec = build_board_spec(
            board_name=f"Test_{profile_id}",
            recipes=recipes,
            group_id=0,
            plate_index=0,
        )

        print(f"\n配置: {profile_id} ({n_colors}色)")

        # 检查几个格子的颜色名
        sample_cells = ["1,1", "5,5", "10,10", "15,15"]
        print(f"  示例格子颜色映射:")
        for cell_key in sample_cells:
            if cell_key in spec.cell_map:
                cell_data = spec.cell_map[cell_key]
                layers = cell_data["layers"]
                slot_names = cell_data["slot_names"]
                print(f"    {cell_key}: 索引{layers} -> 名称{slot_names}")

        # 验证所有 slot_names 都是有效的颜色名
        all_valid = True
        invalid_names = set()
        for cell_key, cell_data in spec.cell_map.items():
            for name in cell_data["slot_names"]:
                if name not in profile.color_names:
                    all_valid = False
                    invalid_names.add(name)

        if all_valid:
            print(f"  [通过] 所有颜色名都有效")
        else:
            print(f"  [错误] 发现无效颜色名: {invalid_names}")


def test_color_profile_integration():
    """测试完整集成：从 ColorProfile 生成 BoardSpec"""
    print("\n" + "=" * 60)
    print("测试4: 完整集成验证（模拟改造后的流程）")
    print("=" * 60)

    manager = get_profile_manager()

    for profile_id in ["rybw", "full_8"]:
        profile = manager.get_profile(profile_id)
        n_colors = profile.num_colors
        num_cells = DATA_ROWS * DATA_COLS

        print(f"\n配置: {profile_id} ({n_colors}色)")

        # 步骤1: 生成配方池（使用颜色数量）
        recipes = build_recipe_pool(
            layers=DEFAULT_LAYERS,
            n_colors=n_colors,
            target_count=num_cells,
        )
        print(f"  步骤1: 生成 {len(recipes)} 个配方")

        # 步骤2: 构建 BoardSpec（当前使用 SLOT_NAMES_8）
        # 改造后应该使用 profile.color_names
        spec = build_board_spec(
            board_name=f"Test_{profile_id}",
            recipes=recipes,
            group_id=0,
            plate_index=0,
        )
        print(f"  步骤2: 构建 BoardSpec，包含 {len(spec.cell_map)} 个格子")

        # 步骤3: 验证颜色名映射
        # 当前 build_board_spec 使用 SLOT_NAMES_8，如果 n_colors != 8 会出错
        if n_colors != 8:
            print(f"  [警告] 当前代码使用硬编码 SLOT_NAMES_8，但配置有 {n_colors} 色")
            print(f"  [警告] 这会导致索引越界或颜色名错误！")

            # 检查是否有越界
            max_layer_idx = -1
            for cell_data in spec.cell_map.values():
                for idx in cell_data["layers"]:
                    if idx > max_layer_idx:
                        max_layer_idx = idx

            if max_layer_idx >= 8:
                print(f"  [错误] 发现越界索引 {max_layer_idx}，SLOT_NAMES_8 只有8个元素")
            else:
                print(f"  [信息] 配方索引范围 0-{max_layer_idx}，在 SLOT_NAMES_8 范围内")


def main():
    print("颜色配置集成验证")
    print("目的: 验证 ColorProfile 与 generate_board 的兼容性")
    print()

    test_color_mapping()
    test_recipe_pool_generation()
    test_board_spec_color_names()
    test_color_profile_integration()

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)
    print("\n关键发现:")
    print("1. build_recipe_pool 函数已经支持任意颜色数量（通过 n_colors 参数）")
    print("2. 但 build_board_spec 函数硬编码使用 SLOT_NAMES_8")
    print("3. 当使用非8色配置时，build_board_spec 会出错或产生错误颜色名")
    print("4. 改造重点：让 build_board_spec 接受 color_names 参数")


if __name__ == "__main__":
    main()
