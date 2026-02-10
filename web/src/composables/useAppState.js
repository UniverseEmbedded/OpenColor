import { ref } from "vue";

/**
 * 应用程序全局状态管理组合式函数
 * 包含所有视图状态、用户配置参数、校色数据以及导出任务状态
 */
export const useAppState = () => {
  // 基础视图状态
  const currentView = ref("generate"); // 当前显示的视图页面
  const helpOpen = ref(false);        // 帮助对话框是否打开
  const aboutOpen = ref(false);       // 关于对话框是否打开

  // 输入设置 (SVG/PNG 转换)
  const inputKind = ref("svg");       // 输入类型: svg, png, mixed
  const inputPath = ref("");          // 输入文件或目录路径
  const svgPaletteMode = ref("auto"); // SVG 调色板模式
  const svgThickness = ref(0.2);      // SVG 基础厚度 (mm)
  const svgTol = ref(0.02);           // SVG 几何容差
  const svgMinArea = ref(0.01);       // SVG 最小忽略面积
  const svgSimplify = ref(0.01);      // SVG 路径简化程度
  const svgPaletteTol = ref(10);      // SVG 颜色聚类容差

  // 通用输出设置
  const outputFormat = ref("stl");    // 输出格式: stl, 3mf
  const outputDir = ref("");          // 输出根目录
  const wmm = ref(120);               // 输出宽度 (mm)
  const hmm = ref(120);               // 输出高度 (mm)
  const layers = ref(6);              // 打印层数

  // LUT 提取与校色 (Calibration) 状态
  const lutPhotoPath = ref("");       // 校色照片路径
  const lutCornerPoints = ref("[[100,100],[900,100],[900,900],[100,900]]"); // 四角定位点 JSON 字符串
  const lutOutDir = ref("");          // LUT 相关输出目录
  const lutZoom = ref(1.0);           // 预览缩放比例
  const lutBarrel = ref(0.0);         // 桶形畸变校正系数
  const lutOffsetX = ref(0.0);        // 预览水平偏移
  const lutOffsetY = ref(0.0);        // 预览垂直偏移
  const lutAutoWb = ref(true);        // 是否启用自动白平衡
  const lutVignetteFix = ref(true);   // 是否启用暗角修正
  const lutWindowPx = ref(8);         // 采样窗口大小 (像素)
  const lutStatus = ref("");          // LUT 任务当前状态描述
  const lutOverlayPath = ref("");     // 叠加定位网格后的照片路径
  const lutWarpedPath = ref("");      // 透视校正后的展平照片路径
  const lutResultSummary = ref("");   // LUT 生成结果摘要
  const lutResultFile = ref("");      // 生成的 .json 或 .icc 路径
  const lutJobId = ref("");           // 当前运行的 LUT 任务 ID
  const lutObservationPath = ref(""); // 采样观测数据路径
  const boardSpecPath = ref("");      // 标靶规格文件路径
  const boardSpecId = ref("");        // 标靶 ID
  const boardSpecName = ref("");      // 标靶名称
  const boardSpecRows = ref(0);       // 标靶行数
  const boardSpecCols = ref(0);       // 标靶列数

  // 数据集 (Dataset) 管理
  const datasetId = ref("");                // 数据集 ID
  const datasetOutDir = ref("");            // 数据集输出目录
  const datasetObservationPath = ref("");   // 数据集关联的观测数据
  const datasetObsCount = ref(0);           // 数据集中观测数据的数量
  const datasetBoardCount = ref(0);         // 数据集中涉及的标靶数量
  const datasetSummaryPath = ref("");       // 数据集摘要文件路径
  const datasetStatus = ref("");            // 数据集任务状态
  const datasetJobId = ref("");             // 当前运行的数据集任务 ID

  // MCRT (蒙特卡洛射线追踪) 验证参数
  const mcrtSamples = ref(200);             // 采样数
  const mcrtBackend = ref("vulkan");        // 渲染后端: vulkan, cpu
  const mcrtLayerHeight = ref(0.2);         // 层高 (mm)
  const mcrtBackingAlbedo = ref(0.9);       // 底板反照率
  const mcrtColorSystem = ref("RYBW");      // 颜色系统
  const mcrtAvgError = ref("");             // 平均色差结果
  const mcrtDiagnosticsPath = ref("");      // 诊断数据路径
  const mcrtDiagnostics = ref({});          // 详细诊断信息对象
  const mcrtStatus = ref("");               // MCRT 任务状态
  const mcrtJobId = ref("");                // 当前运行的 MCRT 任务 ID

  // 标靶网格配置
  const gridRows = ref(0);
  const gridCols = ref(0);
  const gridDataRows = ref(0);
  const gridDataCols = ref(0);
  const gridBorder = ref(0);

  // 位图导出 (Bitmap Export) 设置
  const bitmapImagePath = ref("");          // 输入位图路径
  const bitmapLutPath = ref("");            // 使用的 LUT 路径
  const bitmapNozzle = ref(0.42);           // 喷嘴直径 (mm)
  const bitmapWidth = ref(60);              // 目标宽度 (mm)
  const bitmapLayers = ref(5);              // 打印层数
  const bitmapAlgo = ref("basic");          // 转换算法
  const bitmapSdfSmoothSigma = ref(1.0);    // SDF 平滑系数
  const bitmapSdfSimplifyEps = ref(0.1);    // SDF 简化阈值
  const bitmapAutoBgRemove = ref(false);    // 自动背景移除
  const bitmapBgTol = ref(30);              // 背景移除容差
  const bitmapAlphaThreshold = ref(128);    // 透明度阈值
  const bitmapOutDir = ref("");             // 位图导出目录
  const libraryRoot = ref("");              // 资源库根目录
  const bitmapProgress = ref(-1);           // 任务进度 (0-1)
  const bitmapStage = ref("");              // 任务阶段描述
  const bitmapStatus = ref("");             // 任务状态详细信息
  const bitmapPreview2dPath = ref("");      // 2D 预览图路径
  const bitmapStandard3mfPath = ref("");    // 标准 3MF 导出路径
  const bitmapBambu3mfPath = ref("");       // 拓竹 3MF 导出路径
  const bitmapMetaPath = ref("");           // 元数据路径
  const bitmapJobId = ref("");              // 当前运行的导出任务 ID

  const selectedProfileKey = ref("profileDefault"); // 当前选中的配置预设

  /**
   * 初始化资源库和各个子目录路径
   * @param {Object} tauri - Tauri 桥接对象
   */
  const setupPaths = async (tauri) => {
    if (!tauri.hasTauri()) return;

    try {
      const root = await tauri.invoke("init_library");
      if (root) {
        libraryRoot.value = root;
        // 设置结构化输出目录
        outputDir.value = root; // 根目录作为回退
        lutOutDir.value = await tauri.joinPaths(root, "Profiles");
        bitmapOutDir.value = await tauri.joinPaths(root, "Exports/STL"); // 默认输出到 STL
        datasetOutDir.value = await tauri.joinPaths(root, "Datasets");
      }
    } catch (e) {
      console.error("初始化结构化相册路径失败", e);
    }
  };

  return {
    currentView,
    helpOpen,
    aboutOpen,
    inputKind,
    inputPath,
    svgPaletteMode,
    svgThickness,
    svgTol,
    svgMinArea,
    svgSimplify,
    svgPaletteTol,
    outputFormat,
    outputDir,
    wmm,
    hmm,
    layers,
    lutPhotoPath,
    lutCornerPoints,
    lutOutDir,
    lutZoom,
    lutBarrel,
    lutOffsetX,
    lutOffsetY,
    lutAutoWb,
    lutVignetteFix,
    lutWindowPx,
    lutStatus,
    lutOverlayPath,
    lutWarpedPath,
    lutResultSummary,
    lutResultFile,
    lutJobId,
    lutObservationPath,
    boardSpecPath,
    boardSpecId,
    boardSpecName,
    boardSpecRows,
    boardSpecCols,
    datasetId,
    datasetOutDir,
    datasetObservationPath,
    datasetObsCount,
    datasetBoardCount,
    datasetSummaryPath,
    datasetStatus,
    datasetJobId,
    mcrtSamples,
    mcrtBackend,
    mcrtLayerHeight,
    mcrtBackingAlbedo,
    mcrtColorSystem,
    mcrtAvgError,
    mcrtDiagnosticsPath,
    mcrtDiagnostics,
    mcrtStatus,
    mcrtJobId,
    gridRows,
    gridCols,
    gridDataRows,
    gridDataCols,
    gridBorder,
    bitmapImagePath,
    bitmapLutPath,
    bitmapNozzle,
    bitmapWidth,
    bitmapLayers,
    bitmapAlgo,
    bitmapSdfSmoothSigma,
    bitmapSdfSimplifyEps,
    bitmapAutoBgRemove,
    bitmapBgTol,
    bitmapAlphaThreshold,
    bitmapOutDir,
    libraryRoot,
    bitmapProgress,
    bitmapStage,
    bitmapStatus,
    bitmapPreview2dPath,
    bitmapStandard3mfPath,
    bitmapBambu3mfPath,
    bitmapMetaPath,
    bitmapJobId,
    selectedProfileKey,
    setupPaths
  };
};
