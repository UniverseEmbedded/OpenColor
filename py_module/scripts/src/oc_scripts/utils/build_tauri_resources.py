from __future__ import annotations

"""为 Tauri 应用构建侧边栏资源

本仓库使用由 Tauri 后端调用的 Python 引擎。
发布构建时，我们打包以下内容：

- PyInstaller onedir 输出到: web/src-tauri/resources/engine/
  (必须包含 opencolor_engine.exe 及其兄弟目录 `_internal/`)

- C++ 探测可执行文件到: web/src-tauri/resources/cpp/
  (由 cpp_module/scripts/build_demo.py 复制)

- 数据资源到: web/src-tauri/resources/data/

Rust 代码将这些解析为 BaseDirectory::Resource 并通过 std::process::Command 直接执行。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path



from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """运行命令并打印。"""
    logger.info(f"[cmd] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, env=env)


def _reset_dir(dir_path: Path) -> None:
    """重置目录：删除后重新创建。"""
    if dir_path.exists():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)


def _copy_tree(src: Path, dst: Path) -> None:
    """将目录树复制到目标目录（覆盖目标）。"""
    _reset_dir(dst)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def build_python_engine(project_root: Path) -> None:
    """Build the Python engine using PyInstaller (onedir)."""

    entry = project_root / "py_module" / "engine" / "src" / "oc_engine" / "main.py"
    if not entry.exists():
        raise FileNotFoundError(f"Engine entry not found: {entry}")

    tauri_root = project_root / "web" / "src-tauri"
    res_root = tauri_root / "resources"
    engine_dst = res_root / "engine"

    build_root = tauri_root / "target" / "pyinstaller"
    dist_tmp = build_root / "dist"
    work_tmp = build_root / "build"
    spec_tmp = build_root / "spec"

    # 清理临时构建目录。将它们保留在 `src-tauri/target` 内以避免污染仓库根目录。
    for p in (dist_tmp, work_tmp, spec_tmp):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "-D",  # onedir (multi-file) to avoid onefile temp extraction
        "-n",
        "opencolor_engine",
        str(entry),
        "--paths",
        str(project_root / "py_module"),
        "--distpath",
        str(dist_tmp),
        "--workpath",
        str(work_tmp),
        "--specpath",
        str(spec_tmp),
        "--noconfirm",
        "--clean",
    ]
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    _run(cmd, cwd=project_root, env=env)

    produced_dir = dist_tmp / "opencolor_engine"
    produced_exe = produced_dir / "opencolor_engine.exe"
    if not produced_exe.exists():
        raise RuntimeError(f"PyInstaller did not produce expected executable: {produced_exe}")

    # 将 onedir 输出的内容复制到 resources/engine，以便 Rust 可以解析 `engine/opencolor_engine.exe`。
    _reset_dir(engine_dst)
    for item in produced_dir.iterdir():
        target = engine_dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    logger.info(f"[ok] Python 引擎已打包到: {engine_dst}")
    _analyze_size(engine_dst)


def _analyze_size(path: Path) -> None:
    """Analyze and print the size of the bundled directory."""
    logger.info(f"\n{'='*20} 打包大小分析 {'='*20}")
    total_size = 0
    items = []
    for root, _, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            size = fp.stat().st_size
            total_size += size
            items.append((fp, size))

    logger.info(f"总大小: {total_size / 1024 / 1024:.2f} MB")
    logger.info(f"\n最大的 20 个文件:")
    items.sort(key=lambda x: x[1], reverse=True)
    for fp, size in items[:20]:
        logger.info(f"  {size / 1024 / 1024:7.2f} MB  {fp.relative_to(path)}")

    # Category analysis
    categories: dict[str, float] = {}
    for fp, size in items:
        ext = fp.suffix.lower() or "no_ext"
        categories[ext] = categories.get(ext, 0) + size

    logger.info(f"\n按类别大小:")
    for ext, size in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {ext:10}: {size / 1024 / 1024:7.2f} MB ({size/total_size*100:5.1f}%)")
    logger.info(f"{'='*62}\n")


def bundle_cpp_modules(project_root: Path) -> None:
    """将 C++ 编译的 .pyd 模块复制到引擎资源目录。"""
    # 查找 Release 目录下的 .pyd
    cpp_release = project_root / "cpp_module" / "build" / "Release"
    if not cpp_release.exists():
        # 兼容不同生成器路径
        cpp_release = project_root / "cpp_module" / "build"
        
    pyd_files = list(cpp_release.glob("*.pyd"))
    if not pyd_files:
        logger.warning("[warn] No .pyd modules found in C++ build directory")
        return

    dst = project_root / "web" / "src-tauri" / "resources" / "engine"
    dst.mkdir(parents=True, exist_ok=True)
    
    for pyd in pyd_files:
        shutil.copy2(pyd, dst / pyd.name)
        logger.info(f"[ok] C++ module bundled: {pyd.name} -> {dst}")


def bundle_data_assets(project_root: Path) -> None:
    src = project_root / "data"
    if not src.exists():
        logger.warning("[warn] data/ directory not found; skipping")
        return

    dst = project_root / "web" / "src-tauri" / "resources" / "data"
    _copy_tree(src, dst)
    logger.info(f"[ok] Data assets bundled to: {dst}")


def main() -> None:
    """主函数：构建所有 Tauri 资源。"""
    project_root = Path(__file__).resolve().parents[5]

    # 1) Python 引擎侧边栏（PyInstaller onedir）
    build_python_engine(project_root)

    # 2) C++ 模块 (.pyd)
    bundle_cpp_modules(project_root)

    # 3) 数据资源（如拓竹模板 3MF）
    bundle_data_assets(project_root)

    logger.info("[done] Tauri 资源准备完成")


if __name__ == "__main__":
    main()
