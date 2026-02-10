<template>
  <aside class="sidebar">
    <!-- 导航菜单 -->
    <nav class="nav" aria-label="Navigation">
      <!-- 生成视图按钮 -->
      <button :class="{ active: currentView === 'generate' }" class="centered" @click="setView('generate')">
        <span class="ico"><i class="ti ti-wand"></i></span>
        <span class="btn-label">{{ t("nav.generate") }}</span>
      </button>
      <!-- 校准视图按钮 -->
      <button :class="{ active: currentView === 'calibrate' }" class="centered" @click="setView('calibrate')">
        <span class="ico"><i class="ti ti-camera"></i></span>
        <span class="btn-label">{{ t("nav.calibrate") }}</span>
      </button>
      <!-- 相册视图按钮 -->
      <button :class="{ active: currentView === 'album' }" class="centered" @click="setView('album')">
        <span class="ico"><i class="ti ti-photo"></i></span>
        <span class="btn-label">{{ t("nav.album") }}</span>
      </button>
      <!-- 材料视图按钮 -->
      <button :class="{ active: currentView === 'materials' }" class="centered" @click="setView('materials')">
        <span class="ico"><i class="ti ti-database"></i></span>
        <span class="btn-label">{{ t("nav.materials") }}</span>
      </button>
      <!-- 设置视图按钮 -->
      <button :class="{ active: currentView === 'settings' }" class="centered" @click="setView('settings')">
        <span class="ico"><i class="ti ti-settings"></i></span>
        <span class="btn-label">{{ t("nav.settings") }}</span>
      </button>
    </nav>

    <!-- 侧边卡片：工作空间状态 -->
    <div class="sidecard">
      <h3><i class="ti ti-layout-board"></i>{{ t("sections.workspace") }}</h3>
      <div class="kpi">
        <span class="chip"><i class="ti ti-file-import"></i>{{ chipInput }}</span>
        <span class="chip"><i class="ti ti-database"></i>{{ chipProfile }}</span>
        <span class="chip"><i class="ti ti-printer"></i>{{ chipOutput }}</span>
      </div>
    </div>

    <!-- 侧边操作按钮 -->
    <div class="side-actions">
      <!-- 帮助按钮 -->
      <button class="btn ghost sidebar-only" @click="$emit('openHelp')">
        <i class="ti ti-help"></i><span class="btn-label">{{ t("top.help") }}</span>
      </button>
      <!-- 打开输出目录按钮 -->
      <button class="btn sidebar-only" @click="$emit('openOutput')">
        <i class="ti ti-folder"></i><span class="btn-label">{{ t("top.openOutput") }}</span>
      </button>
      <!-- 关于按钮 -->
      <button class="btn ghost sidebar-only" @click="$emit('openAbout')">
        <i class="ti ti-alert-circle"></i><span class="btn-label">{{ t("footer.about") }}</span>
      </button>
    </div>
  </aside>
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
  currentView: String,    // 当前视图
  chipInput: String,      // 输入状态芯片
  chipProfile: String,   // 配置文件状态芯片
  chipOutput: String     // 输出状态芯片
});

// 定义组件事件
const emit = defineEmits(['setView', 'openHelp', 'openOutput', 'openAbout']);

// 设置视图函数
const setView = (view) => {
  emit('setView', view);
};
</script>
