<template>
  <div class="modal" :class="{ show: isOpen }" role="dialog" aria-modal="true" @click.self="$emit('close')">
    <div class="box" style="width: min(600px, 95vw)">
      <div class="hd">
        <b><i class="ti ti-plus"></i> {{ t('modal.newGroupTitle') }}</b>
        <button class="btn" @click="$emit('close')"><i class="ti ti-x"></i> {{ t('modal.close') }}</button>
      </div>
      <div class="bd" style="max-height: 75vh; overflow-y: auto">
        
        <!-- 步骤 1: 选择模板 -->
        <div v-if="step === 1" class="step-content">
          <h4 style="margin-bottom: 16px"><i class="ti ti-template"></i> {{ t('modal.selectTemplate') }}</h4>
          <div class="templates-grid">
            <div 
              v-for="template in templates" 
              :key="template.id"
              class="template-card"
              :class="{ active: selectedTemplate?.id === template.id }"
              @click="selectTemplate(template)"
            >
              <div class="template-preview">
                <div 
                  v-for="(slot, idx) in template.slots" 
                  :key="idx"
                  class="template-color"
                  :class="{ transparent: slot.filament?.isTransparent }"
                  :style="{ background: slot.filament?.isTransparent ? undefined : `rgba(${slot.filament?.targetColor?.rgba?.join(',')})` }"
                ></div>
              </div>
              <div class="template-info">
                <span class="template-name">{{ template.name }}</span>
                <span class="template-desc">{{ template.descriptionKey ? t(template.descriptionKey) : template.description }}</span>
                <span class="template-count">{{ t('modal.colorCount', { n: template.channelCount }) }}</span>
              </div>
            </div>
            
            <!-- 空白模板 -->
            <div 
              class="template-card blank"
              :class="{ active: selectedTemplate === null }"
              @click="selectTemplate(null)"
            >
              <div class="template-preview blank-preview">
                <i class="ti ti-layout-grid-add"></i>
              </div>
              <div class="template-info">
                <span class="template-name">{{ t('modal.blankConfig') }}</span>
                <span class="template-desc">{{ t('modal.startFromScratch') }}</span>
                <span class="template-count">{{ t('modal.custom') }}</span>
              </div>
            </div>
          </div>
          
          <div class="step-actions">
            <button class="btn" @click="$emit('close')">{{ t('modal.cancel') }}</button>
            <button class="btn primary" @click="step = 2" :disabled="selectedTemplate === undefined">
              {{ t('modal.nextStep') }} <i class="ti ti-arrow-right"></i>
            </button>
          </div>
        </div>
        
        <!-- 步骤 2: 配置详情 -->
        <div v-else class="step-content">
          <h4 style="margin-bottom: 16px"><i class="ti ti-settings"></i> {{ t('modal.configDetails') }}</h4>

          <!-- 名称 -->
          <div class="field" style="margin-bottom: 16px">
            <label><i class="ti ti-tag"></i> {{ t('modal.groupName') }}</label>
            <input v-model="form.name" :placeholder="defaultName" />
          </div>

          <!-- 通道数量 -->
          <div class="field" style="margin-bottom: 16px">
            <label>
              <i class="ti ti-layers-linked"></i> {{ t('modal.channelCount') }}
              <span v-if="isFromTemplate" class="locked-badge">（{{ t('modal.locked') }}）</span>
            </label>
            <div class="channel-selector" :class="{ locked: isFromTemplate }">
              <button
                v-for="n in [3, 4, 5, 6, 8, 9]"
                :key="'channel-' + n"
                class="channel-btn"
                :class="{ active: form.channelCount === n, disabled: isFromTemplate && form.channelCount !== n }"
                @click="!isFromTemplate && (form.channelCount = n)"
                :disabled="isFromTemplate"
              >
                {{ t('modal.colorCount', { n }) }}
              </button>
            </div>
            <small v-if="isFromTemplate" class="hint-text">{{ t('modal.channelLockedHint') }}</small>
          </div>

          <!-- 耗材分配 -->
          <div class="field" style="margin-bottom: 16px">
            <label><i class="ti ti-box"></i> {{ t('modal.filamentAssignment') }}</label>
            <div class="slots-config">
              <div v-for="(slot, index) in form.slots" :key="slot.slotIndex ?? index" class="slot-row">
                <span class="slot-label">{{ t('modal.slot') }} {{ index + 1 }}</span>
                <select v-model="form.slots[index].filamentId" class="slot-select">
                  <option value="">-- {{ t('modal.selectFilament') }} --</option>
                  <option v-for="filament in availableFilaments" :key="filament.id" :value="filament.id">
                    {{ filament.name }} ({{ filament.brand }})
                  </option>
                </select>
                <div
                  v-if="form.slots[index].filamentId"
                  class="slot-color-preview"
                  :style="{ background: getFilamentColor(form.slots[index].filamentId) }"
                ></div>
              </div>
            </div>
          </div>

          <!-- 预览 -->
          <div class="preview-section">
            <label><i class="ti ti-eye"></i> {{ t('modal.preview') }}</label>
            <div class="color-preview">
              <div
                v-for="(slot, index) in form.slots"
                :key="index"
                class="color-block"
                :style="{ background: getFilamentColor(slot.filamentId) || '#e5e5e5' }"
              >
                <span>{{ index + 1 }}</span>
              </div>
            </div>
          </div>

          <div class="step-actions">
            <button class="btn" @click="step = 1"><i class="ti ti-arrow-left"></i> {{ t('modal.prevStep') }}</button>
            <button class="btn primary" @click="submit" :disabled="!isValid">
              <i class="ti ti-check"></i> {{ t('modal.create') }}
            </button>
          </div>
        </div>
        
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = defineProps({
  isOpen: Boolean,
  availableFilaments: { type: Array, default: () => [] },
  templates: { type: Array, default: () => [] },
  // 可选：外部传入的创建临时耗材函数
  createTempFilamentsFn: { type: Function, default: null }
});

