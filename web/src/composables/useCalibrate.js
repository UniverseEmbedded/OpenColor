import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";

/**
 * 校色界面逻辑组合式函数
 * 负责管理校色过程中的画布交互、点位调整、预览缩放、以及诊断信息的显示
 * 
 * @param {Object} props - 组件属性，包含当前点位、图片路径、诊断数据等
 * @param {Function} emit - 组件事件触发器，用于更新点位数据
 */
export function useCalibrate(props, emit) {
  // 基础显示状态
  const calibrateMode = ref("board"); // 校色模式: board (标靶), card (卡片)
  const probeCellId = ref("");        // 当前探测的格子 ID
  const probeMeasuredRgb = ref("");   // 探测格子的实测 RGB
  const probeSimRgb = ref("");        // 探测格子的模拟 RGB
  const probeError = ref("");         // 探测格子的色差
  const isPreviewFullscreen = ref(false); // 预览是否全屏

  // 画布平移 (Panning) 状态
  const panOffset = ref({ x: 0, y: 0 }); // 当前平移偏移量
  const panStart = ref({ x: 0, y: 0 });  // 平移开始时的鼠标坐标
  const panBase = ref({ x: 0, y: 0 });   // 平移开始时的偏移基准
  const isPanning = ref(false);          // 是否正在平移
  
  // 拖拽手柄 (Handles) 状态
  const isHandleDragging = ref(false);   // 是否正在拖拽校色点
  const activeHandle = ref(-1);          // 当前正在操作的手柄索引 (0-3)

  // Konva 画布相关引用
  const konvaWrapper = ref(null);        // 主画布容器
  const miniKonvaWrapper = ref(null);    // 缩略图画布容器
  const stageSize = ref({ width: 0, height: 0 });     // 主画布尺寸
  const miniStageSize = ref({ width: 0, height: 0 }); // 缩略图画布尺寸
  const overlayImage = ref(null);        // 当前显示的图片对象
  const overlaySize = ref({ width: 1000, height: 1000 }); // 图片原始尺寸 (默认为 1000x1000)
  
  let konvaResizeObserver = null;
  let miniResizeObserver = null;

  /**
   * 解析 props 中的四角点位字符串为数组
   * 格式: [[x,y], [x,y], [x,y], [x,y]]
   */
  const points = computed(() => {
    try {
      return JSON.parse(props.lutCornerPoints || "[[100,100],[900,100],[900,900],[100,900]]");
    } catch (e) {
      return [[100, 100], [900, 100], [900, 900], [100, 900]];
    }
  });

  /**
   * 更新画布容器的实际显示尺寸
   */
  const updateSize = (wrapperRef, sizeRef) => {
    const el = wrapperRef.value;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    sizeRef.value = {
      width: Math.max(0, Math.floor(rect.width)),
      height: Math.max(0, Math.floor(rect.height))
    };
  };

  /**
   * 计算图片在画布中等比缩放后的尺寸
   */
  const fitRect = (stage, img) => {
    const stageW = stage.width || 0;
    const stageH = stage.height || 0;
    const imgW = img.width || 1000;
    const imgH = img.height || 1000;
    if (!stageW || !stageH) return { width: 1000, height: 1000 };
    const scale = Math.min(stageW / imgW, stageH / imgH);
    return { width: imgW * scale, height: imgH * scale };
  };

  // 基础矩形区域计算
  const baseRect = computed(() => fitRect(stageSize.value, overlaySize.value));
  const miniBaseRect = computed(() => fitRect(miniStageSize.value, overlaySize.value));
  
  /**
   * 预览缩放比例，处理非法输入
   */
  const lutScale = computed(() => {
    const v = Number(props.lutPreviewScale || 1);
    if (!Number.isFinite(v) || v <= 0) return 1;
    return v;
  });

  // 画布中心位置计算
  const stageCenter = computed(() => {
    return {
      x: stageSize.value.width / 2 + panOffset.value.x,
      y: stageSize.value.height / 2 + panOffset.value.y
    };
  });

  const miniStageCenter = computed(() => {
    return {
      x: miniStageSize.value.width / 2,
      y: miniStageSize.value.height / 2
    };
  });

  /**
   * 将 0-1000 坐标系的点映射到画布矩形坐标系
   */
  const mapPointToRect = (point, rect) => {
    const w = rect.width || 1;
    const h = rect.height || 1;
    return {
      x: (point[0] / 1000 - 0.5) * w,
      y: (point[1] / 1000 - 0.5) * h
    };
  };

  /**
   * 将画布矩形坐标系的点反向映射回 0-1000 坐标系
   */
  const mapPointFromRect = (pos, rect) => {
    const w = rect.width || 1;
    const h = rect.height || 1;
    let x = ((pos.x / w) + 0.5) * 1000;
    let y = ((pos.y / h) + 0.5) * 1000;
    x = Math.max(0, Math.min(1000, x));
    y = Math.max(0, Math.min(1000, y));
    return [x, y];
  };

  // 图片在画布中的边界矩形
  const imageRect = computed(() => {
    return {
      x: -baseRect.value.width / 2,
      y: -baseRect.value.height / 2,
      width: baseRect.value.width,
      height: baseRect.value.height
    };
  });

  const miniImageRect = computed(() => {
    return {
      x: -miniBaseRect.value.width / 2,
      y: -miniBaseRect.value.height / 2,
      width: miniBaseRect.value.width,
      height: miniBaseRect.value.height
    };
  });

  // 映射后的点位数组
  const mappedPoints = computed(() => points.value.map((p) => mapPointToRect(p, baseRect.value)));
  // eslint-disable-next-line no-unused-vars
  const mappedPointsMini = computed(() => points.value.map((p) => mapPointToRect(p, miniBaseRect.value)));

  /**
   * 四边形连线的点坐标数组 (闭合路径)
   */
  const quadLinePoints = computed(() => {
    const pts = mappedPoints.value;
    if (pts.length < 4) return [];
    return [
      pts[0].x, pts[0].y,
      pts[1].x, pts[1].y,
      pts[2].x, pts[2].y,
      pts[3].x, pts[3].y,
      pts[0].x, pts[0].y
    ];
  });

  /**
   * 双线性插值计算四边形内的坐标
   * @param {Array} quad - 四个顶点的数组
   * @param {Array} uv - 归一化坐标 [u, v]
   */
  const toCanvasPoint = (quad, uv) => {
    const [u, v] = uv;
    const [p00, p10, p11, p01] = quad;
    const x = (1 - u) * (1 - v) * p00[0] + u * (1 - v) * p10[0] + u * v * p11[0] + (1 - u) * v * p01[0];
    const y = (1 - u) * (1 - v) * p00[1] + u * (1 - v) * p10[1] + u * v * p11[1] + (1 - u) * v * p01[1];
    return [x, y];
  };

  const diagnosticsMap = computed(() => {
    if (!props.mcrtDiagnostics) return {};
    return props.mcrtDiagnostics;
  });

  /**
   * 计算诊断数据的误差阈值 (用于可视化着色)
   */
  const diagnosticsErrors = computed(() => {
    const values = Object.values(diagnosticsMap.value || {});
    const errors = values.map((item) => Number(item?.error)).filter((v) => Number.isFinite(v));
    if (errors.length === 0) return { threshold: 0, max: 0 };
    const sorted = [...errors].sort((a, b) => a - b);
    const idx = Math.floor(sorted.length * 0.8);
    const threshold = sorted[Math.min(idx, sorted.length - 1)];
    const max = sorted[sorted.length - 1];
    return { threshold, max };
  });

  /**
   * 生成诊断信息标记列表
   * 将每个格子的误差映射为画布上的带颜色的圆点
   */
  const diagnosticsList = computed(() => {
    const list = [];
    const totalRows = Number(props.gridRows || props.boardSpecRows || 0);
    const totalCols = Number(props.gridCols || props.boardSpecCols || 0);
    const diagKeys = Object.keys(diagnosticsMap.value || {});

    if (totalRows <= 0 || totalCols <= 0 || diagKeys.length === 0) return list;

    const { threshold, max } = diagnosticsErrors.value;
    const quad = points.value;

    diagKeys.forEach((key) => {
      const parts = key.split(",");
      if (parts.length < 2) return;
      const r = Number(parts[0]);
      const c = Number(parts[1]);
      if (!Number.isFinite(r) || !Number.isFinite(c)) return;

      const u = (c + 0.5) / totalCols;
      const v = (r + 0.5) / totalRows;
      if (u < 0 || u > 1 || v < 0 || v > 1) return;

      const [x, y] = toCanvasPoint(quad, [u, v]);
      const err = Number(diagnosticsMap.value[key]?.error || 0);
      if (!Number.isFinite(err)) return;

      const alpha = max > 0 ? Math.min(0.9, 0.2 + (err / max) * 0.7) : 0.4;
      if (err >= threshold) {
        list.push({
          key,
          x, y,
          color: `rgba(255, 80, 80, ${alpha})`
        });
      }
    });
    return list;
  });

  /**
   * 当前探测器的画布坐标位置
   */
  const probePos = computed(() => {
    const totalRows = Number(props.gridRows || props.boardSpecRows || 0);
    const totalCols = Number(props.gridCols || props.boardSpecCols || 0);
    if (!probeCellId.value || totalRows <= 0 || totalCols <= 0) return null;

    const parts = probeCellId.value.split(",");
    if (parts.length < 2) return null;

    const r = Number(parts[0]);
    const c = Number(parts[1]);
    if (!Number.isFinite(r) || !Number.isFinite(c)) return null;

    const u = (c + 0.5) / totalCols;
    const v = (r + 0.5) / totalRows;
    const [x, y] = toCanvasPoint(points.value, [u, v]);
    return { x, y };
  });

  // 映射后的诊断标记位置
  const mappedDiagnostics = computed(() => {
    return diagnosticsList.value.map((diag) => {
      const pos = mapPointToRect([diag.x, diag.y], baseRect.value);
      return { ...diag, x: pos.x, y: pos.y };
    });
  });

  const mappedDiagnosticsMini = computed(() => {
    return diagnosticsList.value.map((diag) => {
      const pos = mapPointToRect([diag.x, diag.y], miniBaseRect.value);
      return { ...diag, x: pos.x, y: pos.y };
    });
  });

  // 映射后的探测器位置
  const mappedProbePos = computed(() => {
    if (!probePos.value) return null;
    return mapPointToRect([probePos.value.x, probePos.value.y], baseRect.value);
  });

  const mcrtDiagnosticsText = computed(() => {
    if (!props.mcrtDiagnostics || Object.keys(props.mcrtDiagnostics).length === 0) return "";
    try {
      return JSON.stringify(props.mcrtDiagnostics, null, 2);
    } catch (e) {
      return "";
    }
  });

  /**
   * 更新特定格子的探测结果
   * @param {string} cellId - 格子坐标字符串 "r,c"
   */
  const updateProbeResult = (cellId) => {
    if (!cellId) {
      probeCellId.value = "";
      probeMeasuredRgb.value = "";
      probeSimRgb.value = "";
      probeError.value = "";
      return;
    }
    probeCellId.value = cellId;
    const info = diagnosticsMap.value?.[cellId];
    if (!info) {
      probeMeasuredRgb.value = "";
      probeSimRgb.value = "";
      probeError.value = "";
      return;
    }
    const measured = Array.isArray(info.measured_rgb) ? info.measured_rgb.map((v) => Number(v).toFixed(3)).join(", ") : "";
    const sim = Array.isArray(info.sim_rgb) ? info.sim_rgb.map((v) => Number(v).toFixed(3)).join(", ") : "";
    const err = Number.isFinite(Number(info.error)) ? Number(info.error).toFixed(4) : "";
    probeMeasuredRgb.value = measured;
    probeSimRgb.value = sim;
    probeError.value = err;
  };

  /**
   * 处理手柄拖拽开始
   */
  const handleHandleDragStart = (index) => {
    activeHandle.value = index;
    isHandleDragging.value = true;
  };

  /**
   * 处理手柄拖拽中
   * 将画布坐标实时同步回 props 绑定的点位数据
   */
  const handleHandleDragMove = (index, e) => {
    const rect = baseRect.value;
    if (!rect.width || !rect.height) return;
    const pos = e.target.position();
    const [x, y] = mapPointFromRect(pos, rect);
    const newPoints = [...points.value];
    newPoints[index] = [Math.round(x), Math.round(y)];
    emit('update:lutCornerPoints', JSON.stringify(newPoints));
    const mapped = mapPointToRect(newPoints[index], rect);
    e.target.position(mapped);
  };

  /**
   * 处理手柄拖拽结束
   */
  const handleHandleDragEnd = () => {
    activeHandle.value = -1;
    isHandleDragging.value = false;
  };

  /**
   * 加载校色预览图片
   */
  const loadOverlayImage = (src) => {
    if (!src) {
      overlayImage.value = null;
      return;
    }
    const img = new Image();
    img.onload = () => {
      overlayImage.value = img;
      overlaySize.value = {
        width: img.naturalWidth || img.width || 1000,
        height: img.naturalHeight || img.height || 1000
      };
      updateSize(konvaWrapper, stageSize);
      updateSize(miniKonvaWrapper, miniStageSize);
    };
    img.onerror = () => {
      console.error("预览图片加载失败", src);
      overlayImage.value = null;
    };
    img.src = src;
  };

  /**
   * 开始平移画布
   */
  const startPan = (e) => {
    if (!props.lutOverlaySrc) return;
    if (isHandleDragging.value) return;
    const evt = e?.evt || e;
    if (!evt) return;
    if (evt.button !== undefined && evt.button !== 0) return;
    isPanning.value = true;
    panStart.value = { x: evt.clientX, y: evt.clientY };
    panBase.value = { ...panOffset.value };
    window.addEventListener('pointermove', handlePanMove);
    window.addEventListener('pointerup', stopPan);
  };

  /**
   * 处理平移过程中偏移计算
   */
  const handlePanMove = (e) => {
    if (!isPanning.value) return;
    const dx = e.clientX - panStart.value.x;
    const dy = e.clientY - panStart.value.y;
    panOffset.value = { x: panBase.value.x + dx, y: panBase.value.y + dy };
  };

  /**
   * 停止平移画布
   */
  const stopPan = () => {
    if (!isPanning.value) return;
    isPanning.value = false;
    window.removeEventListener('pointermove', handlePanMove);
    window.removeEventListener('pointerup', stopPan);
  };

  /**
   * 画布点击处理 (排除手柄点击，触发平移)
   */
  const handleStagePointerDown = (event) => {
    if (event.target.getClassName() === 'Circle' && event.target.draggable()) return;
    startPan(event);
  };

  /**
   * 重置预览视图 (位置和缩放)
   */
  const resetPreviewView = () => {
    panOffset.value = { x: 0, y: 0 };
    emit('resetLutPreviewScale');
  };

  /**
   * 切换全屏预览
   */
  const togglePreviewFullscreen = () => {
    isPreviewFullscreen.value = !isPreviewFullscreen.value;
    if (!isPreviewFullscreen.value) {
      resetPreviewView();
    }
  };

  // 监听预览图源变化
  watch(() => props.lutOverlaySrc, (val) => {
    loadOverlayImage(val);
  }, { immediate: true });

  // 监听诊断数据或标靶变化，自动更新探测结果
  watch([() => props.mcrtDiagnostics, () => props.gridRows, () => props.gridCols], () => {
    if (probeCellId.value) {
      updateProbeResult(probeCellId.value);
    }
  }, { deep: true });

  onMounted(() => {
    if (konvaWrapper.value) {
      updateSize(konvaWrapper, stageSize);
      konvaResizeObserver = new ResizeObserver(() => updateSize(konvaWrapper, stageSize));
      konvaResizeObserver.observe(konvaWrapper.value);
    }
    if (miniKonvaWrapper.value) {
      updateSize(miniKonvaWrapper, miniStageSize);
      miniResizeObserver = new ResizeObserver(() => updateSize(miniKonvaWrapper, miniStageSize));
      miniResizeObserver.observe(miniKonvaWrapper.value);
    }
  });

  onBeforeUnmount(() => {
    if (konvaResizeObserver) konvaResizeObserver.disconnect();
    if (miniResizeObserver) miniResizeObserver.disconnect();
    stopPan();
  });

  return {
    calibrateMode,
    probeCellId,
    probeMeasuredRgb,
    probeSimRgb,
    probeError,
    isPreviewFullscreen,
    panOffset,
    activeHandle,
    konvaWrapper,
    miniKonvaWrapper,
    stageSize,
    miniStageSize,
    overlayImage,
    lutScale,
    stageCenter,
    miniStageCenter,
    imageRect,
    miniImageRect,
    mappedPoints,
    quadLinePoints,
    mappedDiagnostics,
    mappedDiagnosticsMini,
    mappedProbePos,
    diagnosticsList,
    mcrtDiagnosticsText,
    updateProbeResult,
    handleHandleDragStart,
    handleHandleDragMove,
    handleHandleDragEnd,
    handleStagePointerDown,
    resetPreviewView,
    togglePreviewFullscreen
  };
}
