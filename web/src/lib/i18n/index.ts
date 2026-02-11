/**
 * 国际化配置
 */

import { locale, dictionary, _ } from 'svelte-i18n';

// 翻译字典
const zhCN = {
  // 通用
  'app.name': 'OpenColor',
  'app.loading': '加载中...',
  'app.error': '出错了',
  'app.save': '保存',
  'app.cancel': '取消',
  'app.confirm': '确认',
  'app.delete': '删除',
  'app.edit': '编辑',
  'app.create': '创建',
  'app.close': '关闭',
  'app.back': '返回',
  'app.next': '下一步',
  'app.done': '完成',
  'app.search': '搜索',
  'app.filter': '筛选',
  'app.refresh': '刷新',
  'app.settings': '设置',
  'app.help': '帮助',
  'app.about': '关于',
  
  // 导航
  'nav.calibrate': '校准',
  'nav.generate': '生成',
  'nav.library': '素材库',
  'nav.settings': '设置',
  
  // 校准子导航
  'nav.calibrate.boardGen': '校准板生成',
  'nav.calibrate.photoWarp': '照片校正与样本提取',
  'nav.calibrate.modelTrain': '模型训练',
  
  // 生成子导航
  'nav.generate.maskGen': '叠色像素生成',
  'nav.generate.vectorize': '矢量化',
  'nav.generate.export': '模型导出',
  
  // 素材库子导航
  'nav.library.boards': '校准板',
  'nav.library.photos': '照片',
  'nav.library.models': '模型',
  'nav.library.materials': '材料',
  'nav.library.exports': '生成文件',
  
  // 设置子导航
  'nav.settings.general': '通用',
  'nav.settings.workspace': '工作区',
  'nav.settings.engine': '引擎',
  'nav.settings.project': '项目',
  
  // 工作区
  'workspace.current': '当前工作区',
  'workspace.switch': '切换工作区',
  'workspace.create': '新建工作区',
  'workspace.createNew': '新建工作区',
  'workspace.open': '打开其他工作区',
  'workspace.openOther': '打开其他工作区',
  'workspace.recent': '最近工作区',
  'workspace.default': '默认工作区',
  'workspace.name': '工作区名称',
  'workspace.path': '工作区路径',
  'workspace.created': '创建时间',
  'workspace.lastOpened': '最后打开',
  'workspace.noCurrent': '无当前工作区',
  'workspace.noRecent': '无最近工作区',
  'workspace.remove': '从列表移除',
  'workspace.selectFolder': '选择文件夹',
  'workspace.openInExplorer': '在资源管理器中打开',
  
  // 设置页面
  'settings.general.title': '通用设置',
  'settings.general.language': '语言',
  'settings.general.language.zh': '中文',
  'settings.general.language.en': '英文',
  'settings.general.language.auto': '自动',
  'settings.general.theme': '主题',
  'settings.general.theme.dark': '深色',
  'settings.general.theme.light': '浅色',
  'settings.general.theme.auto': '跟随系统',
  'settings.general.logLevel': '日志级别',
  'settings.general.windowSizeOverlay': '窗口尺寸提示',
  'settings.general.showWindowSizeOverlay': '窗口过小时显示提示',
  'settings.general.windowSizeOverlayDesc': '当窗口尺寸过小时显示覆盖层提示，建议保持开启以获得最佳体验',

  'settings.workspace.title': '工作区管理',
  'settings.workspace.current': '当前工作区',
  'settings.workspace.actions': '操作',
  
  'settings.engine.title': '引擎设置',
  'settings.engine.path': '引擎路径',
  'settings.engine.gpu': 'GPU加速',
  'settings.engine.gpuAcceleration': '启用Vulkan GPU加速',
  'settings.project.title': '项目设置',
  
  // 状态
  'status.ready': '就绪',
  'status.processing': '处理中',
  'status.completed': '完成',
  'status.error': '错误',
  'status.connecting': '连接中',
  'status.connected': '已连接',
  'status.disconnected': '未连接',
  
  // 页面占位
  'page.developing': '开发中',
  'page.developing.desc': '该功能正在开发中，敬请期待',
  
  // API测试
  'api.test.title': 'API连通性测试',
  'api.test.webToRust': 'Web → Rust',
  'api.test.rustToPython': 'Rust → Python',
  'api.test.pythonResponse': 'Python响应',
  'api.test.run': '运行测试',
  'api.test.success': '测试成功',
  'api.test.failed': '测试失败',

  // 提示信息
  'hint.windowTooSmall': '窗口尺寸过小，请放大窗口以获得更好的体验',

  // 按钮
  'btn.neverShow': '不再显示',
};

