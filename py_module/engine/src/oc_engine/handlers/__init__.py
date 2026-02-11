from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Dict, Optional


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _get_library_index_path() -> Path:
    from oc_core_02.core.app_paths import get_user_documents_dir

    root = get_user_documents_dir()
    index_dir = root / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)
    return index_dir / "library.json"


def _load_library_index() -> Dict[str, Any]:
    path = _get_library_index_path()
    if not path.exists():
        return {"schema_version": 2, "items": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"[资源库] 读取索引失败: {e}")
        traceback.print_exc()
        return {"schema_version": 2, "items": []}


def _write_library_index(index: Dict[str, Any]) -> None:
    path = _get_library_index_path()
    try:
        path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"[资源库] 写入索引失败: {e}")
        traceback.print_exc()


def _get_relative_path(file_path: Path) -> str:
    r"""将绝对路径转换为相对于 OpenColor 目录的路径。

    例如: C:\Users\xxx\Documents\OpenColor\board_generate\file.stl
    转换为: board_generate\file.stl
    """
    from oc_core_02.core.app_paths import get_user_documents_dir

    file_path = Path(file_path).resolve()
    base_dir = get_user_documents_dir().resolve()

    try:
        # 尝试获取相对路径
        rel_path = file_path.relative_to(base_dir)
        return str(rel_path).replace("/", "\\")  # 统一使用 Windows 路径分隔符
    except ValueError:
        # 如果文件不在 base_dir 下，返回原始路径
        return str(file_path)


def _get_next_board_index(index: Dict[str, Any]) -> int:
    """获取下一个色盘递增编号。

    扫描现有 items，找到最大的 board_index，返回 +1
    """
    items = index.get("items", [])
    max_index = 0
    for it in items:
        if isinstance(it, dict):
            # 检查是否是色盘相关文件
            kind = it.get("kind", "")
            short = it.get("short", {})
            if kind in ("json", "board_model") and short.get("kind") == "bd":
                board_index = it.get("board_index")
                if not isinstance(board_index, int):
                    board_index = short.get("board_index", 0)
                if board_index > max_index:
                    max_index = board_index
    return max_index + 1


def upsert_library_item(
    *,
    file_path: Path,
    kind: str,
    short: Optional[Dict[str, Any]] = None,
    long: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        file_path = Path(file_path)
        try:
            st = file_path.stat()
            ctime = int(getattr(st, "st_ctime", 0) or getattr(st, "st_mtime", 0) or 0)
        except Exception as e:
            logger.error(f"[资源库] 获取文件时间失败: {file_path}，原因={e}")
            traceback.print_exc()
            ctime = 0

        index = _load_library_index()
        items = index.get("items")
        if not isinstance(items, list):
            items = []
            index["items"] = items

        # 使用相对路径存储
        rel_path = _get_relative_path(file_path)
        existing = None
        for it in items:
            if isinstance(it, dict) and it.get("path") == rel_path:
                existing = it
                break

        # 判断是否是新的色盘规格文件（json + bd）
        is_new_board_spec = (
            existing is None
            and kind == "json"
            and short is not None
            and short.get("kind") == "bd"
        )

        is_board_model = (
            kind == "board_model" and short is not None and short.get("kind") == "bd"
        )

        # 如果是新的色盘规格文件，分配递增编号
        board_index = None
        if is_new_board_spec:
            board_index = _get_next_board_index(index)
            logger.info(f"[资源库] 分配色盘编号: {board_index}")

        # 如果是色盘模型文件，尽量复用同一批次色盘规格的编号
        if board_index is None and is_board_model and existing is None:
            src_hash = short.get("src_hash") if isinstance(short, dict) else None
            if src_hash:
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    if it.get("kind") != "json":
                        continue
                    it_short = it.get("short")
                    if not isinstance(it_short, dict):
                        continue
                    if it_short.get("kind") != "bd":
                        continue
                    if it_short.get("src_hash") != src_hash:
                        continue
                    found = it.get("board_index")
                    if isinstance(found, int) and found > 0:
                        board_index = found
                        logger.info(
                            f"[资源库] 复用色盘编号: {board_index} (src_hash={src_hash})"
                        )
                        break

        if existing is None:
            existing = {
                "id": rel_path,
                "name": file_path.name,
                "path": rel_path,
                "kind": str(kind),
                "ctime": int(ctime),
            }
            if board_index is not None:
                existing["board_index"] = board_index
            items.append(existing)
        else:
            existing["name"] = file_path.name
            existing["kind"] = str(kind)
            if ctime:
                existing["ctime"] = int(ctime)
            # 保留已有的 board_index
            board_index = existing.get("board_index")

        if short is not None:
            existing["short"] = short
        if long is not None:
            existing["long"] = long

        # 将 board_index 存入 short，供前端使用
        if board_index is not None:
            if existing.get("short") is None:
                existing["short"] = {}
            existing["short"]["board_index"] = board_index

        if "schema_version" not in index:
            index["schema_version"] = 2

        _write_library_index(index)
    except Exception as e:
        logger.error(f"[资源库] 更新索引失败: {e}")
        traceback.print_exc()
