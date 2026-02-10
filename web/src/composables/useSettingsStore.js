import { ref, watch } from "vue";

/**
 * 配置项管理组合式函数
 * 负责应用配置的加载、保存和持久化
 * 
 * @param {Function} invoke Tauri 的 invoke 函数
 * @returns {Object} 包含配置状态和操作方法的对象
 */
export const useSettingsStore = (invoke) => {
  // 响应式配置对象
  const settings = ref({
    locale: "auto", // 语言设置：auto/zh-CN/en-US
    theme: "auto",  // 主题设置：auto/light/dark
    skipWindowSizeCheck: false, // 是否跳过窗口尺寸检查
  });

  /**
   * 从后端或本地迁移加载设置
   */
  const load = async () => {
    try {
      // 尝试从后端配置文件加载
      const loaded = await invoke("load_settings");
      if (loaded && typeof loaded === "object") {
        settings.value = { ...settings.value, ...loaded };
      } else {
        // 如果后端没有配置，尝试从旧版本的 localStorage 迁移
        const oldLocale = localStorage.getItem("locale");
        const oldTheme = localStorage.getItem("theme");
        if (oldLocale || oldTheme) {
          if (oldLocale) settings.value.locale = oldLocale;
          if (oldTheme) settings.value.theme = oldTheme;
          // 迁移后立即保存到后端
          await save();
          console.log("已从 localStorage 迁移设置项");
        }
      }
    } catch (e) {
      console.error("加载设置失败:", e);
    }
  };

  /**
   * 将当前设置保存到后端配置文件
   */
  const save = async () => {
    try {
      await invoke("save_settings", { settings: settings.value });
    } catch (e) {
      console.error("保存设置失败:", e);
    }
  };

  // 深度监听设置变化，一旦变化自动调用保存
  watch(settings, () => {
    save();
  }, { deep: true });

  return {
    settings,
    load,
    save
  };
};
