from __future__ import annotations

import os
import subprocess
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    """
    运行 C++ 模块演示程序

    根据环境变量配置自动退出行为
    """
    # 获取项目根目录（当前文件的上两级）
    project_root = Path(__file__).resolve().parents[2]
    cpp_dir = project_root / "cpp_module"
    build_dir = cpp_dir / "build"
    config = os.environ.get("CMAKE_BUILD_TYPE", "Release").strip()

    # 查找可执行文件
    exe = build_dir / config / "opencolor_cpp_module.exe"
    if not exe.exists():
        raise FileNotFoundError("未找到 demo 可执行文件，请先运行：pixi run cpp-build")

    # 构建命令行参数
    auto_exit_ms_raw = os.environ.get("CPP_MODULE_AUTO_EXIT_MS", "").strip()
    cmd = [str(exe)]
    if auto_exit_ms_raw and auto_exit_ms_raw != "-1":
        cmd += ["--auto-exit-ms", auto_exit_ms_raw]
        logger.info(f"[信息] 已启用自动退出：{auto_exit_ms_raw} ms")
    else:
        logger.info("[信息] 未启用自动退出，窗口将常开（关闭窗口或 Alt+F4 退出）")

    logger.info(f"[命令] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(exe.parent), check=True)


if __name__ == "__main__":
    main()
