"""
OpenColor 工作流交互式运行脚本

提供交互式命令行界面，帮助用户轻松理解和运行各个模块。
支持完整校准流程和生成流程的一键执行。

使用方法:
    pixi run python -m oc_proto.run_workflow
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_menu():
    """打印主菜单"""
    print_header("OpenColor 工作流菜单")
    print("""
请选择要执行的操作:

[校准流程]
  1. 生成校准板 (calib_board_gen)
  2. 照片透视变换 (calib_photo_warp)
  3. 构建样本数据集 (calib_sample_build)
  4. 训练颜色模型 (calib_color_rts)
  5. 【一键执行完整校准流程】

[生成流程]
  6. 生成打印掩码 (gen_masks)
  7. 矢量化 (gen_vector)
  8. 导出3MF模型 (gen_3mf)
  9. 【一键执行完整生成流程】

[工具]
  0. 显示模块帮助信息
  C. 清理输出目录
  Q. 退出
""")


def get_input(prompt: str, default: Optional[str] = None) -> str:
    """获取用户输入"""
    if default is not None:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    try:
        value = input(full_prompt).strip()
        if not value and default is not None:
            return default
        return value
    except (EOFError, KeyboardInterrupt):
        print("\n")
        return "q"


def get_bool_input(prompt: str, default: bool = False) -> bool:
    """获取布尔输入"""
    default_str = "Y/n" if default else "y/N"
    value = get_input(prompt, default_str).lower()
    if value in ("y", "yes", "是"):
        return True
    elif value in ("n", "no", "否"):
        return False
    return default


def get_int_input(prompt: str, default: int) -> int:
    """获取整数输入"""
    value = get_input(prompt, str(default))
    try:
        return int(value)
    except ValueError:
        print(f"输入无效，使用默认值: {default}")
        return default


def get_float_input(prompt: str, default: float) -> float:
    """获取浮点数输入"""
    value = get_input(prompt, str(default))
    try:
        return float(value)
    except ValueError:
        print(f"输入无效，使用默认值: {default}")
        return default


def run_calib_board_gen():
    """运行校准板生成"""
    print_header("生成校准板")

    print("""
可用预设配置:
  - rgb: RGB三原色(3色)
  - rybw: RYBW四色(4色)
  - rgbw: RGBW四色(4色)
  - rgbwk: RGBWK五色(5色)
  - full_8: 完整8色(8色，默认)
""")

    profile = get_input("选择颜色配置", "full_8")
    num_boards = get_int_input("生成板子数量", 2)
    rows = get_int_input("数据区域行数", 32)
    cols = get_int_input("数据区域列数", 32)
    cell_size = get_float_input("格子尺寸(mm)", 4.0)
    layer_height = get_float_input("层高(mm)", 0.12)

    print(f"\n正在生成 {num_boards} 个 {profile} 校准板...")

    try:
        from oc_proto.calib_board_gen.main import run
        from oc_proto.calib_board_gen.color_profiles import get_profile_manager

        manager = get_profile_manager()
        color_profile = manager.get_profile(profile)

        run(
            num_boards=num_boards,
            profile=color_profile,
            layer_height_mm=layer_height,
            cell_size_mm=cell_size,
            data_rows=rows,
            data_cols=cols,
        )
        print("\n校准板生成完成！")
    except Exception as e:
        logger.error(f"生成失败: {e}")
        import traceback

        traceback.print_exc()


def run_calib_photo_warp():
    """运行照片透视变换"""
    print_header("照片透视变换")
    print("""
此步骤需要交互式操作:
  1. 选择校准板照片
  2. 标记四个角点
  3. 保存透视变换结果
