<template>
  <div class="image-preview">
    <img v-if="imageSrc" :src="imageSrc" :alt="alt" @error="handleError" />
    <div v-else class="loading-preview">
      <i :class="loading ? 'ti ti-loader-2 ti-spin' : 'ti ti-alert-circle'"></i>
      {{ loading ? (loadingText || '加载中...') : (errorText || '加载失败') }}
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  imageSrc: {
    type: String,
    default: ''
  },
  alt: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  },
  loadingText: {
    type: String,
    default: ''
  },
  errorText: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['error']);

const handleError = (event) => {
  emit('error', event);
};
</script>

<style scoped>
.image-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--bg-alpha);
  border-radius: 12px;
  padding: 16px;
  min-height: 300px;
}

.image-preview img {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  border-radius: 8px;
}

.loading-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--muted);
}
</style>
