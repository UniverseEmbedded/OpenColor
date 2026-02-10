<template>
  <div class="topbar oc-edge oc-panel">
    <!-- 标题区域 -->
    <div class="title">
      <h2>{{ pageTitle }}</h2>
      <p>{{ pageSubtitle }}</p>
    </div>
    <!-- 操作按钮区域 -->
    <div class="actions">
      <!-- 帮助按钮（仅在顶部栏显示） -->
      <button class="btn ghost topbar-only" @click="$emit('openHelp')"><i class="ti ti-help"></i>{{ t("top.help") }}</button>
      <!-- 打开输出目录按钮（仅在顶部栏显示） -->
      <button class="btn topbar-only" @click="$emit('openOutput')"><i class="ti ti-folder"></i>{{ t("top.openOutput") }}</button>
    </div>
  </div>
</template>

<script setup>
// 导入 Vue 计算属性
import { computed } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
const props = defineProps({
  currentView: String // 当前视图名称
});

// 定义组件事件
defineEmits(['openHelp', 'openOutput']);

// 计算属性：根据当前视图返回页面标题
const pageTitle = computed(() => {
  if (props.currentView === "generate") return t("page.generateTitle");
  if (props.currentView === "calibrate") return t("page.calibrateTitle");
  if (props.currentView === "materials") return t("page.materialsTitle");
  if (props.currentView === "album") return t("page.albumTitle");
  return t("page.settingsTitle");
});

// 计算属性：根据当前视图返回页面副标题
const pageSubtitle = computed(() => {
  if (props.currentView === "generate") return t("page.generateSubtitle");
  if (props.currentView === "calibrate") return t("page.calibrateSubtitle");
  if (props.currentView === "materials") return t("page.materialsSubtitle");
  if (props.currentView === "album") return t("page.albumSubtitle");
  return t("page.settingsSubtitle");
});
</script>
