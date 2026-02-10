<template>
  <section class="view oc-edge">
    <FileDetailModal
      :is-open="showFileDetailModal"
      :item="selectedItem"
      @close="showFileDetailModal = false"
      @toast="handleToast"
    />
    <div class="split mat-split oc-edge">
      <div class="card sideList">
        <div class="hd">
          <div class="title-group">
            <i class="ti ti-library"></i>
            <h3 class="title-label">{{ t("page.albumTitle") }}</h3>
          </div>
          <div class="actions-group">
            <button class="btn ghost icon-only" @click="refresh" :disabled="loading">
              <i class="ti ti-refresh" :class="{ 'ti-spin': loading }"></i>
            </button>
          </div>
        </div>
        <div class="bd">
          <div class="list">
            <button
              v-for="cat in categories"
              :key="cat.kind"
              class="btn profileBtn marquee-btn"
              :class="{ active: currentCategory === cat.kind }"
              @click="currentCategory = cat.kind"
            >
              <i :class="cat.icon"></i>
              <span class="btn-label">
                <span class="marquee-text" :data-text="cat.label">{{ cat.label }}</span>
              </span>
              <span class="count-pill">{{ getCategoryCount(cat.kind) }}</span>
            </button>
          </div>
        </div>
      </div>

      <div class="card mat-detail active">
        <div class="hd">
          <div class="title-group">
            <i :class="currentCategoryIcon"></i>
            <h3 class="title-label">{{ currentCategoryLabel }}</h3>
          </div>
        </div>
        <div class="bd scrollable">
          <div v-if="loading" class="state-msg">
            <img src="../assets/loading.svg" class="loading-icon" />
            <p>{{ t("status.loading") || "加载中..." }}</p>
          </div>
          <div v-else-if="filteredItems.length === 0" class="state-msg">
            <i class="ti ti-box-off" style="font-size: 48px; opacity: 0.1;"></i>
            <p>{{ t("status.emptyCategory") || "暂无内容" }}</p>
          </div>
          <div v-else class="album-grid">
            <div v-for="item in filteredItems" :key="item.id" class="album-item" @click="viewItemDetails(item)">
              <div class="item-icon-wrapper">
                <i v-if="item.kind === 'source_image' || item.kind === 'color_plate'" class="ti ti-photo"></i>
                <i v-else-if="item.kind === 'json'" class="ti ti-file-description"></i>
                <i v-else-if="item.kind === 'model'" class="ti ti-box"></i>
                <i v-else-if="item.kind === 'board_model'" class="ti ti-printer"></i>
                <i v-else class="ti ti-file"></i>
              </div>
              <div class="item-content">
                <div class="item-name" :title="getItemDisplayName(item)">{{ getItemDisplayName(item) }}</div>
                <div class="item-meta">
                  <span class="item-date">{{ formatDate(item.ctime) }}</span>
                </div>
              </div>
              <div class="item-actions">
                <button class="btn ghost icon-only" @click.stop="openFolder(item.path)" :title="t('btn.openDir')">
                  <i class="ti ti-folder"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
// 导入 Vue 响应式 API 和生命周期钩子
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
// 导入国际化功能
import { useI18n } from 'vue-i18n';
// 导入 Tauri API
import { invoke } from '@tauri-apps/api/core';
// 导入 opener 插件
import { revealItemInDir } from '@tauri-apps/plugin-opener';
// 导入路径处理
import { documentDir, join } from '@tauri-apps/api/path';
// 导入文件详情模态框
import FileDetailModal from './FileDetailModal.vue';
// 导入消息队列
import { useMessageQueue } from '../composables/useMessageQueue';

// 定义 props
const props = defineProps({
  currentView: {
    type: String,
    default: ''
  }
});

// 获取国际化翻译函数
const { t } = useI18n();

// 资源库项目列表
const items = ref([]);

// 加载状态
const loading = ref(true);

// 当前分类
const currentCategory = ref('all');

