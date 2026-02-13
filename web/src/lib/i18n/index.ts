/**
 * 国际化配置
 */

import { locale, dictionary, _ as svelteI18n_ } from 'svelte-i18n';
import { derived } from 'svelte/store';

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
  'nav.library.filaments': '耗材',
  'nav.library.profiles': '耗材组',
  'nav.library.exports': '生成文件',
  
  // 设置子导航
  'nav.settings.general': '通用',
  'nav.settings.workspace': '工作区',
  'nav.settings.engine': '引擎',
  'nav.settings.project': '项目',
  'nav.settings.debug': '调试',
  
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
  'settings.engine.devMode': '开发模式',
  'settings.engine.browserMode': '浏览器模式',
  'settings.engine.desktopOnly': '引擎功能仅在桌面应用中可用',
  'settings.engine.devBuild': '开发构建',
  'settings.project.title': '项目设置',
  
  // 调试设置
  'settings.debug.title': '调试',
  'settings.debug.modeInfo': '模式信息',
  'settings.debug.buildMode': '构建模式',
  'settings.debug.runtimeMode': '运行模式',
  'settings.debug.tauriAvailable': 'Tauri 可用',
  'settings.debug.apiTest': 'API 连接测试',
  'settings.debug.testing': '测试中...',
  'settings.debug.testApi': '测试 API 连接',
  'settings.debug.notification': '系统通知测试',
  'settings.debug.notificationDesc': '测试桌面应用的通知功能',
  'settings.debug.sendNotification': '发送测试通知',
  'settings.debug.engineManagement': '引擎管理',
  'settings.debug.engineRestartDesc': '重启Python引擎以应用代码修改（开发模式使用）',
  'settings.debug.restarting': '正在重启引擎...',
  'settings.debug.restartSuccess': '引擎重启成功',
  'settings.debug.restartFailed': '引擎重启失败',
  'settings.debug.restartEngine': '重启Python引擎',
  'settings.debug.loadingOverlay': '加载覆盖层测试',
  'settings.debug.loadingOverlayDesc': '触发加载覆盖层显示3秒，用于测试覆盖层效果',
  'settings.debug.triggerLoadingOverlay': '触发加载覆盖层(3秒)',
  'settings.debug.loadingOverlayMessage': '测试加载覆盖层...',

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
  
  // 校准板生成
  'boardGen.description': '生成8色校准板的规格文件和3MF打印文件',
  'boardGen.configTitle': '生成配置',
  'boardGen.profile': '耗材组',
  'boardGen.colors': '色',
  'boardGen.layerHeight': '层高',
  'boardGen.layerCount': '层数',
  'boardGen.cellSize': '格子尺寸',
  'boardGen.dataRows': '数据行数',
  'boardGen.dataCols': '数据列数',
  'boardGen.totalCells': '总格子数',
  'boardGen.withBorder': '含边框',
  'boardGen.dataCells': '数据格',
  'boardGen.numBoards': '板子数量',
  'boardGen.shrink': '格子缩进量',
  'boardGen.includeApriltag': '包含 AprilTag',
  'boardGen.includeSideTriangles': '包含侧边白色三角形',
  'boardGen.generating': '生成中...',
  'boardGen.generate': '生成校准板',
  'boardGen.generatedFiles': '生成的文件',
  'boardGen.noBoards': '尚未生成校准板',
  'boardGen.clickToGenerate': '配置参数后点击"生成校准板"按钮',
  'boardGen.cells': '格子',
  'boardGen.openInExplorer': '在资源管理器中打开',
  'boardGen.visualPreview': '可视化预览',
  'boardGen.fileList': '文件列表',
  'boardGen.generatedBoards': '生成的色盘（点击切换）',
  'boardGen.selectBoard': '请选择色盘',
  'boardGen.clickCardToView': '点击上方卡片查看详情',
  'boardGen.selectWorkspaceFirst': '请先选择工作区',
  'boardGen.selectProfileFirst': '请先选择耗材组',
  'boardGen.elapsed': '已用',
  'boardGen.remaining': '预计剩余',
  'boardGen.layers': '层',

  // Cell Tooltip
  'cellTooltip.position': '位置',
  'cellTooltip.row': '行',
  'cellTooltip.col': '列',
  'cellTooltip.type': '类型',
  'cellTooltip.type.marker': '标记区',
  'cellTooltip.type.border': '边框',
  'cellTooltip.type.data': '数据区',
  'cellTooltip.targetRgb': '目标RGB',
  'cellTooltip.recipe': '配方',
  'cellTooltip.layerSequence': '层序列',
  'cellTooltip.layer': '层',
  'cellTooltip.color': '颜色',

  // 照片校正与样本提取
  'photoWarp.description': '手动4点透视校正色盘照片，提取颜色样本',
  'photoWarp.fileSelect': '文件选择',
  'photoWarp.boardSpec': '校准板规格',
  'photoWarp.boardPreview': '校准板预览',
  'photoWarp.boardPreviewEmpty': '暂无预览图',
  'photoWarp.selectSpec': '请选择规格文件',
  'photoWarp.photo': '照片',
  'photoWarp.selectPhoto': '选择照片',
  'photoWarp.changePhoto': '更换照片',
  'photoWarp.cornerControl': '角点控制',
  'photoWarp.rotateCCW': '逆时针 90°',
  'photoWarp.rotateCW': '顺时针 90°',
  'photoWarp.clearPoints': '清空角点',
  'photoWarp.executeWarp': '执行校正',
  'photoWarp.processing': '处理中...',
  'photoWarp.photoWarp': '照片校正',
  'photoWarp.warpResult': '校正结果',
  'photoWarp.warpedImage': '校正后图像',
  'photoWarp.gridOverlay': '网格叠加',
  'photoWarp.sampleResult': '样本提取结果',
  'photoWarp.totalCells': '总格子数',
  'photoWarp.enabledCells': '启用格子',
  'photoWarp.closeError': '关闭错误',

  // 模型训练
  'modelTrain.description': '使用RT光学模型+GPR训练颜色预测模型',
  'modelTrain.configTitle': '训练配置',
  'modelTrain.dataset': '数据集',
  'modelTrain.selectDataset': '选择数据集',
  'modelTrain.materialGroup': '材料组',
  'modelTrain.layerHeight': '层高 (mm)',
  'modelTrain.opticalModel': '光学模型',
  'modelTrain.opticalModel.rts': 'RTS (推荐)',
  'modelTrain.opticalModel.fourFlux': 'Four-Flux',
  'modelTrain.opticalModel.tmm': 'TMM',
  'modelTrain.useVulkan': '使用 Vulkan GPU加速',
  'modelTrain.gprKernel': 'GPR核函数',
  'modelTrain.kernel.rbf': 'RBF',
  'modelTrain.kernel.matern': 'Matérn',
  'modelTrain.kernel.rationalQuadratic': 'Rational Quadratic',
  'modelTrain.startTraining': '开始训练',
  'modelTrain.stopTraining': '停止训练',
  'modelTrain.trainingLogs': '训练日志',
  'modelTrain.clearLogs': '清空日志',
  'modelTrain.waitingForTraining': '等待训练开始...',
  'modelTrain.trainedModels': '训练好的模型',
  'modelTrain.noModels': '尚未训练任何模型',
  'modelTrain.epoch': '轮次',
  'modelTrain.loss': '损失',
  'modelTrain.deltaE': 'ΔE',
  
  // 耗材组
  'profile.basicInfo': '基本信息',
  'profile.id': '标识',
  'profile.name': '名称',
  'profile.description': '描述',
  'profile.colorCount': '颜色数量',
  'profile.colorConfig': '颜色配置',
  'profile.markerConfig': '标记颜色配置',
  'profile.markerTL': '左上角 (TL)',
  'profile.markerTR': '右上角 (TR)',
  'profile.markerBR': '右下角 (BR)',
  'profile.markerBL': '左下角 (BL)',
  
  // 应用
  'app.open': '打开',
  'app.export': '导出',
  'app.browse': '浏览',
  
  // 弹窗
  'modal.aboutTitle': '关于',
  'modal.aboutDesc': 'OpenColor 是一个开源的多色3D打印色彩管理系统',
  'modal.aboutGithub': 'GitHub 仓库',
  'modal.aboutVersion': '版本 0.1.0',
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
  
  // 设置子导航
  'nav.settings.general': 'General',
  'nav.settings.workspace': 'Workspace',
  'nav.settings.engine': 'Engine',
  'nav.settings.project': 'Project',
  'nav.settings.debug': 'Debug',
  
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
  'settings.engine.devMode': 'Development Mode',
  'settings.engine.browserMode': 'Browser Mode',
  'settings.engine.desktopOnly': 'Engine features only available in desktop app',
  'settings.engine.devBuild': 'Development Build',
  'settings.project.title': 'Project Settings',
  
  // Debug settings
  'settings.debug.title': 'Debug',
  'settings.debug.modeInfo': 'Mode Info',
  'settings.debug.buildMode': 'Build Mode',
  'settings.debug.runtimeMode': 'Runtime Mode',
  'settings.debug.tauriAvailable': 'Tauri Available',
  'settings.debug.apiTest': 'API Connectivity Test',
  'settings.debug.testing': 'Testing...',
  'settings.debug.testApi': 'Test API Connection',
  'settings.debug.notification': 'Notification Test',
  'settings.debug.notificationDesc': 'Test desktop app notification feature',
  'settings.debug.sendNotification': 'Send Test Notification',
  'settings.debug.engineManagement': 'Engine Management',
  'settings.debug.engineRestartDesc': 'Restart Python engine to apply code changes (for development)',
  'settings.debug.restarting': 'Restarting engine...',
  'settings.debug.restartSuccess': 'Engine restarted successfully',
  'settings.debug.restartFailed': 'Engine restart failed',
  'settings.debug.restartEngine': 'Restart Python Engine',
  'settings.debug.loadingOverlay': 'Loading Overlay Test',
  'settings.debug.loadingOverlayDesc': 'Trigger loading overlay for 3 seconds to test the overlay effect',
  'settings.debug.triggerLoadingOverlay': 'Trigger Loading Overlay (3s)',
  'settings.debug.loadingOverlayMessage': 'Testing loading overlay...',

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
  
  // Board Generation
  'boardGen.description': 'Generate specification files and 3MF print files for 8-color calibration boards',
  'boardGen.configTitle': 'Generation Config',
  'boardGen.profile': 'Filament Profile',
  'boardGen.colors': 'colors',
  'boardGen.layerHeight': 'Layer Height',
  'boardGen.layerCount': 'Layer Count',
  'boardGen.cellSize': 'Cell Size',
  'boardGen.dataRows': 'Data Rows',
  'boardGen.dataCols': 'Data Columns',
  'boardGen.totalCells': 'Total Cells',
  'boardGen.withBorder': 'with border',
  'boardGen.dataCells': 'data cells',
  'boardGen.numBoards': 'Number of Boards',
  'boardGen.shrink': 'Cell Shrink',
  'boardGen.includeApriltag': 'Include AprilTag',
  'boardGen.includeSideTriangles': 'Include Side White Triangles',
  'boardGen.generating': 'Generating...',
  'boardGen.generate': 'Generate Calibration Board',
  'boardGen.generatedFiles': 'Generated Files',
  'boardGen.noBoards': 'No calibration boards generated yet',
  'boardGen.clickToGenerate': 'Click "Generate Calibration Board" button after configuring parameters',
  'boardGen.cells': 'cells',
  'boardGen.openInExplorer': 'Open in Explorer',
  'boardGen.visualPreview': 'Visual Preview',
  'boardGen.fileList': 'File List',
  'boardGen.generatedBoards': 'Generated Boards (Click to switch)',
  'boardGen.selectBoard': 'Please select a board',
  'boardGen.clickCardToView': 'Click a card above to view details',
  'boardGen.selectWorkspaceFirst': 'Please select a workspace first',
  'boardGen.selectProfileFirst': 'Please select a filament profile first',
  'boardGen.elapsed': 'Elapsed',
  'boardGen.remaining': 'Remaining',
  'boardGen.layers': 'layers',

  // Cell Tooltip
  'cellTooltip.position': 'Position',
  'cellTooltip.row': 'Row',
  'cellTooltip.col': 'Col',
  'cellTooltip.type': 'Type',
  'cellTooltip.type.marker': 'Marker',
  'cellTooltip.type.border': 'Border',
  'cellTooltip.type.data': 'Data',
  'cellTooltip.targetRgb': 'Target RGB',
  'cellTooltip.recipe': 'Recipe',
  'cellTooltip.layerSequence': 'Layer Sequence',
  'cellTooltip.layer': 'Layer',
  'cellTooltip.color': 'Color',

  // Photo Warp & Sample Extract
  'photoWarp.description': 'Manual 4-point perspective correction for calibration board photos, extract color samples',
  'photoWarp.fileSelect': 'File Selection',
  'photoWarp.boardSpec': 'Board Specification',
  'photoWarp.boardPreview': 'Board Preview',
  'photoWarp.boardPreviewEmpty': 'No preview image',
  'photoWarp.selectSpec': 'Please select specification file',
  'photoWarp.photo': 'Photo',
  'photoWarp.selectPhoto': 'Select Photo',
  'photoWarp.changePhoto': 'Change Photo',
  'photoWarp.cornerControl': 'Corner Control',
  'photoWarp.rotateCCW': 'Rotate 90° CCW',
  'photoWarp.rotateCW': 'Rotate 90° CW',
  'photoWarp.clearPoints': 'Clear Points',
  'photoWarp.executeWarp': 'Execute Warp',
  'photoWarp.processing': 'Processing...',
  'photoWarp.photoWarp': 'Photo Warp',
  'photoWarp.warpResult': 'Warp Result',
  'photoWarp.warpedImage': 'Warped Image',
  'photoWarp.gridOverlay': 'Grid Overlay',
  'photoWarp.sampleResult': 'Sample Extraction Result',
  'photoWarp.totalCells': 'Total Cells',
  'photoWarp.enabledCells': 'Enabled Cells',
  'photoWarp.closeError': 'Close Error',

  // Model Training
  'modelTrain.description': 'Train color prediction model using RT optical model + GPR',
  'modelTrain.configTitle': 'Training Config',
  'modelTrain.dataset': 'Dataset',
  'modelTrain.selectDataset': 'Select Dataset',
  'modelTrain.materialGroup': 'Material Group',
  'modelTrain.layerHeight': 'Layer Height (mm)',
  'modelTrain.opticalModel': 'Optical Model',
  'modelTrain.opticalModel.rts': 'RTS (Recommended)',
  'modelTrain.opticalModel.fourFlux': 'Four-Flux',
  'modelTrain.opticalModel.tmm': 'TMM',
  'modelTrain.useVulkan': 'Use Vulkan GPU Acceleration',
  'modelTrain.gprKernel': 'GPR Kernel',
  'modelTrain.kernel.rbf': 'RBF',
  'modelTrain.kernel.matern': 'Matérn',
  'modelTrain.kernel.rationalQuadratic': 'Rational Quadratic',
  'modelTrain.startTraining': 'Start Training',
  'modelTrain.stopTraining': 'Stop Training',
  'modelTrain.trainingLogs': 'Training Logs',
  'modelTrain.clearLogs': 'Clear Logs',
  'modelTrain.waitingForTraining': 'Waiting for training to start...',
  'modelTrain.trainedModels': 'Trained Models',
  'modelTrain.noModels': 'No models trained yet',
  'modelTrain.epoch': 'Epoch',
  'modelTrain.loss': 'Loss',
  'modelTrain.deltaE': 'ΔE',
  
  // Profile
  'profile.basicInfo': 'Basic Information',
  'profile.id': 'ID',
  'profile.name': 'Name',
  'profile.description': 'Description',
  'profile.colorCount': 'Color Count',
  'profile.colorConfig': 'Color Configuration',
  'profile.markerConfig': 'Marker Color Configuration',
  'profile.markerTL': 'Top Left (TL)',
  'profile.markerTR': 'Top Right (TR)',
  'profile.markerBR': 'Bottom Right (BR)',
  'profile.markerBL': 'Bottom Left (BL)',
  
  // App
  'app.open': 'Open',
  'app.export': 'Export',
  'app.browse': 'Browse',
  
  // Modal
  'modal.aboutTitle': 'About',
  'modal.aboutDesc': 'OpenColor is an open-source multi-color 3D printing color management system',
  'modal.aboutGithub': 'GitHub Repository',
  'modal.aboutVersion': 'Version 0.1.0',
};

// 设置字典
dictionary.set({
  'zh-CN': zhCN,
  'en-US': enUS,
});

// 设置默认语言
locale.set('zh-CN');

// 导出 locale
export { locale };

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

// 检查键是否存在于字典中
function hasKey(key: string): boolean {
  const currentLocale = getCurrentLanguage();
  const dict = currentLocale === 'zh-CN' ? zhCN : enUS;
  return key in dict;
}

// 包装翻译函数，添加缺失警告
function translateWithWarning(key: string, options?: Record<string, unknown>): string {
  // 检查键是否缺失
  if (!hasKey(key)) {
    console.warn(`[i18n] Missing translation key: "${key}"`);
  }
  // 使用原始的 svelte-i18n _ 函数
  let result = key;
  svelteI18n_.subscribe(t => {
    result = t(key, options);
  })();
  return result;
}

// 创建可订阅的翻译函数
export const _ = derived(svelteI18n_, () => translateWithWarning);
