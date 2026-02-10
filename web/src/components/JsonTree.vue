<template>
  <div class="json-tree">
    <template v-if="isObject">
      <div class="json-object">
        <div v-for="(value, key) in data" :key="key" class="json-item">
          <div class="json-key-value" @click="toggle(key)">
            <span class="json-toggle">
              <i v-if="isExpandable(value)" class="ti" :class="isExpanded(key) ? 'ti-chevron-down' : 'ti-chevron-right'"></i>
              <i v-else class="ti ti-minus" style="opacity:0"></i>
            </span>
            <span class="json-key">"{{ key }}"</span>
            <span class="json-colon">:</span>
            <span v-if="!isExpandable(value)" class="json-value" :class="getValueType(value)">
              {{ formatValue(value) }}
            </span>
            <span v-else class="json-bracket">
              {{ getBracketText(value) }}
            </span>
          </div>
          <div v-if="isExpandable(value) && isExpanded(key)" class="json-children">
            <JsonTree :data="value" :depth="depth + 1" />
          </div>
        </div>
      </div>
    </template>
    <template v-else-if="isArray">
      <div class="json-array">
        <div v-for="(item, index) in displayedItems" :key="index" class="json-item">
          <div class="json-key-value" @click="toggle(index)">
            <span class="json-toggle">
              <i v-if="isExpandable(item)" class="ti" :class="isExpanded(index) ? 'ti-chevron-down' : 'ti-chevron-right'"></i>
              <i v-else class="ti ti-minus" style="opacity:0"></i>
            </span>
            <span class="json-index">[{{ index }}]</span>
            <span class="json-colon">:</span>
            <span v-if="!isExpandable(item)" class="json-value" :class="getValueType(item)">
              {{ formatValue(item) }}
            </span>
            <span v-else class="json-bracket">
              {{ getBracketText(item) }}
            </span>
          </div>
          <div v-if="isExpandable(item) && isExpanded(index)" class="json-children">
            <JsonTree :data="item" :depth="depth + 1" />
          </div>
        </div>
        <div v-if="data.length > maxItems" class="json-more" @click="showAll = !showAll">
          <i class="ti" :class="showAll ? 'ti-chevron-up' : 'ti-chevron-down'"></i>
          {{ showAll ? '收起' : `展开全部 ${data.length} 项` }}
        </div>
      </div>
    </template>
    <template v-else>
      <span class="json-value" :class="getValueType(data)">{{ formatValue(data) }}</span>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  data: { type: [Object, Array, String, Number, Boolean], required: true },
  depth: { type: Number, default: 0 }
});

const maxItems = 50;
const showAll = ref(false);
const expandedKeys = ref(new Set());

const isObject = computed(() => props.data !== null && typeof props.data === 'object' && !Array.isArray(props.data));
const isArray = computed(() => Array.isArray(props.data));

const displayedItems = computed(() => {
  if (!isArray.value) return [];
  return showAll.value ? props.data : props.data.slice(0, maxItems);
});

const isExpandable = (value) => {
  return value !== null && typeof value === 'object';
};

const toggle = (key) => {
  if (expandedKeys.value.has(key)) {
    expandedKeys.value.delete(key);
  } else {
    expandedKeys.value.add(key);
  }
};

const isExpanded = (key) => expandedKeys.value.has(key);

const getValueType = (value) => {
  if (value === null) return 'json-null';
  if (typeof value === 'string') return 'json-string';
  if (typeof value === 'number') return 'json-number';
  if (typeof value === 'boolean') return 'json-boolean';
  return 'json-object';
};

const formatValue = (value) => {
  if (value === null) return 'null';
  if (typeof value === 'string') return `"${value}"`;
  return String(value);
};

const getBracketText = (value) => {
  if (Array.isArray(value)) {
    return '[' + value.length + ']';
  }
  return '{' + Object.keys(value).length + '}';
};
</script>

<style scoped>
.json-tree {
  font-family: var(--mono);
  font-size: 13px;
  line-height: 1.6;
}

.json-item {
  margin: 2px 0;
}

.json-key-value {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background 0.2s;
}

.json-key-value:hover {
  background: var(--bg-alpha);
}

.json-toggle {
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
}

.json-key {
  color: #9cdcfe;
  font-weight: 500;
}

.json-index {
  color: #9cdcfe;
  font-weight: 500;
}

.json-colon {
  color: var(--text);
}

.json-value {
  word-break: break-all;
}

.json-string {
  color: #ce9178;
}

.json-number {
  color: #b5cea8;
}

.json-boolean {
  color: #569cd6;
}

.json-null {
  color: #569cd6;
}

.json-bracket {
  color: var(--muted);
  font-style: italic;
}

.json-children {
  padding-left: 20px;
  border-left: 1px solid var(--line);
  margin-left: 8px;
}

.json-more {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  margin-top: 4px;
  color: var(--muted);
  cursor: pointer;
  font-size: 12px;
  border-radius: 4px;
  transition: background 0.2s;
}

.json-more:hover {
  background: var(--bg-alpha);
}
</style>