// 计算属性：分类列表
const categories = computed(() => [
  { kind: 'all', label: t('page.categoryAll') || '全部', icon: 'ti ti-category' },
  { kind: 'model', label: t('page.categoryModel') || '3D 模型', icon: 'ti ti-box' },
  { kind: 'board_model', label: t('page.categoryBoardModel') || '色盘模型', icon: 'ti ti-printer' },
  { kind: 'material_config', label: t('page.categoryMaterialConfig') || '材料配置', icon: 'ti ti-palette' },
  { kind: 'json', label: t('page.categoryJson') || 'JSON 规格', icon: 'ti ti-file-description' },
  { kind: 'color_plate', label: t('page.categoryColorPlate') || '色盘图片', icon: 'ti ti-photo' },
  { kind: 'source_image', label: t('page.categorySourceImage') || '待生成模型图片', icon: 'ti ti-image' },
  { kind: 'other', label: t('page.categoryOther') || '其他文件', icon: 'ti ti-file' }
]);

const isMaterialConfigItem = (item) => {
  if (!item || item.kind !== 'json') return false;
  const p = String(item.path || '');
  if (p.includes('Profiles\\') || p.includes('Profiles/')) return true;
  const sk = item?.short?.kind;
  return String(sk || '').toLowerCase() === 'mt';
};

// 计算属性：过滤后的项目列表
const filteredItems = computed(() => {
  if (currentCategory.value === 'all') return items.value;
  if (currentCategory.value === 'material_config') {
    return items.value.filter(isMaterialConfigItem);
  }
  return items.value.filter(item => item.kind === currentCategory.value);
});

// 获取分类数量
const getCategoryCount = (kind) => {
  if (kind === 'all') return items.value.length;
  if (kind === 'material_config') return items.value.filter(isMaterialConfigItem).length;
  return items.value.filter(item => item.kind === kind).length;
};

// 计算属性：当前分类标签
const currentCategoryLabel = computed(() => {
  const cat = categories.value.find(c => c.kind === currentCategory.value);
  return cat ? cat.label : '';
});

// 计算属性：当前分类图标
const currentCategoryIcon = computed(() => {
  const cat = categories.value.find(c => c.kind === currentCategory.value);
  return cat ? cat.icon : 'ti ti-folder';
});

// 刷新数据库列表
const refresh = async () => {
  console.log("[数据库] 开始刷新列表");
  loading.value = true;
  try {
    items.value = await invoke('list_album_files');
    console.log("[数据库] 列表刷新完成，数量:", items.value.length);
  } catch (err) {
    console.error("[数据库] 加载列表失败", err);
  } finally {
    loading.value = false;
  }
};

// 文件详情模态框状态
const showFileDetailModal = ref(false);
const selectedItem = ref(null);

// 查看文件详情（点击条目其他位置）
const viewItemDetails = (item) => {
  selectedItem.value = item;
  showFileDetailModal.value = true;
};

// 处理 Toast 提示
const handleToast = (toastData) => {
  // 可以在这里触发全局 Toast，暂时使用 console
  console.log("Toast:", toastData);
};

// 生成色盘项目的编号（使用递增编号）
const getBoardIndex = (item) => {
  // 优先使用 board_index（递增编号）
  const boardIndex = item?.short?.board_index || item?.board_index;
  if (boardIndex) {
    return boardIndex;
  }
  console.warn("[数据库] 缺少色盘自增编号 board_index:", item);
  return '?';
};

const getModelFormat = (item) => {
  const name = String(item?.name || '');
  const ext = name.split('.').pop()?.toUpperCase() || '';
  if (ext === '3MF') return '3MF';
  if (ext === 'STL') return 'STL';
  return ext || '模型';
};

