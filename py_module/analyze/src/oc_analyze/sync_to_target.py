"""
同步当前仓库内容到目标仓库

将当前 Git 仓库的所有追踪文件同步到另一个本地仓库，保持目标仓库的历史记录。
被 Git 忽略的文件不会同步，目标仓库中已在源仓库删除的文件会被清理。
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Set

from dotenv import load_dotenv

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def load_config():
    """加载配置文件"""
    # 从脚本位置向上找到 analyze 模块根目录（src/oc_analyze/ -> src/ -> analyze/）
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"已加载配置文件: {env_path}")
    else:
        logger.warning(f"配置文件不存在: {env_path}")

    target_path = os.getenv("SYNC_TARGET_REPO_PATH")
    if not target_path:
        raise ValueError(
            "未配置 SYNC_TARGET_REPO_PATH，请在 .env 文件中设置目标仓库路径"
        )

    return {
        "target_repo": Path(target_path),
        "commit_message": os.getenv("SYNC_COMMIT_MESSAGE", "update"),
        "auto_push": os.getenv("SYNC_AUTO_PUSH", "false").lower() == "true",
    }


def get_submodule_paths(source_root: Path) -> Set[Path]:
    """获取所有子模块的路径

    Args:
        source_root: 源仓库根目录

    Returns:
        子模块相对路径集合
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "submodule",
                "foreach",
                "-q",
                "echo $name",
            ],
            cwd=source_root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return set()

        submodules = set()
        for line in result.stdout.strip().split("\n"):
            if line:
                submodules.add(Path(line))

        logger.debug(f"发现 {len(submodules)} 个子模块: {submodules}")
        return submodules

    except Exception as e:
        logger.warning(f"获取子模块列表失败: {e}")
        return set()


def get_source_files(source_root: Path) -> Set[Path]:
    """获取源仓库所有被 Git 追踪的文件列表

    使用 git ls-files -z 获取文件列表，正确处理中文文件名和特殊字符。
    通过 core.quotepath=false 避免八进制字符转义问题。
    自动排除子模块目录。

    Args:
        source_root: 源仓库根目录

    Returns:
        被追踪文件的相对路径集合（相对于仓库根目录）
    """
    try:
        # 获取子模块路径列表
        submodule_paths = get_submodule_paths(source_root)

        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=source_root,
            capture_output=True,
            check=True,
        )

        # -z 参数输出以 NUL 分隔的字节流
        output = result.stdout.decode("utf-8")
        files = set()

        for filepath in output.split("\0"):
            if not filepath:
                continue

            path = Path(filepath)

            # 跳过子模块目录及其内容
            if path in submodule_paths:
                logger.debug(f"跳过子模块: {filepath}")
                continue

            # 检查是否在子模块内部
            is_inside_submodule = any(path.is_relative_to(sm) for sm in submodule_paths)
            if is_inside_submodule:
                logger.debug(f"跳过子模块内文件: {filepath}")
                continue

            files.add(path)

        logger.info(f"扫描到 {len(files)} 个被追踪的文件（排除子模块）")
        return files

    except subprocess.CalledProcessError as e:
        logger.error(f"执行 git ls-files 失败: {e}")
        raise
    except Exception as e:
        logger.error(f"获取源文件列表时发生错误: {e}")
        raise


def sync_files(
    source_root: Path, target_root: Path, source_files: Set[Path]
) -> tuple[int, int]:
    """同步文件到目标仓库

    将源文件复制到目标仓库对应位置，确保目录结构一致。

    Args:
        source_root: 源仓库根目录
        target_root: 目标仓库根目录
        source_files: 源文件相对路径集合

    Returns:
        (新增文件数, 更新文件数)
    """
    added = 0
    updated = 0

    for rel_path in source_files:
        source_file = source_root / rel_path
        target_file = target_root / rel_path

        # 确保目标目录存在
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # 检查文件是否需要复制
        need_copy = False
        if not target_file.exists():
            need_copy = True
            added += 1
            logger.debug(f"新增文件: {rel_path}")
        else:
            # 比较文件内容
            try:
                with open(source_file, "rb") as sf, open(target_file, "rb") as tf:
                    if sf.read() != tf.read():
                        need_copy = True
                        updated += 1
                        logger.debug(f"更新文件: {rel_path}")
            except Exception as e:
                logger.error(f"比较文件内容失败 {rel_path}: {e}")
                need_copy = True

        if need_copy:
            try:
                shutil.copy2(source_file, target_file)
            except Exception as e:
                logger.error(f"复制文件失败 {rel_path}: {e}")
                raise

    logger.info(f"文件同步完成: 新增 {added} 个, 更新 {updated} 个")
    return added, updated


