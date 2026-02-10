<template>
  <section class="view oc-edge">
    <div class="subnav oc-edge oc-panel">
      <button :class="{ active: settingsTab === 0 }" @click="settingsTab = 0">{{ t("sections.preferences") }}</button>
      <button :class="{ active: settingsTab === 1 }" @click="settingsTab = 1">{{ t("sections.advOptions") }}</button>
    </div>

    <div class="grid oc-edge">
      <div class="card" :class="{ active: settingsTab === 0 }">
        <div class="hd">
          <div style="display:flex; align-items:center; gap:8px">
            <i class="ti ti-settings" style="opacity:0.6"></i>
            <h3>{{ t("sections.preferences") }}</h3>
          </div>
        </div>
        <div class="bd" style="gap:24px">
          <div class="field">
            <label><i class="ti ti-language"></i>{{ t("label.language") }}</label>
            <select :value="localeSetting" @change="$emit('update:localeSetting', $event.target.value)" style="width:100%">
              <option value="auto">{{ t("lang.auto") }}</option>
              <option value="zh-CN">{{ t("lang.zh") }}</option>
              <option value="en-US">{{ t("lang.en") }}</option>
            </select>
          </div>

          <div class="field">
            <label><i class="ti ti-palette"></i>{{ t("label.theme") }}</label>
            <select :value="theme" @change="$emit('update:theme', $event.target.value)" style="width:100%">
              <option value="auto">{{ t("option.themeAuto") }}</option>
              <option value="dark">{{ t("option.themeDark") }}</option>
              <option value="light">{{ t("option.themeLight") }}</option>
            </select>
          </div>

          <div class="field">
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer">
              <input type="checkbox" :checked="skipWindowSizeCheck" @change="$emit('update:skipWindowSizeCheck', $event.target.checked)" />
              <span>{{ t("label.skipWindowSizeCheck") }}</span>
            </label>
          </div>
        </div>
      </div>
      <div class="card" :class="{ active: settingsTab === 1 }">
        <div class="hd">
          <h3>{{ t("sections.advOptions") }}</h3>
        </div>
        <div class="bd" style="gap:24px">
          <div class="field">
            <label><i class="ti ti-folder"></i>{{ t("label.defaultOutputDir") }}</label>
            <input :value="outputDir" readonly />
            <div class="row" style="margin-top:8px">
              <button class="btn" @click="$emit('pickOutputDir')"><i class="ti ti-folder-open"></i>{{ t("btn.chooseOutputDir") }}</button>
              <button class="btn ghost" @click="$emit('clearOutputDir')"><i class="ti ti-trash"></i>{{ t("btn.clearOutputDir") }}</button>
            </div>
          </div>
          <div class="row row-adaptive">
            <div class="field">
              <label><i class="ti ti-brush"></i>{{ t("label.svgPalette") }}</label>
              <select :value="svgPaletteMode" @change="$emit('update:svgPaletteMode', $event.target.value)">
                <option value="strict">{{ t("option.svgPaletteStrict") }}</option>
                <option value="nearest">{{ t("option.svgPaletteNearest") }}</option>
                <option value="auto">{{ t("option.svgPaletteAuto") }}</option>
              </select>
            </div>
            <div class="field">
              <label><i class="ti ti-layers"></i>{{ t("label.svgThickness") }}</label>
              <input :value="svgThickness" @input="$emit('update:svgThickness', $event.target.value)" type="number" step="0.05" />
            </div>
            <div class="field">
              <label><i class="ti ti-precision"></i>{{ t("label.svgTol") }}</label>
              <input :value="svgTol" @input="$emit('update:svgTol', $event.target.value)" type="number" step="0.01" />
            </div>
            <div class="field">
              <label><i class="ti ti-border-all"></i>{{ t("label.svgMinArea") }}</label>
              <input :value="svgMinArea" @input="$emit('update:svgMinArea', $event.target.value)" type="number" step="0.01" />
            </div>
          </div>
          <div class="row row-adaptive">
            <div class="field">
              <label><i class="ti ti-crop"></i>{{ t("label.svgSimplify") }}</label>
              <input :value="svgSimplify" @input="$emit('update:svgSimplify', $event.target.value)" type="number" step="0.01" />
            </div>
            <div class="field">
              <label><i class="ti ti-settings"></i>{{ t("label.svgPaletteTol") }}</label>
              <input :value="svgPaletteTol" @input="$emit('update:svgPaletteTol', $event.target.value)" type="number" step="1" />
            </div>
          </div>
          <div class="hr"></div>
          <div class="field">
            <label><i class="ti ti-plug"></i>{{ t("btn.pingEngine") }}</label>
            <div class="row">
              <button class="btn" @click="$emit('pingEngine')">
                <i class="ti ti-plug"></i> {{ t("btn.pingEngine") }}
              </button>
            </div>
          </div>
          <div class="hint">{{ t("hint.svgAdvTip") }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
// 导入 Vue 响应式 API
import { ref } from "vue";
// 导入国际化功能
import { useI18n } from "vue-i18n";

// 获取国际化翻译函数
const { t } = useI18n();

// 定义组件属性
const props = defineProps({
  localeSetting: String,   // 语言设置
  theme: String,          // 主题
  skipWindowSizeCheck: Boolean, // 是否跳过窗口尺寸检查
  outputDir: String,      // 输出目录
  svgPaletteMode: String, // SVG 调色板模式
  svgThickness: Number,   // SVG 厚度
  svgTol: Number,        // SVG 容差
  svgMinArea: Number,    // SVG 最小面积
  svgSimplify: Number,   // SVG 简化参数
  svgPaletteTol: Number  // SVG 调色板容差
});

// 定义组件事件
defineEmits(['openAbout', 'pickOutputDir', 'clearOutputDir', 'pingEngine', 'update:localeSetting', 'update:theme', 'update:skipWindowSizeCheck', 'update:svgPaletteMode', 'update:svgThickness', 'update:svgTol', 'update:svgMinArea', 'update:svgSimplify', 'update:svgPaletteTol']);

// 当前选中的设置选项卡
const settingsTab = ref(0);
</script>
