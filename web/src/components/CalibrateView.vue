<template>
  <section class="view oc-edge">
    <ScreenCalibrator 
      :visible="showScreenCalibrator" 
      @close="showScreenCalibrator = false" 
    />
    <StlGenerateModal
      :is-open="showStlGenModal"
      :is-generating="isGeneratingStl"
      :profiles="materialGroups"
      @close="showStlGenModal = false"
      @generate="handleStlGenerate"
      @goToMaterials="$emit('goToMaterials')"
    />
    <div class="grid single oc-edge">
      <div class="card active">
        <div class="hd">
          <div style="display:flex; align-items:center; gap:8px">
            <i class="ti ti-camera" style="opacity:0.6"></i>
            <h3>{{ t("label.calibMode") }}</h3>
          </div>
          <div class="modebar">
            <button class="toggle" :class="{ active: calibrateMode === 'board' }" @click="calibrateMode = 'board'"><i class="ti ti-border-outer"></i>{{ t("option.standardMode") }}</button>
            <button class="toggle" :class="{ active: calibrateMode === 'quick' }" @click="calibrateMode = 'quick'"><i class="ti ti-bolt"></i>{{ t("option.quickMode") }}</button>
          </div>
          <div class="row" style="margin-top:8px">
            <button class="btn ghost" style="margin-left:auto" @click="$emit('useDemoPhoto')"><i class="ti ti-player-play"></i>{{ t("btn.useDemoPhoto") }}</button>
          </div>
        </div>
        <div class="bd">
          <!-- 快速校准模式 -->
          <QuickCalibrateMode
            v-show="calibrateMode === 'quick'"
            @genQuickCalibStl="$emit('genQuickCalibStl')"
            @showScreenCalibrator="showScreenCalibrator = true"
            @importPhoto="$emit('importPhoto')"
            @genProfile="$emit('genProfile')"
            @saveProfile="$emit('saveProfile')"
          />

          <!-- 标准校准模式 -->
          <div v-show="calibrateMode === 'board'">
            <StandardCalibrateMode
              :library-items="libraryItems"
              :board-spec-path="boardSpecPath"
              :board-spec-id="boardSpecId"
              :board-spec-name="boardSpecName"
              :board-spec-rows="boardSpecRows"
              :board-spec-cols="boardSpecCols"
              :lut-photo-path="lutPhotoPath"
              :lut-corner-points="lutCornerPoints"
              :lut-out-dir="lutOutDir"
              :lut-zoom="lutZoom"
              :lut-barrel="lutBarrel"
              :lut-offset-x="lutOffsetX"
              :lut-offset-y="lutOffsetY"
              :lut-auto-wb="lutAutoWb"
              :lut-vignette-fix="lutVignetteFix"
              :lut-window-px="lutWindowPx"
              :lut-status="lutStatus"
              @selectLibraryImage="$emit('update:lutPhotoPath', $event)"
              @selectLibrarySpec="$emit('update:boardSpecPath', $event)"
              @showStlGenModal="showStlGenModal = true"
              @importPhoto="$emit('importPhoto')"
              @manualQuad="$emit('manualQuad')"
              @genProfile="$emit('genProfile')"
              @pickBoardSpec="$emit('pickBoardSpec')"
              @pickBoardSpecToLibrary="$emit('pickBoardSpecToLibrary')"
              @pickLutPhoto="$emit('pickLutPhoto')"
              @pickLutPhotoToLibrary="$emit('pickLutPhotoToLibrary')"
              @pickLutOutDir="$emit('pickLutOutDir')"
              @runLutExtract="$emit('runLutExtract')"
              @update:boardSpecPath="$emit('update:boardSpecPath', $event)"
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
            />

            <!-- 预览区域 -->
            <div class="preview" :class="{ fullscreen: isPreviewFullscreen }" @wheel.prevent="$emit('lutPreviewWheel', $event)" @dblclick="resetPreviewView">
              <div class="badge"><i class="ti ti-eye"></i>{{ t("label.calibPreview") }}</div>
              <div class="preview-toolbar">
                <div class="preview-hint">拖拽移动，滚轮缩放，双击重置</div>
                <div class="preview-actions">
                  <button class="btn sm ghost" @click="resetPreviewView"><i class="ti ti-refresh"></i>重置</button>
                  <button class="btn sm ghost" @click="togglePreviewFullscreen"><i class="ti ti-arrows-maximize"></i>{{ isPreviewFullscreen ? "退出全屏" : "全屏" }}</button>
                </div>
              </div>
              <div class="ph" v-if="!lutOverlaySrc">{{ t("hint.calibPh") }}
                <small>{{ t("hint.calibPhSmall") }}</small>
              </div>
              <div class="preview-container">
                <div v-if="lutOverlaySrc" class="preview-stage">
                  <div ref="konvaWrapper" class="konva-wrapper">
                    <v-stage :config="{ width: stageSize.width, height: stageSize.height }" @mousedown="handleStagePointerDown" @touchstart="handleStagePointerDown">
                      <v-layer>
                        <v-group :x="stageCenter.x" :y="stageCenter.y" :scaleX="lutScale" :scaleY="lutScale">
                          <v-image v-if="overlayImage" :image="overlayImage" :x="imageRect.x" :y="imageRect.y" :width="imageRect.width" :height="imageRect.height" />
                          <v-line v-if="quadLinePoints.length" :points="quadLinePoints" :closed="true" :fill="'rgba(0, 255, 0, 0.12)'" :stroke="'#00ff00'" :strokeWidth="2" :dash="[6, 4]" />
                          <v-circle v-for="diag in mappedDiagnostics" :key="diag.key" :x="diag.x" :y="diag.y" :radius="7" :fill="diag.color" @mouseenter="updateProbeResult(diag.key)" />
                          <v-circle v-for="(p, i) in mappedPoints" :key="`handle-${i}`" :x="p.x" :y="p.y" :radius="activeHandle === i ? 10 : 7" :fill="activeHandle === i ? '#ffffff' : '#00ff00'" :stroke="activeHandle === i ? '#00ff00' : '#ffffff'" :strokeWidth="2" :draggable="true" @dragstart="handleHandleDragStart(i)" @dragmove="handleHandleDragMove(i, $event)" @dragend="handleHandleDragEnd" />
                          <v-circle v-if="mappedProbePos" :x="mappedProbePos.x" :y="mappedProbePos.y" :radius="15" :stroke="'#00ff00'" :strokeWidth="2" :dash="[4, 4]" />
                        </v-group>
                      </v-layer>
                    </v-stage>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="isPreviewFullscreen" class="preview-backdrop" @click="togglePreviewFullscreen"></div>
            <div class="preview-grid">
              <div class="preview preview-sm">
                <div class="badge"><i class="ti ti-photo"></i>校准照片</div>
                <div class="ph" v-if="!lutPhotoSrc">暂无校准照片</div>
                <div class="preview-container">
                  <img v-if="lutPhotoSrc" :src="lutPhotoSrc" />
                </div>
              </div>
              <div class="preview preview-sm">
                <div class="badge"><i class="ti ti-transform"></i>透视矫正结果</div>
                <div class="ph" v-if="!lutWarpedSrc">暂无提取结果</div>
                <div class="preview-container">
                  <img v-if="lutWarpedSrc" :src="lutWarpedSrc" />
                </div>
              </div>
              <div class="preview preview-sm">
                <div class="badge"><i class="ti ti-activity"></i>MCRT 诊断预览</div>
                <div class="ph" v-if="!lutOverlaySrc || diagnosticsList.length === 0">暂无诊断结果</div>
                <div class="preview-container">
                  <div v-if="lutOverlaySrc" class="preview-stage">
                    <div ref="miniKonvaWrapper" class="konva-wrapper">
                      <v-stage :config="{ width: miniStageSize.width, height: miniStageSize.height }">
                        <v-layer>
                          <v-group :x="miniStageCenter.x" :y="miniStageCenter.y">
                            <v-image v-if="overlayImage" :image="overlayImage" :x="miniImageRect.x" :y="miniImageRect.y" :width="miniImageRect.width" :height="miniImageRect.height" />
                            <v-circle v-for="diag in mappedDiagnosticsMini" :key="diag.key" :x="diag.x" :y="diag.y" :radius="6" :fill="diag.color" />
                          </v-group>
                        </v-layer>
                      </v-stage>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="row">
              <div class="field">
                <label><i class="ti ti-target"></i>{{ t("label.probeCell") }}</label>
                <input :value="probeCellId" readonly />
              </div>
              <div class="field">
                <label><i class="ti ti-color-picker"></i>{{ t("label.probeMeasuredRgb") }}</label>
                <input :value="probeMeasuredRgb" readonly />
              </div>
              <div class="field">
                <label><i class="ti ti-color-swatch"></i>{{ t("label.probeSimRgb") }}</label>
                <input :value="probeSimRgb" readonly />
              </div>
              <div class="field">
                <label><i class="ti ti-alert-triangle"></i>{{ t("label.probeError") }}</label>
                <input :value="probeError" readonly />
              </div>
            </div>
            <div class="hr"></div>
            <div class="row">
              <div class="field">
                <label><i class="ti ti-report-analytics"></i>{{ t("label.fitSummary") }}</label>
                <input :value="lutResultSummary" readonly />
              </div>
              <div class="field">
                <label><i class="ti ti-file-code"></i>{{ t("label.outputFile") }}</label>
                <input :value="lutResultFile" readonly />
              </div>
            </div>
            <div class="row" style="margin-top:8px">
              <button class="btn"><i class="ti ti-device-floppy"></i>{{ t("btn.saveProfile") }}</button>
              <button class="btn"><i class="ti ti-wand"></i>{{ t("btn.useInGenerate") }}</button>
            </div>
            <div class="hr"></div>

            <!-- 数据集管理 -->
            <div class="row">
              <div class="field">
                <label><i class="ti ti-folder"></i>{{ t("label.datasetOutDir") }}</label>
                <input :value="datasetOutDir" @input="$emit('update:datasetOutDir', $event.target.value)" :placeholder="t('hint.datasetOutDirPlaceholder')" />
                <div class="row" style="margin-top:8px">
                  <button class="btn" @click="$emit('pickDatasetOutDir')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseDatasetOutDir") }}</button>
                </div>
              </div>
              <div class="field">
                <label><i class="ti ti-database"></i>{{ t("label.datasetId") }}</label>
                <input :value="datasetId" @input="$emit('update:datasetId', $event.target.value)" :placeholder="t('hint.datasetIdPlaceholder')" />
              </div>
            </div>
            <div class="row">
              <div class="field">
                <label><i class="ti ti-file-text"></i>{{ t("label.observationPath") }}</label>
                <input :value="datasetObservationPath" @input="$emit('update:datasetObservationPath', $event.target.value)" :placeholder="t('hint.observationPlaceholder')" />
                <div class="row" style="margin-top:8px">
                  <button class="btn" @click="$emit('pickObservation')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseObservation") }}</button>
                </div>
              </div>
              <div class="field">
                <label><i class="ti ti-status-change"></i>{{ t("label.datasetStatus") }}</label>
                <input :value="datasetStatus" readonly />
              </div>
            </div>
            <div class="row">
              <button class="btn" @click="$emit('runDatasetCreate')"><i class="ti ti-database-plus"></i>{{ t("btn.createDataset") }}</button>
              <button class="btn" @click="$emit('runDatasetAddObservation')"><i class="ti ti-file-plus"></i>{{ t("btn.addObservation") }}</button>
              <button class="btn primary" @click="$emit('runDatasetAggregate')"><i class="ti ti-merge"></i>{{ t("btn.aggregateDataset") }}</button>
            </div>
            <div class="row">
              <div class="field">
                <label><i class="ti ti-list-check"></i>{{ t("label.datasetObsCount") }}</label>
                <input :value="datasetObsCount" readonly />
              </div>
              <div class="field">
                <label><i class="ti ti-layout-board"></i>{{ t("label.datasetBoardCount") }}</label>
                <input :value="datasetBoardCount" readonly />
              </div>
            </div>
            <div class="row">
              <div class="field">
                <label><i class="ti ti-file-analytics"></i>{{ t("label.datasetSummary") }}</label>
                <input :value="datasetSummaryPath" readonly />
              </div>
            </div>
            <div class="hr"></div>

            <!-- MCRT 验证 -->
            <div class="row row-adaptive">
              <div class="field">
                <label><i class="ti ti-cpu"></i>{{ t("label.mcrtBackend") }}</label>
                <input :value="mcrtBackend" @input="$emit('update:mcrtBackend', $event.target.value)" />
              </div>
              <div class="field">
                <label><i class="ti ti-atom"></i>{{ t("label.mcrtSamples") }}</label>
                <input :value="mcrtSamples" @input="$emit('update:mcrtSamples', $event.target.value)" type="number" step="1" />
              </div>
              <div class="field">
                <label><i class="ti ti-layers-intersect"></i>{{ t("label.mcrtLayerHeight") }}</label>
                <input :value="mcrtLayerHeight" @input="$emit('update:mcrtLayerHeight', $event.target.value)" type="number" step="0.01" />
              </div>
              <div class="field">
                <label><i class="ti ti-contrast"></i>{{ t("label.mcrtBackingAlbedo") }}</label>
                <input :value="mcrtBackingAlbedo" @input="$emit('update:mcrtBackingAlbedo', $event.target.value)" type="number" step="0.01" />
              </div>
            </div>
            <div class="row row-adaptive">
              <div class="field">
                <label><i class="ti ti-palette"></i>{{ t("label.mcrtColorSystem") }}</label>
                <input :value="mcrtColorSystem" @input="$emit('update:mcrtColorSystem', $event.target.value)" />
              </div>
              <div class="field">
                <label><i class="ti ti-report-analytics"></i>{{ t("label.mcrtAvgError") }}</label>
                <input :value="mcrtAvgError" readonly />
              </div>
              <div class="field">
                <label><i class="ti ti-activity"></i>{{ t("label.mcrtStatus") }}</label>
                <input :value="mcrtStatus" readonly />
              </div>
            </div>
            <div class="row">
              <button class="btn primary" @click="$emit('runMcrtValidate')"><i class="ti ti-beaker"></i>{{ t("btn.runMcrtValidate") }}</button>
              <div class="hint" v-if="mcrtStatus">{{ mcrtStatus }}</div>
            </div>
            <div class="row">
              <div class="field">
                <label><i class="ti ti-file-search"></i>{{ t("label.mcrtDiagnosticsPath") }}</label>
                <input :value="mcrtDiagnosticsPath" readonly />
              </div>
            </div>
            <div class="field">
              <label><i class="ti ti-code"></i>{{ t("label.mcrtDiagnostics") }}</label>
              <textarea :value="mcrtDiagnosticsText" rows="6" readonly></textarea>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
