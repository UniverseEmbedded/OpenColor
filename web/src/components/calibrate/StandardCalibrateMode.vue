<template>
  <div>
    <!-- 资源库部分 -->
    <div class="library-section" v-if="libraryItems && libraryItems.length > 0">
      <div class="library-header">
        <h4><i class="ti ti-library"></i> 数据库资源</h4>
      </div>
      <div class="library-grid">
        <div class="library-group">
          <h5>最近照片</h5>
          <div class="library-items scroll-x">
            <div v-for="item in libraryItems.filter(i => i.kind === 'image')" :key="item.id" class="lib-item" @click="$emit('selectLibraryImage', item.path)">
              <div class="lib-name">{{ item.name }}</div>
              <div class="lib-meta">{{ new Date(item.ctime * 1000).toLocaleDateString() }}</div>
            </div>
          </div>
        </div>
        <div class="library-group">
          <h5>规格库</h5>
          <div class="library-items scroll-x">
            <div v-for="item in libraryItems.filter(i => i.kind === 'spec')" :key="item.id" class="lib-item" @click="$emit('selectLibrarySpec', item.path)">
              <div class="lib-name">{{ item.name }}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="hr"></div>
    </div>

    <!-- 步骤 -->
    <div class="steps">
      <div class="step">
        <b><i class="ti ti-circle-number-1"></i> {{ t("btn.genCalibStl") }}</b>
        <div class="sub">{{ t("hint.step1Desc") }}</div>
        <div style="margin-top:10px"><button class="btn" @click="$emit('showStlGenModal')"><i class="ti ti-file-download"></i>{{ t("btn.genCalibStl") }}</button></div>
      </div>
      <div class="step">
        <b><i class="ti ti-circle-number-2"></i> {{ t("btn.importPhoto") }}</b>
        <div class="sub">{{ t("hint.step2Desc") }}</div>
        <div style="margin-top:10px" class="row">
          <button class="btn" @click="$emit('importPhoto')"><i class="ti ti-photo-plus"></i>{{ t("btn.importPhoto") }}</button>
          <button class="btn" @click="$emit('manualQuad')"><i class="ti ti-focus-2"></i>{{ t("btn.autoDetectPoints") }}</button>
        </div>
      </div>
      <div class="step">
        <b><i class="ti ti-circle-number-3"></i> {{ t("btn.genProfile") }}</b>
        <div class="sub">{{ t("hint.step3Desc") }}</div>
        <div style="margin-top:10px"><button class="btn primary" @click="$emit('genProfile')"><i class="ti ti-checklist"></i>{{ t("btn.genProfile") }}</button></div>
      </div>
    </div>
    <div class="hr"></div>

    <!-- 色盘规格 -->
    <div class="field">
      <label><i class="ti ti-layout-board"></i>{{ t("label.boardSpecPath") }}</label>
      <input :value="boardSpecPath" @input="$emit('update:boardSpecPath', $event.target.value)" :placeholder="t('hint.boardSpecPlaceholder')" />
      <div class="row" style="margin-top:8px">
        <button class="btn" @click="$emit('pickBoardSpec')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseBoardSpec") }}</button>
        <button class="btn secondary" @click="$emit('pickBoardSpecToLibrary')"><i class="ti ti-plus"></i>导入到相册</button>
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label><i class="ti ti-id"></i>{{ t("label.boardSpecId") }}</label>
        <input :value="boardSpecId" readonly />
      </div>
      <div class="field">
        <label><i class="ti ti-tag"></i>{{ t("label.boardSpecName") }}</label>
        <input :value="boardSpecName" readonly />
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label><i class="ti ti-grid-pattern"></i>{{ t("label.boardSpecRows") }}</label>
        <input :value="boardSpecRows" readonly />
      </div>
      <div class="field">
        <label><i class="ti ti-grid-pattern"></i>{{ t("label.boardSpecCols") }}</label>
        <input :value="boardSpecCols" readonly />
      </div>
    </div>
    <div class="hr"></div>

    <!-- 校准照片 -->
    <div class="field">
      <label><i class="ti ti-photo"></i>{{ t("label.calibPhotoPath") }}</label>
      <input :value="lutPhotoPath" @input="$emit('update:lutPhotoPath', $event.target.value)" :placeholder="t('hint.calibPhotoPlaceholder')" />
      <div class="row" style="margin-top:8px">
        <button class="btn" @click="$emit('pickLutPhoto')"><i class="ti ti-folder-open"></i>{{ t("btn.choosePhoto") }}</button>
        <button class="btn secondary" @click="$emit('pickLutPhotoToLibrary')"><i class="ti ti-plus"></i>导入到相册</button>
      </div>
    </div>
    <div class="row">
      <div class="field" style="min-width:260px">
        <label><i class="ti ti-focus-2"></i>{{ t("label.cornerPointsJson") }}</label>
        <textarea :value="lutCornerPoints" @input="$emit('update:lutCornerPoints', $event.target.value)" rows="3"></textarea>
      </div>
      <div class="field">
        <label><i class="ti ti-ruler-2"></i>{{ t("label.outputDir") }}</label>
        <input :value="lutOutDir" @input="$emit('update:lutOutDir', $event.target.value)" :placeholder="t('hint.lutOutDirPlaceholder')" />
        <div class="row" style="margin-top:8px">
          <button class="btn" @click="$emit('pickLutOutDir')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseOutputDir") }}</button>
        </div>
      </div>
    </div>

    <!-- 参数调整 -->
    <div class="row row-adaptive">
      <div class="field">
        <label><i class="ti ti-zoom-in"></i>{{ t("label.zoom") }}</label>
        <input :value="lutZoom" @input="$emit('update:lutZoom', $event.target.value)" type="number" step="0.01" />
      </div>
      <div class="field">
        <label><i class="ti ti-bulb"></i>{{ t("label.barrel") }}</label>
        <input :value="lutBarrel" @input="$emit('update:lutBarrel', $event.target.value)" type="number" step="0.0001" />
      </div>
      <div class="field">
        <label><i class="ti ti-arrows-move"></i>{{ t("label.offsetX") }}</label>
        <input :value="lutOffsetX" @input="$emit('update:lutOffsetX', $event.target.value)" type="number" step="1" />
      </div>
      <div class="field">
        <label><i class="ti ti-arrows-move"></i>{{ t("label.offsetY") }}</label>
        <input :value="lutOffsetY" @input="$emit('update:lutOffsetY', $event.target.value)" type="number" step="1" />
      </div>
    </div>
    <div class="row row-adaptive">
      <div class="field">
        <label><i class="ti ti-wand"></i>{{ t("label.autoWb") }}</label>
        <select :value="lutAutoWb" @change="$emit('update:lutAutoWb', $event.target.value === 'true')">
          <option value="true">{{ t("option.ditherOn") }}</option>
          <option value="false">{{ t("option.ditherOff") }}</option>
        </select>
      </div>
      <div class="field">
        <label><i class="ti ti-brightness"></i>{{ t("label.vignetteFix") }}</label>
        <select :value="lutVignetteFix" @change="$emit('update:lutVignetteFix', $event.target.value === 'true')">
          <option value="true">{{ t("option.ditherOn") }}</option>
          <option value="false">{{ t("option.ditherOff") }}</option>
        </select>
      </div>
      <div class="field">
        <label><i class="ti ti-box"></i>{{ t("label.windowPx") }}</label>
        <input :value="lutWindowPx" @input="$emit('update:lutWindowPx', $event.target.value)" type="number" step="1" />
      </div>
    </div>
    <div class="row">
      <button class="btn primary" @click="$emit('runLutExtract')"><i class="ti ti-wand"></i>{{ t("btn.extractLut") }}</button>
      <div class="hint" v-if="lutStatus">{{ lutStatus }}</div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  libraryItems: {
    type: Array,
    default: () => []
  },
  boardSpecPath: String,
  boardSpecId: String,
  boardSpecName: String,
  boardSpecRows: Number,
  boardSpecCols: Number,
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
  lutStatus: String
});

