<template>
  <div class="app">
    <Sidebar 
      :currentView="currentView"
      :chipInput="chipInput"
      :chipProfile="chipProfile"
      :chipOutput="chipOutput"
      @setView="setView"
      @openHelp="helpOpen = true"
      @openOutput="openOutputDir"
      @openAbout="aboutOpen = true"
    />

    <AppMain
      :currentView="currentView"
      :inputKind="inputKind"
      :inputPath="inputPath"
      :previewSrc="previewSrc"
      :previewScale="previewScale"
      :hasProcessedPreview="hasProcessedPreview"
      :previewToggleLabel="previewToggleLabel"
      :outputFormat="outputFormat"
      :outputDir="outputDir"
      :wmm="wmm"
      :hmm="hmm"
      :layers="layers"
      :selectedProfileKey="selectedProfileKey"
      :bitmapImagePath="bitmapImagePath"
      :bitmapLutPath="bitmapLutPath"
      :bitmapNozzle="bitmapNozzle"
      :bitmapWidth="bitmapWidth"
      :bitmapLayers="bitmapLayers"
      :bitmapAlgo="bitmapAlgo"
      :bitmapSdfSmoothSigma="bitmapSdfSmoothSigma"
      :bitmapSdfSimplifyEps="bitmapSdfSimplifyEps"
      :bitmapAutoBgRemove="bitmapAutoBgRemove"
      :bitmapBgTol="bitmapBgTol"
      :bitmapAlphaThreshold="bitmapAlphaThreshold"
      :bitmapOutDir="bitmapOutDir"
      :bitmapProgress="bitmapProgress"
      :bitmapStage="bitmapStage"
      :bitmapStatus="bitmapStatus"
      :bitmapPreview2dSrc="bitmapPreview2dSrc"
      :bitmapStandard3mfPath="bitmapStandard3mfPath"
      :bitmapBambu3mfPath="bitmapBambu3mfPath"
      :bitmapMetaPath="bitmapMetaPath"
      :bitmapJobId="bitmapJobId"
      :bitmapPreviewScale="bitmapPreviewScale"
      :lutPhotoPath="lutPhotoPath"
      :lutCornerPoints="lutCornerPoints"
      :lutOutDir="lutOutDir"
      :lutZoom="lutZoom"
      :lutBarrel="lutBarrel"
      :lutOffsetX="lutOffsetX"
      :lutOffsetY="lutOffsetY"
      :lutAutoWb="lutAutoWb"
      :lutVignetteFix="lutVignetteFix"
      :lutWindowPx="lutWindowPx"
      :lutStatus="lutStatus"
      :lutOverlaySrc="lutOverlaySrc"
      :lutPhotoSrc="lutPhotoSrc"
      :lutWarpedSrc="lutWarpedSrc"
      :lutResultSummary="lutResultSummary"
      :lutResultFile="lutResultFile"
      :lutPreviewScale="lutPreviewScale"
      :boardSpecPath="boardSpecPath"
      :boardSpecId="boardSpecId"
      :boardSpecName="boardSpecName"
      :boardSpecRows="boardSpecRows"
      :boardSpecCols="boardSpecCols"
      :datasetId="datasetId"
      :datasetOutDir="datasetOutDir"
      :datasetObservationPath="datasetObservationPath"
      :datasetObsCount="datasetObsCount"
      :datasetBoardCount="datasetBoardCount"
      :datasetSummaryPath="datasetSummaryPath"
      :datasetStatus="datasetStatus"
      :mcrtSamples="mcrtSamples"
      :mcrtBackend="mcrtBackend"
      :mcrtLayerHeight="mcrtLayerHeight"
      :mcrtBackingAlbedo="mcrtBackingAlbedo"
      :mcrtColorSystem="mcrtColorSystem"
      :mcrtAvgError="mcrtAvgError"
      :mcrtDiagnosticsPath="mcrtDiagnosticsPath"
      :mcrtDiagnostics="mcrtDiagnostics"
      :mcrtStatus="mcrtStatus"
      :gridRows="gridRows"
      :gridCols="gridCols"
      :gridDataRows="gridDataRows"
      :gridDataCols="gridDataCols"
      :gridBorder="gridBorder"
      :libraryItems="libraryItems"
      :filaments="filaments"
      :materialGroups="materialGroups"
      :currentMaterialGroup="currentMaterialGroup"
      :groupTemplates="groupTemplates"
      :isMaterialsLoading="isMaterialsLoading"
      :localeSetting="localeSetting"
      :theme="theme"
      :skipWindowSizeCheck="settings.skipWindowSizeCheck"
      :svgPaletteMode="svgPaletteMode"
      :svgThickness="svgThickness"
      :svgTol="svgTol"
      :svgMinArea="svgMinArea"
      :svgSimplify="svgSimplify"
      :svgPaletteTol="svgPaletteTol"
      @openHelp="helpOpen = true"
      @openOutput="openOutputDir"
      @setImported="setImported"
      @previewWheel="handlePreviewWheel"
      @resetPreviewScale="resetPreviewScale"
      @togglePreview="togglePreview"
      @update:outputFormat="outputFormat = $event"
      @update:wmm="wmm = $event"
      @update:hmm="hmm = $event"
      @update:layers="layers = $event"
      @update:selectedProfileKey="selectedProfileKey = $event"
      @update:bitmapImagePath="bitmapImagePath = $event"
      @update:bitmapLutPath="bitmapLutPath = $event"
      @update:bitmapNozzle="bitmapNozzle = $event"
      @update:bitmapWidth="bitmapWidth = $event"
      @update:bitmapLayers="bitmapLayers = $event"
      @update:bitmapAlgo="bitmapAlgo = $event"
      @update:bitmapSdfSmoothSigma="bitmapSdfSmoothSigma = $event"
      @update:bitmapSdfSimplifyEps="bitmapSdfSimplifyEps = $event"
      @update:bitmapAutoBgRemove="bitmapAutoBgRemove = $event"
      @update:bitmapBgTol="bitmapBgTol = $event"
      @update:bitmapAlphaThreshold="bitmapAlphaThreshold = $event"
      @update:bitmapOutDir="bitmapOutDir = $event"
      @update:inputKind="inputKind = $event"
      @pickOutputDir="pickOutputDir"
      @clearOutputDir="clearOutputDir"
      @goQuickCalib="goQuickCalib"
      @pickLut="pickLut"
      @pickOutDir="pickOutDir"
      @runBitmapExport="runBitmapExport"
      @cancelBitmapExport="cancelBitmapExport"
      @openOutputDir="(dir) => toastShow(t('top.openOutput'), dir)"
      @openFile="(title, path) => toastShow(title, path)"
      @openInSlicer="toastShow(t('btn.openInSlicer'), t('toast.launch'))"
      @bitmapPreviewWheel="handleBitmapPreviewWheel"
      @resetBitmapPreviewScale="resetBitmapPreviewScale"
      @copyTips="copyTips"
      @runGenerate="runGenerate"
      @pingEngine="pingEngine"
      @importPhoto="pickLutPhoto(false)"
      @importPhotoToLibrary="pickLutPhoto(true)"
      @genProfile="(title, subtitle) => toastShow(title, subtitle)"
      @genCalibStl="handleGenCalibStl"
      @manualQuad="runLutDetect"
      @pickLutPhoto="pickLutPhoto(false)"
      @pickLutPhotoToLibrary="pickLutPhoto(true)"
      @pickLutOutDir="pickLutOutDir"
      @pickBoardSpec="pickBoardSpec(false)"
      @pickBoardSpecToLibrary="pickBoardSpec(true)"
      @pickObservation="pickObservation"
      @pickDatasetOutDir="pickDatasetOutDir"
      @runLutExtract="runLutExtract"
      @runDatasetCreate="runDatasetCreate"
      @runDatasetAddObservation="runDatasetAddObservation"
      @runDatasetAggregate="runDatasetAggregate"
      @runMcrtValidate="runMcrtValidate"
      @lutPreviewWheel="handleLutPreviewWheel"
      @resetLutPreviewScale="resetLutPreviewScale"
      @useDemoPhoto="() => { lutPhotoPath = './image/calibration_board_rybw.jpg'; toastShow(t('toast.demoLoadedTitle'), t('toast.demoLoadedDesc')); }"
      @update:lutPhotoPath="lutPhotoPath = $event"
      @update:lutCornerPoints="lutCornerPoints = $event"
      @update:lutOutDir="lutOutDir = $event"
      @update:lutZoom="lutZoom = $event"
      @update:lutBarrel="lutBarrel = $event"
      @update:lutOffsetX="lutOffsetX = $event"
      @update:lutOffsetY="lutOffsetY = $event"
      @update:lutAutoWb="lutAutoWb = $event"
      @update:lutVignetteFix="lutVignetteFix = $event"
      @update:lutWindowPx="lutWindowPx = $event"
      @update:boardSpecPath="boardSpecPath = $event"
      @update:datasetId="datasetId = $event"
      @update:datasetOutDir="datasetOutDir = $event"
      @update:datasetObservationPath="datasetObservationPath = $event"
      @update:mcrtSamples="mcrtSamples = $event"
      @update:mcrtBackend="mcrtBackend = $event"
      @update:mcrtLayerHeight="mcrtLayerHeight = $event"
      @update:mcrtBackingAlbedo="mcrtBackingAlbedo = $event"
      @update:mcrtColorSystem="mcrtColorSystem = $event"
      @genQuickCalibStl="runQuickCalibCardGenerate"
      @selectGroup="handleSelectMaterialGroup"
      @newGroup="handleNewMaterialGroup"
      @saveGroup="handleSaveMaterialGroup"
      @saveAsGroup="handleSaveAsMaterialGroup"
      @importGroup="handleImportMaterialGroup"
      @exportGroup="handleExportMaterialGroup"
      @fromCalib="(title, subtitle) => toastShow(title, subtitle)"
      @importTemplate="(title, subtitle) => toastShow(title, subtitle)"
      @updateGroup="handleUpdateMaterialGroup"
      @addFilament="handleAddFilament"
      @updateFilament="handleUpdateFilament"
      @deleteFilament="handleDeleteFilament"
      @createFilamentsFromTemplate="handleCreateFilamentsFromTemplate"
      @goToMaterials="goToMaterials"
      @openAbout="aboutOpen = true"
      @update:localeSetting="localeSetting = $event"
      @update:theme="theme = $event"
      @update:skipWindowSizeCheck="settings.skipWindowSizeCheck = $event"
      @update:svgPaletteMode="svgPaletteMode = $event"
      @update:svgThickness="svgThickness = $event"
      @update:svgTol="svgTol = $event"
      @update:svgMinArea="svgMinArea = $event"
      @update:svgSimplify="svgSimplify = $event"
      @update:svgPaletteTol="svgPaletteTol = $event"
    />
  </div>

  <HelpModal 
    :isOpen="helpOpen"
    @close="helpOpen = false"
  />

  <AboutModal 
    :isOpen="aboutOpen"
    @close="aboutOpen = false"
  />

  <Toast 
    :visible="toastVisible"
    :title="toastTitle"
    :subtitle="toastSubtitle"
  />

  <div class="window-size-overlay">
    <div class="overlay-content">
      <img src="./assets/icon.svg" alt="Logo" class="overlay-logo" />
      <p>{{ t('hint.windowTooSmall') }}</p>
      <button class="btn" style="margin-top: 10px; border: 1px solid var(--line);" @click="settings.skipWindowSizeCheck = true">
        <i class="ti ti-eye-off"></i>
        {{ t('btn.neverShow') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed, ref, watch, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import Sidebar from "./components/Sidebar.vue";
import AppMain from "./components/AppMain.vue";
import HelpModal from "./components/HelpModal.vue";
import AboutModal from "./components/AboutModal.vue";
import Toast from "./components/Toast.vue";
import { useAppState } from "./composables/useAppState";
import { useAppChips } from "./composables/useAppChips";
import { useLocaleSetting } from "./composables/useLocaleSetting";
import { useThemeSetting } from "./composables/useThemeSetting";
import { useToast } from "./composables/useToast";
import { useTauriBridge } from "./composables/useTauriBridge";
import { usePreviewState } from "./composables/usePreviewState";
import { useFileHandlers } from "./composables/useFileHandlers";
import { useEngineOps } from "./composables/useEngineOps";
import { useSettingsStore } from "./composables/useSettingsStore";
import { useLibrary } from "./composables/useLibrary";
import { useMaterials } from "./composables/useMaterials";
import { openPath } from "@tauri-apps/plugin-opener";

const { t, locale } = useI18n();
const tauriBridge = useTauriBridge(t);
const { hasTauri, invoke, listen, openDialog, getDocumentsDir, joinPaths } = tauriBridge;

// 初始化设置存储
const settingsStore = useSettingsStore(invoke);
const { settings } = settingsStore;

const { localeSetting } = useLocaleSetting(locale, settings);
const { theme } = useThemeSetting(settings);
const { toastVisible, toastTitle, toastSubtitle, toastShow } = useToast();
const appState = useAppState();

// 窗口尺寸检查逻辑
const isWindowSmall = ref(false);
const checkWindowSize = () => {
  isWindowSmall.value = window.innerWidth <= 640 || window.innerHeight <= 480;
};

// 监听尺寸变化和设置变化，更新 body 类名
watch([isWindowSmall, () => settings.value.skipWindowSizeCheck], ([small, skip]) => {
  if (small && !skip) {
    document.body.classList.add("window-too-small");
  } else {
    document.body.classList.remove("window-too-small");
  }
}, { immediate: true });

const {
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
} = appState;

const previewState = usePreviewState({
  t,
  hasTauri,
  invoke,
  inputPath,
  bitmapPreview2dPath,
  lutOverlayPath,
  lutPhotoPath,
  lutWarpedPath
});

const {
  previewMode,
  previewScale,
  bitmapPreviewScale,
  lutPreviewScale,
  hasProcessedPreview,
  previewSrc,
  previewToggleLabel,
  togglePreview,
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
} = previewState;

const { chipInput, chipProfile, chipOutput } = useAppChips({
  t,
  inputPath,
  inputKind,
  selectedProfileKey,
  outputFormat
});

const combinedState = { ...appState, ...previewState };
const library = useLibrary(invoke);
const libraryItems = computed(() => library.items.value);

// 材料配置管理
const materials = useMaterials(invoke);
const filaments = computed(() => materials.filaments.value);
const materialGroups = computed(() => materials.materialGroups.value);
const currentMaterialGroup = computed(() => materials.currentGroup.value);
const groupTemplates = computed(() => materials.groupTemplates);
const isMaterialsLoading = computed(() => materials.isLoading.value);

const {
  setImported,
  pickOutputDir,
  pickLutPhoto,
  pickLut,
  pickOutDir,
  pickLutOutDir,
  pickBoardSpec,
  pickObservation,
  pickDatasetOutDir,
  clearOutputDir,
} = useFileHandlers(combinedState, t, toastShow, openDialog, library);

const {
  pingEngine,
  runLutExtract,
  runLutDetect,
  runBoardGenerate,
  runQuickCalibCardGenerate,
  runDatasetCreate,
  runDatasetAddObservation,
  runDatasetAggregate,
  runMcrtValidate,
  runBitmapExport,
  cancelBitmapExport,
  runGenerate,
  registerJobListeners,
} = useEngineOps(combinedState, t, toastShow, invoke, joinPaths);

const setView = (view) => {
  currentView.value = view;
};

const selectProfile = (name) => {
  selectedProfileKey.value = name;
  toastShow(t("toast.profileSelected"), t(`option.${selectedProfileKey.value}`));
};

// 材料配置相关处理函数
const handleSelectMaterialGroup = (groupId) => {
  materials.selectGroup(groupId);
  toastShow("已选择材料组", currentMaterialGroup.value?.name || "");
};

const handleNewMaterialGroup = async ({ name, channelCount, slots, isFromTemplate }) => {
  try {
    // 如果是从模板创建的，先保存临时耗材
    if (isFromTemplate) {
      const savedFilaments = await materials.saveTempFilaments();
      if (savedFilaments.length > 0) {
        console.log(`[材料组] 保存了 ${savedFilaments.length} 个临时耗材`);
      }
    }
    
    const newGroup = await materials.createAndSaveGroup(name, channelCount, slots);
    toastShow("创建成功", `已创建新材料组: ${newGroup.name}`);
  } catch (e) {
    console.error("创建材料组失败:", e);
    toastShow("创建失败", e.message || "未知错误");
    // 创建失败时清理临时耗材
    materials.clearTempFilaments();
  }
};

const handleSaveMaterialGroup = async (group) => {
  try {
    await materials.saveGroup(group);
    toastShow("保存成功", `已保存材料组: ${group.name}`);
  } catch (e) {
    console.error("保存材料组失败:", e);
    toastShow("保存失败", e.message || "未知错误");
  }
};

const handleSaveAsMaterialGroup = async (group) => {
  try {
    const newGroup = await materials.createGroup(group.name, group.channelCount, group.slots);
    await materials.saveGroup(newGroup);
    materials.currentGroup.value = newGroup;
    toastShow("另存成功", `已另存为: ${newGroup.name}`);
  } catch (e) {
    console.error("另存材料组失败:", e);
    toastShow("另存失败", e.message || "未知错误");
  }
};

const handleImportMaterialGroup = async () => {
  try {
    const group = await materials.importGroup(openDialog);
    if (group) {
      toastShow("导入成功", `已导入材料组: ${group.name}`);
    }
  } catch (e) {
    console.error("导入材料组失败:", e);
    toastShow("导入失败", e.message || "未知错误");
  }
};

const handleExportMaterialGroup = async (group) => {
  try {
    await materials.exportGroup(group, openDialog);
    toastShow("导出成功", `已导出材料组: ${group.name}`);
  } catch (e) {
    console.error("导出材料组失败:", e);
    toastShow("导出失败", e.message || "未知错误");
  }
};

const handleUpdateMaterialGroup = (groupId, updates) => {
  materials.updateGroup(groupId, updates);
};

// 耗材相关处理函数
const handleAddFilament = async (filament) => {
  try {
    const newFilament = await materials.addFilament(filament);
    toastShow("添加成功", `已添加耗材: ${newFilament.name}`);
  } catch (e) {
    console.error("添加耗材失败:", e);
    toastShow("添加失败", e.message || "未知错误");
  }
};

const handleUpdateFilament = (filamentId, updates) => {
  // TODO: 实现耗材更新
  console.log("更新耗材:", filamentId, updates);
};

const handleDeleteFilament = (filamentId) => {
  // TODO: 实现耗材删除
  const index = materials.filaments.value.findIndex(f => f.id === filamentId);
  if (index !== -1) {
    materials.filaments.value.splice(index, 1);
    toastShow("删除成功", "耗材已删除");
  }
};

// 从模板创建临时耗材
const handleCreateFilamentsFromTemplate = (slots, callback) => {
  // 如果 slots 为 null，表示清理临时耗材
  if (slots === null) {
    materials.clearTempFilaments();
    if (callback) callback(new Map());
    return;
  }
  
  try {
    // 创建临时耗材（不保存到数据库）
    const { createdTempFilaments, slotFilamentMap } = materials.createTempFilamentsFromTemplate(slots);
    
    // 将临时耗材添加到可用耗材列表中（用于UI显示）
    for (const tempFil of materials.tempFilaments.value) {
      if (!materials.filaments.value.find(f => f.id === tempFil.id)) {
        materials.filaments.value.push(tempFil);
      }
    }
    
    if (createdTempFilaments.length > 0) {
      console.log(`[模板] 创建了 ${createdTempFilaments.length} 个临时耗材`);
    }
    
    // 调用回调函数返回映射关系
    if (callback) {
      callback(slotFilamentMap);
    }
  } catch (e) {
    console.error("创建临时耗材失败:", e);
    toastShow("创建失败", e.message || "创建临时耗材失败");
    if (callback) callback(new Map());
  }
};

const goToMaterials = () => {
  currentView.value = "materials";
};

// 处理生成色盘 STL，传递弹窗参数
const handleGenCalibStl = async (params) => {
  console.log("[App] 生成色盘 STL，参数:", params);
  await runBoardGenerate(params);
};

const goQuickCalib = () => {
  currentView.value = "calibrate";
  toastShow(t("toast.jumpToCalib"), t("toast.jumpToCalibDesc"));
};

const copyTips = async () => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(t("toast.copyTipsContent"));
  }
  toastShow(t("toast.copyTips"), t("toast.copyTipsDesc"));
};