// 导入 Vue 响应式 API
import { ref } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";
// 导入子组件
import ScreenCalibrator from "./ScreenCalibrator.vue";
import StlGenerateModal from "./StlGenerateModal.vue";
import QuickCalibrateMode from "./calibrate/QuickCalibrateMode.vue";
import StandardCalibrateMode from "./calibrate/StandardCalibrateMode.vue";
// 导入校准组合式函数
import { useCalibrate } from "../composables/useCalibrate";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
const props = defineProps({
  bitmapPreviewScale: Number,
  lutPhotoPath: String,
  lutCornerPoints: String,
  lutOutDir: String,
  lutZoom: Number,
  lutBarrel: Number,
  lutOffsetX: Number,
  lutOffsetY: Number,
  lutAutoWb: Boolean,
  lutVignetteFix: Boolean,
  lutWindowPx: Number,
  lutStatus: String,
  lutOverlaySrc: String,
  lutPhotoSrc: String,
  lutWarpedSrc: String,
  lutResultSummary: String,
  lutResultFile: String,
  lutPreviewScale: Number,
  boardSpecPath: String,
  boardSpecId: String,
  boardSpecName: String,
  boardSpecRows: Number,
  boardSpecCols: Number,
  datasetId: String,
  datasetOutDir: String,
  datasetObservationPath: String,
  datasetObsCount: Number,
  datasetBoardCount: Number,
  datasetSummaryPath: String,
  datasetStatus: String,
  mcrtSamples: Number,
  mcrtBackend: String,
  mcrtLayerHeight: Number,
  mcrtBackingAlbedo: Number,
  mcrtColorSystem: String,
  mcrtAvgError: String,
  mcrtDiagnosticsPath: String,
  mcrtDiagnostics: Object,
  mcrtStatus: String,
  gridRows: Number,
  gridCols: Number,
  gridDataRows: Number,
  gridDataCols: Number,
  gridBorder: Number,
  libraryItems: {
    type: Array,
    default: () => []
  },
  materialGroups: {
    type: Array,
    default: () => []
  }
});

