"""SDF 导出模块 - 处理网格导出和 3MF 导出

本模块提供 SDF（有符号距离场）处理后的网格导出功能，
包括层合并、网格清理、STL 导出和通用 3MF 导出。
"""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Any, Tuple

import numpy as np
import trimesh

from oc_core_02.core.color_systems import ColorSystem
from oc_core_02.core.mesh_export import export_stl
from oc_core_02.core.model_analysis import analyze_mesh
from .sdf_mesh import clean_mesh


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def finalize_slot_mesh(
    slot_name: str,
    layer_meshes: List[trimesh.Trimesh],
    cs: ColorSystem,
    out_dir: Path,
    mesh_report: Dict[str, Any],
    *,
    use_cpp_union: bool = False,
) -> Tuple[trimesh.Trimesh, Path]:
    """完成槽位网格处理并导出 STL

    合并层网格，可选使用 C++ 布尔运算去除内部面，
    清理网格，分析质量，并导出为 STL 文件

    Args:
        slot_name: 槽位名称（如 "R", "G", "B", "W"）
        layer_meshes: 层网格列表
        cs: 颜色系统对象
        out_dir: 输出目录
        mesh_report: 网格报告字典，用于记录分析结果
        use_cpp_union: 是否使用 C++ 布尔运算合并网格

    Returns:
        清理后的网格对象和 STL 文件路径的元组

    Raises:
        RuntimeError: 当网格处理失败时抛出
    """
    t0 = perf_counter()
    logger.info(
        f"[进度] finalize_slot_mesh({slot_name}): 开始合并 {len(layer_meshes)} 个网格..."
    )
    # 合并所有层网格
    if not layer_meshes:
        full_mesh = trimesh.Trimesh(
            vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64)
        )
    else:
        full_mesh = trimesh.util.concatenate(layer_meshes)
    t_merge = perf_counter()
    logger.info(
        f"[进度] finalize_slot_mesh({slot_name}): 网格合并完成，顶点={len(full_mesh.vertices)}, 面={len(full_mesh.faces)}, 用时={t_merge - t0:.3f}s"
    )

    # 使用 C++ 布尔运算去除层间内部面
    if bool(use_cpp_union) and len(layer_meshes) >= 2:
        import opencolor_geometry as cpp_geometry

        union_fn = getattr(cpp_geometry, "manifold_union_nogil", None) or getattr(
            cpp_geometry, "manifold_union", None
        )
        if union_fn is None:
            raise RuntimeError("C++ 几何模块缺少 manifold_union(_nogil)")

        mesh_report.setdefault(slot_name, {})

        cpp_meshes: list[tuple[np.ndarray, np.ndarray]] = []
        cpp_mesh_src: list[trimesh.Trimesh] = []
        watertight_flags: list[bool] = []

        for m in layer_meshes:
            if m is None or bool(getattr(m, "is_empty", False)):
                continue
            if (
                getattr(m, "vertices", None) is None
                or getattr(m, "faces", None) is None
            ):
                continue
            if int(getattr(m.faces, "shape", [0])[0]) <= 0:
                continue
            v = np.ascontiguousarray(np.asarray(m.vertices, dtype=np.float64))
            f = np.ascontiguousarray(np.asarray(m.faces, dtype=np.int64))
            cpp_meshes.append((v, f))
            cpp_mesh_src.append(m)
            try:
                watertight_flags.append(bool(getattr(m, "is_watertight", False)))
            except Exception as e:
                logger.error(
                    "[错误] 计算 watertight 失败，将按非封闭处理: slot={}, 原因={} ",
                    slot_name,
                    e,
                )
                watertight_flags.append(False)

        watertight_count = int(sum(1 for x in watertight_flags if x))
        mesh_report[slot_name]["cpp_union_input_meshes"] = int(len(cpp_meshes))
        mesh_report[slot_name]["cpp_union_input_watertight_meshes"] = int(
            watertight_count
        )

        if len(cpp_meshes) >= 2:
            logger.info(
                "[信息] 3D 并集：开始去除层间内部面: slot={}, 输入网格数={} (watertight={}/{})",
                slot_name,
                len(cpp_meshes),
                watertight_count,
                len(cpp_meshes),
            )
            t_u0 = perf_counter()
            try:
                u_v, u_f = union_fn(cpp_meshes)
            except Exception as e:
                mesh_report[slot_name]["cpp_union_error"] = str(e)
                logger.error("[错误] 3D 并集失败: slot={}, 原因={}", slot_name, e)

                msg = str(e)
                m_idx = re.search(r"第\s*(\d+)\s*个输入网格", msg)
                if m_idx is not None:
                    try:
                        fail_local_idx = int(m_idx.group(1))
                        fail_mesh = (
                            cpp_mesh_src[fail_local_idx]
                            if 0 <= fail_local_idx < len(cpp_mesh_src)
                            else None
                        )
                        if fail_mesh is not None:
                            debug_path = (
                                out_dir
                                / f"debug_union_fail_{slot_name}_idx{fail_local_idx}.stl"
                            )
                            export_stl(fail_mesh, debug_path)
                            logger.error(
                                "[错误] 已导出失败输入网格用于排查: slot={}, idx={}, path={}",
                                slot_name,
                                fail_local_idx,
                                debug_path.name,
                            )
                    except Exception as dump_e:
                        logger.error(
                            "[错误] 导出失败输入网格也失败: slot={}, 原因={}",
                            slot_name,
                            dump_e,
                        )

                raise RuntimeError(f"3D 并集失败: slot={slot_name}, 原因={e}") from e
            t_u1 = perf_counter()

            out_faces = int(getattr(u_f, "shape", [0])[0])
            if out_faces <= 0 and int(getattr(full_mesh.faces, "shape", [0])[0]) > 0:
                raise RuntimeError("3D 并集返回空网格")
            full_mesh = trimesh.Trimesh(vertices=u_v, faces=u_f, process=False)
            logger.info(
                f"[信息] 3D 并集：完成: slot={slot_name}, faces={out_faces}, 用时={t_u1 - t_u0:.3f}s"
            )

    # 分析清理前的网格
    logger.info(f"[进度] finalize_slot_mesh({slot_name}): 开始分析清理前网格...")
    mesh_report.setdefault(slot_name, {})
    t_analyze_before0 = perf_counter()
    try:
        mesh_report[slot_name]["before_clean"] = analyze_mesh(
            full_mesh, f"SDF/{cs.name}/{slot_name}/清理前"
        )
        mesh_report[slot_name]["before_watertight"] = bool(
            mesh_report[slot_name]["before_clean"].get("watertight", 0)
        )
    except Exception as e:
        logger.error("[错误] 清理前分析失败({}): {}", slot_name, e)
        raise
    t_analyze_before1 = perf_counter()
    logger.info(
        f"[进度] finalize_slot_mesh({slot_name}): 清理前分析完成，watertight={mesh_report[slot_name]['before_watertight']}, 用时={t_analyze_before1 - t_analyze_before0:.3f}s"
    )

    t_before = perf_counter()

    # 清理网格
    logger.info(f"[进度] finalize_slot_mesh({slot_name}): 开始清理网格...")
    t_clean0 = perf_counter()
    try:
        cleaned_mesh = clean_mesh(full_mesh, slot_name)
    except Exception as e:
        logger.error("[错误] 网格清理失败({}): {}", slot_name, e)
        raise
    t_clean1 = perf_counter()
    logger.info(
        f"[进度] finalize_slot_mesh({slot_name}): 网格清理完成，顶点={len(cleaned_mesh.vertices)}, 面={len(cleaned_mesh.faces)}, 用时={t_clean1 - t_clean0:.3f}s"
    )

    t_clean = perf_counter()

    # 分析清理后的网格
    logger.info(f"[进度] finalize_slot_mesh({slot_name}): 开始分析清理后网格...")
    t_analyze_after0 = perf_counter()
    try:
        mesh_report[slot_name]["after_clean"] = analyze_mesh(
            cleaned_mesh, f"SDF/{cs.name}/{slot_name}/清理后"
        )
        mesh_report[slot_name]["after_watertight"] = bool(
            mesh_report[slot_name]["after_clean"].get("watertight", 0)
        )
    except Exception as e:
        logger.error("[错误] 清理后分析失败({}): {}", slot_name, e)
        raise
    t_analyze_after1 = perf_counter()
    logger.info(
        f"[进度] finalize_slot_mesh({slot_name}): 清理后分析完成，watertight={mesh_report[slot_name]['after_watertight']}, 用时={t_analyze_after1 - t_analyze_after0:.3f}s"
    )

    t_after = perf_counter()

    # 导出 STL
    logger.info(f"[进度] finalize_slot_mesh({slot_name}): 开始导出STL...")
    t_export0 = perf_counter()
    stl_path = out_dir / f"model_{cs.name}_{slot_name}.stl"
    export_stl(cleaned_mesh, stl_path)
    t_export1 = perf_counter()
    logger.info(
        f"[进度] finalize_slot_mesh({slot_name}): STL导出完成，路径={stl_path.name}, 用时={t_export1 - t_export0:.3f}s"
    )

    t_export = perf_counter()

    logger.info(
        f"[信息] 槽位网格处理完成: slot={slot_name} | 合并={t_merge - t0:.3f}s, 分析前={t_analyze_before1 - t_analyze_before0:.3f}s, 清理={t_clean1 - t_clean0:.3f}s, 分析后={t_analyze_after1 - t_analyze_after0:.3f}s, 导出={t_export1 - t_export0:.3f}s, 总计={t_export - t0:.3f}s"
    )
    return cleaned_mesh, stl_path


