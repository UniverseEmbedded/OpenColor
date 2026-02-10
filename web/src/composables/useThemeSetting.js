import { onMounted, ref, watch } from "vue";

/**
 * 主题设置管理组合式函数
 * 处理应用的主题切换、自动跟随系统以及持久化
 * 
 * @param {Object} settings 配置项对象 (Ref)
 * @returns {Object} 包含主题状态的对象
 */
export const useThemeSetting = (settings) => {
  // 当前主题设置，默认为 'auto' (自动)
  const theme = ref(settings.value.theme || "auto");

  // 监听外部 settings 的变化（例如从文件加载后）
  watch(() => settings.value.theme, (newVal) => {
    if (newVal) theme.value = newVal;
  });

  /**
   * 应用主题到 DOM 元素
   * 通过设置 html 元素的 data-theme 属性来实现 CSS 变量切换
   * 
   * @param {string} val 主题名称 'light'/'dark'/'auto'
   */
  const applyTheme = (val) => {
    let targetTheme = val;
    if (val === "auto") {
      // 自动模式下检测系统偏好
      targetTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }
    document.documentElement.setAttribute("data-theme", targetTheme);
  };

  // 监听 theme 变化，保存到配置并应用主题
  watch(theme, (newVal) => {
    settings.value.theme = newVal;
    applyTheme(newVal);
  });

  onMounted(() => {
    // 初次加载时应用主题
    applyTheme(theme.value);
    // 监听系统主题变化事件
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
      // 只有在 auto 模式下才自动响应系统变化
      if (theme.value === "auto") applyTheme("auto");
    });
  });

  return {
    theme
  };
};
