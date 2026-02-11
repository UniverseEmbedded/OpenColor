/**
 * lib 统一导出
 */

// 类型
export * from './types';

// 状态管理
export { settingsStore } from './stores/settings.svelte';
export { navigationStore, navItems } from './stores/navigation.svelte';

// 国际化
export { _, locale, setLanguage, getCurrentLanguage } from './i18n';

// Tauri桥接
export { getTauriBridge } from './tauri/bridge';
