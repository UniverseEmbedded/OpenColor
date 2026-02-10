"""模型分析模块 - 提供网格质量分析和 3MF 文件验证功能

本模块提供多种网格分析功能，包括通用网格分析、lib3mf 库分析
以及 Bambu Studio CLI 分析，用于验证 3D 模型的可打印性。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import trimesh

from oc_core_02.utils.logger import get_logger
from oc_core_02.utils.bin_loader import import_cpp_extension

logger = get_logger(__name__)

# C++ 分析函数缓存
_CPP_ANALYZE_FN = None


def _get_cpp_analyze_fn():
    """获取 C++ 网格分析函数

    动态导入 C++ 几何模块并返回 mesh_analyze_basic_nogil 函数

    Returns:
        C++ 分析函数

    Raises:
        RuntimeError: 当无法导入模块或找不到函数时抛出
    """
    global _CPP_ANALYZE_FN
    if _CPP_ANALYZE_FN is not None:
        return _CPP_ANALYZE_FN
    try:
        cpp_geometry = import_cpp_extension("opencolor_geometry")
    except Exception as e:
        logger.error("导入 C++ 几何模块失败，无法进行模型分析(通用网格): {}", e)
        raise

    fn = getattr(cpp_geometry, "mesh_analyze_basic_nogil", None)
    if fn is None:
        raise RuntimeError("C++ 几何模块缺少 mesh_analyze_basic_nogil，无法进行模型分析(通用网格)")

    _CPP_ANALYZE_FN = fn
    return _CPP_ANALYZE_FN


# 环境变量加载标志
_ENV_LOADED = False


def _project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parents[5]


def _load_env() -> None:
    """加载环境变量

    从项目根目录的 .env 文件加载环境变量
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = _project_root() / ".env"
    if env_path.exists():
        text = env_path.read_text(encoding="utf-8", errors="ignore")
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"')
            if key and key not in os.environ:
                os.environ[key] = value
    _ENV_LOADED = True


def _get_bambu_studio_path() -> Optional[str]:
    """获取 Bambu Studio 可执行文件路径

    Returns:
        Bambu Studio 路径，如果未配置则返回 None
    """
    _load_env()
    path = os.environ.get("BAMBUSTUDIO_PATH", "").strip()
    if not path:
        return None
    return path


def analyze_mesh(mesh: trimesh.Trimesh, label: str) -> Dict[str, int]:
    """分析网格质量（通用网格分析）

    使用 C++ 模块分析网格的拓扑结构和几何属性，
    包括非流形边、边界边、退化面等

    Args:
        mesh: Trimesh 网格对象
        label: 分析标签，用于日志输出

    Returns:
        包含分析结果的字典，包括顶点数、面数、非流形边数等
    """
    if mesh.vertices is None or mesh.faces is None:
        logger.info("模型分析(通用网格): {} 网格为空", label)
        return {
            "vertices": 0,
            "faces": 0,
            "non_manifold_edges": 0,
            "boundary_edges": 0,
            "degenerate_faces": 0,
            "duplicate_faces": 0,
            "watertight": 0,
        }
    vertices = mesh.vertices
    faces = mesh.faces
    v_count = int(vertices.shape[0])
    f_count = int(faces.shape[0])
    if f_count == 0 or v_count == 0:
        logger.info("模型分析(通用网格): {} 顶点={} 面={}", label, v_count, f_count)
        return {
            "vertices": v_count,
            "faces": f_count,
            "non_manifold_edges": 0,
            "boundary_edges": 0,
            "degenerate_faces": 0,
            "duplicate_faces": 0,
            "watertight": 0,
        }
    try:
        analyze_fn = _get_cpp_analyze_fn()
        result = analyze_fn(
            np.asarray(vertices, dtype=np.float64),
            np.asarray(faces, dtype=np.int64),
        )
    except Exception as e:
        logger.error("模型分析(通用网格)失败: {}，原因={}", label, e)
        raise

    non_manifold_edges = int(result.get("non_manifold_edges", 0))
    boundary_edges = int(result.get("boundary_edges", 0))
    degenerate_faces = int(result.get("degenerate_faces", 0))
    duplicate_faces = int(result.get("duplicate_faces", 0))
    watertight = bool(result.get("watertight", False))
    logger.info(
        "模型分析(通用网格): {} 顶点={} 面={} 非流形边={} 边界边={} 退化面={} 重复面={} 封闭={}",
        label, v_count, f_count, non_manifold_edges, boundary_edges, degenerate_faces, duplicate_faces, watertight
    )
    return {
        "vertices": v_count,
        "faces": f_count,
        "non_manifold_edges": non_manifold_edges,
        "boundary_edges": boundary_edges,
        "degenerate_faces": degenerate_faces,
        "duplicate_faces": duplicate_faces,
        "watertight": int(watertight),
    }