const emit = defineEmits(['close', 'submit', 'createFilamentsFromTemplate']);

const step = ref(1);
const selectedTemplate = ref(undefined);
const isFromTemplate = ref(false);
const templateSlotMapping = ref(new Map()); // 模板槽位到耗材ID的映射

const form = ref({
  name: '',
  channelCount: 4,
  slots: []
});

// 所有可用的通道数量选项
const channelOptions = [3, 4, 5, 6, 8, 9];

// 生成默认名称
const defaultName = computed(() => {
  if (selectedTemplate.value) {
    return t('modal.defaultGroupName', { name: selectedTemplate.value.name });
  }
  return t('modal.newGroupDefault');
});

// 验证
const isValid = computed(() => {
  return form.value.name.trim() !== '' && 
         form.value.slots.some(s => s.filamentId !== '');
});

// 监听弹窗打开
watch(() => props.isOpen, (isOpen) => {
  if (isOpen) {
    step.value = 1;
    selectedTemplate.value = undefined;
    isFromTemplate.value = false;
    templateSlotMapping.value = new Map();
    form.value = {
      name: '',
      channelCount: 4,
      slots: Array(4).fill(null).map((_, i) => ({ slotIndex: i, filamentId: '' }))
    };
  }
});

// 监听通道数量变化（仅空白配置时有效）
watch(() => form.value.channelCount, (newCount) => {
  // 如果是从模板创建的，不允许修改通道数量
  if (isFromTemplate.value) return;
  
  const currentSlots = form.value.slots;
  if (newCount > currentSlots.length) {
    // 添加槽位
    for (let i = currentSlots.length; i < newCount; i++) {
      currentSlots.push({ slotIndex: i, filamentId: '' });
    }
  } else if (newCount < currentSlots.length) {
    // 移除槽位
    form.value.slots = currentSlots.slice(0, newCount);
  }
});

const selectTemplate = async (template) => {
  selectedTemplate.value = template;
  
  if (template) {
    // 从模板创建
    isFromTemplate.value = true;
    form.value.name = t('modal.defaultGroupName', { name: template.name });
    
    // 先根据模板初始化槽位（使用临时ID）
    // 注意：必须先设置slots，再设置channelCount，避免watch截断槽位
    form.value.slots = template.slots.map((slot, i) => ({
      slotIndex: i,
      filamentId: slot.filament?.id || ''
    }));
    
    // 设置通道数量（在slots之后设置，避免watch触发截断）
    form.value.channelCount = template.channelCount;
    
    console.log('[模板] 初始化槽位:', form.value.slots.length, '个槽位, 通道数:', template.channelCount);
    
    // 通知父组件创建临时耗材，并等待完成
    // 此时耗材还未保存到数据库，只是临时创建
    await new Promise(resolve => {
      emit('createFilamentsFromTemplate', template.slots, () => {
        resolve();
      });
    });
    
    // 临时耗材创建完成后，更新槽位的 filamentId
    // 使用 nextTick 确保父组件已经更新了 availableFilaments
    await nextTick();
    
    // 根据模板中的理想颜色匹配新创建的临时耗材
    form.value.slots = form.value.slots.map((slot, i) => {
      const templateSlot = template.slots[i];
      if (templateSlot?.filament) {
        // 查找匹配的临时耗材（通过理想颜色匹配）
        const matchedFilament = props.availableFilaments.find(f => 
          f.targetColor?.hex === templateSlot.filament.targetColor?.hex
        );
        if (matchedFilament) {
          return { ...slot, filamentId: matchedFilament.id };
        }
      }
      return slot;
    });
    
    console.log('[模板] 更新槽位耗材ID:', form.value.slots);
  } else {
    // 空白配置
    isFromTemplate.value = false;
    templateSlotMapping.value = new Map();
    form.value.name = '';
    form.value.slots = Array(4).fill(null).map((_, i) => ({ slotIndex: i, filamentId: '' }));
    form.value.channelCount = 4;
    
    // 通知父组件清理临时耗材
    emit('createFilamentsFromTemplate', null, null);
  }
};

