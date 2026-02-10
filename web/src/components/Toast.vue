<template>
  <div class="toast" :class="{ show: visible }">
    <!-- 提示标题 -->
    <p class="t">{{ title }}</p>
    <!-- 提示副标题 -->
    <p class="s">{{ subtitle }}</p>
  </div>
</template>

<script setup>
// 定义组件属性
const props = defineProps({
  visible: Boolean, // 是否可见
  title: String,   // 标题
  subtitle: String // 副标题
});
</script>
