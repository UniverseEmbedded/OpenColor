from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """执行命令并打印命令内容"""
    logger.info(f"[命令] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def main() -> None:
    """主函数：初始化并设置 vcpkg 环境"""
    # 获取项目根目录（当前文件的上两级目录）
    project_root = Path(__file__).resolve().parents[2]
    cpp_dir = project_root / "cpp_module"
    vcpkg_rel = Path("cpp_module") / "vcpkg"
    vcpkg_dir = project_root / vcpkg_rel

    # 检查 cpp_module 目录是否存在
    if not cpp_dir.exists():
        raise RuntimeError("未找到 cpp_module 目录")

    # 检查是否为 Git 仓库
    git_dir = project_root / ".git"
    if not git_dir.exists():
        raise RuntimeError(
            "未检测到 Git 仓库，无法初始化 vcpkg 子模块，请先确保项目为 git 仓库"
        )

    # 获取 vcpkg 仓库地址（可从环境变量配置）
    url_raw = os.environ.get(
        "VCPKG_URL", "https://github.com/microsoft/vcpkg.git"
    ).strip()
    url = url_raw.strip().strip("`\"'")

    # 检查是否已存在 vcpkg 子模块配置
    gitmodules = project_root / ".gitmodules"
    has_submodule = False
    if gitmodules.exists():
        content = gitmodules.read_text(encoding="utf-8")
        if f"path = {vcpkg_rel.as_posix()}" in content:
            has_submodule = True

    # 检查 vcpkg 是否已作为子模块被跟踪
    modules_dir = git_dir / "modules" / vcpkg_rel
    tracked_check = subprocess.run(
        ["git", "ls-files", "--stage", vcpkg_rel.as_posix()],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    tracked_as_submodule = "160000" in tracked_check.stdout

    # 如果存在非子模块的 vcpkg 目录，则清理后重新初始化
    if vcpkg_dir.exists() and not tracked_as_submodule:
        logger.info("[信息] 检测到非子模块的 vcpkg 目录，将清理后重新初始化")
        shutil.rmtree(vcpkg_dir)

    # 如果未作为子模块跟踪，则添加子模块
    if not tracked_as_submodule:
        logger.info(f"[信息] 未检测到 vcpkg 子模块，将通过子模块从 {url} 拉取")
        _run(
            [
                "git",
                "submodule",
                "add",
                "-f",
                "--depth",
                "1",
                url,
                vcpkg_rel.as_posix(),
            ],
            cwd=project_root,
        )

    # 初始化并更新子模块
    _run(
        ["git", "submodule", "update", "--init", "--depth", "1", vcpkg_rel.as_posix()],
        cwd=project_root,
    )

    # 切换到指定的 vcpkg 版本
    vcpkg_ref = os.environ.get("VCPKG_REF", "2024.12.16").strip()
    if vcpkg_ref:
        logger.info(f"[信息] 已设置 VCPKG_REF={vcpkg_ref}，将拉取并切换到指定版本")
        _run(
            ["git", "-C", str(vcpkg_dir), "fetch", "--depth", "1", "origin", vcpkg_ref],
            cwd=project_root,
        )
        _run(["git", "-C", str(vcpkg_dir), "checkout", "FETCH_HEAD"], cwd=project_root)

    # 根据操作系统执行对应的引导脚本
    system = platform.system().lower()
    if system == "windows":
        bootstrap = vcpkg_dir / "bootstrap-vcpkg.bat"
        if not bootstrap.exists():
            raise FileNotFoundError("未找到 bootstrap-vcpkg.bat，请确认 vcpkg 拉取完整")
        _run(["cmd", "/c", str(bootstrap), "-disableMetrics"], cwd=vcpkg_dir)
        return

    # Linux/Mac 系统
    bootstrap = vcpkg_dir / "bootstrap-vcpkg.sh"
    if not bootstrap.exists():
        raise FileNotFoundError("未找到 bootstrap-vcpkg.sh，请确认 vcpkg 拉取完整")
    _run(["bash", str(bootstrap), "-disableMetrics"], cwd=vcpkg_dir)


if __name__ == "__main__":
    main()
