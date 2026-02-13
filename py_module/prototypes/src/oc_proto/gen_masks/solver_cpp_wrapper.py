"""
C++ HillClimbingSolver 包装器
提供与Python版本完全相同的接口，但内部使用C++加速
"""

import numpy as np

from oc_core_02.utils.bin_loader import import_cpp_extension
from oc_core_02.utils.logger import get_logger
from oc_proto.gen_masks.solver import HillClimbingSolver, HillClimbingSolverML

logger = get_logger(__name__)

# 尝试导入C++模块
opencolor_solver = None
CPP_AVAILABLE = False
try:
    opencolor_solver = import_cpp_extension("opencolor_solver")
    CPP_AVAILABLE = True
    try:
        logger.info("已加载 C++求解器模块: {}", opencolor_solver.__file__)
    except Exception:
        logger.info("已加载 C++求解器模块，但无法获取模块路径")
except Exception as e:
    CPP_AVAILABLE = False
    logger.warning("C++求解器模块不可用，将回退到Python实现: {}", e)


class HillClimbingSolverCpp:
    """C++加速的HillClimbingSolver包装器"""

    def __init__(self, model, *, use_vulkan: bool = True):
        """
        初始化求解器

        Args:
            model: Python PhysGPRModel 对象
        """
        if not CPP_AVAILABLE:
            raise RuntimeError("C++求解器模块不可用")

        self.model = model
        self.material_keys = model.optical.material_keys
        self.n_layers = model.optical.n_layers
        self.m = len(self.material_keys)

        # 转换模型数据为C++格式
        optical_dict = self._convert_optical(model.optical)
        gpr_L_dict = self._convert_gpr(model.gpr_L)
        gpr_a_dict = self._convert_gpr(model.gpr_a)
        gpr_b_dict = self._convert_gpr(model.gpr_b)

        self.use_vulkan = bool(use_vulkan)

        self._solver = opencolor_solver.HillClimbingSolver(
            optical_dict,
            gpr_L_dict,
            gpr_a_dict,
            gpr_b_dict,
            model.feature_names,
            n_random_samples=1000,
            hill_climb_iterations=10,
            n_layers=self.n_layers,
            layer_names_order="bottom_first",
            use_vulkan=self.use_vulkan,
        )

    def _convert_optical(self, optical):
        """转换光学参数"""
        out = {
            "mu_a": optical.mu_a.astype(np.float32),
            "mu_s": optical.mu_s.astype(np.float32),
            "g": optical.g.astype(np.float32),
            "n_layers": optical.n_layers,
            "k1": float(optical.k1),
            "k2": float(optical.k2),
            "backing": float(optical.backing),
            "material_keys": optical.material_keys,
        }

        alpha = getattr(optical, "alpha", None)
        beta = getattr(optical, "beta", None)
        gamma = getattr(optical, "gamma", None)
        if alpha is not None and beta is not None and gamma is not None:
            alpha = np.asarray(alpha, dtype=np.float32)
            beta = np.asarray(beta, dtype=np.float32)
            gamma = np.asarray(gamma, dtype=np.float32)
            if alpha.size > 0 and beta.size > 0 and gamma.size > 0:
                out["alpha"] = alpha
                out["beta"] = beta
                out["gamma"] = gamma

        return out

    def _convert_gpr(self, gpr):
        """转换GPR参数"""
        return {
            "X_train": gpr.X_train.astype(np.float32),
            "alpha": gpr.alpha.astype(np.float32),
            "x_mean": gpr.x_mean.astype(np.float32),
            "x_std": gpr.x_std.astype(np.float32),
            "y_mean": float(gpr.y_mean),
            "y_std": float(gpr.y_std),
            "lengthscale": float(gpr.lengthscale),
            "signal_var": float(gpr.signal_var),
            "noise": float(gpr.noise),
        }

    def _predict_batch(self, recipe_indices_list):
        """批量预测配方颜色（Lab）"""
        # C++求解器返回Lab颜色
        result = self._solver.predict_batch(recipe_indices_list.astype(np.int32))
        return result.astype(np.float32)

    def solve(self, target_rgb_list, n_random_samples=1000):
        """
        为一组RGB颜色实时求解最优配方

        Args:
            target_rgb_list: (N, 3) 0..1 float numpy数组
            n_random_samples: 随机采样数量（C++版本忽略此参数，使用构造时的值）

        Returns:
            (N, n_layers) int32 numpy数组，表示每层的材料索引
        """
        n_targets = len(target_rgb_list)
        if n_targets == 0:
            return np.zeros((0, self.n_layers), dtype=np.int32)

        # 确保输入是float32
        target_rgb = target_rgb_list.astype(np.float32)

        # 调用C++求解器
        result = self._solver.solve(target_rgb)

        return result.astype(np.int32)


def create_solver(
    model, use_cpp=True, force_cpp: bool = False, *, prefer_vulkan: bool = True
):
    """
    创建求解器工厂函数

    Args:
        model: Python PhysGPRModel 对象
        use_cpp: 是否尝试使用C++加速

    Returns:
        HillClimbingSolverCpp 或 Python HillClimbingSolver
    """
    if hasattr(model, "model_L") and hasattr(model, "model_a") and hasattr(model, "model_b"):
        logger.info("[信息] 已检测到ML残差模型，使用Python求解器")
        return HillClimbingSolverML(model)

    if force_cpp and not CPP_AVAILABLE:
        raise RuntimeError("已要求强制使用C++求解器，但当前无法导入 opencolor_solver")

    if use_cpp and CPP_AVAILABLE:
        try:
            alpha = getattr(getattr(model, "optical", None), "alpha", None)
            beta = getattr(getattr(model, "optical", None), "beta", None)
            gamma = getattr(getattr(model, "optical", None), "gamma", None)
            has_rts = (alpha is not None) and (beta is not None) and (gamma is not None)

            if prefer_vulkan:
                if has_rts:
                    logger.info("[信息] 尝试启用 Vulkan(GPU) 路径进行求解")
                else:
                    logger.info(
                        "[信息] 尝试启用 Vulkan(GPU) 路径进行求解（仅用于GPR加速，物理预测走CPU）"
                    )
                cpp_solver = HillClimbingSolverCpp(model, use_vulkan=True)
                # Vulkan失败直接报错，不回退到CPU
            else:
                cpp_solver = HillClimbingSolverCpp(model, use_vulkan=False)

            return cpp_solver
        except Exception as e:
            raise RuntimeError(f"C++求解器初始化失败: {e}")

    logger.info("[信息] 使用Python求解器")
    return HillClimbingSolver(model)


# 测试函数
def test_cpp_solver():
    """测试C++求解器是否可用"""
    if not CPP_AVAILABLE:
        logger.info("C++求解器模块不可用")
        return False

    try:
        result = opencolor_solver.ping()
        logger.info(f"C++求解器测试: {result}")
        return True
    except Exception as e:
        logger.error(f"C++求解器测试失败: {e}")
        return False


if __name__ == "__main__":
    test_cpp_solver()