// 定义组件事件
const emit = defineEmits(['pingEngine', 'importPhoto', 'importPhotoToLibrary', 'genProfile', 'saveProfile', 'genCalibStl', 'manualQuad', 'pickLutPhoto', 'pickLutPhotoToLibrary', 'pickLutOutDir', 'pickBoardSpec', 'pickBoardSpecToLibrary', 'pickObservation', 'pickDatasetOutDir', 'runLutExtract', 'runDatasetCreate', 'runDatasetAddObservation', 'runDatasetAggregate', 'runMcrtValidate', 'lutPreviewWheel', 'resetLutPreviewScale', 'useDemoPhoto', 'update:lutPhotoPath', 'update:lutCornerPoints', 'update:lutOutDir', 'update:lutZoom', 'update:lutBarrel', 'update:lutOffsetX', 'update:lutOffsetY', 'update:lutAutoWb', 'update:lutVignetteFix', 'update:lutWindowPx', 'update:boardSpecPath', 'update:datasetId', 'update:datasetOutDir', 'update:datasetObservationPath', 'update:mcrtSamples', 'update:mcrtBackend', 'update:mcrtLayerHeight', 'update:mcrtBackingAlbedo', 'update:mcrtColorSystem', 'goToMaterials', 'genQuickCalibStl']);

