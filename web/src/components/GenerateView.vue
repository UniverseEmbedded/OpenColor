<template>
  <section class="view oc-edge">
    <!-- 子导航栏，用于切换输入和输出设置 -->
    <div class="subnav oc-edge oc-panel">
      <!-- 输入设置选项卡 -->
      <button :class="{ active: generateTab === 0 }" @click="generateTab = 0"><i class="ti ti-file-import"></i>{{ t("subnav.generateInput") }}</button>
      <!-- 输出设置选项卡 -->
      <button :class="{ active: generateTab === 1 }" @click="generateTab = 1"><i class="ti ti-settings-automation"></i>{{ t("subnav.generateOutput") }}</button>
    </div>
    <!-- 网格布局，包含输入卡片和输出卡片 -->
    <div class="grid oc-edge">
      <!-- 输入卡片组件 -->
      <GenerateInputCard
        :active="generateTab === 0"
        :inputKind="inputKind"
        :inputPath="inputPath"
        :previewSrc="previewSrc"
        :previewScale="previewScale"
        :hasProcessedPreview="hasProcessedPreview"
        :previewToggleLabel="previewToggleLabel"
        @setImported="$emit('setImported', $event)"
        @previewWheel="$emit('previewWheel', $event)"
        @resetPreviewScale="$emit('resetPreviewScale')"
        @togglePreview="$emit('togglePreview')"
        @update:inputKind="$emit('update:inputKind', $event)"
      />

      <!-- 输出卡片组件 -->
      <GenerateOutputCard
        :active="generateTab === 1"
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
        @copyTips="$emit('copyTips')"
        @update:outputFormat="$emit('update:outputFormat', $event)"
        @pickOutputDir="$emit('pickOutputDir')"
        @clearOutputDir="$emit('clearOutputDir')"
        @update:wmm="$emit('update:wmm', $event)"
        @update:hmm="$emit('update:hmm', $event)"
        @update:layers="$emit('update:layers', $event)"
        @goQuickCalib="$emit('goQuickCalib')"
        @update:selectedProfileKey="$emit('update:selectedProfileKey', $event)"
        @pickLut="$emit('pickLut')"
        @pickOutDir="$emit('pickOutDir')"
        @runBitmapExport="$emit('runBitmapExport')"
        @cancelBitmapExport="$emit('cancelBitmapExport')"
        @openOutputDir="$emit('openOutputDir', $event)"
        @openFile="$emit('openFile', ...$event)"
        @openInSlicer="$emit('openInSlicer')"
        @bitmapPreviewWheel="$emit('bitmapPreviewWheel', $event)"
        @resetBitmapPreviewScale="$emit('resetBitmapPreviewScale')"
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
      />
    </div>
    <!-- 底部操作按钮 -->
    <div class="bottom-actions">
      <button class="btn primary" @click="$emit('runGenerate')"><i class="ti ti-player-play"></i>{{ t("top.generate") }}</button>
    </div>
  </section>
</template>

<script setup>
// 导入 Vue 响应式 API
import { ref } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";
// 导入子组件
import GenerateInputCard from "./GenerateInputCard.vue";
import GenerateOutputCard from "./GenerateOutputCard.vue";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
const props = defineProps({
  inputKind: String,           // 输入类型
  inputPath: String,           // 输入路径
  previewSrc: String,          // 预览图片源
  previewScale: Number,        // 预览缩放比例
  hasProcessedPreview: Boolean, // 是否有处理后的预览
  previewToggleLabel: String,  // 预览切换标签
  outputFormat: String,        // 输出格式
  outputDir: String,           // 输出目录
  wmm: Number,                 // 宽度（毫米）
  hmm: Number,                 // 高度（毫米）
  layers: Number,              // 层数
  selectedProfileKey: String,  // 选中的配置文件键
  bitmapImagePath: String,     // 位图图片路径
  bitmapLutPath: String,       // 位图 LUT 路径
  bitmapNozzle: Number,        // 位图喷嘴宽度
  bitmapWidth: Number,         // 位图宽度
  bitmapLayers: Number,         // 位图层数
  bitmapAlgo: String,          // 位图算法
  bitmapSdfSmoothSigma: Number, // SDF 平滑参数
  bitmapSdfSimplifyEps: Number, // SDF 简化参数
  bitmapAutoBgRemove: Boolean, // 是否自动移除背景
  bitmapBgTol: Number,         // 背景容差
  bitmapAlphaThreshold: Number, // 透明度阈值
  bitmapOutDir: String,        // 位图输出目录
  bitmapProgress: Number,      // 位图进度
  bitmapStage: String,         // 位图阶段
  bitmapStatus: String,        // 位图状态
  bitmapPreview2dSrc: String,  // 位图 2D 预览源
  bitmapStandard3mfPath: String, // 标准 3MF 路径
  bitmapBambu3mfPath: String,  // Bambu 3MF 路径
  bitmapMetaPath: String,      // 元数据路径
  bitmapJobId: String,         // 位图任务 ID
  bitmapPreviewScale: Number   // 位图预览缩放比例
});

// 定义组件事件
defineEmits(['setImported', 'previewWheel', 'resetPreviewScale', 'togglePreview', 'updateOutputChip', 'pickOutputDir', 'clearOutputDir', 'goQuickCalib', 'updateProfileChip', 'pickLut', 'pickOutDir', 'runBitmapExport', 'cancelBitmapExport', 'openOutputDir', 'openFile', 'openInSlicer', 'bitmapPreviewWheel', 'resetBitmapPreviewScale', 'update:outputFormat', 'update:wmm', 'update:hmm', 'update:layers', 'update:selectedProfileKey', 'update:bitmapImagePath', 'update:bitmapLutPath', 'update:bitmapNozzle', 'update:bitmapWidth', 'update:bitmapLayers', 'update:bitmapAlgo', 'update:bitmapSdfSmoothSigma', 'update:bitmapSdfSimplifyEps', 'update:bitmapAutoBgRemove', 'update:bitmapBgTol', 'update:bitmapAlphaThreshold', 'update:bitmapOutDir', 'update:inputKind', 'copyTips', 'runGenerate']);

// 当前选中的选项卡（0: 输入, 1: 输出）
const generateTab = ref(0);
</script>
