/**
 * 校准环节状态管理
 */

import { writable, get } from 'svelte/store';
import type { 
  BoardItem, SampleDataset, 
  SampleCell, Point, TrainingConfig, TrainingProgress, ModelItem 
} from '$lib/types';
import { getTauriBridge } from '../tauri/bridge';

const bridge = getTauriBridge();

// 校准板生成状态
interface BoardGenState {
  isGenerating: boolean;
  progress: number;
  generatedBoards: BoardItem[];
  error: string | null;
}

// 照片校正状态
interface PhotoWarpState {
  isProcessing: boolean;
  selectedPhoto: string | null;
  selectedSpec: string | null;
  cornerPoints: Point[];
  rotationCount: number;
  warpedImage: string | null;
  overlayImage: string | null;
  error: string | null;
}

// 样本提取状态
interface SampleExtractState {
  isProcessing: boolean;
  dataset: SampleDataset | null;
  cells: SampleCell[];
  selectedCells: Set<string>; // "row,col" 格式
  previewBefore: string | null;
  previewAfter: string | null;
  error: string | null;
}

// 模型训练状态
interface ModelTrainState {
  isTraining: boolean;
  jobId: string | null;
  progress: TrainingProgress | null;
  logs: string[];
  trainedModels: ModelItem[];
  error: string | null;
}

// 创建校准板生成 store
function createBoardGenStore() {
  const state = writable<BoardGenState>({
    isGenerating: false,
    progress: 0,
    generatedBoards: [],
    error: null
  });

  return {
    subscribe: state.subscribe,
    
    // 生成校准板
    async generateBoards(config: {
      outputDir: string;
      specName: string;
      numBoards: number;
      shrink: number;
      layerHeightMm: number;
      includeApriltag: boolean;
      includeSideTriangles: boolean;
    }) {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }

      state.update(s => ({ ...s, isGenerating: true, progress: 0, error: null }));

      try {
        const result = await bridge.invoke<{ specPaths: string[]; printPaths: string[] }>('board_gen', config);
        
        // 刷新校准板列表
        await this.loadBoards(config.outputDir);
        
        state.update(s => ({ ...s, isGenerating: false, progress: 1 }));
        return result;
      } catch (e) {
        const errorMsg = String(e);
        state.update(s => ({ ...s, isGenerating: false, error: errorMsg }));
        throw e;
      }
    },

    // 加载校准板列表
    async loadBoards(workspacePath: string) {
      if (!bridge.hasTauri) return;

      try {
        const result = await bridge.invoke<{ boards: BoardItem[] }>('library_list_boards', { 
          workspacePath 
        });
        state.update(s => ({ ...s, generatedBoards: result.boards }));
      } catch (e) {
        console.error('加载校准板列表失败:', e);
      }
    },

    clearError() {
      state.update(s => ({ ...s, error: null }));
    }
  };
}

// 创建照片校正 store
function createPhotoWarpStore() {
  const state = writable<PhotoWarpState>({
    isProcessing: false,
    selectedPhoto: null,
    selectedSpec: null,
    cornerPoints: [],
    rotationCount: 0,
    warpedImage: null,
    overlayImage: null,
    error: null
  });

  return {
    subscribe: state.subscribe,

    // 选择照片
    selectPhoto(photoPath: string) {
      state.update(s => ({ ...s, selectedPhoto: photoPath }));
    },

    // 选择规格文件
    selectSpec(specPath: string) {
      state.update(s => ({ ...s, selectedSpec: specPath }));
    },

    // 设置角点
    setCornerPoints(points: Point[]) {
      state.update(s => ({ ...s, cornerPoints: points }));
    },

    // 添加角点
    addCornerPoint(point: Point) {
      state.update(s => {
        const points = [...s.cornerPoints, point];
        return { ...s, cornerPoints: points };
      });
    },

    // 清空角点
    clearCornerPoints() {
      state.update(s => ({ ...s, cornerPoints: [] }));
    },

    // 旋转
    rotate(clockwise: boolean) {
      state.update(s => ({
        ...s,
        rotationCount: (s.rotationCount + (clockwise ? 1 : -1) + 4) % 4
      }));
    },

    // 执行透视校正
    async warpPhoto(config: {
      specPath: string;
      photoPath: string;
      cornerPoints: Point[];
      rotationCount: number;
      outputDir: string;
    }) {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }

      state.update(s => ({ ...s, isProcessing: true, error: null }));

      try {
        const result = await bridge.invoke<{
          warpedPath: string;
          overlayPath: string;
          warpParamsPath: string;
        }>('photo_warp', config);

        state.update(s => ({
          ...s,
          isProcessing: false,
          warpedImage: result.warpedPath,
          overlayImage: result.overlayPath
        }));

        return result;
      } catch (e) {
        const errorMsg = String(e);
        state.update(s => ({ ...s, isProcessing: false, error: errorMsg }));
        throw e;
      }
    },

    clearError() {
      state.update(s => ({ ...s, error: null }));
    },

    reset() {
      state.set({
        isProcessing: false,
        selectedPhoto: null,
        selectedSpec: null,
        cornerPoints: [],
        rotationCount: 0,
        warpedImage: null,
        overlayImage: null,
        error: null
      });
    }
  };
}

