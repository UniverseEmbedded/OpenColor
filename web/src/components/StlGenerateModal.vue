<template>
  <div class="modal" :class="{ show: isOpen }" role="dialog" aria-modal="true" aria-labelledby="stlGenTitle" @click.self="$emit('close')">
    <div class="box" style="width:min(720px, 95vw)">
      <div class="hd">
        <b id="stlGenTitle"><i class="ti ti-printer"></i> {{ t("modal.stlGenTitle") }}</b>
        <button class="btn" @click="$emit('close')"><i class="ti ti-x"></i>{{ t("btn.close") }}</button>
      </div>
      <div class="bd" style="max-height:70vh; overflow-y:auto">
        <div class="hint" style="margin-bottom:16px; padding:12px; background:var(--bg-alpha); border-radius:12px">
          <i class="ti ti-info-circle"></i> {{ t("hint.stlGenDesc") }}
        </div>

        <!-- 材料配置选择 -->
        <div class="field" style="margin-bottom:16px">
          <label><i class="ti ti-palette"></i>材料配置</label>
          <div class="row" style="gap:8px">
            <select v-model="selectedProfileId" style="flex:1" @change="handleProfileChange">
              <option value="">使用默认配置 (RYBW)</option>
              <option v-for="profile in profiles" :key="profile.id" :value="profile.id">
                {{ profile.name }} ({{ profile.slots?.length || profile.channelCount || 4 }}色)
              </option>
            </select>
            <button class="btn" @click="goToMaterials" title="管理材料配置">
              <i class="ti ti-settings"></i>
            </button>
          </div>
          <div class="sub" v-if="selectedProfile" style="margin-top:4px; font-size:12px; color:var(--muted)">
            已选择: {{ selectedProfile.name }} - {{ selectedProfile.slots?.length || selectedProfile.channelCount || 4 }} 种材料
          </div>
        </div>

        <div class="row row-adaptive" style="margin-bottom:12px">
          <div class="field">
            <label><i class="ti ti-grid-pattern"></i>{{ t("label.boardRows") }}</label>
            <input v-model.number="localParams.rows" type="number" min="1" max="30" step="1" />
          </div>
          <div class="field">
            <label><i class="ti ti-grid-pattern"></i>{{ t("label.boardCols") }}</label>
            <input v-model.number="localParams.cols" type="number" min="1" max="30" step="1" />
          </div>
        </div>

        <div class="row row-adaptive" style="margin-bottom:12px">
          <div class="field">
            <label><i class="ti ti-ruler-2"></i>{{ t("label.tileSizeMm") }}</label>
            <input v-model.number="localParams.tileSizeMm" type="number" min="3" max="20" step="0.5" />
          </div>
          <div class="field">
            <label><i class="ti ti-layers-difference"></i>{{ t("label.layers") }}</label>
            <input v-model.number="localParams.layers" type="number" min="1" max="10" step="1" />
          </div>
        </div>

        <div class="row row-adaptive" style="margin-bottom:12px">
          <div class="field">
            <label><i class="ti ti-arrow-bar-to-down"></i>{{ t("label.layerHeightMm") }}</label>
            <input v-model.number="localParams.layerHeightMm" type="number" min="0.08" max="0.4" step="0.04" />
          </div>
          <div class="field">
            <label><i class="ti ti-spacing-horizontal"></i>{{ t("label.shrink") }}</label>
            <input v-model.number="localParams.shrink" type="number" min="0" max="1" step="0.05" />
          </div>
        </div>

        <div class="field" style="margin-bottom:12px">
          <label><i class="ti ti-file-description"></i>{{ t("label.outputFileName") }}</label>
          <input v-model="localParams.fileName" :placeholder="t('hint.fileNamePlaceholder')" />
        </div>

        <!-- 导出格式选择 -->
        <div class="field" style="margin-bottom:16px">
          <label><i class="ti ti-file-export"></i>导出格式</label>
          <div class="row" style="gap:12px; flex-wrap:wrap">
            <label class="checkbox-label" style="display:flex; align-items:center; gap:6px; cursor:pointer">
              <input type="checkbox" v-model="localParams.exportFormats" value="3mf" />
              <span>3MF (推荐)</span>
            </label>
            <label class="checkbox-label" style="display:flex; align-items:center; gap:6px; cursor:pointer">
              <input type="checkbox" v-model="localParams.exportFormats" value="stl" />
              <span>STL (多文件)</span>
            </label>
          </div>
        </div>

        <div class="preview-box" style="margin-bottom:16px; padding:16px; background:var(--bg-alpha); border-radius:12px; text-align:center">
          <div style="font-size:12px; color:var(--muted); margin-bottom:8px">
            <i class="ti ti-eye"></i> {{ t("label.preview") }}
          </div>
          <div class="board-preview" :style="previewStyle">
            <div v-for="r in Math.min(localParams.rows, 17)" :key="r" class="preview-row">
              <div v-for="c in Math.min(localParams.cols, 17)" :key="c" class="preview-cell" :class="{ 'is-ellipsis': r > 16 || c > 16 }" :style="getCellStyle(r-1, c-1)">
                <span v-if="r <= 16 && c <= 16">{{ getCellLabel(r-1, c-1) }}</span>
                <span v-else>...</span>
              </div>
            </div>
            <div v-if="localParams.rows > 17 || localParams.cols > 17" class="preview-more">
              +{{ localParams.rows > 17 ? localParams.rows - 17 : 0 }}×{{ localParams.cols > 17 ? localParams.cols - 17 : 0 }}
            </div>
          </div>
          <div style="font-size:11px; color:var(--muted); margin-top:8px">
            {{ localParams.rows }}×{{ localParams.cols }} = {{ localParams.rows * localParams.cols }} {{ t("label.cells") }}
            <span v-if="selectedProfile">({{ selectedProfile.slots?.length || selectedProfile.channelCount || 4 }}色材料)</span>
          </div>
        </div>

        <div class="row" style="justify-content:flex-end; margin-top:16px; padding-top:16px; border-top:1px solid var(--hr-color)">
          <button class="btn" @click="resetParams"><i class="ti ti-refresh"></i>{{ t("btn.reset") }}</button>
          <button class="btn primary" @click="generate" :disabled="isGenerating || !hasValidExportFormat">
            <i class="ti" :class="isGenerating ? 'ti-loader-2 ti-spin' : 'ti-file-download'"></i>
            {{ isGenerating ? t("btn.generating") : t("btn.generate") }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  isOpen: Boolean,
  isGenerating: Boolean,
  profiles: {
    type: Array,
    default: () => []
  },
  defaultParams: {
    type: Object,
    default: () => ({
      // 参考 generate_8color_board.py 的默认参数
      rows: 15,           // DATA_ROWS = 15
      cols: 15,           // DATA_COLS = 15
      tileSizeMm: 6.0,    // DEFAULT_CELL_SIZE = 6.0
      layerHeightMm: 0.12, // DEFAULT_LAYER_HEIGHT = 0.12
      layers: 5,          // DEFAULT_LAYERS = 5
      shrink: 0.0,        // DEFAULT_SHRINK = 0.0
      fileName: "",
      exportFormats: ["3mf"]
    })
  }
});

