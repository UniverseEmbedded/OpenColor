<template>
  <div class="modal" :class="{ show: isOpen && item }" role="dialog" aria-modal="true" aria-labelledby="fileDetailTitle" @click.self="$emit('close')">
    <div class="box" :style="boxStyle">
      <div class="hd">
        <b id="fileDetailTitle">
          <i :class="fileIcon"></i> 
          {{ fileTitle }}
        </b>
        <button class="btn" @click="$emit('close')"><i class="ti ti-x"></i>{{ t("btn.close") }}</button>
      </div>
      <div class="bd" style="max-height:70vh; overflow-y:auto">
        <div v-if="!item" class="state-msg">
          <p>{{ t("status.noFileSelected") }}</p>
        </div>
        
        <template v-else>
          <div class="file-header" style="margin-bottom:16px; padding:12px; background:var(--bg-alpha); border-radius:12px">
            <div class="file-name" style="font-size:16px; font-weight:600; margin-bottom:8px; word-break:break-all">
              {{ item.name }}
            </div>
            <div class="file-meta" style="display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:var(--muted)">
              <span><i class="ti ti-file"></i> {{ fileTypeLabel }}</span>
              <span v-if="fileSize"><i class="ti ti-weight"></i> {{ fileSize }}</span>
              <span><i class="ti ti-calendar"></i> {{ formatDate(item.ctime) }}</span>
              <span v-if="item.path"><i class="ti ti-folder"></i> {{ getFolderName(item.path) }}</span>
            </div>
          </div>
          
          <div class="file-content">
            <!-- 图片预览 -->
            <ImagePreview
              v-if="isImage && isPathReady"
              :image-src="imageSrc"
              :alt="item.name"
              :loading="imageLoading"
              :loading-text="t('status.loading')"
              :error-text="imageErrorText"
              @error="handleImageError"
            />

            <!-- 色盘预览图 -->
            <div v-else-if="hasPreview && isPathReady" class="image-preview">
              <div class="preview-label" style="margin-bottom:8px; font-size:12px; color:var(--muted)">
                <i class="ti ti-photo"></i> {{ t("label.boardPreview") || "色盘预览" }}
              </div>
              <ImagePreview
                :image-src="previewSrc"
                :alt="item.name"
                :loading="previewLoading"
                :loading-text="t('status.loadingPreview') || '加载预览图...'"
                :error-text="previewErrorText"
                @error="handleImageError"
              />
            </div>

            <!-- 加载中 -->
            <div v-else-if="(isImage || hasPreview) && !isPathReady" class="loading-preview">
              <i class="ti ti-loader-2 ti-spin"></i> {{ t("status.loading") || "加载中..." }}
            </div>

            <!-- 3D模型预览 -->
            <ModelPreview
              v-else-if="is3DModel"
              :file-path="imageAbsPath"
              :file-name="item.name"
              :file-data="modelData"
              :model-info="modelInfo"
              :loading="modelLoading"
              :error-text="modelErrorText"
            />
            
            <!-- 文本预览 -->
            <div v-else-if="isText" class="text-preview">
              <!-- 色盘规格 JSON -->
              <BoardSpecPreview
                v-if="isBoardSpecJson && boardSpec"
                :board-spec="boardSpec"
                :raw-content="textContent"
              />

              <!-- 普通 JSON -->
              <div v-else-if="isGenericJson && parsedJson" class="json-structured">
                <div class="json-header">
                  <div class="json-title">
                    <i class="ti ti-file-code"></i>
                    <span>JSON 数据</span>
                  </div>
                  <div class="json-meta">
                    <span class="pill"><i class="ti ti-braces"></i>{{ jsonKeyCount }} 个键</span>
                    <span class="pill"><i class="ti ti-list"></i>{{ jsonType }}</span>
                  </div>
                </div>
                
                <div class="json-content">
                  <JsonTree :data="parsedJson" :depth="0" />
                </div>

                <details class="raw-json" style="margin-top:12px">
                  <summary><i class="ti ti-file-code"></i>原始 JSON</summary>
                  <pre class="mono" style="margin:0; white-space:pre-wrap"><code>{{ textContent }}</code></pre>
                </details>
              </div>

              <!-- 纯文本 -->
              <pre v-else-if="textContent"><code>{{ textContent }}</code></pre>
              <div v-else-if="textLoading" class="loading-text">
                <i class="ti ti-loader-2 ti-spin"></i> {{ t("status.loading") }}
              </div>
              <div v-else class="error-text">
                <i class="ti ti-alert-circle"></i> {{ textError || t("status.loadFailed") }}
              </div>
            </div>
            
            <!-- 通用预览 -->
            <div v-else class="generic-preview">
              <div class="generic-placeholder">
                <i :class="fileIcon" style="font-size:64px; opacity:0.3"></i>
                <p>{{ t("hint.unsupportedPreview") }}</p>
                <p style="font-size:12px; color:var(--muted)">{{ item.path }}</p>
              </div>
            </div>
          </div>
          
          <div class="file-actions" style="margin-top:16px; padding-top:16px; border-top:1px solid var(--hr-color); display:flex; gap:10px; justify-content:flex-end">
            <button class="btn" @click="openFolder">
              <i class="ti ti-folder"></i> {{ t("btn.openDir") }}
            </button>
            <button v-if="isImage || is3DModel" class="btn" @click="openFile">
              <i class="ti ti-external-link"></i> {{ t("btn.openFile") }}
            </button>
            <button v-if="isText" class="btn" @click="copyContent">
              <i class="ti ti-copy"></i> {{ t("btn.copy") }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";
import { invoke } from "@tauri-apps/api/core";
import JsonTree from "./JsonTree.vue";
import { revealItemInDir } from "@tauri-apps/plugin-opener";
import { documentDir, join } from "@tauri-apps/api/path";

// 导入拆分出的组件
import ImagePreview from "./filePreview/ImagePreview.vue";
import ModelPreview from "./filePreview/ModelPreview.vue";
import BoardSpecPreview from "./filePreview/BoardSpecPreview.vue";

const { t } = useI18n();

const props = defineProps({
  isOpen: Boolean,
  item: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['close', 'toast']);

const textContent = ref("");
const textLoading = ref(false);
const textError = ref("");
const imageLoadError = ref(false);
const imageLoading = ref(false);
const previewLoading = ref(false);
const imageErrorText = ref("");
const previewErrorText = ref("");
const imageDataUrl = ref("");
const previewDataUrl = ref("");
const modelData = ref(null);
const modelLoading = ref(false);
const modelErrorText = ref("");

const hasTauri = () => Boolean(window.__TAURI__?.core?.invoke);

const readFileAsDataUrl = async (path) => {
  if (!path) return "";
  const p = String(path);
  if (p.startsWith("http") || p.startsWith("data:")) return p;
  if (!hasTauri()) return "";
  try {
    const result = await invoke("read_file_base64", { path: p });
    if (!result || !result.data) return "";
    const mime = result.mime || "application/octet-stream";
    return `data:${mime};base64,${result.data}`;
  } catch (e) {
    console.error("读取本地文件失败:", e);
    return "";
  }
};

const readFileAsArrayBuffer = async (path) => {
  if (!path) return null;
  if (!hasTauri()) return null;
  try {
    const result = await invoke("read_file_base64", { path: String(path) });
    if (!result || !result.data) return null;
    const binary = atob(String(result.data || ''));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  } catch (e) {
    console.error("读取模型文件失败:", e);
    return null;
  }
};

const isImage = computed(() => {
  if (!props.item) return false;
  return props.item.kind === 'source_image' || props.item.kind === 'color_plate' || 
         /\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i.test(props.item.name);
});

const hasPreview = computed(() => {
  if (!props.item) return false;
  if (props.item.kind === 'json' && props.item?.short?.kind === 'bd') {
    return true;
  }
  return false;
});

const is3DModel = computed(() => {
  if (!props.item) return false;
  return props.item.kind === 'model' || props.item.kind === 'board_model' ||
         /\.(stl|obj|3mf|ply|gltf|glb)$/i.test(props.item.name);
});

const isText = computed(() => {
  if (!props.item) return false;
  return props.item.kind === 'json' || props.item.kind === 'spec' ||
         /\.(json|txt|md|yaml|yml|xml|csv)$/i.test(props.item.name);
});

const isBoardSpecJson = computed(() => {
  if (!props.item) return false;
  return props.item.kind === 'json' && props.item?.short?.kind === 'bd';
});

const isGenericJson = computed(() => {
  if (!props.item) return false;
  return props.item.kind === 'json' && !isBoardSpecJson.value;
});

const jsonKeyCount = computed(() => {
  if (!parsedJson.value) return 0;
  if (Array.isArray(parsedJson.value)) return parsedJson.value.length;
  if (typeof parsedJson.value === 'object') return Object.keys(parsedJson.value).length;
  return 0;
});

const jsonType = computed(() => {
  if (!parsedJson.value) return 'null';
  if (Array.isArray(parsedJson.value)) return `数组[${parsedJson.value.length}]`;
  if (typeof parsedJson.value === 'object') return '对象';
  return typeof parsedJson.value;
});

const parsedJsonError = ref("");
const parsedJson = computed(() => {
  parsedJsonError.value = "";
  if (!textContent.value) return null;
  try {
    return JSON.parse(String(textContent.value));
  } catch (e) {
    parsedJsonError.value = String(e || "JSON 解析失败");
    console.error("[文件详情] JSON 解析失败:", e);
    return null;
  }
});

const boardSpec = computed(() => {
  if (!isBoardSpecJson.value) return null;
  const v = parsedJson.value;
  if (!v || typeof v !== 'object') return null;
  return v;
});

const fileIcon = computed(() => {
  if (!props.item) return 'ti ti-file';
  if (props.item.kind === 'source_image' || props.item.kind === 'color_plate') return 'ti ti-photo';
  if (props.item.kind === 'json') return 'ti ti-file-description';
  if (props.item.kind === 'model') return 'ti ti-box';
  if (props.item.kind === 'board_model') return 'ti ti-printer';
  return 'ti ti-file';
});

const fileTitle = computed(() => {
  if (!props.item) return t("modal.fileDetailTitle");
  if (isImage.value) return t("modal.imageDetailTitle");
  if (is3DModel.value) return t("modal.modelDetailTitle");
  if (isText.value) return t("modal.textDetailTitle");
  return t("modal.fileDetailTitle");
});

const fileTypeLabel = computed(() => {
  if (!props.item) return '-';
  const kindMap = {
    'source_image': t("page.categorySourceImage"),
    'color_plate': t("page.categoryColorPlate"),
    'json': t("page.categoryJson"),
    'model': t("page.categoryModel"),
    'board_model': t("page.categoryBoardModel"),
    'spec': t("label.specFile"),
    'other': t("page.categoryOther")
  };
  return kindMap[props.item.kind] || props.item.kind || t("page.categoryOther");
});

const fileSize = computed(() => {
  if (!props.item || !props.item.size) return null;
  const size = props.item.size;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
});

const modelInfo = computed(() => {
  if (!props.item) return null;
  return {
    format: props.item.name?.split('.').pop()?.toUpperCase() || '-',
    size: fileSize.value || '-'
  };
});

const boxStyle = computed(() => {
  if (isImage.value) {
    return { width: 'min(800px, 96vw)' };
  }
  return { width: 'min(600px, 92vw)' };
});

const imageAbsPath = ref('');
const previewPath = ref('');
const isPathReady = ref(false);
let updateSeq = 0;

const toAbsolutePath = async (relPath) => {
  if (!relPath) return relPath;
  if (relPath.includes(':\\') || relPath.startsWith('/')) {
    return relPath;
  }
  try {
    const docDir = await documentDir();
    const absPath = await join(docDir, 'OpenColor', relPath);
    return absPath;
  } catch (err) {
    console.error("路径转换失败:", err);
    return relPath;
  }
};

const updateImagePath = async () => {
  const seq = ++updateSeq;
  isPathReady.value = false;
  imageLoadError.value = false;
  imageLoading.value = false;
  previewLoading.value = false;
  imageErrorText.value = "";
  previewErrorText.value = "";
  imageDataUrl.value = "";
  previewDataUrl.value = "";
  modelData.value = null;
  modelLoading.value = false;
  modelErrorText.value = "";
  
  if (!props.item?.path) {
    imageAbsPath.value = '';
    previewPath.value = '';
    return;
  }
  if (props.item.path.startsWith('http')) {
    imageAbsPath.value = props.item.path;
    previewPath.value = '';
    isPathReady.value = true;
    imageDataUrl.value = props.item.path;
    return;
  }
  
  if (props.item.kind === 'json' && props.item?.short?.kind === 'bd') {
    const metaPreview = props.item?.long?.meta?.preview;
    if (metaPreview) {
      previewPath.value = await toAbsolutePath(metaPreview);
    } else {
      previewPath.value = '';
    }
  } else {
    previewPath.value = '';
  }
  
  imageAbsPath.value = await toAbsolutePath(props.item.path);
  isPathReady.value = true;

  if (is3DModel.value && props.isOpen) {
    modelLoading.value = true;
    const buffer = await readFileAsArrayBuffer(imageAbsPath.value);
    if (seq !== updateSeq) return;
    modelData.value = buffer;
    modelLoading.value = false;
    if (!buffer) {
      modelErrorText.value = hasTauri() ? "加载失败" : "浏览器模式下无法预览本地 3D 模型";
    }
  }

  if (isImage.value) {
    imageLoading.value = true;
    const dataUrl = await readFileAsDataUrl(imageAbsPath.value);
    if (seq !== updateSeq) return;
    imageDataUrl.value = dataUrl;
    imageLoading.value = false;
    if (!dataUrl) {
      imageErrorText.value = hasTauri() ? "加载失败" : "浏览器模式下无法预览本地图片";
    }
  }

  if (hasPreview.value) {
    previewLoading.value = true;
    const dataUrl = await readFileAsDataUrl(previewPath.value);
    if (seq !== updateSeq) return;
    previewDataUrl.value = dataUrl;
    previewLoading.value = false;
    if (!dataUrl) {
      previewErrorText.value = hasTauri() ? "加载失败" : "浏览器模式下无法预览本地预览图";
    }
  }
};

const imageSrc = computed(() => {
  if (imageLoadError.value) return "";
  return imageDataUrl.value || "";
});

const previewSrc = computed(() => {
  if (imageLoadError.value) return "";
  return previewDataUrl.value || "";
});

const handleImageError = (event) => {
  imageLoadError.value = true;
  const failedSrc = event?.target?.src || 'unknown';
  console.error("图片加载失败:", failedSrc);
  if (isImage.value) imageErrorText.value = "图片加载失败";
  if (hasPreview.value) previewErrorText.value = "预览图加载失败";
};

const loadTextContent = async () => {
  if (!props.item || !isText.value) return;

  textLoading.value = true;
  textError.value = "";
  textContent.value = "";

  try {
    const absPath = await toAbsolutePath(props.item.path);
    const content = await invoke('read_text_file', { path: absPath });
    if (typeof content === 'string') {
      textContent.value = content.substring(0, 10000);
      if (content.length > 10000) {
        textContent.value += '\n\n... (' + t("hint.contentTruncated") + ')';
      }
    } else if (props.item.content) {
      textContent.value = JSON.stringify(props.item.content, null, 2);
    }
  } catch (err) {
    console.error("读取文件失败:", err);
    textError.value = err.toString();
    if (props.item.content) {
      textContent.value = JSON.stringify(props.item.content, null, 2);
    }
  } finally {
    textLoading.value = false;
  }
};

watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    imageLoadError.value = false;
    updateImagePath();
    if (isText.value) {
      loadTextContent();
    }
  } else {
    textContent.value = "";
    textError.value = "";
    imageAbsPath.value = '';
    previewPath.value = '';
    imageDataUrl.value = "";
    previewDataUrl.value = "";
    modelData.value = null;
    imageLoading.value = false;
    previewLoading.value = false;
    imageErrorText.value = "";
    previewErrorText.value = "";
    modelLoading.value = false;
    modelErrorText.value = "";
  }
});

