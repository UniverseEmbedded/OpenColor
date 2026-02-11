/**
 * 类型定义
 */

// 工作区信息
export interface WorkspaceInfo {
  path: string;
  name: string;
  createdAt: string;
}

// 导航项
export interface NavItem {
  id: string;
  label: string;
  icon?: string;
  children?: NavItem[];
}

// 主题类型
export type Theme = 'dark' | 'light' | 'auto';

// 语言类型
export type Locale = 'zh-CN' | 'en-US' | 'auto';

// APP设置
export interface AppSettings {
  locale: Locale;
  theme: Theme;
  currentWorkspace: string;
  recentWorkspaces: string[];
  windowSize?: { width: number; height: number };
  enginePath: string;
  gpuAcceleration: boolean;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  skipWindowSizeCheck: boolean;
  showWindowSizeOverlay: boolean; // 恢复展示小窗口覆盖层
}

// 项目设置
export interface ProjectSettings {
  defaultMaterialGroupId: string;
  defaultLayerHeightMm: number;
  defaultModelId: string;
  exportPreferences: {
    exportStl: boolean;
    export3mf: boolean;
    useCppAcceleration: boolean;
    meshRepair: boolean;
  };
  maskGenParams: {
    superresEnabled: boolean;
    superresScale: number;
    layer0BiasEnabled: boolean;
    postprocessMode: 'joint' | 'none';
  };
}

// 任务进度
export interface JobProgress {
  jobId: string;
  progress: number;
  stage: string;
  message?: string;
}

// 任务结果
export interface JobResult<T> {
  jobId: string;
  result: T;
}

// 任务错误
export interface JobError {
  jobId: string;
  code: string;
  message: string;
  details?: any;
}

// API错误
export interface ApiError {
  code: string;
  message: string;
  details?: any;
  level: 'warn' | 'error' | 'fatal';
}

// ============================================
// CP3: 校准环节类型定义
// ============================================

// 坐标点
export interface Point {
  x: number;
  y: number;
}

// RGB颜色
export interface Rgb {
  r: number;
  g: number;
  b: number;
}

// 校准板规格
export interface BoardSpec {
  name: string;
  rows: number;
  cols: number;
  cellSizeMm: number;
  layerHeightMm: number;
  cells: BoardCell[];
}

// 校准板格子
export interface BoardCell {
  row: number;
  col: number;
  targetRgb: Rgb;
  recipe: Record<string, number>;
}

// 校准板列表项
export interface BoardItem {
  path: string;
  name: string;
  rows: number;
  cols: number;
  modifiedAt: string;
}

// 校正参数
export interface WarpParams {
  specPath: string;
  cornerPoints: Point[];
  rotationCount: number;
}

// 样本格子
export interface SampleCell {
  row: number;
  col: number;
  enabled: boolean;
  measuredRgb: Rgb;
  targetRgb: Rgb;
  recipe: Record<string, number>;
}

// 样本数据集
export interface SampleDataset {
  version: string;
  specName: string;
  rows: number;
  cols: number;
  warpedImage: string;
  specPath: string;
  patchedPath: string | null;
  cells: SampleCell[];
}

// 训练配置
export interface TrainingConfig {
  datasetPaths: string[];
  materialGroupId: string;
  layerHeightMm: number;
  opticalModel: 'rts' | 'four_flux' | 'tmm';
  useVulkan: boolean;
  gprParams?: GprParams;
}

// GPR参数
export interface GprParams {
  kernel: string;
  lengthScale: number;
  noiseLevel: number;
}

// 训练进度
export interface TrainingProgress {
  epoch: number;
  totalEpochs: number;
  loss: number;
  avgDeltaE: number;
}

// 训练好的模型
export interface ModelItem {
  path: string;
  name: string;
  materialGroup: string;
  layerHeightMm: number;
  avgDeltaE: number;
  trainedAt: string;
}

// 颜色模型
export interface ColorModel {
  version: string;
  materialGroup: string;
  layerHeightMm: number;
  trainingStats: {
    epochs: number;
    finalLoss: number;
    avgDeltaE: number;
  };
  modelParams: any;
}
