<template>
  <div class="card" :class="{ active }">
    <div class="hd">
      <div style="display:flex; align-items:center; gap:8px">
        <i class="ti ti-settings" style="opacity:0.6"></i>
        <h3>{{ t("sections.outputSettings") }}</h3>
      </div>
      <div class="row">
        <button class="btn" @click="$emit('copyTips')"><i class="ti ti-copy"></i>{{ t("btn.copyTips") }}</button>
      </div>
    </div>
    <div class="bd">
      <div class="field">
        <label><i class="ti ti-file-export"></i>{{ t("label.outputFormat") }}</label>
        <select :value="outputFormat" @change="$emit('update:outputFormat', $event.target.value)">
          <option value="stl">{{ t("option.stl") }}</option>
          <option value="3mf">{{ t("option.mf3") }}</option>
        </select>
      </div>
      <div class="field" style="margin-top: 10px;">
        <label><i class="ti ti-folder"></i>{{ t("label.outputDir") }}</label>
        <input :value="outputDir" readonly />
        <div class="row" style="margin-top:8px">
          <button class="btn" @click="$emit('pickOutputDir')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseOutputDir") }}</button>
          <button class="btn ghost" @click="$emit('clearOutputDir')"><i class="ti ti-trash"></i>{{ t("btn.clearOutputDir") }}</button>
        </div>
      </div>

      <div class="row row-adaptive" style="margin-top: 10px;">
        <div class="field">
          <label><i class="ti ti-arrows-horizontal"></i>{{ t("label.width") }}</label>
          <input :value="wmm" @input="$emit('update:wmm', $event.target.value)" type="number" />
        </div>
        <div class="field">
          <label><i class="ti ti-arrows-vertical"></i>{{ t("label.height") }}</label>
          <input :value="hmm" @input="$emit('update:hmm', $event.target.value)" type="number" />
        </div>
        <div class="field">
          <label><i class="ti ti-layers-intersect"></i>{{ t("label.layers") }}</label>
          <input :value="layers" @input="$emit('update:layers', $event.target.value)" type="number" />
        </div>
      </div>

      <div class="hr"></div>

      <div class="card expand-card" :class="{ collapsed: expandCollapsed }">
        <div class="hd" @click="expandCollapsed = !expandCollapsed">
          <div style="display:flex; align-items:center; gap:8px">
            <span class="arrow"><i class="ti ti-chevron-down"></i></span>
            <i class="ti ti-database" style="opacity:0.6"></i>
            <h3>{{ t("sections.materialsConfig") }}</h3>
          </div>
          <div class="row">
            <button class="btn" @click.stop="$emit('goQuickCalib')"><i class="ti ti-bolt"></i>{{ t("btn.quickCalib") }}</button>
          </div>
        </div>
        <div class="bd" style="overflow:visible; flex:none">
          <div class="row" style="margin-bottom:10px">
            <div class="field" style="min-width:260px">
              <label><i class="ti ti-list-details"></i>{{ t("label.profileSelect") }}</label>
              <select :value="selectedProfileKey" @change="$emit('update:selectedProfileKey', $event.target.value)">
                <option value="profileDefault">{{ t("option.profileDefault") }}</option>
                <option value="profileMy">{{ t("option.profileMy") }}</option>
                <option value="profileDemo">{{ t("option.profileDemo") }}</option>
              </select>
            </div>
            <div class="field">
              <label><i class="ti ti-info-square"></i>{{ t("label.summary") }}</label>
              <input :value="t('status.summaryDesc', { status: t('status.neverCalib') })" readonly />
            </div>
          </div>

          <div class="matgrid">
            <div class="mat">
              <div class="sw" style="background:rgba(255,80,80,.85)"></div>
              <div class="mini"><div class="name">{{ t("label.chanR") }}</div><span class="pill"><i class="ti ti-box"></i>PLA</span></div>
              <div class="meta"><i class="ti ti-color-swatch"></i>{{ t("label.colorRed") }} · <i class="ti ti-sparkles"></i>{{ t("label.finishGlossy") }}</div>
            </div>
            <div class="mat">
              <div class="sw" style="background:rgba(100,255,140,.85)"></div>
              <div class="mini"><div class="name">{{ t("label.chanG") }}</div><span class="pill"><i class="ti ti-box"></i>PLA</span></div>
              <div class="meta"><i class="ti ti-color-swatch"></i>{{ t("label.colorGreen") }} · <i class="ti ti-blur"></i>{{ t("label.finishMatte") }}</div>
            </div>
            <div class="mat">
              <div class="sw" style="background:rgba(90,160,255,.90)"></div>
              <div class="mini"><div class="name">{{ t("label.chanB") }}</div><span class="pill"><i class="ti ti-box"></i>PLA</span></div>
              <div class="meta"><i class="ti ti-color-swatch"></i>{{ t("label.colorBlue") }} · <i class="ti ti-sparkles"></i>{{ t("label.finishGlossy") }}</div>
            </div>
            <div class="mat">
              <div class="sw" style="background:rgba(245,245,245,.92)"></div>
              <div class="mini"><div class="name">{{ t("label.chanW") }}</div><span class="pill"><i class="ti ti-box"></i>PLA</span></div>
              <div class="meta"><i class="ti ti-color-swatch"></i>{{ t("label.colorWhite") }} · <i class="ti ti-blur"></i>{{ t("label.finishMatte") }}</div>
            </div>
          </div>

          <div class="hr"></div>

          <details>
            <summary><i class="ti ti-adjustments-horizontal"></i>{{ t("label.advOptions") }}</summary>
            <div class="inside">
              <div class="row">
                <div class="field">
                  <label><i class="ti ti-clock-pause"></i>{{ t("label.swapPenalty") }}</label>
                  <input type="number" value="1.0" />
                </div>
                <div class="field">
                  <label><i class="ti ti-stack-2"></i>{{ t("label.layerPenalty") }}</label>
                  <input type="number" value="0.2" />
                </div>
                <div class="field">
                  <label><i class="ti ti-color-filter"></i>{{ t("label.quantColors") }}</label>
                  <select>
                    <option selected>4</option>
                    <option>8</option>
                  </select>
                </div>
              </div>
              <div class="row">
                <div class="field">
                  <label><i class="ti ti-border-all"></i>{{ t("label.brimStrategy") }}</label>
                  <select>
                    <option selected>{{ t("option.brimBoth") }}</option>
                    <option>{{ t("option.brimOnly") }}</option>
                    <option>{{ t("option.brimNone") }}</option>
                  </select>
                  <div class="hint">{{ t("hint.brimHint") }}</div>
                </div>
                <div class="field">
                  <label><i class="ti ti-grain"></i>{{ t("label.dither") }}</label>
                  <select>
                    <option selected>{{ t("option.ditherOff") }}</option>
                    <option>{{ t("option.ditherOn") }}</option>
                  </select>
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>

      <div class="hr"></div>
      <div class="field">
        <label><i class="ti ti-plug"></i>{{ t("label.engineDemo") }}</label>
        <div class="hint">{{ t("hint.engineDemoDesc") }}</div>
      </div>
      <div class="row">
        <div class="field">
          <label><i class="ti ti-photo"></i>{{ t("label.imagePath") }}</label>
          <input :value="bitmapImagePath" @input="$emit('update:bitmapImagePath', $event.target.value)" :placeholder="t('hint.imagePathPlaceholder')" />
        </div>
        <div class="field">
          <label><i class="ti ti-file"></i>{{ t("label.lutPath") }}</label>
          <input :value="bitmapLutPath" @input="$emit('update:bitmapLutPath', $event.target.value)" :placeholder="t('hint.lutPathPlaceholder')" />
          <div class="row" style="margin-top:8px">
            <button class="btn" @click="$emit('pickLut')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseLut") }}</button>
          </div>
        </div>
      </div>
      <div class="row row-adaptive">
        <div class="field">
          <label><i class="ti ti-arrows-horizontal"></i>{{ t("label.nozzleWidth") }}</label>
          <input :value="bitmapNozzle" @input="$emit('update:bitmapNozzle', $event.target.value)" type="number" step="0.01" />
        </div>
        <div class="field">
          <label><i class="ti ti-ruler"></i>{{ t("label.targetWidth") }}</label>
          <input :value="bitmapWidth" @input="$emit('update:bitmapWidth', $event.target.value)" type="number" step="1" />
        </div>
        <div class="field">
          <label><i class="ti ti-layers"></i>{{ t("label.layers") }}</label>
          <input :value="bitmapLayers" @input="$emit('update:bitmapLayers', $event.target.value)" type="number" step="1" />
        </div>
        <div class="field">
          <label><i class="ti ti-lambda"></i>{{ t("label.algo") }}</label>
          <select :value="bitmapAlgo" @change="$emit('update:bitmapAlgo', $event.target.value)">
            <option value="Standard">Standard</option>
            <option value="SDF (Smooth)">SDF (Smooth)</option>
          </select>
        </div>
      </div>
      <div class="row row-adaptive" v-if="bitmapAlgo === 'SDF (Smooth)'">
        <div class="field">
          <label><i class="ti ti-blur"></i>{{ t("label.sdfSmoothSigma") }}</label>
          <input :value="bitmapSdfSmoothSigma" @input="$emit('update:bitmapSdfSmoothSigma', $event.target.value)" type="number" step="0.1" />
        </div>
        <div class="field">
          <label><i class="ti ti-vector"></i>{{ t("label.sdfSimplifyEps") }}</label>
          <input :value="bitmapSdfSimplifyEps" @input="$emit('update:bitmapSdfSimplifyEps', $event.target.value)" type="number" step="0.001" />
        </div>
      </div>
      <div class="row row-adaptive">
        <div class="field">
          <label><i class="ti ti-scissors"></i>{{ t("label.autoBgRemove") }}</label>
          <select :value="bitmapAutoBgRemove" @change="$emit('update:bitmapAutoBgRemove', $event.target.value === 'true')">
            <option value="false">{{ t("option.off") }}</option>
            <option value="true">{{ t("option.on") }}</option>
          </select>
        </div>
        <div class="field" v-if="bitmapAutoBgRemove">
          <label><i class="ti ti-adjustments-horizontal"></i>{{ t("label.bgTol") }}</label>
          <input :value="bitmapBgTol" @input="$emit('update:bitmapBgTol', $event.target.value)" type="number" step="1" />
        </div>
        <div class="field">
          <label><i class="ti ti-contrast"></i>{{ t("label.alphaThreshold") }}</label>
          <input :value="bitmapAlphaThreshold" @input="$emit('update:bitmapAlphaThreshold', $event.target.value)" type="number" step="1" />
        </div>
      </div>
      <div class="row row-adaptive">
        <div class="field">
          <label><i class="ti ti-folder"></i>{{ t("label.outputDir") }}</label>
          <input :value="bitmapOutDir" @input="$emit('update:bitmapOutDir', $event.target.value)" :placeholder="t('hint.outputDirPlaceholder')" />
          <div class="row" style="margin-top:8px">
            <button class="btn" @click="$emit('pickOutDir')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseOutputDir") }}</button>
          </div>
        </div>
      </div>
      <div class="row">
        <button class="btn primary" @click="$emit('runBitmapExport')"><i class="ti ti-player-play"></i>{{ t("btn.bitmapExport") }}</button>
        <button class="btn ghost" @click="$emit('cancelBitmapExport')" v-if="bitmapJobId && bitmapProgress >= 0 && bitmapProgress < 1"><i class="ti ti-player-stop"></i>{{ t("btn.cancel") }}</button>
        <div class="hint" v-if="bitmapStatus">{{ bitmapStatus }}</div>
      </div>
      <div class="row" v-if="bitmapProgress >= 0">
        <div class="field" style="min-width:260px">
          <label><i class="ti ti-progress"></i>{{ t("label.progress") }}</label>
          <input :value="bitmapProgressText" readonly />
        </div>
        <div class="field">
          <label><i class="ti ti-activity"></i>{{ t("label.stage") }}</label>
          <input :value="bitmapStage" readonly />
        </div>
      </div>
      <div class="preview" v-if="bitmapPreview2dSrc" @wheel.prevent="$emit('bitmapPreviewWheel', $event)" @dblclick="$emit('resetBitmapPreviewScale')">
        <div class="badge"><i class="ti ti-photo"></i>{{ t("label.preview") }}</div>
        <div class="preview-container">
          <img :src="bitmapPreview2dSrc" :style="{ transform: `scale(${bitmapPreviewScale})`, transformOrigin: 'center center' }" />
        </div>
      </div>
      <div class="row" v-if="bitmapOutDir">
        <button class="btn" @click="$emit('openOutputDir', bitmapOutDir)"><i class="ti ti-folder"></i>{{ t("top.openOutput") }}</button>
      </div>
      <div class="row" v-if="bitmapStandard3mfName || bitmapBambu3mfName">
        <div class="field" style="flex:1">
          <label><i class="ti ti-file-3d"></i>{{ t("label.mf3Output") }}</label>
          <input :value="[bitmapStandard3mfName, bitmapBambu3mfName].filter(Boolean).join(' · ')" readonly />
        </div>
      </div>
      <div class="row" v-if="bitmapStandard3mfPath || bitmapBambu3mfPath">
        <button class="btn" v-if="bitmapStandard3mfPath" @click="$emit('openFile', t('label.standardMf3'), bitmapStandard3mfPath)"><i class="ti ti-file"></i>{{ t("label.standardMf3") }}</button>
        <button class="btn" v-if="bitmapBambu3mfPath" @click="$emit('openFile', t('label.bambuMf3'), bitmapBambu3mfPath)"><i class="ti ti-file"></i>{{ t("label.bambuMf3") }}</button>
        <button class="btn ghost" v-if="bitmapMetaPath" @click="$emit('openFile', 'meta.json', bitmapMetaPath)"><i class="ti ti-braces"></i>meta.json</button>
      </div>

      <div class="footerbar">
        <div class="kpis">
          <span class="pill"><i class="ti ti-layers-linked"></i>{{ t("label.estLayers") }} 6</span>
          <span class="pill"><i class="ti ti-arrows-exchange"></i>{{ t("label.estSwaps") }} 48</span>
          <span class="pill"><i class="ti ti-activity"></i>{{ t("label.estError") }} {{ t("status.low") }}</span>
        </div>
        <div class="row">
          <button class="btn" @click="$emit('openInSlicer')"><i class="ti ti-external-link"></i>{{ t("btn.openInSlicer") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 导入 Vue 响应式 API
import { computed, ref } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
const props = defineProps({
  active: Boolean,                  // 是否激活
  outputFormat: String,           // 输出格式
  outputDir: String,              // 输出目录
  wmm: Number,                   // 宽度（毫米）
  hmm: Number,                   // 高度（毫米）
  layers: Number,                // 层数
  selectedProfileKey: String,     // 选中的配置文件键
  bitmapImagePath: String,        // 位图图片路径
  bitmapLutPath: String,         // 位图 LUT 路径
  bitmapNozzle: Number,          // 位图喷嘴宽度
  bitmapWidth: Number,           // 位图宽度
  bitmapLayers: Number,           // 位图层数
  bitmapOutDir: String,          // 位图输出目录
  bitmapProgress: Number,         // 位图进度
  bitmapStage: String,           // 位图阶段
  bitmapStatus: String,          // 位图状态
  bitmapPreview2dSrc: String,    // 位图 2D 预览源
  bitmapStandard3mfPath: String, // 标准 3MF 路径
  bitmapBambu3mfPath: String,   // Bambu 3MF 路径
  bitmapMetaPath: String,        // 元数据路径
  bitmapJobId: String,           // 位图任务 ID
  bitmapPreviewScale: Number,    // 位图预览缩放比例
  bitmapAlgo: String,           // 位图算法
  bitmapSdfSmoothSigma: Number,  // SDF 平滑参数
  bitmapSdfSimplifyEps: Number, // SDF 简化参数
  bitmapAutoBgRemove: Boolean,   // 是否自动移除背景
  bitmapBgTol: Number,          // 背景容差
  bitmapAlphaThreshold: Number   // 透明度阈值
});

// 定义组件事件
defineEmits([
  "copyTips",
  "update:outputFormat",
  "pickOutputDir",
  "clearOutputDir",
  "update:wmm",
  "update:hmm",
  "update:layers",
  "goQuickCalib",
  "update:selectedProfileKey",
  "pickLut",
  "pickOutDir",
  "runBitmapExport",
  "cancelBitmapExport",
  "openOutputDir",
  "openFile",
  "openInSlicer",
  "bitmapPreviewWheel",
  "resetBitmapPreviewScale",
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
  "update:bitmapOutDir"
]);

// 可展开卡片折叠状态
const expandCollapsed = ref(false);

// 计算属性：标准 3MF 文件名
const bitmapStandard3mfName = computed(() => (props.bitmapStandard3mfPath ? props.bitmapStandard3mfPath.split(/[\\/]/).pop() : ""));

// 计算属性：Bambu 3MF 文件名
const bitmapBambu3mfName = computed(() => (props.bitmapBambu3mfPath ? props.bitmapBambu3mfPath.split(/[\\/]/).pop() : ""));

// 计算属性：位图进度文本
const bitmapProgressText = computed(() => {
  if (props.bitmapProgress < 0) return "";
  return `${Math.round(props.bitmapProgress * 100)}%`;
});
</script>
