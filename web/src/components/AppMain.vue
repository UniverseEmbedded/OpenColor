<template>
  <main class="main">
    <TopBar 
      :currentView="currentView"
      @openHelp="$emit('openHelp')"
      @openOutput="$emit('openOutput')"
    />

    <GenerateView 
      v-show="currentView === 'generate'"
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
      @setImported="$emit('setImported', $event)"
      @previewWheel="$emit('previewWheel', $event)"
      @resetPreviewScale="$emit('resetPreviewScale')"
      @togglePreview="$emit('togglePreview')"
      @update:outputFormat="$emit('update:outputFormat', $event)"
      @update:wmm="$emit('update:wmm', $event)"
      @update:hmm="$emit('update:hmm', $event)"
      @update:layers="$emit('update:layers', $event)"
      @update:selectedProfileKey="$emit('update:selectedProfileKey', $event)"
      @update:bitmapImagePath="$emit('update:bitmapImagePath', $event)"
      @update:bitmapLutPath="$emit('update:bitmapLutPath', $event)"
      @update:bitmapNozzle="$emit('update:bitmapNozzle', $event)"
      @update:bitmapWidth="$emit('update:bitmapWidth', $event)"
      @update:bitmapLayers="$emit('update:bitmapLayers', $event)"
      @update:bitmapAlgo="$emit('update:bitmapAlgo', $event)"
      @update:bitmapSdfSmoothSigma="$emit('update:bitmapSdfSmoothSigma', $event)"
      @update:bitmapSdfSimplifyEps="$emit('update:bitmapSdfSimplifyEps', $event)"
      @update:bitmapAutoBgRemove="$emit('update:bitmapAutoBgRemove', $event)"
      @update:bitmapBgTol="$emit('update:bitmapBgTol', $event)"
      @update:bitmapAlphaThreshold="$emit('update:bitmapAlphaThreshold', $event)"
      @update:bitmapOutDir="$emit('update:bitmapOutDir', $event)"
      @update:inputKind="$emit('update:inputKind', $event)"
      @pickOutputDir="$emit('pickOutputDir')"
      @clearOutputDir="$emit('clearOutputDir')"
      @goQuickCalib="$emit('goQuickCalib')"
      @pickLut="$emit('pickLut')"
      @pickOutDir="$emit('pickOutDir')"
      @runBitmapExport="$emit('runBitmapExport')"
      @cancelBitmapExport="$emit('cancelBitmapExport')"
      @openOutputDir="$emit('openOutputDir', $event)"
      @openFile="$emit('openFile', $event)"
      @openInSlicer="$emit('openInSlicer')"
      @bitmapPreviewWheel="$emit('bitmapPreviewWheel', $event)"
      @resetBitmapPreviewScale="$emit('resetBitmapPreviewScale')"
      @copyTips="$emit('copyTips')"
      @runGenerate="$emit('runGenerate')"
    />

    <CalibrateView
      v-show="currentView === 'calibrate'"
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
      :materialGroups="materialGroups"
      @pingEngine="$emit('pingEngine')"
      @importPhoto="$emit('importPhoto', $event)"
      @genProfile="$emit('genProfile', $event)"
      @saveProfile="$emit('saveProfile', $event)"
      @genCalibStl="$emit('genCalibStl', $event)"
      @manualQuad="$emit('manualQuad', $event)"
      @pickLutPhoto="$emit('pickLutPhoto')"
      @pickLutPhotoToLibrary="$emit('pickLutPhotoToLibrary')"
      @pickLutOutDir="$emit('pickLutOutDir')"
      @pickBoardSpec="$emit('pickBoardSpec')"
      @pickBoardSpecToLibrary="$emit('pickBoardSpecToLibrary')"
      @pickObservation="$emit('pickObservation')"
      @pickDatasetOutDir="$emit('pickDatasetOutDir')"
      @runLutExtract="$emit('runLutExtract')"
      @runDatasetCreate="$emit('runDatasetCreate')"
      @runDatasetAddObservation="$emit('runDatasetAddObservation')"
      @runDatasetAggregate="$emit('runDatasetAggregate')"
      @runMcrtValidate="$emit('runMcrtValidate')"
      @lutPreviewWheel="$emit('lutPreviewWheel', $event)"
      @resetLutPreviewScale="$emit('resetLutPreviewScale')"
      @useDemoPhoto="$emit('useDemoPhoto', $event)"
      @update:lutPhotoPath="$emit('update:lutPhotoPath', $event)"
      @update:lutCornerPoints="$emit('update:lutCornerPoints', $event)"
      @update:lutOutDir="$emit('update:lutOutDir', $event)"
      @update:lutZoom="$emit('update:lutZoom', $event)"
      @update:lutBarrel="$emit('update:lutBarrel', $event)"
      @update:lutOffsetX="$emit('update:lutOffsetX', $event)"
      @update:lutOffsetY="$emit('update:lutOffsetY', $event)"
      @update:lutAutoWb="$emit('update:lutAutoWb', $event)"
      @update:lutVignetteFix="$emit('update:lutVignetteFix', $event)"
      @update:lutWindowPx="$emit('update:lutWindowPx', $event)"
      @update:boardSpecPath="$emit('update:boardSpecPath', $event)"
      @update:datasetId="$emit('update:datasetId', $event)"
      @update:datasetOutDir="$emit('update:datasetOutDir', $event)"
      @update:datasetObservationPath="$emit('update:datasetObservationPath', $event)"
      @update:mcrtSamples="$emit('update:mcrtSamples', $event)"
      @update:mcrtBackend="$emit('update:mcrtBackend', $event)"
      @update:mcrtLayerHeight="$emit('update:mcrtLayerHeight', $event)"
      @update:mcrtBackingAlbedo="$emit('update:mcrtBackingAlbedo', $event)"
      @update:mcrtColorSystem="$emit('update:mcrtColorSystem', $event)"
      @genQuickCalibStl="$emit('genQuickCalibStl')"
      @goToMaterials="$emit('goToMaterials')"
    />

    <AlbumView 
      v-show="currentView === 'album'"
      :currentView="currentView"
    />

    <MaterialsView
      v-show="currentView === 'materials'"
      :filaments="filaments"
      :materialGroups="materialGroups"
      :currentGroup="currentMaterialGroup"
      :groupTemplates="groupTemplates"
      :isLoading="isMaterialsLoading"
      @selectGroup="$emit('selectGroup', $event)"
      @newGroup="$emit('newGroup', $event)"
      @saveGroup="$emit('saveGroup', $event)"
      @saveAsGroup="$emit('saveAsGroup', $event)"
      @importGroup="$emit('importGroup', $event)"
      @exportGroup="$emit('exportGroup', $event)"
      @fromCalib="$emit('fromCalib', $event)"
      @importTemplate="$emit('importTemplate', $event)"
      @updateGroup="$emit('updateGroup', $event)"
      @addFilament="$emit('addFilament', $event)"
      @updateFilament="$emit('updateFilament', $event)"
      @deleteFilament="$emit('deleteFilament', $event)"
      @createFilamentsFromTemplate="(slots, callback) => $emit('createFilamentsFromTemplate', slots, callback)"
    />

    <SettingsView 
      v-show="currentView === 'settings'"
      :localeSetting="localeSetting"
      :theme="theme"
      :skipWindowSizeCheck="skipWindowSizeCheck"
      :outputDir="outputDir"
      :svgPaletteMode="svgPaletteMode"
      :svgThickness="svgThickness"
      :svgTol="svgTol"
      :svgMinArea="svgMinArea"
      :svgSimplify="svgSimplify"
      :svgPaletteTol="svgPaletteTol"
      @openAbout="$emit('openAbout')"
      @pickOutputDir="$emit('pickOutputDir')"
      @clearOutputDir="$emit('clearOutputDir')"
      @pingEngine="$emit('pingEngine')"
      @update:localeSetting="$emit('update:localeSetting', $event)"
      @update:theme="$emit('update:theme', $event)"
      @update:skipWindowSizeCheck="$emit('update:skipWindowSizeCheck', $event)"
      @update:svgPaletteMode="$emit('update:svgPaletteMode', $event)"
      @update:svgThickness="$emit('update:svgThickness', $event)"
      @update:svgTol="$emit('update:svgTol', $event)"
      @update:svgMinArea="$emit('update:svgMinArea', $event)"
      @update:svgSimplify="$emit('update:svgSimplify', $event)"
      @update:svgPaletteTol="$emit('update:svgPaletteTol', $event)"
    />

    <div class="main-footer">
      <button class="btn ghost about-btn centered" @click="$emit('openAbout')">
        <i class="ti ti-alert-circle"></i> <span class="btn-label">{{ t('footer.about') }}</span>
      </button>
      <div class="footer-banner">{{ t("footer.hint") }}</div>
      <button v-if="currentView === 'generate'" class="btn primary footer-gen-btn centered" @click="$emit('runGenerate')">
        <i class="ti ti-player-play"></i> <span class="btn-label">{{ t('top.generate') }}</span>
      </button>
    </div>
  </main>
