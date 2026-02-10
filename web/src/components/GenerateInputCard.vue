<template>
  <div class="card" :class="{ active }">
    <div class="hd">
      <div style="display:flex; align-items:center; gap:8px">
        <i class="ti ti-file-import" style="opacity:0.6"></i>
        <h3>{{ t("sections.input") }}</h3>
      </div>
      <div class="row">
        <!-- 导入 SVG 按钮 -->
        <button class="btn" @click="$emit('setImported', 'svg')"><i class="ti ti-file-vector"></i>{{ t("btn.importSvg") }}</button>
        <!-- 导入 PNG 按钮 -->
        <button class="btn" @click="$emit('setImported', 'png')"><i class="ti ti-photo"></i>{{ t("btn.importPng") }}</button>
      </div>
    </div>
    <div class="bd">
      <!-- 预览区域 -->
      <div class="preview" :class="{ fullscreen: isPreviewFullscreen }" @wheel.prevent="$emit('previewWheel', $event)" @dblclick="handleResetPreview">
        <!-- 输入类型徽章 -->
        <div class="badge"><i class="ti ti-question-mark"></i>{{ inputTypeBadge }}</div>
        <!-- 预览工具栏 -->
        <div class="preview-toolbar" v-if="previewSrc">
          <div class="preview-hint">拖拽移动，滚轮缩放，双击重置</div>
          <div class="preview-actions">
            <button class="btn sm ghost" @click="handleResetPreview"><i class="ti ti-refresh"></i>重置</button>
            <button class="btn sm ghost" @click="togglePreviewFullscreen"><i class="ti ti-arrows-maximize"></i>{{ isPreviewFullscreen ? "退出全屏" : "全屏" }}</button>
            <!-- 预览切换按钮 -->
            <button v-if="hasProcessedPreview" class="btn sm ghost" @click="$emit('togglePreview')">
              <i class="ti ti-switch-2"></i>{{ previewToggleLabel }}
            </button>
          </div>
        </div>
        <div class="preview-container">
          <div v-if="previewSrc" class="preview-stage">
            <!-- Konva 画布包装器 -->
            <div ref="konvaWrapper" class="konva-wrapper">
              <v-stage :config="{ width: stageSize.width, height: stageSize.height }" @mousedown="handleStagePointerDown" @touchstart="handleStagePointerDown">
                <v-layer>
                  <!-- 图片组 -->
                  <v-group :x="stageCenter.x" :y="stageCenter.y" :scaleX="displayScale" :scaleY="displayScale">
                    <v-image v-if="overlayImage" :image="overlayImage" :x="imageRect.x" :y="imageRect.y" :width="imageRect.width" :height="imageRect.height" />
                  </v-group>
                </v-layer>
              </v-stage>
            </div>
          </div>
          <!-- 占位提示 -->
          <div class="ph" v-else>
            {{ t("label.previewPlaceholder") }}
            <small>{{ t("label.previewHint") }}</small>
          </div>
        </div>
      </div>
      <!-- 全屏背景遮罩 -->
      <div v-if="isPreviewFullscreen" class="preview-backdrop" @click="togglePreviewFullscreen"></div>

      <div class="hr"></div>

      <!-- 状态显示 -->
      <div class="status">
        <span class="pill ok"><i class="ti ti-check"></i>{{ t("status.supportOk") }}</span>
        <span class="pill warn"><i class="ti ti-color-swatch"></i>{{ t("status.bitmapQuantized") }}</span>
        <span class="pill"><i class="ti ti-ruler-2"></i>{{ t("status.dimensions") }}</span>
      </div>

      <div class="hr"></div>

      <!-- 输入设置 -->
      <div class="row">
        <div class="field">
          <label><i class="ti ti-alert-circle"></i>{{ t("label.importStatus") }}</label>
          <input :value="inputPath" :placeholder="t('hint.notSelected')" readonly />
          <div class="hint">{{ importStatusHint }}</div>
        </div>
        <div class="field">
          <label><i class="ti ti-category"></i>{{ t("label.inputType") }}</label>
          <select :value="inputKind" @change="$emit('update:inputKind', $event.target.value)">
            <option value="svg">{{ t("option.svg") }}</option>
            <option value="png">{{ t("option.png") }}</option>
            <option value="mixed">{{ t("option.mixed") }}</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 导入 Vue 响应式 API
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
const props = defineProps({
  active: Boolean,              // 是否激活
  inputKind: String,           // 输入类型
  inputPath: String,           // 输入路径
  previewSrc: String,          // 预览图片源
  previewScale: Number,        // 预览缩放比例
  hasProcessedPreview: Boolean, // 是否有处理后的预览
  previewToggleLabel: String   // 预览切换标签
});

// 定义组件事件
const emit = defineEmits(["setImported", "previewWheel", "resetPreviewScale", "togglePreview", "update:inputKind"]);

