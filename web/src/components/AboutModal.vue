<template>
  <div class="modal" :class="{ show: isOpen }" role="dialog" aria-modal="true" aria-labelledby="aboutTitle" @click.self="$emit('close')">
    <div class="box" style="width:min(480px, 92vw)">
      <div class="hd">
        <!-- 模态框标题 -->
        <b id="aboutTitle"><i class="ti ti-alert-circle"></i> {{ t("modal.aboutTitle") }}</b>
        <!-- 关闭按钮 -->
        <button class="btn" @click="$emit('close')"><i class="ti ti-x"></i>{{ t("btn.close") }}</button>
      </div>
      <div class="bd" style="text-align:center; padding:30px 20px">
        <!-- Logo 区域 -->
        <div class="logo-big">
          <img 
            src="/src/assets/icon.svg" 
            alt="OpenColor Logo" 
            @click="triggerEasterEgg"
            :class="{ 'easter-egg': isEasterEgg }"
          />
        </div>
        <!-- 应用名称 -->
        <h2 style="margin:0 0 10px; font-size:24px">{{ t("app.name") }}</h2>
        <!-- 应用描述 -->
        <p style="color:var(--muted); font-size:14px; line-height:1.6; margin-bottom:24px">
          {{ t("modal.aboutDesc") }}
        </p>
        <div class="hr"></div>
        <!-- GitHub 链接 -->
        <div style="margin:20px 0">
          <a href="https://github.com/UniverseEmbedded/OpenColor" target="_blank" style="color:var(--accent); text-decoration:none; display:flex; align-items:center; justify-content:center; gap:8px; font-size:14px">
            <i class="ti ti-brand-github" style="font-size:20px"></i>
            {{ t("modal.aboutGithub") }}
          </a>
        </div>
        <!-- 版本信息 -->
        <div class="muted" style="font-size:12px; margin-top:30px">
          {{ t("modal.aboutVersion") }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 导入 Vue 响应式 API
import { ref } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";

// 获取国际化翻译函数
const { t } = useI18n();
// 彩蛋动画状态
const isEasterEgg = ref(false);

// 定义组件属性
const props = defineProps({
  isOpen: Boolean // 是否打开
});

// 定义组件事件
const emit = defineEmits(['close']);

// 触发彩蛋动画
const triggerEasterEgg = () => {
  if (isEasterEgg.value) return;
  isEasterEgg.value = true;
  // 动画时长约 3.5s，之后恢复
  setTimeout(() => {
    isEasterEgg.value = false;
  }, 3500);
};
</script>