</template>

<script setup>
// 导入国际化功能
import { useI18n } from "vue-i18n";
// 导入子组件
import TopBar from "./TopBar.vue";
import GenerateView from "./GenerateView.vue";
import CalibrateView from "./CalibrateView.vue";
import AlbumView from "./AlbumView.vue";
import MaterialsView from "./MaterialsView.vue";
import SettingsView from "./SettingsView.vue";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
defineProps({
  currentView: String,            // 当前视图
  inputKind: String,             // 输入类型
  inputPath: String,             // 输入路径
  previewSrc: String,            // 预览图片源
  previewScale: Number,          // 预览缩放比例
  hasProcessedPreview: Boolean,   // 是否有处理后的预览
  previewToggleLabel: String,     // 预览切换标签
  outputFormat: String,          // 输出格式
  outputDir: String,             // 输出目录
  wmm: Number,                  // 宽度（毫米）
  hmm: Number,                  // 高度（毫米）
  layers: Number,               // 层数
  selectedProfileKey: String,    // 选中的配置文件键
  bitmapImagePath: String,       // 位图图片路径
  bitmapLutPath: String,        // 位图 LUT 路径
  bitmapNozzle: Number,         // 位图喷嘴宽度
  bitmapWidth: Number,          // 位图宽度
  bitmapLayers: Number,          // 位图层数
  bitmapAlgo: String,           // 位图算法
  bitmapSdfSmoothSigma: Number,  // SDF 平滑参数
  bitmapSdfSimplifyEps: Number, // SDF 简化参数
  bitmapAutoBgRemove: Boolean,   // 是否自动移除背景
  bitmapBgTol: Number,          // 背景容差
  bitmapAlphaThreshold: Number,   // 透明度阈值
  bitmapOutDir: String,         // 位图输出目录
  bitmapProgress: Number,        // 位图进度
  bitmapStage: String,          // 位图阶段
  bitmapStatus: String,         // 位图状态
  bitmapPreview2dSrc: String,   // 位图 2D 预览源
  bitmapStandard3mfPath: String, // 标准 3MF 路径
  bitmapBambu3mfPath: String,   // Bambu 3MF 路径
  bitmapMetaPath: String,        // 元数据路径
  bitmapJobId: String,          // 位图任务 ID
  bitmapPreviewScale: Number,    // 位图预览缩放比例
  lutPhotoPath: String,         // LUT 照片路径
  lutCornerPoints: String,      // LUT 角点坐标
  lutOutDir: String,           // LUT 输出目录
  lutZoom: Number,             // LUT 缩放比例
  lutBarrel: Number,           // LUT 桶形畸变系数
  lutOffsetX: Number,         // LUT X 偏移量
  lutOffsetY: Number,         // LUT Y 偏移量
  lutAutoWb: Boolean,         // LUT 自动白平衡
  lutVignetteFix: Boolean,    // LUT 晕影修正
  lutWindowPx: Number,       // LUT 窗口像素大小
  lutStatus: String,          // LUT 状态
  lutOverlaySrc: String,     // LUT 覆盖图源
  lutPhotoSrc: String,       // LUT 照片源
  lutWarpedSrc: String,      // LUT 矫正后图片源
  lutResultSummary: String,   // LUT 结果摘要
  lutResultFile: String,     // LUT 结果文件
  lutPreviewScale: Number,   // LUT 预览缩放比例
  boardSpecPath: String,     // 色盘规格路径
  boardSpecId: String,      // 色盘规格 ID
  boardSpecName: String,     // 色盘规格名称
  boardSpecRows: Number,    // 色盘规格行数
  boardSpecCols: Number,    // 色盘规格列数
  datasetId: String,        // 数据集 ID
  datasetOutDir: String,    // 数据集输出目录
  datasetObservationPath: String, // 数据集观察路径
  datasetObsCount: Number,  // 数据集观察数量
  datasetBoardCount: Number, // 数据集色盘数量
  datasetSummaryPath: String, // 数据集摘要路径
  datasetStatus: String,     // 数据集状态
  mcrtSamples: Number,      // MCRT 采样数
  mcrtBackend: String,      // MCRT 后端
  mcrtLayerHeight: Number,  // MCRT 层高
  mcrtBackingAlbedo: Number, // MCRT 背景反射率
  mcrtColorSystem: String,  // MCRT 颜色系统
  mcrtAvgError: String,     // MCRT 平均误差
  mcrtDiagnosticsPath: String, // MCRT 诊断路径
  mcrtDiagnostics: Object,  // MCRT 诊断数据
  mcrtStatus: String,       // MCRT 状态
  gridRows: Number,         // 网格行数
  gridCols: Number,         // 网格列数
  gridDataRows: Number,      // 网格数据行数
  gridDataCols: Number,      // 网格数据列数
  gridBorder: Number,       // 网格边框
  localeSetting: String,    // 语言设置
  theme: String,            // 主题
  skipWindowSizeCheck: Boolean, // 是否跳过窗口尺寸检查
  svgPaletteMode: String,   // SVG 调色板模式
  svgThickness: Number,     // SVG 厚度
  svgTol: Number,          // SVG 容差
  svgMinArea: Number,       // SVG 最小面积
  svgSimplify: Number,      // SVG 简化参数
  svgPaletteTol: Number,   // SVG 调色板容差
  libraryItems: {           // 相册资源项
    type: Array,
    default: () => []
  },
  materialGroups: {         // 材料组列表
    type: Array,
    default: () => []
  },
  currentMaterialGroup: {   // 当前选中的材料组
    type: Object,
    default: null
  },
  filaments: {              // 耗材列表
    type: Array,
    default: () => []
  },
  groupTemplates: {         // 材料组模板
    type: Array,
    default: () => []
  },
  isMaterialsLoading: {     // 材料配置加载状态
    type: Boolean,
    default: false
  }
});