// Konva 状态管理
const konvaWrapper = ref(null);           // Konva 包装器引用
const stageSize = ref({ width: 0, height: 0 }); // 舞台尺寸
const overlayImage = ref(null);            // 覆盖图片
const overlaySize = ref({ width: 1000, height: 1000 }); // 覆盖尺寸
const panOffset = ref({ x: 0, y: 0 });   // 平移偏移
const panStart = ref({ x: 0, y: 0 });    // 平移起始点
const panBase = ref({ x: 0, y: 0 });     // 平移基准点
const isPanning = ref(false);             // 是否正在平移
const isPreviewFullscreen = ref(false);    // 是否全屏预览

let resizeObserver = null; // 尺寸观察器

// 计算属性：显示缩放比例
const displayScale = computed(() => {
  const v = Number(props.previewScale || 1);
  if (!Number.isFinite(v) || v <= 0) return 1;
  return v;
});

// 更新尺寸函数
const updateSize = (wrapper, sizeRef) => {
  if (wrapper.value) {
    sizeRef.value = {
      width: wrapper.value.offsetWidth,
      height: wrapper.value.offsetHeight
    };
  }
};

// 适配矩形函数：将图片适配到舞台中
const fitRect = (stage, image) => {
  if (!stage.width || !stage.height || !image.width || !image.height) {
    return { width: 100, height: 100 };
  }
  const ratio = Math.min(stage.width / image.width, stage.height / image.height) * 0.9;
  return {
    width: image.width * ratio,
    height: image.height * ratio
  };
};

// 计算属性：基础矩形尺寸
const baseRect = computed(() => fitRect(stageSize.value, overlaySize.value));

// 计算属性：舞台中心点
const stageCenter = computed(() => {
  return {
    x: stageSize.value.width / 2 + panOffset.value.x,
    y: stageSize.value.height / 2 + panOffset.value.y
  };
});

// 计算属性：图片矩形位置
const imageRect = computed(() => {
  return {
    x: -baseRect.value.width / 2,
    y: -baseRect.value.height / 2,
    width: baseRect.value.width,
    height: baseRect.value.height
  };
});

// 处理舞台指针按下事件
const handleStagePointerDown = (event) => {
  // 允许点击图片时也能触发平移
  startPan(event);
};

// 开始平移
const startPan = (e) => {
  if (!props.previewSrc) return;
  const evt = e?.evt || e;
  if (!evt) return;
  if (evt.button !== undefined && evt.button !== 0) return; // 只响应左键
  isPanning.value = true;
  panStart.value = { x: evt.clientX, y: evt.clientY };
  panBase.value = { ...panOffset.value };
  window.addEventListener('pointermove', handlePanMove);
  window.addEventListener('pointerup', stopPan);
};

// 处理平移移动
const handlePanMove = (e) => {
  if (!isPanning.value) return;
  const dx = e.clientX - panStart.value.x;
  const dy = e.clientY - panStart.value.y;
  panOffset.value = { x: panBase.value.x + dx, y: panBase.value.y + dy };
};

// 停止平移
const stopPan = () => {
  if (!isPanning.value) return;
  isPanning.value = false;
  window.removeEventListener('pointermove', handlePanMove);
  window.removeEventListener('pointerup', stopPan);
};

// 处理重置预览
const handleResetPreview = () => {
  panOffset.value = { x: 0, y: 0 };
  emit('resetPreviewScale');
};

// 切换全屏预览
const togglePreviewFullscreen = () => {
  isPreviewFullscreen.value = !isPreviewFullscreen.value;
  if (!isPreviewFullscreen.value) {
    handleResetPreview();
  }
};

// 加载覆盖图片
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
  };
  img.onerror = () => {
    console.error("预览图片加载失败", src);
    overlayImage.value = null;
  };
  img.src = src;
};

// 监听预览图片源变化
watch(() => props.previewSrc, (val) => {
  loadOverlayImage(val);
}, { immediate: true });

// 组件挂载时初始化
onMounted(() => {
  if (konvaWrapper.value) {
    updateSize(konvaWrapper, stageSize);
    resizeObserver = new ResizeObserver(() => updateSize(konvaWrapper, stageSize));
    resizeObserver.observe(konvaWrapper.value);
  }
});

// 组件卸载前清理
onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
  stopPan();
});

// 计算属性：导入状态提示
const importStatusHint = computed(() => {
  if (!props.inputPath) return t("hint.notSelected");
  return t("status.supportOk");
});

// 计算属性：输入类型徽章
const inputTypeBadge = computed(() => {
  if (!props.inputPath) return t("status.notImported");
  if (props.inputKind === "svg") return t("badge.svg");
  if (props.inputKind === "png") return t("badge.png");
  return t("badge.mixed");
});
</script>