""")

    if not get_bool_input("是否启动交互式UI?", True):
        print("已取消")
        return

    try:
        from oc_proto.calib_photo_warp.app import main

        print("\n启动交互式应用...")
        main()
    except Exception as e:
        logger.error(f"运行失败: {e}")
        import traceback

        traceback.print_exc()


def run_calib_sample_build():
    """运行样本构建"""
    print_header("构建样本数据集")

    mode = get_input("选择模式 (batch/single)", "batch")

    try:
        from oc_proto.calib_sample_build.main import run

        if mode == "single":
            warped = get_input("输入 warped 图像路径")
            spec = get_input("输入 spec JSON路径")
            patched = get_input("输入 patched JSON路径")
            run(
                warped_path=warped,
                spec_path=spec,
                patched_path=patched,
            )
        else:
            print("\n正在批量处理...")
            run()

        print("\n样本构建完成！")
    except Exception as e:
        logger.error(f"构建失败: {e}")
        import traceback

        traceback.print_exc()


def run_calib_color_rts():
    """运行颜色模型训练"""
    print_header("训练颜色校准模型")

    optical_model = get_input("光学模型 (rts/four_flux/tmm)", "rts")
    opt_steps = get_int_input("优化步数", 500)
    use_vulkan = get_bool_input("启用Vulkan加速?", True)
    optimize_k = get_bool_input("优化Saunderson参数?", False)

    print(f"\n开始训练模型 (模型: {optical_model}, 步数: {opt_steps})...")

    try:
        from oc_proto.calib_color_rts.main import run
        from oc_proto.calib_color_rts.cli import FitArgs

        args = FitArgs(
            optical_model=optical_model,
            opt_steps=opt_steps,
            use_vulkan=use_vulkan,
            optimize_k=optimize_k,
        )
        run(args=args)
        print("\n模型训练完成！")
    except Exception as e:
        logger.error(f"训练失败: {e}")
        import traceback

        traceback.print_exc()


def run_full_calib_workflow():
    """运行完整校准流程"""
    print_header("执行完整校准流程")

    print("""
即将执行以下步骤:
  1. 生成校准板
  2. 照片透视变换（交互式）
  3. 构建样本数据集
  4. 训练颜色模型
""")

    if not get_bool_input("确认执行?", True):
        print("已取消")
        return

    run_calib_board_gen()

    if get_bool_input("是否继续照片透视变换?", True):
        run_calib_photo_warp()

    if get_bool_input("是否继续构建样本数据集?", True):
        run_calib_sample_build()

    if get_bool_input("是否继续训练颜色模型?", True):
        run_calib_color_rts()

    print("\n完整校准流程执行完毕！")


def run_gen_masks():
    """运行掩码生成"""
    print_header("生成打印掩码")

    image_path = get_input("输入图像路径 (默认: data/image/龙娘.png)", "data/image/龙娘.png")
    use_superres = get_bool_input("启用超分辨率?", False)
    postprocess = get_input("后处理模式 (none/conv/guided/joint/island)", "island")
    enable_joint_l0 = get_bool_input("启用首层联合优化?", False)

    print(f"\n正在生成掩码...")

    try:
        from oc_proto.gen_masks.main import run

        result = run(
            image_path=image_path,
            superres_enabled=use_superres,
            postprocess_mode=postprocess,
            joint_l0_enabled=enable_joint_l0,
        )

        output_dir = result.get("output_dir", "unknown")
        print(f"\n掩码生成完成！输出目录: {output_dir}")
        return output_dir
    except Exception as e:
        logger.error(f"生成失败: {e}")
        import traceback

        traceback.print_exc()
        return None


def run_gen_vector(mask_dir: Optional[str] = None):
    """运行矢量化"""
    print_header("矢量化掩码")

    if mask_dir is None:
        mask_dir = get_input("输入掩码目录路径 (留空自动查找)", "")
        if not mask_dir:
            mask_dir = None

    use_resample = get_bool_input("启用共享边界重采样?", True)
    impl = get_input("实现方式 (cpp/python)", "cpp")

    print(f"\n正在矢量化...")

    try:
        from oc_proto.gen_vector.main import run

        result = run(
            mask_input_dir=mask_dir,
            resample=use_resample,
            impl=impl,
        )

        output_dir = result.get("output_dir", "unknown")
        print(f"\n矢量化完成！输出目录: {output_dir}")
        return output_dir
    except Exception as e:
        logger.error(f"矢量化失败: {e}")
        import traceback

        traceback.print_exc()
        return None


def run_gen_3mf(vector_dir: Optional[str] = None):
    """运行3MF导出"""
    print_header("导出3MF模型")

    if vector_dir is None:
        vector_dir = get_input("输入矢量目录路径 (留空自动查找)", "")
        if not vector_dir:
            vector_dir = None

    use_cpp = get_bool_input("启用C++加速?", True)
    export_stl = get_bool_input("导出STL?", True)
    export_3mf = get_bool_input("导出3MF?", True)

    print(f"\n正在导出...")

    try:
        from oc_proto.gen_3mf.main import run

        run(
            poly_input_dir=vector_dir,
            use_cpp=use_cpp,
            export_stl=export_stl,
            export_3mf=export_3mf,
        )

        print("\n3MF导出完成！")
    except Exception as e:
        logger.error(f"导出失败: {e}")
        import traceback

        traceback.print_exc()


def run_full_gen_workflow():
    """运行完整生成流程"""
    print_header("执行完整生成流程")

    print("""