const getFilamentColor = (filamentId) => {
  if (!filamentId) return null;
  const filament = props.availableFilaments.find(f => f.id === filamentId);
  if (!filament) return null;
  // 优先使用理想颜色
  if (filament.targetColor?.rgba) {
    return `rgba(${filament.targetColor.rgba.join(',')})`;
  }
  // 兼容旧格式
  return filament.colorHex || (filament.rgba ? `rgba(${filament.rgba.join(',')})` : null);
};

const submit = () => {
  if (!isValid.value) return;
  
  const profile = {
    name: form.value.name.trim() || defaultName.value,
    channelCount: form.value.channelCount,
    slots: form.value.slots.map((slot, index) => ({
      slotIndex: index,
      filamentId: slot.filamentId,
      filament: props.availableFilaments.find(f => f.id === slot.filamentId)
    })).filter(s => s.filamentId),
    // 标记是否来自模板，用于父组件决定是否保存临时耗材
    isFromTemplate: isFromTemplate.value
  };
  
  emit('submit', profile);
  emit('close');
};
</script>

<style scoped>
.step-content {
  padding: 8px;
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.template-card {
  border: 2px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.template-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.template-card.active {
  border-color: var(--primary-color);
  background: rgba(74, 158, 255, 0.1);
}

.template-card.blank {
  border-style: dashed;
}

.template-preview {
  display: flex;
  justify-content: center;
  gap: 4px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  min-height: 32px;
}

.template-color {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
}

.template-color.transparent {
  background: 
    linear-gradient(45deg, #ccc 25%, transparent 25%),
    linear-gradient(-45deg, #ccc 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #ccc 75%),
    linear-gradient(-45deg, transparent 75%, #ccc 75%);
  background-size: 8px 8px;
  background-position: 0 0, 0 4px, 4px -4px, -4px 0px;
  background-color: #fff;
}

.template-preview .more {
  font-size: 11px;
  color: var(--muted);
  align-self: center;
}

.blank-preview {
  align-items: center;
}

.blank-preview i {
  font-size: 32px;
  color: var(--muted);
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-name {
  font-weight: 600;
  font-size: 14px;
}

.template-desc {
  font-size: 12px;
  color: var(--muted);
}

.template-count {
  font-size: 11px;
  color: var(--primary-color);
  font-weight: 500;
}

.channel-selector {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  min-height: 40px;
}

.channel-selector:empty::after {
  content: 'Loading...';
  color: var(--muted);
  font-size: 12px;
}

.channel-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-color);
  color: var(--text-color);
  cursor: pointer;
  transition: all 0.2s;
}

.channel-btn:hover {
  border-color: var(--primary-color);
}

.channel-btn.active {
  background: var(--primary-color, #4a9eff);
  color: #ffffff;
  border-color: var(--primary-color, #4a9eff);
  font-weight: 600;
}

.channel-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.channel-selector.locked {
  opacity: 0.8;
}

.locked-badge {
  color: var(--primary-color);
  font-size: 12px;
  margin-left: 8px;
}

.hint-text {
  display: block;
  margin-top: 8px;
  color: var(--muted);
  font-size: 12px;
}

.slots-config {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
  padding: 8px;
  background: var(--bg-alpha);
  border-radius: 8px;
}

.slot-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slot-label {
  width: 70px;
  font-size: 13px;
  color: var(--muted);
}

.slot-select {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-color);
  color: var(--text-color);
}

.slot-color-preview {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  flex-shrink: 0;
}

.preview-section {
  margin-top: 20px;
  padding: 16px;
  background: var(--bg-alpha);
  border-radius: 8px;
}

.preview-section label {
  display: block;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--muted);
}

.color-preview {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.color-block {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
  border: 2px solid var(--border-color);
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}
</style>
