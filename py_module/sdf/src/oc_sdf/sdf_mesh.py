from __future__ import annotations

from time import perf_counter

import numpy as np
import trimesh

from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)

# C++ 网格清理模块导入状态标志
_CPP_MESH_CLEAN_IMPORT_TRIED = False
# C++ 网格清理函数引用
_CPP_MESH_CLEAN = None


def _get_cpp_mesh_clean_basic():
    """获取 C++ 实现的网格清理函数。

    尝试导入 opencolor_geometry 模块中的 mesh_clean_basic_nogil 函数，
    如果导入失败则返回 None，后续将使用 Python 实现的清理逻辑。

    Returns:
        callable 或 None: C++ 网格清理函数，导入失败时返回 None
    """
    global _CPP_MESH_CLEAN_IMPORT_TRIED
    global _CPP_MESH_CLEAN

    if _CPP_MESH_CLEAN_IMPORT_TRIED:
        return _CPP_MESH_CLEAN

    _CPP_MESH_CLEAN_IMPORT_TRIED = True
    try:
        import opencolor_geometry as cpp_geometry

        _CPP_MESH_CLEAN = getattr(cpp_geometry, "mesh_clean_basic_nogil", None)
        if _CPP_MESH_CLEAN is None:
            logger.warning("C++ 几何模块已加载，但缺少 mesh_clean_basic_nogil，网格清理将回退到 Python")
        return _CPP_MESH_CLEAN
    except Exception as e:
        logger.warning("导入 C++ 几何模块失败，网格清理将回退到 Python: {}", e)
        import traceback

        traceback.print_exc()
        _CPP_MESH_CLEAN = None
        return None

def clean_mesh(m: trimesh.Trimesh, slot_name: str) -> trimesh.Trimesh:
    """对网格进行保守清理，避免破坏拓扑结构。

    根据排查手册，禁用可能破坏拓扑的操作：
    - 保留：去除 NaN/Inf、删除未引用顶点、去除退化面/重复面
    - 禁用：merge_vertices/weld（可能引入非流形边）
    - 可选：修复法线一致性

    Args:
        m: 输入的 trimesh 网格对象
        slot_name: 槽位名称，用于日志标识

    Returns:
        清理后的 trimesh 网格对象
    """
    t0 = perf_counter()

    # 尝试使用 C++ 实现的网格清理
    cpp_clean = _get_cpp_mesh_clean_basic()
    if cpp_clean is not None:
        try:
            # 准备输入数据：确保数组是连续的，并转换为指定类型
            v_in = np.ascontiguousarray(np.asarray(m.vertices, dtype=np.float64))
            f_in = np.ascontiguousarray(np.asarray(m.faces, dtype=np.int64))
            t_prep = perf_counter()
            # 调用 C++ 清理函数
            v2, f2, rep = cpp_clean(v_in, f_in)
            t_cpp = perf_counter()

            # 使用清理后的顶点和面创建新的网格对象
            out = trimesh.Trimesh(vertices=v2, faces=f2, process=False)
            t_mesh = perf_counter()

            face_n = int(getattr(out.faces, "shape", [0])[0])
            # 优化：只有非封闭网格才需要修复法线，且根据面数动态调整阈值
            if face_n <= 50_000:
                # 小网格：正常修复法线
                if hasattr(out, "fix_normals"):
                    out.fix_normals()
            elif face_n <= 150_000:
                # 中等网格：只在非封闭时修复
                if not out.is_watertight and hasattr(out, "fix_normals"):
                    out.fix_normals()
            else:
                # 大网格：跳过法线修复，依赖C++清理已经处理了法线
                logger.info("网格较大，跳过 fix_normals 以提升性能: slot={}, faces={}", slot_name, face_n)
            t_normals = perf_counter()

            logger.info(
                "网格清理(C++基础清理) 完成: slot={} | {} | 用时={:.3f}s (准备={:.3f}s, C++={:.3f}s, 构网格={:.3f}s, 法线={:.3f}s)",
                slot_name, rep, t_normals - t0, t_prep - t0, t_cpp - t_prep, t_mesh - t_cpp, t_normals - t_mesh
            )
            return out
        except Exception as e:
            logger.error("C++ 网格清理失败，将回退到 Python: slot={}, 原因={}", slot_name, e)
            import traceback

            traceback.print_exc()

    # C++ 清理失败或不可用时，使用 Python 实现的清理逻辑
    try:
        t1 = perf_counter()
        # 去除无穷值（NaN/Inf）
        if hasattr(m, "remove_infinite_values"):
            m.remove_infinite_values()
        t2 = perf_counter()

        # 去除退化面（面积为零或极小的面）
        if hasattr(m, "remove_degenerate_faces"):
            m.remove_degenerate_faces()
        t3 = perf_counter()

        # 去除重复面
        if hasattr(m, "remove_duplicate_faces"):
            m.remove_duplicate_faces()
        t4 = perf_counter()

        # 【排查手册步骤1】禁用merge_vertices，避免焊接破坏拓扑
        # 之前这里使用merge_vertices导致非流形边暴涨
        # try:
        #     if hasattr(m, "merge_vertices"):
        #         m.merge_vertices(radius=1e-7)
        # except Exception:
        #     pass

        # 删除未被任何面引用的顶点
        if hasattr(m, "remove_unreferenced_vertices"):
            m.remove_unreferenced_vertices()
        t5 = perf_counter()

        face_n = int(getattr(getattr(m, "faces", None), "shape", [0])[0])
        # 优化：只有非封闭网格才需要修复法线，且根据面数动态调整阈值
        if face_n <= 50_000:
            # 小网格：正常修复法线
            if hasattr(m, "fix_normals"):
                m.fix_normals()
        elif face_n <= 150_000:
            # 中等网格：只在非封闭时修复
            if not m.is_watertight and hasattr(m, "fix_normals"):
                m.fix_normals()
        else:
            # 大网格：跳过法线修复
            logger.info("网格较大，跳过 fix_normals 以提升性能: slot={}, faces={}", slot_name, face_n)
        t6 = perf_counter()

        logger.info(
            "网格清理(Python) 完成: slot={} | NaN/Inf={:.3f}s, 退化面={:.3f}s, 重复面={:.3f}s, 去未引用点={:.3f}s, 法线={:.3f}s, 总计={:.3f}s",
            slot_name, t2 - t1, t3 - t2, t4 - t3, t5 - t4, t6 - t5, t6 - t0
        )
    except Exception as e:
        logger.error("网格清理失败(slot={}): {}", slot_name, e)
        import traceback

        traceback.print_exc()
    return m