即将执行以下步骤:
  1. 生成打印掩码
  2. 矢量化
  3. 导出3MF模型
""")

    if not get_bool_input("确认执行?", True):
        print("已取消")
        return

    mask_dir = run_gen_masks()

    if mask_dir and get_bool_input("是否继续矢量化?", True):
        vector_dir = run_gen_vector(mask_dir)

        if vector_dir and get_bool_input("是否继续导出3MF?", True):
            run_gen_3mf(vector_dir)

    print("\n完整生成流程执行完毕！")


def show_help():
    """显示帮助信息"""
    print_header("模块帮助信息")

    modules = [
        ("calib_board_gen", "校准板生成器"),
        ("calib_photo_warp", "照片透视变换"),
        ("calib_sample_build", "样本构建"),
        ("calib_color_rts", "颜色模型训练"),
        ("gen_masks", "掩码生成器"),
        ("gen_vector", "矢量化器"),
        ("gen_3mf", "3MF导出器"),
    ]

    print("\n可用模块:")
    for i, (name, desc) in enumerate(modules, 1):
        print(f"  {i}. {name:20s} - {desc}")

    choice = get_input("\n选择要查看帮助的模块编号 (1-7)", "")

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(modules):
            module_name = modules[idx][0]
            print(f"\n--- {module_name} 帮助信息 ---")

            import subprocess

            result = subprocess.run(
                ["pixi", "run", "python", "-m", f"oc_proto.{module_name}.main", "--help"],
                capture_output=True,
                text=True,
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
    except (ValueError, IndexError):
        print("无效选择")


def run_clean():
    """运行清理"""
    print_header("清理输出目录")

    print("""
清理选项:
  1. 清理校准数据 (calib)
  2. 清理生成数据 (gen)
  3. 清理所有数据 (all)
""")

    choice = get_input("选择清理类型 (1/2/3)", "")

    clean_type = None
    if choice == "1":
        clean_type = "calib"
    elif choice == "2":
        clean_type = "gen"
    elif choice == "3":
        clean_type = "all"
    else:
        print("无效选择")
        return

    if not get_bool_input(f"确认清理 {clean_type} 数据? 此操作不可恢复!", False):
        print("已取消")
        return

    try:
        from oc_proto.common.clean import main as clean_main

        # 模拟命令行参数
        import sys

        old_argv = sys.argv
        sys.argv = ["clean", "--type", clean_type]
        clean_main()
        sys.argv = old_argv

        print(f"\n{clean_type} 数据清理完成！")
    except Exception as e:
        logger.error(f"清理失败: {e}")
        import traceback

        traceback.print_exc()


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║           OpenColor 工作流交互式运行工具                 ║
║                                                          ║
║  帮助用户理解和运行各个模块，支持一键执行完整流程        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    while True:
        print_menu()
        choice = get_input("请输入选项").lower()

        if choice in ("q", "quit", "exit", "退出"):
            print("\n感谢使用，再见！")
            break
        elif choice == "1":
            run_calib_board_gen()
        elif choice == "2":
            run_calib_photo_warp()
        elif choice == "3":
            run_calib_sample_build()
        elif choice == "4":
            run_calib_color_rts()
        elif choice == "5":
            run_full_calib_workflow()
        elif choice == "6":
            run_gen_masks()
        elif choice == "7":
            run_gen_vector()
        elif choice == "8":
            run_gen_3mf()
        elif choice == "9":
            run_full_gen_workflow()
        elif choice == "0":
            show_help()
        elif choice == "c":
            run_clean()
        else:
            print("无效选项，请重新输入")

        input("\n按回车键继续...")


if __name__ == "__main__":
    main()