// 打开输出目录
const openOutputDir = async () => {
  if (!hasTauri()) {
    toastShow(t('top.openOutput'), t('toast.openOutputHint'));
    return;
  }
  try {
    // 优先使用位图输出目录，其次使用 LUT 输出目录
    const dir = bitmapOutDir.value || lutOutDir.value;
    if (dir) {
      // 使用 opener 插件打开文件夹，避免被360拦截
      await openPath(dir);
      toastShow(t('top.openOutput'), t('toast.openOutputSuccess'));
    } else {
      toastShow(t('top.openOutput'), t('toast.noOutputDir'));
    }
  } catch (e) {
    console.error('打开输出目录失败', e);
    toastShow(t('top.openOutput'), t('toast.openOutputFail'));
  }
};

onMounted(async () => {
  const bootStart = performance.now();
  const ms = (t0) => Math.round(performance.now() - t0);

  const runStep = async (name, fn) => {
    const t0 = performance.now();
    console.log(`[启动] ${name} 开始`);
    try {
      const res = await fn();
      console.log(`[启动] ${name} 完成，耗时 ${ms(t0)} ms`);
      return res;
    } catch (e) {
      console.error(`[启动] ${name} 失败，耗时 ${ms(t0)} ms`, e);
      throw e;
    }
  };

  try {
    // 初始化窗口尺寸检查
    runStep("窗口尺寸检查", async () => {
      checkWindowSize();
      window.addEventListener("resize", checkWindowSize);
    });

    const fontsReadyPromise = runStep("字体加载", async () => {
      if (!document.fonts) return;
      try {
        await document.fonts.ready;
      } catch (e) {
        console.error("字体加载失败", e);
      }
    });

    const settingsPromise = runStep("加载设置", async () => {
      await settingsStore.load();
    });

    const pathsPromise = runStep("设置路径", async () => {
      await setupPaths(tauriBridge);
    });

    const libraryPromise = runStep("初始化资源库", async () => {
      await library.init();
    });

    const materialsPromise = runStep("加载材料配置", async () => {
      await materials.loadFilaments();
      await materials.loadGroups();
    });

    const listenersPromise = runStep("注册引擎监听器", async () => {
      await registerJobListeners(listen);
    });

    // 等待字体加载并移除加载屏幕
    const removeLoading = () => {
      const loadingScreen = document.getElementById("loading-screen");
      if (loadingScreen) {
        loadingScreen.style.opacity = "0";
        setTimeout(() => {
          loadingScreen.remove();
        }, 300);
      }
    };

    await Promise.all([settingsPromise, fontsReadyPromise]);
    console.log(`[启动] 准备移除启动遮罩，总耗时 ${Math.round(performance.now() - bootStart)} ms`);
    removeLoading();

    const bg = [pathsPromise, libraryPromise, materialsPromise, listenersPromise];
    const bgResults = await Promise.allSettled(bg);
    for (const r of bgResults) {
      if (r.status === "rejected") {
        console.error("启动后台初始化任务失败", r.reason);
      }
    }

    runStep("引擎预热 Ping", async () => {
      await listenersPromise;
      await pingEngine();
    });
  } catch (e) {
    console.error("启动初始化失败", e);
  }
});

onUnmounted(() => {
  window.removeEventListener("resize", checkWindowSize);
});
</script>