const emit = defineEmits(['close', 'generate', 'goToMaterials']);

const localParams = ref({ ...props.defaultParams });
const selectedProfileId = ref("");

// 监听弹窗打开，重置参数
watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    localParams.value = { ...props.defaultParams };
    selectedProfileId.value = "";
  }
});

// 计算选中的配置
const selectedProfile = computed(() => {
  if (!selectedProfileId.value) return null;
  return props.profiles.find(p => p.id === selectedProfileId.value) || null;
});

// 计算是否有有效的导出格式
const hasValidExportFormat = computed(() => {
  return localParams.value.exportFormats && localParams.value.exportFormats.length > 0;
});

// 获取材料颜色用于预览
const getMaterialColor = (index) => {
  const profile = selectedProfile.value;
  const slots = profile?.slots || [];
  if (slots.length === 0) {
    // 默认颜色
    const defaultColors = [
      [245, 245, 245], // White
      [25, 25, 25],    // Black
      [230, 70, 70],   // Red
      [70, 210, 120],  // Green
      [80, 140, 240],  // Blue
      [70, 210, 210],  // Cyan
      [220, 90, 210],  // Magenta
      [240, 210, 90],  // Yellow
    ];
    return defaultColors[index % defaultColors.length];
  }
  const slot = slots[index % slots.length];
  const mat = slot?.filament;
  if (mat && mat.rgba) {
    return [mat.rgba[0], mat.rgba[1], mat.rgba[2]];
  }
  return [200, 200, 200];
};