const enUS = {
  // General
  'app.name': 'OpenColor',
  'app.loading': 'Loading...',
  'app.error': 'Error',
  'app.save': 'Save',
  'app.cancel': 'Cancel',
  'app.confirm': 'Confirm',
  'app.delete': 'Delete',
  'app.edit': 'Edit',
  'app.create': 'Create',
  'app.close': 'Close',
  'app.back': 'Back',
  'app.next': 'Next',
  'app.done': 'Done',
  'app.search': 'Search',
  'app.filter': 'Filter',
  'app.refresh': 'Refresh',
  'app.settings': 'Settings',
  'app.help': 'Help',
  'app.about': 'About',
  
  // Navigation
  'nav.calibrate': 'Calibrate',
  'nav.generate': 'Generate',
  'nav.library': 'Library',
  'nav.settings': 'Settings',
  
  // Calibrate sub-nav
  'nav.calibrate.boardGen': 'Board Generation',
  'nav.calibrate.photoWarp': 'Photo Warp & Sample',
  'nav.calibrate.modelTrain': 'Model Training',
  
  // Generate sub-nav
  'nav.generate.maskGen': 'Mask Generation',
  'nav.generate.vectorize': 'Vectorize',
  'nav.generate.export': 'Export',
  
  // Library sub-nav
  'nav.library.boards': 'Boards',
  'nav.library.photos': 'Photos',
  'nav.library.models': 'Models',
  'nav.library.materials': 'Materials',
  'nav.library.exports': 'Exports',
  
  // Settings sub-nav
  'nav.settings.general': 'General',
  'nav.settings.workspace': 'Workspace',
  'nav.settings.engine': 'Engine',
  'nav.settings.project': 'Project',
  
  // Workspace
  'workspace.current': 'Current Workspace',
  'workspace.switch': 'Switch Workspace',
  'workspace.create': 'Create Workspace',
  'workspace.createNew': 'Create New Workspace',
  'workspace.open': 'Open Other Workspace',
  'workspace.openOther': 'Open Other Workspace',
  'workspace.recent': 'Recent Workspaces',
  'workspace.default': 'Default Workspace',
  'workspace.name': 'Workspace Name',
  'workspace.path': 'Workspace Path',
  'workspace.created': 'Created At',
  'workspace.lastOpened': 'Last Opened',
  'workspace.noCurrent': 'No Current Workspace',
  'workspace.noRecent': 'No Recent Workspaces',
  'workspace.remove': 'Remove from List',
  'workspace.selectFolder': 'Select Folder',
  'workspace.openInExplorer': 'Open in Explorer',

  // Settings pages
  'settings.general.title': 'General Settings',
  'settings.general.language': 'Language',
  'settings.general.language.zh': 'Chinese',
  'settings.general.language.en': 'English',
  'settings.general.language.auto': 'Auto',
  'settings.general.theme': 'Theme',
  'settings.general.theme.dark': 'Dark',
  'settings.general.theme.light': 'Light',
  'settings.general.theme.auto': 'System',
  'settings.general.logLevel': 'Log Level',
  'settings.general.windowSizeOverlay': 'Window Size Hint',
  'settings.general.showWindowSizeOverlay': 'Show hint when window is too small',
  'settings.general.windowSizeOverlayDesc': 'Display an overlay hint when the window size is too small. Recommended to keep enabled for the best experience.',

  'settings.workspace.title': 'Workspace Management',
  'settings.workspace.current': 'Current Workspace',
  'settings.workspace.actions': 'Actions',
  
  'settings.engine.title': 'Engine Settings',
  'settings.engine.path': 'Engine Path',
  'settings.engine.gpu': 'GPU Acceleration',
  'settings.engine.gpuAcceleration': 'Enable Vulkan GPU Acceleration',
  'settings.project.title': 'Project Settings',
  
  // Status
  'status.ready': 'Ready',
  'status.processing': 'Processing',
  'status.completed': 'Completed',
  'status.error': 'Error',
  'status.connecting': 'Connecting',
  'status.connected': 'Connected',
  'status.disconnected': 'Disconnected',
  
  // Page placeholder
  'page.developing': 'Developing',
  'page.developing.desc': 'This feature is under development',
  
  // API Test
  'api.test.title': 'API Connectivity Test',
  'api.test.webToRust': 'Web → Rust',
  'api.test.rustToPython': 'Rust → Python',
  'api.test.pythonResponse': 'Python Response',
  'api.test.run': 'Run Test',
  'api.test.success': 'Test Success',
  'api.test.failed': 'Test Failed',

  // Hints
  'hint.windowTooSmall': 'Window size is too small. Please resize for a better experience.',

  // Buttons
  'btn.neverShow': 'Never Show',
};

// 设置字典
dictionary.set({
  'zh-CN': zhCN,
  'en-US': enUS,
});

// 设置默认语言
locale.set('zh-CN');

// 导出便捷函数
export { locale, _ };

// 切换语言
export function setLanguage(lang: 'zh-CN' | 'en-US' | 'auto') {
  if (lang === 'auto') {
    // 检测系统语言
    const systemLang = navigator.language;
    if (systemLang.startsWith('zh')) {
      locale.set('zh-CN');
    } else {
      locale.set('en-US');
    }
  } else {
    locale.set(lang);
  }
}

// 获取当前语言
export function getCurrentLanguage(): string {
  let current = 'zh-CN';
  locale.subscribe(l => { current = l || 'zh-CN'; })();
  return current;
}
