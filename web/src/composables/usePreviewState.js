import { computed, ref, watch } from "vue";

/**
 * 预览状态管理组合式函数
 * 处理图片预览的数据转换、缩放、平移和对比逻辑
 * 
 * @param {Object} params 参数对象
 * @returns {Object} 预览相关的状态和方法
 */
export const usePreviewState = ({
  t,
  hasTauri,
  invoke,
  inputPath,
  bitmapPreview2dPath,
  lutOverlayPath,
  lutPhotoPath,
  lutWarpedPath
}) => {
  // 输入文件的预览 DataURL
  const inputPreviewDataUrl = ref("");
  // 处理后的预览 DataURL
  const processedPreviewDataUrl = ref("");

  /**
   * 将本地文件路径读取并转换为 DataURL
   * 
   * @param {string} path 文件路径
   * @returns {Promise<string>} DataURL 字符串
   */
  const readFileAsDataUrl = async (path) => {
    if (!path) return "";
    const p = String(path);
    // 如果已经是 data: 开头，直接返回
    if (p.startsWith("data:")) return p;
    // 如果不在 Tauri 环境下，无法读取本地文件
    if (!hasTauri()) return "";
    try {
      const result = await invoke("read_file_base64", { path: p });
      if (!result || !result.data) return "";
      const mime = result.mime || "application/octet-stream";
      return `data:${mime};base64,${result.data}`;
    } catch (e) {
      console.error("读取本地文件失败", e);
      return "";
    }
  };

  const lutOverlayDataUrl = ref("");
  const lutPhotoDataUrl = ref("");
  const lutWarpedDataUrl = ref("");
  const bitmapPreview2dDataUrl = ref("");

  watch(inputPath, async (newVal) => {
    const current = newVal || "";
    const dataUrl = await readFileAsDataUrl(current);
    if (inputPath.value === current) {
      inputPreviewDataUrl.value = dataUrl;
    }
  });

  watch(bitmapPreview2dPath, async (newVal) => {
    const current = newVal || "";
    const dataUrl = await readFileAsDataUrl(current);
    if (bitmapPreview2dPath.value === current) {
      bitmapPreview2dDataUrl.value = dataUrl;
      processedPreviewDataUrl.value = dataUrl;
    }
  });

  watch(lutOverlayPath, async (newVal) => {
    const current = newVal || "";
    const dataUrl = await readFileAsDataUrl(current);
    if (lutOverlayPath.value === current) {
      lutOverlayDataUrl.value = dataUrl;
    }
  });

  watch(lutPhotoPath, async (newVal) => {
    const current = newVal || "";
    const dataUrl = await readFileAsDataUrl(current);
    if (lutPhotoPath.value === current) {
      lutPhotoDataUrl.value = dataUrl;
    }
  });

  watch(lutWarpedPath, async (newVal) => {
    const current = newVal || "";
    const dataUrl = await readFileAsDataUrl(current);
    if (lutWarpedPath.value === current) {
      lutWarpedDataUrl.value = dataUrl;
    }
  });

  const inputPreviewSrc = computed(() => inputPreviewDataUrl.value);
  const processedPreviewSrc = computed(() => processedPreviewDataUrl.value);
  const previewMode = ref("input");
  const previewScale = ref(1);
  const bitmapPreviewScale = ref(1);
  const lutPreviewScale = ref(1);
  const hasProcessedPreview = computed(() => Boolean(processedPreviewSrc.value));
  const previewSrc = computed(() => {
    if (previewMode.value === "processed" && hasProcessedPreview.value) return processedPreviewSrc.value;
    return inputPreviewSrc.value;
  });
  const previewToggleLabel = computed(() => {
    return previewMode.value === "processed" ? t("btn.previewToOriginal") : t("btn.previewToProcessed");
  });
  const togglePreview = () => {
    if (!hasProcessedPreview.value) return;
    previewMode.value = previewMode.value === "processed" ? "input" : "processed";
  };

  const handlePreviewWheel = (event) => {
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    previewScale.value = Math.max(0.1, Math.min(5, previewScale.value + delta));
  };

  const resetPreviewScale = () => {
    previewScale.value = 1;
  };

  const handleBitmapPreviewWheel = (event) => {
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    bitmapPreviewScale.value = Math.max(0.1, Math.min(5, bitmapPreviewScale.value + delta));
  };

  const resetBitmapPreviewScale = () => {
    bitmapPreviewScale.value = 1;
  };

  const handleLutPreviewWheel = (event) => {
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    lutPreviewScale.value = Math.max(0.1, Math.min(5, lutPreviewScale.value + delta));
  };

  const resetLutPreviewScale = () => {
    lutPreviewScale.value = 1;
  };

  const lutOverlaySrc = computed(() => lutOverlayDataUrl.value);
  const lutPhotoSrc = computed(() => lutPhotoDataUrl.value);
  const lutWarpedSrc = computed(() => lutWarpedDataUrl.value);
  const bitmapPreview2dSrc = computed(() => bitmapPreview2dDataUrl.value);

  return {
    inputPreviewDataUrl,
    processedPreviewDataUrl,
    previewScale,
    togglePreview,
    readFileAsDataUrl,
    previewMode,
    bitmapPreviewScale,
    lutPreviewScale,
    hasProcessedPreview,
    previewSrc,
    previewToggleLabel,
    handlePreviewWheel,
    resetPreviewScale,
    handleBitmapPreviewWheel,
    resetBitmapPreviewScale,
    handleLutPreviewWheel,
    resetLutPreviewScale,
    lutOverlaySrc,
    lutPhotoSrc,
    lutWarpedSrc,
    bitmapPreview2dSrc
  };
};