// 定义组件事件
defineEmits([
  "openHelp",
  "openOutput",
  "setImported",
  "previewWheel",
  "resetPreviewScale",
  "togglePreview",
  "update:outputFormat",
  "update:wmm",
  "update:hmm",
  "update:layers",
  "update:selectedProfileKey",
  "update:bitmapImagePath",
  "update:bitmapLutPath",
  "update:bitmapNozzle",
  "update:bitmapWidth",
  "update:bitmapLayers",
  "update:bitmapAlgo",
  "update:bitmapSdfSmoothSigma",
  "update:bitmapSdfSimplifyEps",
  "update:bitmapAutoBgRemove",
  "update:bitmapBgTol",
  "update:bitmapAlphaThreshold",
  "update:bitmapOutDir",
  "update:inputKind",
  "pickOutputDir",
  "clearOutputDir",
  "goQuickCalib",
  "pickLut",
  "pickOutDir",
  "runBitmapExport",
  "cancelBitmapExport",
  "openOutputDir",
  "openFile",
  "openInSlicer",
  "bitmapPreviewWheel",
  "resetBitmapPreviewScale",
  "copyTips",
  "runGenerate",
  "pingEngine",
  "importPhoto",
  "genProfile",
  "saveProfile",
  "genCalibStl",
  "manualQuad",
  "pickLutPhoto",
  "pickLutPhotoToLibrary",
  "pickLutOutDir",
  "pickBoardSpec",
  "pickBoardSpecToLibrary",
  "pickObservation",
  "pickDatasetOutDir",
  "runLutExtract",
  "runDatasetCreate",
  "runDatasetAddObservation",
  "runDatasetAggregate",
  "runMcrtValidate",
  "lutPreviewWheel",
  "resetLutPreviewScale",
  "useDemoPhoto",
  "update:lutPhotoPath",
  "update:lutCornerPoints",
  "update:lutOutDir",
  "update:lutZoom",
  "update:lutBarrel",
  "update:lutOffsetX",
  "update:lutOffsetY",
  "update:lutAutoWb",
  "update:lutVignetteFix",
  "update:lutWindowPx",
  "update:boardSpecPath",
  "update:datasetId",
  "update:datasetOutDir",
  "update:datasetObservationPath",
  "update:mcrtSamples",
  "update:mcrtBackend",
  "update:mcrtLayerHeight",
  "update:mcrtBackingAlbedo",
  "update:mcrtColorSystem",
  "selectProfile",
  "importJson",
  "exportJson",
  "fromCalib",
  "importTemplate",
  "openAbout",
  "update:localeSetting",
  "update:theme",
  "update:skipWindowSizeCheck",
  "update:svgPaletteMode",
  "update:svgThickness",
  "update:svgTol",
  "update:svgMinArea",
  "update:svgSimplify",
  "update:svgPaletteTol",
  "newGroup",
  "saveGroup",
  "saveAsGroup",
  "importGroup",
  "exportGroup",
  "updateGroup",
  "goToMaterials",
  "addFilament",
  "updateFilament",
  "deleteFilament"
]);
</script>