defineEmits([
  'selectLibraryImage',
  'selectLibrarySpec',
  'showStlGenModal',
  'importPhoto',
  'manualQuad',
  'genProfile',
  'pickBoardSpec',
  'pickBoardSpecToLibrary',
  'pickLutPhoto',
  'pickLutPhotoToLibrary',
  'pickLutOutDir',
  'runLutExtract',
  'update:boardSpecPath',
  'update:lutPhotoPath',
  'update:lutCornerPoints',
  'update:lutOutDir',
  'update:lutZoom',
  'update:lutBarrel',
  'update:lutOffsetX',
  'update:lutOffsetY',
  'update:lutAutoWb',
  'update:lutVignetteFix',
  'update:lutWindowPx'
]);
</script>

<style scoped>
.library-section {
  margin-bottom: 16px;
}

.library-header h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px 0;
  font-size: 14px;
}

.library-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.library-group h5 {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: var(--muted);
}

.library-items {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.lib-item {
  flex-shrink: 0;
  background: var(--bg-alpha);
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  min-width: 120px;
}

.lib-item:hover {
  background: var(--bg-alpha2);
}

.lib-name {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-meta {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step {
  background: var(--bg-alpha);
  border-radius: 12px;
  padding: 16px;
}

.step b {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  margin-bottom: 8px;
}

.step .sub {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
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

.row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.row-adaptive {
  flex-wrap: wrap;
}

.row-adaptive .field {
  min-width: 140px;
}

.hr {
  height: 1px;
  background: var(--hr-color);
  margin: 16px 0;
}

.hint {
  font-size: 12px;
  color: var(--muted);
}
</style>
