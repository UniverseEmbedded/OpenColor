"""灰阶测试模块 - 生成灰阶渐变图并求解最优配方

用于测试颜色模型在灰阶渐变上的表现，生成每层每色的掩码和报告。
"""

import json
import shutil
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image
from oc_proto.calib_color_model_fit.color_space import lab_to_rgb01
from oc_proto.calib_color_model_fit.model_io import load_model

from oc_core_02.core.bitmap_pipeline import BitmapParams
from oc_core_02.core.bitmap_pipeline_sdf import _generate_layer_volumes
from oc_core_02.core.color_systems import ColorSystem
from oc_proto.gen_masks.solver_cpp_wrapper import CPP_AVAILABLE, create_solver


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)


def _rmtree_retry(p: Path, *, tries: int = 8, wait_s: float = 0.2) -> None:
    """带重试的目录删除

    在删除目录时处理可能的权限错误，支持多次重试。

    参数:
        p: 要删除的目录路径
        tries: 重试次数
        wait_s: 每次重试的等待时间（秒）
    """
    for i in range(int(tries)):
        try:
            shutil.rmtree(p)
            return
        except PermissionError as e:
            if i >= int(tries) - 1:
                raise
            logger.error(
                f"警告: 删除目录失败(可能被占用)，将重试 {i + 1}/{tries}: {p}，原因={e}"
            )
            time.sleep(float(wait_s))


def _clear_dir_keep_root(d: Path) -> None:
    """清空目录但保留根目录

    删除目录中的所有内容，如果目录不存在则创建它。

    参数:
        d: 目标目录路径
    """
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
        return
    for child in d.iterdir():
        if child.is_dir():
            _rmtree_retry(child)
        else:
            try:
                child.unlink()
            except PermissionError as e:
                logger.error(f"警告: 删除文件失败(可能被占用): {child}，原因={e}")
                raise


def _find_model_dir(calib_root: Path) -> Path:
    """查找模型目录

    在校准根目录中查找最新的颜色模型目录，优先选择包含"four_flux"的模型。

    参数:
        calib_root: 校准根目录

    返回:
        模型目录路径

    异常:
        FileNotFoundError: 未找到可用模型
    """
    candidates: list[tuple[int, float, Path]] = []
    for meta_path in calib_root.rglob("color_model.json"):
        model_dir = meta_path.parent
        npz_path = model_dir / "phys_gpr_model.npz"
        if not npz_path.exists():
            continue
        try:
            mtime = meta_path.stat().st_mtime
        except Exception as e:
            logger.warning(f"警告: 无法读取模型时间戳: {meta_path}，原因={e}")
            mtime = 0.0
        p = str(model_dir).lower()
        # 优先选择four_flux模型
        prefer_four_flux = 1 if "four_flux" in p else 0
        candidates.append((prefer_four_flux, mtime, model_dir))
    if not candidates:
        raise FileNotFoundError(f"在目录中未找到可用模型: {calib_root}")
    # 按优先级和时间排序
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def _make_gray_ramp_rgba(h: int, w: int) -> np.ndarray:
    """生成灰阶渐变RGBA图像

    创建水平方向的灰阶渐变图，从左到右从黑到白。

    参数:
        h: 图像高度
        w: 图像宽度

    返回:
        RGBA图像数组 (H, W, 4)
    """
    ramp = np.arange(w, dtype=np.uint8)
    gray = np.tile(ramp[None, :], (h, 1))
    rgb = np.stack([gray, gray, gray], axis=-1)
    a = np.full((h, w, 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, a], axis=-1)