// 使用校准组合式函数
const {
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
  mcrtDiagnosticsText,
  updateProbeResult,
  handleHandleDragStart,
  handleHandleDragMove,
  handleHandleDragEnd,
  handleStagePointerDown,
  resetPreviewView,
  togglePreviewFullscreen
} = useCalibrate(props, emit);

// 屏幕校准器显示状态
const showScreenCalibrator = ref(false);

// STL 生成模态框状态
const showStlGenModal = ref(false);
const isGeneratingStl = ref(false);

// 处理 STL 生成
const handleStlGenerate = async (params) => {
  isGeneratingStl.value = true;
  try {
    // 将参数传递给父组件进行实际生成
    emit('genCalibStl', params);
  } finally {
    isGeneratingStl.value = false;
    showStlGenModal.value = false;
  }
};
</script>

<style scoped>
.view {
  padding: 16px;
}

.grid {
  display: grid;
  gap: 16px;
}

.card {
  background: var(--panel);
  border-radius: 16px;
  overflow: hidden;
}

.card .hd {
  padding: 16px;
  border-bottom: 1px solid var(--line);
}

.card .hd h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.card .bd {
  padding: 16px;
}

.modebar {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
}

.toggle.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.row-adaptive {
  flex-wrap: wrap;
}

.field {
  flex: 1;
  min-width: 0;
}

.field label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
}

.field input,
.field textarea,
.field select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
}

.field textarea {
  resize: vertical;
}

.hr {
  height: 1px;
  background: var(--hr-color);
  margin: 16px 0;
}

/* 预览区域样式 */
.preview {
  position: relative;
  background: var(--bg-alpha);
  border-radius: 12px;
  overflow: hidden;
  margin: 16px 0;
}

.preview.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  border-radius: 0;
  margin: 0;
}

.preview-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}

.badge {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--bg);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  z-index: 10;
}

.preview-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 10;
}

.preview-hint {
  font-size: 12px;
  color: var(--muted);
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.ph {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: var(--muted);
  font-size: 14px;
}

.ph small {
  font-size: 12px;
  margin-top: 4px;
}

.preview-container {
  padding: 16px;
}

.preview-stage {
  width: 100%;
  height: 100%;
}

.konva-wrapper {
  width: 100%;
  height: 100%;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 16px;
}

.preview-sm {
  min-height: 150px;
}

.preview-sm .preview-container {
  padding: 8px;
}

.preview-sm img {
  max-width: 100%;
  max-height: 120px;
  object-fit: contain;
}

.hint {
  font-size: 12px;
  color: var(--muted);
}
</style>
