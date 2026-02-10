// 国际化配置文件
import { createI18n } from "vue-i18n";
// 导入语言包
import zhCN from "./locales/zh-CN.json";
import enUS from "./locales/en-US.json";

// 创建 i18n 实例
const i18n = createI18n({
  legacy: false, // 使用组合式 API
  locale: localStorage.getItem("locale") || "zh-CN", // 从本地存储读取语言，默认中文
  fallbackLocale: {
    "zh": ["zh-CN"],
    "en": ["en-US"],
    "default": ["zh-CN"]
  }, // 回退语言配置
  messages: {
    "zh-CN": zhCN, // 中文语言包
    "en-US": enUS,  // 英文语言包
    "zh": zhCN, // 添加 zh 映射到 zh-CN
    "en": enUS  // 添加 en 映射到 en-US
  }
});

export default i18n;