def analyze_3mf_lib3mf(path: Path) -> None:
    """使用 lib3mf 库分析 3MF 文件

    读取 3MF 文件并输出每个对象的顶点数、面数、流形状态等信息

    Args:
        path: 3MF 文件路径
    """
    try:
        import lib3mf
    except Exception as e:
        logger.warning("3MF分析(lib3mf)不可用: {}", e)
        return
    if not path.exists():
        logger.warning("3MF分析(lib3mf)失败，文件不存在: {}", path)
        return
    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    reader = model.QueryReader("3mf")
    reader.ReadFromFile(str(path))
    it = model.GetObjects()
    idx = 0
    while it.MoveNext():
        obj = it.GetCurrentObject()
        idx += 1
        name = obj.GetName()
        rid = obj.GetResourceID()
        if not hasattr(obj, "GetVertexCount") or not hasattr(obj, "GetTriangleCount"):
            obj_type = type(obj).__name__
            logger.info(
                "3MF分析(lib3mf): 文件={} 对象序号={} 资源ID={} 名称={} 类型={} 跳过",
                path.name, idx, rid, name, obj_type
            )
            continue
        v_count = obj.GetVertexCount()
        t_count = obj.GetTriangleCount()
        is_manifold = False
        if hasattr(obj, "IsManifoldAndOriented"):
            try:
                is_manifold = bool(obj.IsManifoldAndOriented())
            except Exception as e:
                logger.warning("3MF分析(lib3mf)对象检测失败: {}", e)
        logger.info(
            "3MF分析(lib3mf): 文件={} 对象序号={} 资源ID={} 名称={} 顶点={} 面={} 流形且定向={}",
            path.name, idx, rid, name, v_count, t_count, is_manifold
        )


def analyze_3mf_bambu_cli(path: Path) -> None:
    """使用 Bambu Studio CLI 分析 3MF 文件

    调用 Bambu Studio 命令行工具进行切片分析，
    检测非流形几何等潜在问题

    Args:
        path: 3MF 文件路径
    """
    bambu_path = _get_bambu_studio_path()
    if not bambu_path:
        logger.info("3MF分析(Bambu CLI)未配置路径")
        return
    exe_path = Path(bambu_path)
    if not exe_path.exists():
        logger.warning("3MF分析(Bambu CLI)路径无效: {}", exe_path)
        return
    if not path.exists():
        logger.warning("3MF分析(Bambu CLI)失败，文件不存在: {}", path)
        return
    out_dir = path.parent / "_bambu_cli"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_3mf = out_dir / f"{path.stem}_sliced.3mf"
    cmd = [
        str(exe_path),
        "--slice",
        "0",
        "--debug",
        "2",
        "--uptodate",
        "--export-3mf",
        str(out_3mf),
        "--outputdir",
        str(out_dir),
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as e:
        logger.error("3MF分析(Bambu CLI)执行失败: {}", e)
        return
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    keywords = ["non-manifold", "non manifold", "非流形", "11695"]
    hits: List[str] = []
    for line in out.splitlines():
        low = line.lower()
        if any(k in low for k in keywords):
            hits.append(line)
    logger.info("3MF分析(Bambu CLI): 文件={} 退出码={}", path.name, proc.returncode)
    if hits:
        for line in hits:
            logger.warning("3MF分析(Bambu CLI)命中: {}", line)
    else:
        logger.info("3MF分析(Bambu CLI)未发现非流形关键字")
