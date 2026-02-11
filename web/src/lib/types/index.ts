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