def run(out_dir: str | None = None, *, ramp_w: int = 256, ramp_h: int = 64) -> None:
    """运行灰阶测试

    生成灰阶渐变图，使用颜色模型求解最优配方，输出每层每色的掩码和报告。

    参数:
        out_dir: 输出目录，默认为原型目录下的out_gray_test
        ramp_w: 灰阶图宽度（决定灰阶数量）
        ramp_h: 灰阶图高度
    """
    start_wall = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"开始时间: {start_wall}")

    # 定位模型目录
    prototype_dir = Path(__file__).resolve().parent
    calib_root = prototype_dir.parent / "calib_color_model_fit"
    model_dir = _find_model_dir(calib_root)
    logger.info(f"使用模型目录: {model_dir}")

    # 检查C++求解器可用性
    if not CPP_AVAILABLE:
        raise RuntimeError(
            "当前环境无法导入 opencolor_solver.pyd，无法按要求使用C++求解器"
        )

    # 加载模型和创建求解器
    model = load_model(model_dir)
    solver = create_solver(model, use_cpp=True, force_cpp=True)

    # 创建颜色系统
    cs = ColorSystem.from_material_keys(
        name="DynamicModelSystem",
        keys=model.optical.material_keys,
    )

    n_layers = int(model.optical.n_layers)
    if n_layers != 5:
        logger.warning(f"警告: 当前模型层数为 {n_layers}，不是 5。仍将按模型层数输出。")

    # 准备输出目录
    if out_dir is None:
        out_path = prototype_dir / "out_gray_test"
    else:
        out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    _clear_dir_keep_root(out_path)

    # 创建子目录
    input_dir = out_path / "00_input"
    preview_dir = out_path / "01_preview"
    mask_dir = out_path / "02_masks"
    layer_viz_dir = out_path / "04_layer_solved_palette"
    for d in [input_dir, preview_dir, mask_dir, layer_viz_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 设置位图参数
    params = BitmapParams()
    params.n_layers = n_layers
    params.auto_bg_remove = False

    # 生成并保存灰阶图
    rgba_u8 = _make_gray_ramp_rgba(int(ramp_h), int(ramp_w))
    input_png = input_dir / f"gray_ramp_{ramp_w}x{ramp_h}.png"
    Image.fromarray(rgba_u8).save(input_png)
    logger.info(f"已保存输入灰阶图: {input_png}")

    # 准备像素数据
    rgb01 = rgba_u8[..., :3].astype(np.float32) / 255.0
    pix = rgb01.reshape(-1, 3)
    # 去重以加速求解
    unique_pix, inverse = np.unique(pix, axis=0, return_inverse=True)
    logger.info(
        f"待求解像素总数={int(pix.shape[0])}，唯一颜色数={int(unique_pix.shape[0])}"
    )

    # 求解最优配方
    logger.info("开始求解 0~255 灰阶对应的最优配方...")
    t0 = time.time()
    unique_recipe_indices_solved = solver.solve(unique_pix)
    t1 = time.time()
    logger.info(f"求解完成，用时 {t1 - t0:.3f} 秒")

    # 反转层序（从底层到顶层）
    unique_recipe_indices_print = unique_recipe_indices_solved[:, ::-1].copy()
    idxs = inverse
    recipe_digits = unique_recipe_indices_print

    # 生成正面预测预览图
    logger.info("生成叠色预测预览图(正面/反面)...")
    predicted_labs = solver._predict_batch(unique_recipe_indices_solved)
    predicted_rgbs = lab_to_rgb01(predicted_labs)
    full_predicted_rgbs = predicted_rgbs[inverse].reshape(int(ramp_h), int(ramp_w), 3)
    front_u8 = np.clip(full_predicted_rgbs * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(front_u8).save(preview_dir / "01_preview_predicted_front.png")

    # 生成反面预测预览图
    predicted_labs_back = solver._predict_batch(unique_recipe_indices_print)
    predicted_rgbs_back = lab_to_rgb01(predicted_labs_back)
    full_back_rgbs = predicted_rgbs_back[inverse].reshape(int(ramp_h), int(ramp_w), 3)
    back_u8 = np.clip(full_back_rgbs * 255.0 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(back_u8).save(preview_dir / "01_preview_predicted_back.png")

    # 生成每层调色板预览图
    rgb_lut = np.asarray(
        [cs.slot_preview_rgb[n] for n in cs.slot_names], dtype=np.uint8
    )
    logger.info("生成每层 8 色分配预览图...")
    for z in range(n_layers):
        digits_z = (
            recipe_digits[idxs, int(z)]
            .reshape(int(ramp_h), int(ramp_w))
            .astype(np.int32, copy=False)
        )
        img = rgb_lut[digits_z]
        Image.fromarray(img).save(layer_viz_dir / f"L{z:02d}_solved_palette.png")

    # 生成体素体积数据
    ys, xs = np.indices((int(ramp_h), int(ramp_w)))
    ys = ys.reshape(-1)
    xs = xs.reshape(-1)
    volumes = _generate_layer_volumes(
        params, cs, ys, xs, idxs, int(ramp_h), int(ramp_w), recipe_digits=recipe_digits
    )
    full_mask = np.ones((int(ramp_h), int(ramp_w)), dtype=bool)

    # 导出每层每色掩码
    logger.info("导出每层每色 mask...")
    for z in range(n_layers):
        for slot_name in cs.slot_names:
            mask = volumes[slot_name][z]
            if int(np.count_nonzero(mask)) == 0:
                continue
            prefix = f"L{z:02d}_{slot_name}"
            Image.fromarray((mask.astype(np.uint8) * 255)).save(
                mask_dir / f"{prefix}_mask.png"
            )

    Image.fromarray((full_mask.astype(np.uint8) * 255)).save(mask_dir / "full_mask.png")

    # 准备报告数据
    intensity = np.clip(np.rint(unique_pix[:, 0] * 255.0), 0, 255).astype(np.int32)
    order = np.argsort(intensity)
    intensity_sorted = intensity[order]
    recipe_sorted = unique_recipe_indices_print[order]
    pred_front_sorted = predicted_rgbs[order]
    pred_back_sorted = predicted_rgbs_back[order]

    # 构建报告
    report = {
        "版本": "gen_masks.gray_test",
        "时间": start_wall,
        "模型目录": str(model_dir),
        "层数": int(n_layers),
        "槽位": list(cs.slot_names),
        "灰阶图尺寸": [int(ramp_w), int(ramp_h)],
        "灰阶映射": [],
        "参数": {"bitmap_params": asdict(params)},
    }

    # 填充灰阶映射数据
    for i in range(int(intensity_sorted.shape[0])):
        g = int(intensity_sorted[i])
        digits = recipe_sorted[i].astype(int).tolist()
        front_rgb = (
            np.clip(np.rint(pred_front_sorted[i] * 255.0), 0, 255).astype(int).tolist()
        )
        back_rgb = (
            np.clip(np.rint(pred_back_sorted[i] * 255.0), 0, 255).astype(int).tolist()
        )
        report["灰阶映射"].append(
            {
                "gray": g,
                "layer_digits": digits,
                "layer_slot_names": [cs.slot_names[int(d)] for d in digits],
                "predicted_front_rgb": front_rgb,
                "predicted_back_rgb": back_rgb,
            }
        )

    # 保存报告
    (out_path / "gray_test_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"已写出报告: {out_path / 'gray_test_report.json'}")
    logger.info(f"完成。输出目录: {out_path}")


if __name__ == "__main__":
    try:
        run(
            out_dir=r"D:\pama1234\pfp\p-2026-01\OpenColor-02\py_module\prototypes\src\oc_proto\gen_masks\out_gray_test",
            ramp_w=256,
            ramp_h=64,
        )
    except Exception as e:
        logger.error(f"执行失败: {e}")
        traceback.print_exc()
        raise