def get_target_tracked_files(target_root: Path) -> Set[Path]:
    """获取目标仓库中被 Git 追踪的文件列表

    Args:
        target_root: 目标仓库根目录

    Returns:
        被追踪文件的相对路径集合
    """
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=target_root,
            capture_output=True,
            check=True,
        )

        output = result.stdout.decode("utf-8")
        files = set()

        for filepath in output.split("\0"):
            if filepath:
                files.add(Path(filepath))

        return files

    except subprocess.CalledProcessError:
        return set()
    except Exception:
        return set()


def cleanup_target(target_root: Path, source_files: Set[Path]) -> int:
    """清理目标仓库中多余的文件

    只删除目标仓库中被 Git 追踪但源仓库已不存在的文件。
    未被 Git 管理的文件（如 .idea/ 等 IDE 配置）会被保留。

    Args:
        target_root: 目标仓库根目录
        source_files: 源文件相对路径集合

    Returns:
        删除的文件数
    """
    deleted = 0

    # 获取目标仓库中被 Git 追踪的文件
    target_tracked_files = get_target_tracked_files(target_root)

    if not target_tracked_files:
        logger.warning("无法获取目标仓库的追踪文件列表，跳过清理")
        return 0

    # 只删除目标仓库追踪了但源仓库不存在的文件
    files_to_delete = target_tracked_files - source_files

    for rel_path in files_to_delete:
        target_file = target_root / rel_path
        try:
            target_file.unlink()
            deleted += 1
            logger.debug(f"删除文件: {rel_path}")

            # 清理空目录
            parent = target_file.parent
            while parent != target_root:
                try:
                    parent.rmdir()
                    logger.debug(f"清理空目录: {parent.relative_to(target_root)}")
                    parent = parent.parent
                except OSError:
                    break
        except Exception as e:
            logger.error(f"删除文件失败 {rel_path}: {e}")

    logger.info(f"清理完成: 删除 {deleted} 个多余文件（目标仓库追踪的文件）")
    return deleted


def git_commit_and_push(
    target_root: Path, commit_message: str, auto_push: bool
) -> bool:
    """在目标仓库执行 Git 提交和推送

    Args:
        target_root: 目标仓库根目录
        commit_message: 提交信息
        auto_push: 是否自动推送

    Returns:
        是否成功提交
    """
    try:
        # 检查是否有变更
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=target_root,
            capture_output=True,
            text=True,
            check=True,
        )

        if not status_result.stdout.strip():
            logger.info("目标仓库没有变更，无需提交")
            return False

        # 添加所有变更
        subprocess.run(
            ["git", "add", "-A"],
            cwd=target_root,
            check=True,
        )
        logger.info("已添加所有变更到暂存区")

        # 提交
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=target_root,
            check=True,
        )
        logger.info(f"已提交: {commit_message}")

        # 推送
        if auto_push:
            subprocess.run(
                ["git", "push"],
                cwd=target_root,
                check=True,
            )
            logger.info("已推送到远程仓库")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git 操作失败: {e}")
        raise
    except Exception as e:
        logger.error(f"Git 操作发生错误: {e}")
        raise


def main():
    """主函数"""
    logger.info("=== 开始同步到目标仓库 ===")

    # 加载配置
    config = load_config()
    target_repo = config["target_repo"]
    commit_message = config["commit_message"]
    auto_push = config["auto_push"]

    # 验证目标仓库
    if not target_repo.exists():
        raise FileNotFoundError(f"目标仓库不存在: {target_repo}")

    git_dir = target_repo / ".git"
    if not git_dir.exists():
        raise ValueError(f"目标目录不是 Git 仓库: {target_repo}")

    logger.info(f"目标仓库: {target_repo}")

    # 获取源仓库根目录（当前脚本向上 4 级）
    source_repo = Path(__file__).resolve().parents[4]
    logger.info(f"源仓库: {source_repo}")

    # 获取源文件列表
    source_files = get_source_files(source_repo)

    if not source_files:
        logger.warning("源仓库没有追踪的文件")
        return

    # 同步文件
    added, updated = sync_files(source_repo, target_repo, source_files)

    # 清理多余文件
    deleted = cleanup_target(target_repo, source_files)

    # 提交变更
    has_commit = git_commit_and_push(target_repo, commit_message, auto_push)

    # 输出统计
    logger.info("=== 同步完成 ===")
    logger.info(f"新增文件: {added}")
    logger.info(f"更新文件: {updated}")
    logger.info(f"删除文件: {deleted}")
    logger.info(f"提交状态: {'已提交' if has_commit else '无变更'}")


if __name__ == "__main__":
    main()
