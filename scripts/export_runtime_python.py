#!/usr/bin/env python3
"""导出 Pixi runtime 环境到 Tauri 资源目录"""

import os
import shutil
import subprocess
from pathlib import Path

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def get_project_root() -> Path:
    """获取项目根目录"""
    script_dir = Path(__file__).parent.resolve()
    return script_dir.parent


def ensure_runtime_env(project_root: Path) -> None:
    env_path = project_root / ".pixi" / "envs" / "runtime"
    if env_path.exists():
        return

    logger.info("未检测到 runtime 环境，正在执行：pixi install -e runtime")
    subprocess.run(["pixi", "install", "-e", "runtime"], cwd=project_root, check=True)


def get_runtime_env_path() -> Path:
    """获取 runtime 环境路径"""
    project_root = get_project_root()
    # Pixi 环境位于 .pixi/envs/runtime/
    env_path = project_root / ".pixi" / "envs" / "runtime"
    if env_path.exists():
        return env_path
    # 如果没有独立环境，使用默认环境
    default_env = project_root / ".pixi" / "envs" / "default"
    if default_env.exists():
        logger.warning("未找到 runtime 环境，将改用 default 环境")
        return default_env
    raise FileNotFoundError("未找到 Pixi runtime 环境")


def should_ignore(name: str, path: Path) -> bool:
    """判断是否应该忽略该文件/目录"""
    ignore_patterns = {
        # Python 开发工具
        '__pycache__',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.pytest_cache',
        'pytest',
        '_pytest',
        'py.test',
        # 构建工具
        'pip',
        'setuptools',
        'wheel',
        'distutils',
        # 文档和测试
        'tests',
        'test',
        'docs',
        'doc',
        'Documentation',
        'examples',
        'demos',
        # 版本控制
        '.git',
        '.gitignore',
        '.github',
        # 调试符号
        '*.pdb',
        '*.lib',
        # 开发配置文件
        '*.h',
        '*.hpp',
        '*.c',
        '*.cpp',
        # 其他
        'include',  # C 头文件目录
        'tcl',
        'tk',
        'tix',
        'idlelib',  # Python IDLE
    }
    
    # 检查是否匹配忽略模式
    for pattern in ignore_patterns:
        if pattern.startswith('*'):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern or name.lower() == pattern.lower():
            return True
    
    return False


def copy_runtime_env():
    """复制 runtime 环境到目标目录"""
    project_root = get_project_root()
    ensure_runtime_env(project_root)
    source_env = get_runtime_env_path()
    target_dir = project_root / "web" / "src-tauri" / "resources" / "python"

    logger.info(f"源环境: {source_env}")
    logger.info(f"目标目录: {target_dir}")
    
    # 清理旧的环境
    if target_dir.exists():
        logger.info("清理旧的环境")
        shutil.rmtree(target_dir)
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 统计信息
    copied_files = 0
    skipped_files = 0
    copied_size = 0
    copy_errors: list[tuple[Path, str]] = []
    
    # 遍历并复制文件
    for root, dirs, files in os.walk(source_env):
        root_path = Path(root)
        
        # 过滤目录
        dirs[:] = [
            d for d in dirs 
            if not should_ignore(d, root_path / d)
        ]
        
        # 创建目标目录
        relative_path = root_path.relative_to(source_env)
        target_path = target_dir / relative_path
        target_path.mkdir(parents=True, exist_ok=True)
        
        # 复制文件
        for file in files:
            if should_ignore(file, root_path / file):
                skipped_files += 1
                continue
            
            source_file = root_path / file
            target_file = target_path / file
            
            try:
                shutil.copy2(source_file, target_file)
                copied_files += 1
                copied_size += source_file.stat().st_size
            except Exception as e:
                logger.error(f"复制失败 {source_file}: {e}")
                copy_errors.append((source_file, str(e)))
                skipped_files += 1

    logger.info("复制完成")
    logger.info(f"复制文件: {copied_files}")
    logger.info(f"跳过文件: {skipped_files}")
    logger.info(f"总大小: {copied_size / (1024 * 1024):.2f} MB")

    if copy_errors:
        max_show = 8
        shown = "\n".join(
            f"- {p}: {msg}" for p, msg in copy_errors[:max_show]
        )
        more = "" if len(copy_errors) <= max_show else f"\n- ... 以及另外 {len(copy_errors) - max_show} 个错误"
        raise RuntimeError(f"复制过程中发生错误：\n{shown}{more}")
    
    return target_dir


def create_python_config(target_dir: Path):
    """创建 Python 配置文件"""
    config_content = """import os
import sys

PYTHON_HOME = os.path.dirname(os.path.abspath(__file__))

os.environ["PYTHONHOME"] = PYTHON_HOME
os.environ["PYTHONPATH"] = os.path.join(PYTHON_HOME, "Lib", "site-packages")

site_packages = os.path.join(PYTHON_HOME, "Lib", "site-packages")
dlls = os.path.join(PYTHON_HOME, "DLLs")

if site_packages not in sys.path:
    sys.path.insert(0, site_packages)
if dlls not in sys.path:
    sys.path.insert(0, dlls)
"""
    
    config_file = target_dir / "python_config.py"
    config_file.write_text(config_content, encoding='utf-8')
    logger.info(f"创建配置文件: {config_file}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("导出 Pixi Runtime Python 环境")
    logger.info("=" * 60)

    target_dir = copy_runtime_env()
    create_python_config(target_dir)

    logger.info("=" * 60)
    logger.info("导出完成")
    logger.info(f"目标目录: {target_dir}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