watch(() => props.item, (newItem) => {
  if (newItem) {
    updateImagePath();
    if (isText.value && props.isOpen) {
      loadTextContent();
    }
  }
});

onBeforeUnmount(() => {
  // 清理工作已在各子组件中处理
});

const formatDate = (timestamp) => {
  if (!timestamp) return '-';
  const date = new Date(timestamp * 1000);
  return date.toLocaleString();
};

const getFolderName = (path) => {
  if (!path) return '-';
  const parts = path.split(/[\\/]/);
  parts.pop();
  return parts.pop() || '-';
};

const openFolder = async () => {
  if (!props.item?.path) return;
  try {
    const absPath = await toAbsolutePath(props.item.path);
    await revealItemInDir(absPath);
  } catch (err) {
    console.error("打开文件夹失败:", err);
  }
};

const openFile = async () => {
  if (!props.item?.path) return;
  try {
    const absPath = await toAbsolutePath(props.item.path);
    await invoke('open_file', { path: absPath });
  } catch (err) {
    console.error("打开文件失败:", err);
  }
};

const copyContent = async () => {
  if (!textContent.value) return;
  try {
    await navigator.clipboard.writeText(textContent.value);
    emit('toast', { title: t("toast.copied"), message: t("toast.copiedDesc") });
  } catch (err) {
    console.error("复制失败:", err);
  }
};
</script>