// 获取色盘模型的子编号（字母序号-颜色标识）
const getBoardSubIndex = (item) => {
  const name = item?.name || '';
  const cs = String(item?.short?.cs || '').toUpperCase();
  // 从文件名中提取颜色标识，如 White, Red, Blue 等
  const match = name.match(/_([A-Za-z]+)\.(stl|3mf)$/i);
  if (match) {
    const color = match[1];
    const colorUpper = String(color).toUpperCase();
    const orderByCs = {
      'RYBW': ['Red', 'Yellow', 'Blue', 'White'],
      'CMYW': ['Cyan', 'Magenta', 'Yellow', 'White'],
    };
    const order = orderByCs[cs] || [];
    const idx = order.findIndex(v => v.toUpperCase() === colorUpper);
    if (idx >= 0) {
      const letter = String.fromCharCode('A'.charCodeAt(0) + idx);
      return `${letter}-${colorUpper}`;
    }
    return colorUpper;
  }
  console.warn("[相册] 无法从色盘模型文件名解析颜色:", name);
  return 'UNKNOWN';
};

const getItemDisplayName = (item) => {
  // 对于色盘相关文件，使用新的编号格式
  if (item?.kind === 'board_model') {
    const index = getBoardIndex(item);
    const subIndex = getBoardSubIndex(item);
    const fmt = getModelFormat(item);
    return t('album.file.board.model', { fmt, index, subIndex });
  }
  if (item?.kind === 'json' && item?.short?.kind === 'bd') {
    const index = getBoardIndex(item);
    return t('album.file.board.spec', { index });
  }

  // 对于其他文件，使用原有的显示逻辑
  const key = item?.display_key;
  if (key) {
    const res = t(key, item?.display_args || {});
    if (res && res !== key) return res;
  }
  return item?.name || '';
};

// 将相对路径转换为绝对路径
const toAbsolutePath = async (relPath) => {
  try {
    const docDir = await documentDir();
    const absPath = await join(docDir, 'OpenColor', relPath);
    return absPath;
  } catch (err) {
    console.error("路径转换失败:", err);
    return relPath;
  }
};

// 打开文件夹（点击文件夹按钮）
const openFolder = async (relPath) => {
  try {
    const absPath = await toAbsolutePath(relPath);
    await revealItemInDir(absPath);
    console.log("已在资源管理器中定位:", absPath);
  } catch (err) {
    console.error("打开文件夹失败:", err);
  }
};

// 格式化日期
const formatDate = (timestamp) => {
  if (!timestamp) return '-';
  const date = new Date(timestamp * 1000);
  return date.toLocaleString();
};

// 使用消息队列监听相册刷新事件
useMessageQueue({
  types: ['album-refresh'],
  onMessage: (message) => {
    console.log('[相册] 收到消息队列消息:', message.type, message.payload);
    refresh();
  }
});

// 监听 currentView 变化，当切换到相册页面时自动刷新
watch(() => props.currentView, (newView, oldView) => {
  console.log(`[相册] 视图变化: ${oldView} -> ${newView}`);
  if (newView === 'album') {
    console.log('[相册] 切换到相册页面，自动刷新');
    refresh();
  }
});

// 组件挂载时刷新列表
onMounted(() => {
  console.log("[相册] 组件挂载");
  refresh();
});
</script>

<style scoped>
.count-pill {
  font-size: 10px;
  background: var(--bg-alpha2);
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: auto;
  opacity: 0.7;
  min-width: 24px;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}

.profileBtn.active .count-pill {
  background: rgba(255, 255, 255, 0.2);
  opacity: 1;
}

.scrollable {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.state-msg {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: var(--muted);
}

.loading-icon {
  width: 48px;
  height: 48px;
}

.album-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.album-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: var(--bg-alpha);
  border: 1px solid var(--border-alpha);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 0;
}

.album-item:hover {
  background: var(--bg-alpha2);
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.item-icon-wrapper {
  width: 44px;
  height: 44px;
  background: var(--btn);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: var(--accent);
  margin-right: 12px;
  flex-shrink: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
}

.item-actions {
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.album-item:hover .item-actions {
  opacity: 1;
}

.ti-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 600px) {
  .album-grid {
    grid-template-columns: 1fr;
  }
}
</style>
