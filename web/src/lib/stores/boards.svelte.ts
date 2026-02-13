/**
 * 校准板素材库状态管理
 */

import { writable, get } from 'svelte/store';
import type { BoardCell, BoardItem, BoardSpec } from '$lib/types';
import { getTauriBridge } from '../tauri/bridge';
import { workspaceStore } from './workspace.svelte';

const bridge = getTauriBridge();

// 状态接口
interface BoardsState {
  boards: BoardItem[];
  selectedBoard: BoardItem | null;
  boardSpec: BoardSpec | null;
  isLoading: boolean;
  error: string | null;
}

// 创建校准板素材库 store
function createBoardsStore() {
  const state = writable<BoardsState>({
    boards: [],
    selectedBoard: null,
    boardSpec: null,
    isLoading: false,
    error: null
  });

  return {
    subscribe: state.subscribe,

    // 获取当前状态
    getState(): BoardsState {
      return get(state);
    },

    // 加载校准板列表
    async loadBoards(): Promise<void> {
      const workspace = workspaceStore.currentWorkspace;
      if (!workspace) {
        state.update(s => ({ ...s, error: '未选择工作区' }));
        return;
      }

      state.update(s => ({ ...s, isLoading: true, error: null }));

      try {
        const result = await bridge.invoke<{ boards: BoardItem[] }>('library_list_boards', {
          workspacePath: workspace.path
        });
        state.update(s => ({ ...s, boards: result.boards, isLoading: false }));
      } catch (e) {
        const errorMsg = String(e);
        console.error('加载校准板列表失败:', e);
        state.update(s => ({ ...s, isLoading: false, error: errorMsg }));
        throw e;
      }
    },

    // 选择校准板并加载详情
    async selectBoard(board: BoardItem | null): Promise<void> {
      state.update(s => ({ ...s, selectedBoard: board, boardSpec: null }));

      if (!board) return;

      try {
        const content = await bridge.invoke<string>('read_text_file', {
          path: board.path
        });
        const rawSpec = JSON.parse(content);
        const baseSpec: BoardSpec = {
          name: rawSpec.name || board.name,
          rows: Number(rawSpec.rows ?? board.rows ?? 0),
          cols: Number(rawSpec.cols ?? board.cols ?? 0),
          cellSizeMm: Number(rawSpec.cellSizeMm ?? rawSpec.cell_size_mm ?? board.cellSizeMm ?? 0),
          layerHeightMm: Number(rawSpec.layerHeightMm ?? rawSpec.layer_height_mm ?? board.layerHeightMm ?? 0),
          cells: []
        };

        if (board.profileId) {
          const result = await bridge.invoke<{ cells: BoardCell[] }>('board_preview', {
            profileId: board.profileId,
            specPath: board.path
          });
          state.update(s => ({ ...s, boardSpec: { ...baseSpec, cells: result.cells } }));
          return;
        }

        state.update(s => ({ ...s, boardSpec: baseSpec, error: '校准板缺少耗材组信息，无法生成预览' }));
      } catch (e) {
        console.error('读取规格文件失败:', e);
        state.update(s => ({ ...s, error: '读取规格文件失败' }));
      }
    },

    // 删除校准板
    async deleteBoard(path: string): Promise<void> {
      try {
        await bridge.invoke('delete_board', { path });
        // 如果删除的是当前选中的，清空选中状态
        const currentState = get(state);
        if (currentState.selectedBoard?.path === path) {
          state.update(s => ({ ...s, selectedBoard: null, boardSpec: null }));
        }
        // 重新加载列表
        await this.loadBoards();
      } catch (e) {
        console.error('删除校准板失败:', e);
        throw e;
      }
    },

    // 重命名校准板
    async renameBoard(path: string, newName: string): Promise<void> {
      try {
        await bridge.invoke('rename_board', { path, newName });
        // 重新加载列表
        await this.loadBoards();
        // 如果重命名的是当前选中的，更新选中状态
        const currentState = get(state);
        if (currentState.selectedBoard?.path === path) {
          await this.selectBoard(currentState.selectedBoard);
        }
      } catch (e) {
        console.error('重命名校准板失败:', e);
        throw e;
      }
    },

    // 刷新列表
    async refresh(): Promise<void> {
      await this.loadBoards();
    },

    // 清空错误
    clearError(): void {
      state.update(s => ({ ...s, error: null }));
    },

    // 重置状态
    reset(): void {
      state.set({
        boards: [],
        selectedBoard: null,
        boardSpec: null,
        isLoading: false,
        error: null
      });
    }
  };
}

// 导出单例
export const boardsStore = createBoardsStore();