// 创建样本提取 store
function createSampleExtractStore() {
  const state = writable<SampleExtractState>({
    isProcessing: false,
    dataset: null,
    cells: [],
    selectedCells: new Set(),
    previewBefore: null,
    previewAfter: null,
    error: null
  });

  return {
    subscribe: state.subscribe,

    // 提取样本
    async extractSamples(config: {
      warpedPath: string;
      specPath: string;
      warpParamsPath: string;
      outputDir: string;
    }) {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }

      state.update(s => ({ ...s, isProcessing: true, error: null }));

      try {
        const result = await bridge.invoke<{
          datasetPath: string;
          previewBeforePath: string;
          previewAfterPath: string;
          cellCount: number;
          enabledCellCount: number;
        }>('sample_extract', config);

        // 读取数据集
        const textContent = await bridge.invoke<string>('file_read_text', {
          path: result.datasetPath
        });
        const dataset = JSON.parse(textContent) as SampleDataset;

        state.update(s => ({
          ...s,
          isProcessing: false,
          dataset,
          cells: dataset.cells,
          previewBefore: result.previewBeforePath,
          previewAfter: result.previewAfterPath
        }));

        return result;
      } catch (e) {
        const errorMsg = String(e);
        state.update(s => ({ ...s, isProcessing: false, error: errorMsg }));
        throw e;
      }
    },

    // 切换格子启用状态
    toggleCell(row: number, col: number) {
      const key = `${row},${col}`;
      state.update(s => {
        const selected = new Set(s.selectedCells);
        if (selected.has(key)) {
          selected.delete(key);
        } else {
          selected.add(key);
        }
        return { ...s, selectedCells: selected };
      });
    },

    // 更新格子状态
    async updateCell(datasetPath: string, row: number, col: number, enabled: boolean) {
      if (!bridge.hasTauri) return;

      try {
        await bridge.invoke('sample_update_cell', { datasetPath, row, col, enabled });
        
        // 更新本地状态
        state.update(s => ({
          ...s,
          cells: s.cells.map(c => 
            c.row === row && c.col === col ? { ...c, enabled } : c
          )
        }));
      } catch (e) {
        console.error('更新格子状态失败:', e);
        throw e;
      }
    },

    clearError() {
      state.update(s => ({ ...s, error: null }));
    },

    reset() {
      state.set({
        isProcessing: false,
        dataset: null,
        cells: [],
        selectedCells: new Set(),
        previewBefore: null,
        previewAfter: null,
        error: null
      });
    }
  };
}

// 创建模型训练 store
function createModelTrainStore() {
  const state = writable<ModelTrainState>({
    isTraining: false,
    jobId: null,
    progress: null,
    logs: [],
    trainedModels: [],
    error: null
  });

  // 监听训练进度事件
  function setupEventListeners() {
    if (!bridge.hasTauri) return;

    bridge.listen<{
      jobId: string;
      progress: number;
      stage: string;
      message?: string;
    }>('engine:job_progress', (payload) => {
      state.update(s => {
        if (s.jobId !== payload.jobId) return s;
        return {
          ...s,
          progress: {
            epoch: Math.floor(payload.progress * 100),
            totalEpochs: 100,
            loss: 0,
            avgDeltaE: 0
          }
        };
      });
    });

    bridge.listen<{ jobId: string; result: any }>('engine:job_complete', (payload) => {
      state.update(s => {
        if (s.jobId !== payload.jobId) return s;
        return {
          ...s,
          isTraining: false,
          jobId: null,
          progress: null
        };
      });
    });

    bridge.listen<{ jobId: string; code: string; message: string }>('engine:job_error', (payload) => {
      state.update(s => {
        if (s.jobId !== payload.jobId) return s;
        return {
          ...s,
          isTraining: false,
          jobId: null,
          error: payload.message
        };
      });
    });

    bridge.listen<{ level: string; message: string; timestamp: string }>('engine:log', (payload) => {
      state.update(s => ({
        ...s,
        logs: [...s.logs, `[${payload.level}] ${payload.message}`]
      }));
    });
  }

  return {
    subscribe: state.subscribe,
    setupEventListeners,

    // 开始训练
    async startTraining(config: {
      trainingConfig: TrainingConfig;
      outputDir: string;
    }) {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }

      state.update(s => ({
        ...s,
        isTraining: true,
        jobId: null,
        progress: null,
        logs: [],
        error: null
      }));

      try {
        const result = await bridge.invoke<{ jobId: string }>('model_train_start', config);
        state.update(s => ({ ...s, jobId: result.jobId }));
        return result;
      } catch (e) {
        const errorMsg = String(e);
        state.update(s => ({ ...s, isTraining: false, error: errorMsg }));
        throw e;
      }
    },

    // 取消训练
    async cancelTraining() {
      const currentState = get(state);
      if (!currentState.jobId) return;

      try {
        await bridge.invoke('model_train_cancel', { jobId: currentState.jobId });
        state.update(s => ({
          ...s,
          isTraining: false,
          jobId: null,
          progress: null
        }));
      } catch (e) {
        console.error('取消训练失败:', e);
      }
    },

    // 加载模型列表
    async loadModels(workspacePath: string) {
      if (!bridge.hasTauri) return;

      try {
        const result = await bridge.invoke<{ models: ModelItem[] }>('library_list_models', {
          workspacePath
        });
        state.update(s => ({ ...s, trainedModels: result.models }));
      } catch (e) {
        console.error('加载模型列表失败:', e);
      }
    },

    clearLogs() {
      state.update(s => ({ ...s, logs: [] }));
    },

    clearError() {
      state.update(s => ({ ...s, error: null }));
    },

    reset() {
      state.set({
        isTraining: false,
        jobId: null,
        progress: null,
        logs: [],
        trainedModels: [],
        error: null
      });
    }
  };
}

// 导出单例
export const boardGenStore = createBoardGenStore();
export const photoWarpStore = createPhotoWarpStore();
export const sampleExtractStore = createSampleExtractStore();
export const modelTrainStore = createModelTrainStore();