// 计算单元格样式（根据材料颜色）
const getCellStyle = (row, col) => {
  // 根据行列计算材料索引
  const profile = selectedProfile.value;
  const materialCount = profile?.slots?.length || profile?.channelCount || 4;

  // 简化的颜色分配逻辑
  let colorIndex = 0;
  if (row === 0 && col === 0) colorIndex = 1 % materialCount;
  else if (row === 0 && col === localParams.value.cols - 1) colorIndex = 2 % materialCount;
  else if (row === localParams.value.rows - 1 && col === localParams.value.cols - 1) colorIndex = 3 % materialCount;
  else if (row === localParams.value.rows - 1 && col === 0) colorIndex = 0;
  else {
    // 内部格子根据位置分配颜色
    const dataRow = row - 1;
    const dataCol = col - 1;
    if (dataRow >= 0 && dataCol >= 0 && dataRow < localParams.value.rows - 2 && dataCol < localParams.value.cols - 2) {
      colorIndex = (dataRow + dataCol) % materialCount;
    } else {
      colorIndex = 0; // 边框默认白色
    }
  }

  const rgb = getMaterialColor(colorIndex);
  return {
    background: `rgba(${rgb.join(',')}, 0.85)`
  };
};

const previewStyle = computed(() => {
  const gap = 1;
  return {
    display: 'inline-flex',
    flexDirection: 'column',
    gap: `${gap}px`,
    padding: '6px',
    background: '#f0f0f0',
    borderRadius: '6px',
    maxWidth: '100%',
    overflow: 'auto'
  };
});

const getCellLabel = (row, col) => {
  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  return `${letters[col] || '?'}${row + 1}`;
};

const resetParams = () => {
  localParams.value = { ...props.defaultParams };
  selectedProfileId.value = "";
};

const handleProfileChange = () => {
  // 当选择配置时，可以根据配置的材料数量调整一些参数
  const profile = selectedProfile.value;
  if (profile && profile.slots) {
    console.log("选择材料配置:", profile.name, "材料数:", profile.slots.length);
  }
};

const goToMaterials = () => {
  emit('goToMaterials');
  emit('close');
};

const generate = () => {
  // 构建生成参数
  const profile = selectedProfile.value;
  const materials = profile?.slots?.map(slot => {
    const filament = slot?.filament;
    return filament ? {
      name: filament.name,
      rgba: filament.rgba
    } : null;
  }).filter(Boolean) || null;

  const params = {
    ...localParams.value,
    // 如果选择了材料配置，传递 materials
    materials: materials,
    profileId: selectedProfileId.value || null,
    profileName: profile?.name || null
  };

  // 转换字段名以匹配引擎期望的格式
  const engineParams = {
    rows: params.rows,
    cols: params.cols,
    tileSizeMm: params.tileSizeMm,
    tile_size_mm: params.tileSizeMm,
    layerHeightMm: params.layerHeightMm,
    layer_height_mm: params.layerHeightMm,
    layers: params.layers,
    n_layers: params.layers,
    shrink: params.shrink,
    fileName: params.fileName,
    file_name: params.fileName,
    materials: params.materials,
    export_formats: params.exportFormats,
    exportFormats: params.exportFormats,
  };

  emit('generate', engineParams);
};
</script>

<style scoped>
.board-preview {
  display: inline-flex;
  flex-direction: column;
}

.preview-row {
  display: flex;
  gap: 1px;
}

.preview-cell {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 3px;
  font-size: 8px;
  font-weight: 600;
  color: #333;
  transition: background-color 0.2s;
}

.preview-cell.is-ellipsis {
  background: rgba(200, 200, 200, 0.5);
  color: #666;
}

.preview-more {
  margin-top: 4px;
  font-size: 10px;
  color: var(--muted);
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}
</style>
