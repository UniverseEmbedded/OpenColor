<template>
  <section class="view oc-edge">
    <!-- 顶部标签切换 -->
    <div class="subnav mat-subnav oc-edge oc-panel">
      <button :class="{ active: activeTab === 'filaments' }" @click="activeTab = 'filaments'">
        <i class="ti ti-box"></i><span class="btn-label">{{ t('modal.filamentLibrary') }}</span>
      </button>
      <button :class="{ active: activeTab === 'groups' }" @click="activeTab = 'groups'">
        <i class="ti ti-layers-linked"></i><span class="btn-label">{{ t('modal.materialGroups') }}</span>
      </button>
    </div>

    <!-- 耗材库页面 -->
    <div v-show="activeTab === 'filaments'" class="materials-layout">
      <!-- 耗材列表 -->
      <div class="list-panel">
        <div class="panel-header">
          <h3><i class="ti ti-box"></i> {{ t('modal.filamentList') }} ({{ filaments.length }})</h3>
          <button class="btn primary" @click="showNewFilamentModal = true">
            <i class="ti ti-plus"></i> {{ t('modal.new') }}
          </button>
        </div>
        <div class="list-content">
          <div v-for="filament in filaments" :key="filament.id" 
               class="list-item" 
               :class="{ active: selectedFilament?.id === filament.id }"
               @click="selectFilament(filament)">
            <div class="color-indicator" :style="{ background: getFilamentColor(filament) }"></div>
            <div class="item-info">
              <span class="item-name">{{ filament.name }}</span>
              <span class="item-meta">{{ filament.brand }} · {{ filament.type }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 耗材详情 -->
      <div class="detail-panel" v-if="selectedFilament">
        <div class="panel-header">
          <h3><i class="ti ti-file-description"></i> {{ t('modal.filamentDetails') }}</h3>
          <div class="header-actions">
            <button class="btn danger" @click="deleteFilament(selectedFilament)">
              <i class="ti ti-trash"></i> {{ t('modal.delete') }}
            </button>
          </div>
        </div>
        <div class="detail-content">
          <!-- 可视化预览 -->
          <div class="filament-preview-large" :style="{ background: getFilamentColor(selectedFilament) }">
            <input
              v-model="selectedFilament.name"
              class="preview-name-input"
              @blur="saveFilamentEdit(selectedFilament)"
              @keyup.enter="$event.target.blur()"
            />
          </div>

          <!-- 结构化数据展示 -->
          <div class="structured-data">
            <h4><i class="ti ti-database"></i> {{ t('modal.dataInfo') }}</h4>
            <div class="data-grid">
              <div class="data-item">
                <label>{{ t('modal.id') }}</label>
                <span class="value">{{ selectedFilament.id }}</span>
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.name') }}</label>
                <input v-model="selectedFilament.name" @blur="saveFilamentEdit(selectedFilament)" />
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.brand') }}</label>
                <input v-model="selectedFilament.brand" @blur="saveFilamentEdit(selectedFilament)" :placeholder="t('modal.unknown')" />
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.type') }}</label>
                <select v-model="selectedFilament.type" @change="saveFilamentEdit(selectedFilament)">
                  <option value="PLA">PLA</option>
                  <option value="PETG">PETG</option>
                  <option value="ABS">ABS</option>
                  <option value="TPU">TPU</option>
                </select>
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.color') }}</label>
                <input v-model="selectedFilament.color" @blur="saveFilamentEdit(selectedFilament)" :placeholder="t('modal.unknown')" />
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.rgba') }}</label>
                <div class="rgba-inputs">
                  <input type="color" :value="rgbaToHex(selectedFilament.rgba)" @input="updateRgbaFromInput($event, selectedFilament)" />
                  <input v-model="selectedFilament.rgba" @blur="parseRgbaString(selectedFilament)" :placeholder="t('modal.rgbaPlaceholder')" />
                </div>
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.transparent') }}</label>
                <input type="checkbox" v-model="selectedFilament.isTransparent" @change="saveFilamentEdit(selectedFilament)" />
              </div>
              <div class="data-item">
                <label>{{ t('modal.createdAt') }}</label>
                <span class="value">{{ formatDate(selectedFilament.createdAt) }}</span>
              </div>
            </div>
          </div>

          <!-- JSON 预览 -->
          <div class="json-preview-section">
            <h4 @click="showFilamentJson = !showFilamentJson" class="collapsible">
              <i class="ti ti-code"></i> {{ t('modal.jsonSource') }}
              <i class="ti" :class="showFilamentJson ? 'ti-chevron-up' : 'ti-chevron-down'"></i>
            </h4>
            <pre v-show="showFilamentJson" class="json-code">{{ JSON.stringify(selectedFilament, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <div class="detail-panel empty" v-else>
        <div class="empty-state">
          <i class="ti ti-box-off"></i>
          <p>{{ t('modal.selectFilamentHint') }}<br>{{ t('modal.orClickNew') }}</p>
        </div>
      </div>
    </div>

    <!-- 材料组页面 -->
    <div v-show="activeTab === 'groups'" class="materials-layout">
      <!-- 材料组列表 -->
      <div class="list-panel">
        <div class="panel-header">
          <h3><i class="ti ti-layers-linked"></i> {{ t('modal.groupList') }} ({{ materialGroups.length }})</h3>
          <button class="btn primary" @click="openNewGroupModal">
            <i class="ti ti-plus"></i> {{ t('modal.new') }}
          </button>
        </div>
        <div class="list-content">
          <div v-for="group in materialGroups" :key="group.id" 
               class="list-item" 
               :class="{ active: selectedGroup?.id === group.id }"
               @click="selectGroup(group)">
            <div class="group-colors">
              <div v-for="(slot, idx) in group.slots.slice(0, 4)" :key="idx"
                   class="mini-color" 
                   :style="{ background: getFilamentColorById(slot.filamentId) }"></div>
              <span v-if="group.slots.length > 4" class="more-indicator">+{{ group.slots.length - 4 }}</span>
            </div>
            <div class="item-info">
              <span class="item-name">{{ group.name }}</span>
              <span class="item-meta">{{ t('modal.colorCount', { n: group.channelCount }) }} · {{ t('modal.assignedCount', { assigned: group.slots.filter(s => s.filamentId).length }) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 材料组详情 -->
      <div class="detail-panel" v-if="selectedGroup">
        <div class="panel-header">
          <h3><i class="ti ti-file-description"></i> {{ t('modal.groupDetails') }}</h3>
          <div class="header-actions">
            <button class="btn" @click="exportGroup(selectedGroup)">
              <i class="ti ti-file-export"></i> {{ t('modal.export') }}
            </button>
            <button class="btn danger" @click="deleteGroup(selectedGroup)">
              <i class="ti ti-trash"></i> {{ t('modal.delete') }}
            </button>
          </div>
        </div>
        <div class="detail-content">
          <!-- 槽位可视化 -->
          <div class="slots-visualization">
            <h4><i class="ti ti-layout-grid"></i> {{ t('modal.slotConfig') }}</h4>
            <div class="slots-grid">
              <div v-for="(slot, index) in selectedGroup.slots" :key="index" class="slot-item">
                <div class="slot-number">{{ index + 1 }}</div>
                <div class="slot-color" :style="{ background: getFilamentColorById(slot.filamentId) || '#ccc' }"></div>
                <div class="slot-filament-name">{{ getFilamentNameById(slot.filamentId) || t('modal.unassigned') }}</div>
              </div>
            </div>
          </div>

          <!-- 结构化数据展示 -->
          <div class="structured-data">
            <h4><i class="ti ti-database"></i> {{ t('modal.dataInfo') }}</h4>
            <div class="data-grid">
              <div class="data-item">
                <label>{{ t('modal.id') }}</label>
                <span class="value">{{ selectedGroup.id }}</span>
              </div>
              <div class="data-item editable">
                <label>{{ t('modal.name') }}</label>
                <input v-model="selectedGroup.name" @blur="saveGroupEdit(selectedGroup)" />
              </div>
              <div class="data-item">
                <label>{{ t('modal.channelCountShort') }}</label>
                <span class="value">{{ selectedGroup.channelCount }}</span>
              </div>
              <div class="data-item">
                <label>{{ t('modal.version') }}</label>
                <span class="value">{{ selectedGroup.version }}</span>
              </div>
              <div class="data-item">
                <label>{{ t('modal.assigned') }}</label>
                <span class="value">{{ selectedGroup.slots.filter(s => s.filamentId).length }} / {{ selectedGroup.slots.length }}</span>
              </div>
              <div class="data-item">
                <label>{{ t('modal.createdAt') }}</label>
                <span class="value">{{ formatDate(selectedGroup.createdAt) }}</span>
              </div>
              <div class="data-item">
                <label>{{ t('modal.updatedAt') }}</label>
                <span class="value">{{ formatDate(selectedGroup.updatedAt) }}</span>
              </div>
            </div>
          </div>

          <!-- 槽位详细数据 -->
          <div class="structured-data slots-data">
            <h4><i class="ti ti-list-details"></i> {{ t('modal.slotDetails') }}</h4>
            <div class="slots-table">
              <div class="table-header">
                <span>{{ t('modal.slot') }}</span>
                <span>{{ t('modal.filamentId') }}</span>
                <span>{{ t('modal.filamentName') }}</span>
                <span>{{ t('modal.color') }}</span>
              </div>
              <div v-for="(slot, index) in selectedGroup.slots" :key="index" class="table-row">
                <span class="slot-idx">{{ slot.slotIndex + 1 }}</span>
                <span class="filament-id">{{ slot.filamentId || '-' }}</span>
                <span class="filament-name">{{ getFilamentNameById(slot.filamentId) || t('modal.unassigned') }}</span>
                <span class="filament-color">
                  <span class="color-dot-small" :style="{ background: getFilamentColorById(slot.filamentId) || '#ccc' }"></span>
                </span>
              </div>
            </div>
          </div>

          <!-- JSON 预览 -->
          <div class="json-preview-section">
            <h4 @click="showGroupJson = !showGroupJson" class="collapsible">
              <i class="ti ti-code"></i> {{ t('modal.jsonSource') }}
              <i class="ti" :class="showGroupJson ? 'ti-chevron-up' : 'ti-chevron-down'"></i>
            </h4>
            <pre v-show="showGroupJson" class="json-code">{{ JSON.stringify(selectedGroup, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <div class="detail-panel empty" v-else>
        <div class="empty-state">
          <i class="ti ti-layers-off"></i>
          <p>{{ t('modal.selectGroupHint') }}<br>{{ t('modal.orClickNewGroup') }}</p>
        </div>
      </div>
    </div>

    <!-- 新建材料组弹窗 -->
    <NewProfileModal
      :is-open="showNewGroupModal"
      :available-filaments="filaments"
      :templates="groupTemplates"
      @close="showNewGroupModal = false"
      @submit="handleNewGroupSubmit"
      @createFilamentsFromTemplate="handleCreateFilamentsFromTemplate"
    />

    <!-- 新建耗材弹窗 -->
    <div class="modal" :class="{ show: showNewFilamentModal }" @click.self="showNewFilamentModal = false">
      <div class="box" style="width: min(480px, 92vw)">
        <div class="hd">
          <b><i class="ti ti-plus"></i> {{ t('modal.newFilament') }}</b>
          <button class="btn" @click="showNewFilamentModal = false"><i class="ti ti-x"></i></button>
        </div>
        <div class="bd">
          <div class="field">
            <label>{{ t('modal.name') }}</label>
            <input v-model="newFilamentForm.name" :placeholder="t('modal.namePlaceholder')" />
          </div>
          <div class="field">
            <label>{{ t('modal.brand') }}</label>
            <input v-model="newFilamentForm.brand" :placeholder="t('modal.brandPlaceholder')" />
          </div>
          <div class="field">
            <label>{{ t('modal.type') }}</label>
            <select v-model="newFilamentForm.type">
              <option value="PLA">PLA</option>
              <option value="PETG">PETG</option>
              <option value="ABS">ABS</option>
              <option value="TPU">TPU</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('modal.color') }}</label>
            <input v-model="newFilamentForm.color" :placeholder="t('modal.colorPlaceholder')" />
          </div>
          <div class="field">
            <label>{{ t('modal.rgba') }}</label>
            <div class="color-input-row">
              <input type="color" v-model="newFilamentForm.colorHex" @change="updateRgbaFromHex" />
              <input v-model="newFilamentForm.rgba" :placeholder="t('modal.rgbaPlaceholder')" />
            </div>
          </div>
          <div class="field checkbox">
            <label>
              <input type="checkbox" v-model="newFilamentForm.isTransparent" />
              {{ t('modal.transparentFilament') }}
            </label>
          </div>
          <div class="row" style="justify-content: flex-end; margin-top: 16px;">
            <button class="btn" @click="showNewFilamentModal = false">{{ t('modal.cancel') }}</button>
            <button class="btn primary" @click="submitNewFilament">{{ t('modal.create') }}</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import NewProfileModal from './NewProfileModal.vue';

const { t } = useI18n();

const props = defineProps({
  filaments: { type: Array, default: () => [] },
  materialGroups: { type: Array, default: () => [] },
  groupTemplates: { type: Array, default: () => [] },
  currentGroup: { type: Object, default: null },
  isLoading: { type: Boolean, default: false }
});

const emit = defineEmits([
  'selectGroup', 'newGroup', 'saveGroup', 'saveAsGroup', 
  'importGroup', 'exportGroup', 'fromCalib', 'updateGroup',
  'addFilament', 'updateFilament', 'deleteFilament', 'createFilamentsFromTemplate'
]);

// 状态
const activeTab = ref('filaments');
const selectedFilament = ref(null);
const selectedGroup = ref(null);
const showNewGroupModal = ref(false);
const showNewFilamentModal = ref(false);
const showFilamentJson = ref(false);
const showGroupJson = ref(false);

// 新建耗材表单
const newFilamentForm = ref({
  name: '',
  brand: '',
  type: 'PLA',
  color: '',
  colorHex: '#ffffff',
  rgba: '255,255,255,255',
  isTransparent: false
});

// 监听当前组变化
watch(() => props.currentGroup, (newGroup) => {
  if (newGroup) selectedGroup.value = newGroup;
}, { immediate: true });

// 工具函数
const getFilamentColor = (filament) => {
  if (!filament) return '#ccc';
  return filament.colorHex || (filament.rgba ? `rgba(${filament.rgba.join(',')})` : '#ccc');
};

const getFilamentColorById = (filamentId) => {
  const filament = props.filaments.find(f => f.id === filamentId);
  return getFilamentColor(filament);
};

const getFilamentNameById = (filamentId) => {
  const filament = props.filaments.find(f => f.id === filamentId);
  return filament?.name || null;
};

const formatDate = (timestamp) => {
  if (!timestamp) return t('modal.unknown');
  return new Date(timestamp).toLocaleString();
};

// 选择操作
const selectFilament = (filament) => {
  selectedFilament.value = filament;
};

const selectGroup = (group) => {
  selectedGroup.value = group;
  emit('selectGroup', group.id);
};

// 耗材操作
const deleteFilament = (filament) => {
  if (confirm(t('modal.confirmDeleteFilament', { name: filament.name }))) {
    emit('deleteFilament', filament.id);
    if (selectedFilament.value?.id === filament.id) {
      selectedFilament.value = null;
    }
  }
};

// 直接编辑耗材
const saveFilamentEdit = (filament) => {
  filament.updatedAt = Date.now();
  emit('updateFilament', filament.id, filament);
};

const rgbaToHex = (rgba) => {
  if (!rgba || !Array.isArray(rgba)) return '#ffffff';
  const [r, g, b] = rgba;
  return `#${(r || 0).toString(16).padStart(2, '0')}${(g || 0).toString(16).padStart(2, '0')}${(b || 0).toString(16).padStart(2, '0')}`;
};

const updateRgbaFromInput = (event, filament) => {
  const hex = event.target.value;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const a = filament.isTransparent ? 180 : 255;
  filament.rgba = [r, g, b, a];
  filament.colorHex = hex;
  saveFilamentEdit(filament);
};

const parseRgbaString = (filament) => {
  if (typeof filament.rgba === 'string') {
    filament.rgba = filament.rgba.split(',').map(Number);
  }
  saveFilamentEdit(filament);
};

const updateRgbaFromHex = () => {
  // 简单的 hex 转 rgba
  const hex = newFilamentForm.value.colorHex.replace('#', '');
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const a = newFilamentForm.value.isTransparent ? 180 : 255;
  newFilamentForm.value.rgba = `${r},${g},${b},${a}`;
};

const submitNewFilament = () => {
  const rgba = newFilamentForm.value.rgba.split(',').map(Number);
  const filament = {
    name: newFilamentForm.value.name,
    brand: newFilamentForm.value.brand,
    type: newFilamentForm.value.type,
    color: newFilamentForm.value.color,
    colorHex: newFilamentForm.value.colorHex,
    rgba: rgba,
    isTransparent: newFilamentForm.value.isTransparent
  };
  emit('addFilament', filament);
  showNewFilamentModal.value = false;
  // 重置表单
  newFilamentForm.value = {
    name: '', brand: '', type: 'PLA', color: '',
    colorHex: '#ffffff', rgba: '255,255,255,255', isTransparent: false
  };
};

// 材料组操作
const openNewGroupModal = () => {
  showNewGroupModal.value = true;
};

const handleNewGroupSubmit = (data) => {
  emit('newGroup', data);
  showNewGroupModal.value = false;
};

// 从模板创建耗材
const handleCreateFilamentsFromTemplate = (slots, callback) => {
  // 通过事件通知父组件，父组件处理完成后调用回调
  emit('createFilamentsFromTemplate', slots, (slotFilamentMap) => {
    if (callback) {
      callback(slotFilamentMap);
    }
  });
};

// 直接编辑材料组
const saveGroupEdit = (group) => {
  group.updatedAt = Date.now();
  emit('saveGroup', group);
};

const exportGroup = (group) => {
  emit('exportGroup', group);
};

const deleteGroup = (group) => {
  if (confirm(t('modal.confirmDeleteGroup', { name: group.name }))) {
    // TODO: 实现删除
    console.log('删除材料组:', group);
  }
};
</script>

<style scoped>
.materials-layout {
  display: flex;
  height: calc(100vh - 180px);
  gap: 16px;
  padding: 16px;
  overflow: hidden;
}

.list-panel {
  width: 320px;
  background: var(--panel);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-panel {
  flex: 1;
  background: var(--panel);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-panel.empty {
  align-items: center;
  justify-content: center;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.list-item:hover {
  background: var(--hover-bg);
}

.list-item.active {
  background: var(--active-bg);
  border-left: 3px solid var(--primary-color);
}

.color-indicator {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  flex-shrink: 0;
}

.group-colors {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.mini-color {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: 1px solid var(--border-color);
}

.more-indicator {
  font-size: 10px;
  color: var(--muted);
  padding: 2px 4px;
}

.item-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.item-name {
  font-weight: 500;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  font-size: 12px;
  color: var(--muted);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  text-align: center;
  color: var(--muted);
}

.empty-state i {
  font-size: 64px;
  margin-bottom: 16px;
  display: block;
}

.filament-preview-large {
  height: 120px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.preview-name {
  font-size: 28px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 2px 4px rgba(0,0,0,0.5);
}

.structured-data {
  background: var(--bg-alpha);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.structured-data h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.data-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.data-item label {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.data-item .value {
  font-size: 13px;
  font-family: var(--mono);
  word-break: break-all;
}

.rgba-value {
  display: flex;
  align-items: center;
  gap: 8px;
}

.color-preview-small {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: 1px solid var(--border-color);
}

.slots-visualization {
  margin-bottom: 20px;
}

.slots-visualization h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
}

.slots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 12px;
}

.slot-item {
  background: var(--bg-alpha);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.slot-number {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}

.slot-color {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  margin: 0 auto 8px;
  border: 2px solid var(--border-color);
}

.slot-filament-name {
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slots-data .slots-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.table-header, .table-row {
  display: grid;
  grid-template-columns: 60px 1fr 1fr 60px;
  gap: 12px;
  padding: 8px 12px;
  align-items: center;
}

.table-header {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  border-bottom: 1px solid var(--border-color);
}

.table-row {
  background: var(--bg-alpha);
  border-radius: 6px;
  font-size: 13px;
}

.slot-idx {
  font-weight: 600;
  color: var(--muted);
}

.filament-id {
  font-family: var(--mono);
  font-size: 11px;
}

.color-dot-small {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-block;
  border: 1px solid var(--border-color);
}

.json-preview-section {
  margin-top: 20px;
}

.json-preview-section h4 {
  margin: 0;
  padding: 12px;
  background: var(--bg-alpha);
  border-radius: 8px 8px 0 0;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.json-code {
  margin: 0;
  padding: 16px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 0 0 8px 8px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}

.color-input-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.color-input-row input[type="color"] {
  width: 50px;
  height: 36px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
}

.field.checkbox label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.field.checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
}

.btn.danger {
  color: #ef4444;
}

.btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
}
</style>