<style scoped>
.file-content {
  min-height: 200px;
}

.loading-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--muted);
}

.generic-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.generic-placeholder {
  text-align: center;
  padding: 40px;
  background: var(--bg-alpha);
  border-radius: 12px;
  width: 100%;
}

.text-preview {
  background: var(--bg-alpha);
  border-radius: 12px;
  padding: 16px;
  min-height: 200px;
}

.text-preview pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Maple Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
  max-height: 50vh;
  overflow-y: auto;
}

.text-preview code {
  font-family: inherit;
}

.loading-text,
.error-text {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--muted);
}

.error-text {
  color: var(--danger);
}

.state-msg {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--muted);
}

/* JSON 结构化展示样式 */
.json-structured {
  background: var(--panel);
  border-radius: 12px;
  padding: 16px;
}

.json-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.json-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.json-meta {
  display: flex;
  gap: 8px;
}

.json-content {
  background: var(--bg);
  border-radius: 8px;
  padding: 12px;
  max-height: 50vh;
  overflow-y: auto;
}

.raw-json summary {
  cursor: pointer;
  color: var(--muted);
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--bg-alpha);
  border-radius: 4px;
  font-size: 11px;
  color: var(--muted);
}

.image-preview .preview-label {
  margin-bottom: 8px;
}
</style>
