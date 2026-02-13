/**
 * 设置状态管理
 */

import { writable, get } from 'svelte/store';
import type { AppSettings, ProjectSettings, Theme, Locale } from '$lib/types';
import { setLanguage } from '$lib/i18n';

// 默认APP设置
const defaultAppSettings: AppSettings = {
  locale: 'zh-CN',
  theme: 'dark',
  currentWorkspace: '',
  recentWorkspaces: [],
  enginePath: 'auto',
  gpuAcceleration: true,
  logLevel: 'info',
  skipWindowSizeCheck: false,
  showWindowSizeOverlay: true,
};

// 默认项目设置
const defaultProjectSettings: ProjectSettings = {
  defaultMaterialGroupId: '',
  defaultLayerHeightMm: 0.2,
  defaultModelId: '',
  exportPreferences: {
    exportStl: true,
    export3mf: true,
    useCppAcceleration: true,
    meshRepair: true,
  },
  maskGenParams: {
    superresEnabled: true,
    superresScale: 2,
    layer0BiasEnabled: true,
    postprocessMode: 'joint',
  },
};

// 使用 writable store
const appSettings = writable<AppSettings>({ ...defaultAppSettings });
const projectSettings = writable<ProjectSettings>({ ...defaultProjectSettings });

// 从localStorage加载设置
function loadSettings() {
  if (typeof localStorage !== 'undefined') {
    const saved = localStorage.getItem('opencolor:settings');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        appSettings.set({ ...defaultAppSettings, ...parsed });
        // 应用主题
        applyTheme(get(appSettings).theme);
        // 应用语言
        setLanguage(get(appSettings).locale);
      } catch (e) {
        console.error('[Settings] 加载设置失败:', e);
      }
    }
  }
}

// 保存设置到localStorage
function saveSettings() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('opencolor:settings', JSON.stringify(get(appSettings)));
  }
}

// 应用主题
function applyTheme(theme: Theme) {
  const root = document.documentElement;
  
  if (theme === 'auto') {
    // 检测系统主题
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
  } else {
    root.setAttribute('data-theme', theme);
  }
}

// 监听系统主题变化
if (typeof window !== 'undefined') {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (get(appSettings).theme === 'auto') {
      document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    }
  });
}

// 创建设置 store
function createSettingsStore() {
  return {
    subscribe: (callback: (value: { appSettings: AppSettings; projectSettings: ProjectSettings }) => void) => {
      let currentApp = get(appSettings);
      let currentProject = get(projectSettings);
      callback({ appSettings: currentApp, projectSettings: currentProject });

      const unsubscribeApp = appSettings.subscribe(app => {
        currentApp = app;
        callback({ appSettings: currentApp, projectSettings: currentProject });
      });

      const unsubscribeProject = projectSettings.subscribe(project => {
        currentProject = project;
        callback({ appSettings: currentApp, projectSettings: currentProject });
      });

      return () => {
        unsubscribeApp();
        unsubscribeProject();
      };
    },
    
    get appSettings() { return get(appSettings); },
    get projectSettings() { return get(projectSettings); },
    
    updateAppSettings(settings: Partial<AppSettings>) {
      appSettings.update(current => ({ ...current, ...settings }));
      saveSettings();
    },
    
    setTheme(theme: Theme) {
      appSettings.update(current => ({ ...current, theme }));
      applyTheme(theme);
      saveSettings();
    },
    
    setLocale(locale: Locale) {
      appSettings.update(current => ({ ...current, locale }));
      setLanguage(locale);
      saveSettings();
    },
    
    updateProjectSettings(settings: Partial<ProjectSettings>) {
      projectSettings.update(current => ({ ...current, ...settings }));
    },

    setSkipWindowSizeCheck(skip: boolean) {
      appSettings.update(current => ({ ...current, skipWindowSizeCheck: skip }));
      saveSettings();
    },

    setShowWindowSizeOverlay(show: boolean) {
      appSettings.update(current => ({ ...current, showWindowSizeOverlay: show }));
      saveSettings();
    },

    init() {
      loadSettings();
    },
  };
}

// 导出单例
export const settingsStore = createSettingsStore();

// 直接导出 appSettings store 以便使用 $ 前缀订阅
export { appSettings };
