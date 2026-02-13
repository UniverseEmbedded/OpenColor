"""
交互式校准板生成脚本
通过问答方式收集用户配置，生成多色校准板

使用方式:
    pixi run python -m oc_proto.calib_board_gen.interactive_gen
"""

import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

from oc_proto.calib_board_gen import generate_board as gen_bd
from oc_proto.calib_board_gen.color_profiles import (
    get_profile_manager,
    ColorProfile,
    ColorProfileManager,
)
from oc_proto.calib_board_gen.main import run, get_default_border_color


def print_header(title: str):
    """打印章节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_options(options: List[Tuple[str, str, Any]], show_index: bool = True):
    """打印选项列表"""
    for i, (key, desc, _) in enumerate(options, 1):
        prefix = f"{i}. " if show_index else "   "
        print(f"{prefix}[{key}] {desc}")


def ask_choice(prompt: str, options: List[Tuple[str, str, Any]], default: int = 1) -> Any:
    """询问用户选择"""
    print()
    print_options(options)
    while True:
        try:
            user_input = input(f"\n{prompt} (默认 {default}): ").strip()
            if not user_input:
                choice = default
            else:
                choice = int(user_input)
            if 1 <= choice <= len(options):
                return options[choice - 1][2]
            else:
                print(f"请输入 1-{len(options)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """询问是/否"""
    default_str = "Y/n" if default else "y/N"
    while True:
        user_input = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not user_input:
            return default
        if user_input in ("y", "yes", "是"):
            return True
        if user_input in ("n", "no", "否"):
            return False
        print("请输入 y 或 n")


def ask_number(prompt: str, default: float, min_val: float = None, max_val: float = None, allow_float: bool = True) -> float:
    """询问数字输入"""
    while True:
        user_input = input(f"{prompt} (默认 {default}): ").strip()
        if not user_input:
            return default
        try:
            value = float(user_input) if allow_float else int(user_input)
            if min_val is not None and value < min_val:
                print(f"值不能小于 {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"值不能大于 {max_val}")
                continue
            return value
        except ValueError:
            print("请输入有效的数字")


def ask_string(prompt: str, default: str = "") -> str:
    """询问字符串输入"""
    user_input = input(f"{prompt} (默认 '{default}'): ").strip()
    return user_input if user_input else default


def ask_color_rgb(color_name: str) -> Tuple[int, int, int, int]:
    """询问颜色RGB值"""
    print(f"\n设置颜色 '{color_name}' 的 RGBA 值 (0-255)")
    r = int(ask_number("  红色 (R)", 128, 0, 255, allow_float=False))
    g = int(ask_number("  绿色 (G)", 128, 0, 255, allow_float=False))
    b = int(ask_number("  蓝色 (B)", 128, 0, 255, allow_float=False))
    a = int(ask_number("  透明度 (A, 255=不透明)", 255, 0, 255, allow_float=False))
    return (r, g, b, a)


def configure_color_profile() -> ColorProfile:
    """配置颜色方案"""
    print_header("步骤 1/4: 颜色配置")

    manager = get_profile_manager()
    profiles = manager.list_profiles()

    profile_options = []
    for pid in profiles:
        p = manager.get_profile(pid)
        profile_options.append((pid, f"{p.name} ({p.num_colors}色)", pid))

    profile_options.append(("custom", "自定义颜色配置", "custom"))
    profile_options.append(("file", "从JSON文件加载配置", "file"))

    choice = ask_choice("请选择颜色配置方式", profile_options, default=5)

    if choice == "custom":
        return configure_custom_colors()
    elif choice == "file":
        return load_profile_from_file()
    else:
        profile = manager.get_profile(choice)
        print(f"\n已选择: {profile.name}")
        print(f"颜色: {', '.join(profile.color_names)}")
        return profile


def configure_custom_colors() -> ColorProfile:
    """配置自定义颜色"""
    print_header("自定义颜色配置")

    color_count = int(ask_number("请输入颜色数量", 4, 2, 8, allow_float=False))

    colors: Dict[str, List[int]] = {}
    print("\n请为每种颜色设置名称和RGBA值")

    default_names = ["Red", "Green", "Blue", "White", "Yellow", "Cyan", "Magenta", "Black"]

    for i in range(color_count):
        default_name = default_names[i] if i < len(default_names) else f"Color{i+1}"
        print(f"\n--- 颜色 {i+1}/{color_count} ---")
        name = ask_string("颜色名称", default_name)
        rgba = ask_color_rgb(name)
        colors[name] = list(rgba)

    print("\n生成的颜色配置:")
    for name, rgba in colors.items():
        print(f"  {name}: RGBA({rgba[0]}, {rgba[1]}, {rgba[2]}, {rgba[3]})")

    profile_name = ask_string("配置名称", "自定义配置")

    return ColorProfile(name=profile_name, colors=colors)


def load_profile_from_file() -> ColorProfile:
    """从文件加载配置"""
    print_header("从文件加载配置")

    while True:
        filepath = ask_string("请输入配置文件路径")
        if not filepath:
            print("路径不能为空")
            continue

        path = Path(filepath)
        if not path.exists():
            print(f"文件不存在: {filepath}")
            retry = ask_yes_no("是否重新输入路径?", default=True)
            if not retry:
                print("切换到默认配置...")
                manager = get_profile_manager()
                return manager.get_profile("full_8")
            continue

        try:
            manager = get_profile_manager()
            profile_id = manager.load_from_file(path)
            profile = manager.get_profile(profile_id)
            print(f"\n成功加载配置: {profile.name}")
            print(f"颜色: {', '.join(profile.color_names)}")
            return profile
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            retry = ask_yes_no("是否重新输入路径?", default=True)
            if not retry:
                print("切换到默认配置...")
                manager = get_profile_manager()
                return manager.get_profile("full_8")


def configure_board_dimensions() -> Dict[str, Any]:
    """配置色盘尺寸"""
    print_header("步骤 2/4: 色盘尺寸配置")

    print("色盘由数据区域和边框组成。数据区域包含校准格子，边框用于标记定位。")
    print()

    presets = [
        ("small", "小型 (16x16 数据区, 2mm格子)", {"rows": 16, "cols": 16, "cell_size": 2.0}),
        ("medium", "中型 (32x32 数据区, 4mm格子, 推荐)", {"rows": 32, "cols": 32, "cell_size": 4.0}),
        ("large", "大型 (48x48 数据区, 3mm格子)", {"rows": 48, "cols": 48, "cell_size": 3.0}),
        ("custom", "自定义尺寸", "custom"),
    ]

    choice = ask_choice("请选择色盘尺寸预设", presets, default=2)

    if choice == "custom":
        print("\n自定义尺寸配置:")
        rows = int(ask_number("数据区域行数", 32, 4, 64, allow_float=False))
        cols = int(ask_number("数据区域列数", 32, 4, 64, allow_float=False))
        cell_size = ask_number("格子尺寸 (mm)", 4.0, 1.0, 10.0)
    else:
        rows = choice["rows"]
        cols = choice["cols"]
        cell_size = choice["cell_size"]

    core_size = max(rows, cols) + 2
    total_size_mm = core_size * cell_size

    print(f"\n配置确认:")
    print(f"  数据区域: {rows}行 x {cols}列")
    print(f"  格子尺寸: {cell_size}mm")
    print(f"  含边框总尺寸: {core_size}x{core_size} 格子 = {total_size_mm:.1f}x{total_size_mm:.1f} mm")

    return {
        "rows": rows,
        "cols": cols,
        "cell_size_mm": cell_size,
    }


def configure_print_settings() -> Dict[str, Any]:
    """配置打印参数"""
    print_header("步骤 3/4: 打印参数配置")

    print("打印参数影响3MF文件的层高和层数。")
    print()

    layer_height = ask_number("层高 (mm)", gen_bd.DEFAULT_LAYER_HEIGHT, 0.04, 0.4)
    layers = int(ask_number("总层数", gen_bd.DEFAULT_LAYERS, 2, 10, allow_float=False))

    total_thickness = layer_height * layers

    print(f"\n配置确认:")
    print(f"  层高: {layer_height}mm")
    print(f"  层数: {layers}")
    print(f"  总厚度: {total_thickness:.2f}mm")

    return {
        "layer_height_mm": layer_height,
        "layers": layers,
    }


def configure_generation_options() -> Dict[str, Any]:
    """配置生成选项"""
    print_header("步骤 4/4: 生成选项")

    num_boards = int(ask_number("生成板子数量", 8, 1, 26, allow_float=False))

    print(f"\n配置确认:")
    print(f"  板子数量: {num_boards} 个")

    return {
        "num_boards": num_boards,
    }


def confirm_and_run(config: Dict[str, Any]) -> bool:
    """确认配置并运行"""
    print_header("配置确认")

    profile: ColorProfile = config["profile"]

    print("请确认以下配置:")
    print()
    print(f"【颜色配置】")
    print(f"  名称: {profile.name}")
    print(f"  颜色: {', '.join(profile.color_names)}")
    print(f"  数量: {profile.num_colors} 色")
    print()
    print(f"【色盘尺寸】")
    print(f"  数据区域: {config['rows']}行 x {config['cols']}列")
    print(f"  格子尺寸: {config['cell_size_mm']}mm")
    print()
    print(f"【打印参数】")
    print(f"  层高: {config['layer_height_mm']}mm")
    print(f"  层数: {config['layers']}")
    print()
    print(f"【生成选项】")
    print(f"  板子数量: {config['num_boards']} 个")
    print()

    confirmed = ask_yes_no("确认以上配置并开始生成?", default=True)
    return confirmed


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  OpenColor 校准板交互式生成工具")
    print("=" * 60)
    print("\n本工具将通过问答方式收集配置信息，生成多色校准板。")
    print("按提示输入即可，直接回车将使用默认值。")

    try:
        config = {}

        config["profile"] = configure_color_profile()

        dims = configure_board_dimensions()
        config.update(dims)

        print_settings = configure_print_settings()
        config.update(print_settings)

        gen_options = configure_generation_options()
        config.update(gen_options)

        if not confirm_and_run(config):
            print("\n已取消生成。如需修改配置，请重新运行脚本。")
            return

        print_header("开始生成校准板")

        profile = config["profile"]
        slot_names = profile.color_names
        slot_colors = {name: profile.get_color_rgba(name) for name in slot_names}
        marker_colors = profile.marker_colors
        default_border_color = get_default_border_color(profile)

        run(
            num_boards=config["num_boards"],
            shrink=0.0,
            profile=profile,
            layer_height_mm=config["layer_height_mm"],
            cell_size_mm=config["cell_size_mm"],
            data_rows=config["rows"],
            data_cols=config["cols"],
        )

        print("\n" + "=" * 60)
        print("  生成完成！")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n用户中断，已退出。")
        sys.exit(0)
    except Exception as e:
        logger.error(f"生成过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