def export_3mf_generic(
    out_3mf: Path,
    slot_meshes: Dict[str, trimesh.Trimesh],
    slot_preview_rgb: Dict[str, Tuple[int, int, int]],
) -> Path | None:
    """导出通用 3MF 文件

    将多个槽位的网格导出为标准的 3MF 格式文件，支持多颜色/多材质

    Args:
        out_3mf: 输出 3MF 文件路径
        slot_meshes: 槽位名称到网格的字典
        slot_preview_rgb: 槽位名称到 RGB 颜色的字典

    Returns:
        导出的 3MF 文件路径，如果导出失败则返回 None
    """
    if not slot_meshes:
        logger.warning("没有网格可导出到 3MF")
        return None

    try:
        # 使用 trimesh 导出 3MF
        import trimesh

        # 创建场景并添加网格
        scene = trimesh.Scene()

        for slot_name, mesh in slot_meshes.items():
            if mesh is None or len(mesh.vertices) == 0:
                continue

            # 创建网格的副本以避免修改原始数据
            mesh_copy = mesh.copy()

            # 设置网格名称
            mesh_copy.name = slot_name

            # 添加到场景
            scene.add_geometry(mesh_copy, node_name=slot_name, geom_name=slot_name)

        if len(scene.geometry) == 0:
            logger.warning("场景为空，无法导出 3MF")
            return None

        # 导出为 3MF
        scene.export(str(out_3mf))

        if out_3mf.exists():
            logger.info(f"3MF 导出成功: {out_3mf}")
            return out_3mf
        else:
            logger.error("3MF 导出失败: 文件未生成")
            return None

    except Exception as e:
        logger.error("导出 3MF 失败: {}", e)
        return None
