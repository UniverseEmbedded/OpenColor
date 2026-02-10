import { ref, watch, onMounted } from "vue";

/**
 * 语言设置管理组合式函数
 * 处理应用的语言切换、持久化和自动检测
 * 
 * @param {Object} locale vue-i18n 的 locale 对象
 * @param {Object} settings 配置项对象 (Ref)
 * @returns {Object} 包含语言设置相关的状态和方法
 */
export const useLocaleSetting = (locale, settings) => {
  // 当前语言设置，默认为 'auto' (自动检测)
  const localeSetting = ref(settings.value.locale || "auto");

  // 监听 settings 中的 locale 变化并同步
  watch(() => settings.value.locale, (newVal) => {
    if (newVal) localeSetting.value = newVal;
  });

  /**
   * 解析最终生效的语言标识符
   * @param {string} pref 用户偏好的语言设置
   * @returns {string} 最终的语言标识，如 'zh-CN' 或 'en-US'
   */
  const resolveLocale = (pref) => {
    if (pref && pref !== "auto") return pref;
    // 自动检测系统语言
    const lang = (navigator?.language || "").toLowerCase();
    if (lang.startsWith("zh")) return "zh-CN";
    return "en-US";
  };

  // 监听 localeSetting 变化，更新 i18n 的 locale
  watch(localeSetting, (newVal) => {
    locale.value = resolveLocale(newVal);
  }, { immediate: true });

  /**
   * 更新语言设置并保存到配置文件
   * @param {string} val 语言标识符
   */
  const updateLocale = (val) => {
    localeSetting.value = val;
    settings.value.locale = val;
  };

  return {
    localeSetting,
    updateLocale,
  };
};
