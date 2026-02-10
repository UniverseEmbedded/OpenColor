import { useTauriBridge } from "./useTauriBridge";
import { useToast } from "./useToast";
import { useI18n } from "vue-i18n";

/**
 * 文件处理逻辑的组合式函数
 * 处理各种导入、导出以及路径选择操作
 * 
 * @param {Object} state 全局状态对象
 * @param {Function} t 国际化翻译函数
 * @param {Function} toastShow 显示提示消息的函数
 * @param {Function} openDialog 打开系统对话框的函数
 * @param {Object} library 资源库管理对象
 * @returns {Object} 包含各种文件处理方法的对象
 */
export const useFileHandlers = (state, t, toastShow, openDialog, library) => {
  /**
   * 设置导入路径
   * 根据指定的类型（svg/png/jpg等）打开对话框让用户选择文件
   * 
   * @param {string} kind 导入类型，如 'svg', 'png'
   */
  const setImported = async (kind) => {
    state.inputKind.value = kind;
    const exts = kind === "svg" ? ["svg"] : ["png", "jpg", "jpeg", "webp"];
    const picked = await openDialog({
      multiple: false,
      filters: [{ name: kind.toUpperCase(), extensions: exts }],
    });
    if (typeof picked === "string" && picked) {
      state.inputPath.value = picked;
      state.previewMode.value = "input";
      // 如果是位图，同时设置位图预览路径
      if (kind === "png") state.bitmapImagePath.value = picked;
      toastShow(t("toast.imported"), picked);
    }
  };

  /**
   * 设置导出路径
   * 打开保存对话框让用户选择导出位置
   */
  const setExported = async () => {
    const picked = await openDialog({
      multiple: false,
      directory: true,
    });
    if (typeof picked === "string" && picked) {
      state.outputPath.value = picked;
      toastShow(t("toast.output_set"), picked);
    }
  };

  /**
   * 选择 LUT 照片
   * 用于从资源库或本地选择用于生成 LUT 的照片
   */
  const pickLutPhoto = async () => {
    const picked = await openDialog({
      multiple: false,
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "webp"] }],
    });
    if (typeof picked === "string" && picked) {
      state.lutPhotoPath.value = picked;
      state.previewMode.value = "lut";
      // 自动尝试导入到资源库
      try {
        await library.importFile(picked, 'image');
        toastShow(t("toast.imported"), picked);
      } catch (e) {
        console.error("导入 LUT 照片到资源库失败:", e);
        toastShow("导入资源库失败", e.message || "未知错误");
      }
    }
  };

  /**
   * 选择校准照片
   * 用于从资源库或本地选择需要进行颜色校准的照片
   */
  const pickCalibrationPhoto = async () => {
    const picked = await openDialog({
      multiple: false,
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "webp"] }],
    });
    if (typeof picked === "string" && picked) {
      state.calibrationPhotoPath.value = picked;
      state.previewMode.value = "calibrate";
      // 自动尝试导入到资源库
      try {
        await library.importFile(picked, 'image');
        toastShow(t("toast.imported"), picked);
      } catch (e) {
        console.error("导入校准照片到资源库失败:", e);
        toastShow("导入资源库失败", e.message || "未知错误");
      }
    }
  };

  return {
    setImported,
    setExported,
    pickLutPhoto,
    pickCalibrationPhoto,
  };
};
