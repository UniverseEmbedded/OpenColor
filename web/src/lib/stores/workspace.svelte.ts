/**
 * 工作区状态管理
 */

import { writable, get } from 'svelte/store';
import { getTauriBridge } from '../tauri/bridge';

const bridge = getTauriBridge();

export interface WorkspaceInfo {
  id: string;
  name: string;
  path: string;
  created_at: number;
  last_opened: number;
}

// 使用 writable store
const currentWorkspace = writable<WorkspaceInfo | null>(null);
const recentWorkspaces = writable<WorkspaceInfo[]>([]);
const isLoading = writable<boolean>(false);
const error = writable<string | null>(null);

// 创建工作区 store
function createWorkspaceStore() {
  return {
    subscribe: (callback: (value: { 
      currentWorkspace: WorkspaceInfo | null; 
      recentWorkspaces: WorkspaceInfo[];
      isLoading: boolean;
      error: string | null;
    }) => void) => {
      const unsubscribeCurrent = currentWorkspace.subscribe(current => {
        const unsubscribeRecent = recentWorkspaces.subscribe(recent => {
          const unsubscribeLoading = isLoading.subscribe(loading => {
            const unsubscribeError = error.subscribe(err => {
              callback({ 
                currentWorkspace: current, 
                recentWorkspaces: recent,
                isLoading: loading,
                error: err
              });
            });
            return unsubscribeError;
          });
          return unsubscribeLoading;
        });
        return unsubscribeRecent;
      });
      return unsubscribeCurrent;
    },
    
    get currentWorkspace() { return get(currentWorkspace); },
    get recentWorkspaces() { return get(recentWorkspaces); },
    get isLoading() { return get(isLoading); },
    get error() { return get(error); },
    
    // 初始化工作区
    async init() {
      if (!bridge.hasTauri) {
        console.log('[Workspace] 不在 Tauri 环境中，跳过初始化');
        return;
      }
      
      isLoading.set(true);
      error.set(null);
      
      try {
        // 获取当前工作区
        const current = await bridge.invoke<string | null>('workspace_get_current');
        if (current) {
          // 从路径解析工作区信息
          const name = current.split(/[/\\]/).pop() || 'default';
          currentWorkspace.set({
            id: name,
            name,
            path: current,
            created_at: Date.now(),
            last_opened: Date.now(),
          });
        }
        
        // 获取最近工作区列表
        await this.loadRecentWorkspaces();
      } catch (e) {
        console.error('[Workspace] 初始化失败:', e);
        error.set(String(e));
      } finally {
        isLoading.set(false);
      }
    },
    
    // 加载最近工作区列表
    async loadRecentWorkspaces() {
      if (!bridge.hasTauri) return;
      
      try {
        const recent = await bridge.invoke<WorkspaceInfo[]>('workspace_list_recent');
        recentWorkspaces.set(recent);
      } catch (e) {
        console.error('[Workspace] 加载最近工作区失败:', e);
      }
    },
    
    // 创建工作区
    async create(name?: string, customPath?: string) {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }
      
      isLoading.set(true);
      error.set(null);
      
      try {
        const workspace = await bridge.invoke<WorkspaceInfo>('workspace_create', {
          name,
          customPath,
        });
        
        currentWorkspace.set(workspace);
        await this.loadRecentWorkspaces();
        
        return workspace;
      } catch (e) {
        console.error('[Workspace] 创建工作区失败:', e);
        error.set(String(e));
        throw e;
      } finally {
        isLoading.set(false);
      }
    },
    
    // 切换工作区
    async switchTo(path: string) {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }
      
      isLoading.set(true);
      error.set(null);
      
      try {
        await bridge.invoke('workspace_set_current', { path });
        
        // 更新当前工作区
        const name = path.split(/[/\\]/).pop() || 'default';
        currentWorkspace.set({
          id: name,
          name,
          path,
          created_at: Date.now(),
          last_opened: Date.now(),
        });
        
        await this.loadRecentWorkspaces();
      } catch (e) {
        console.error('[Workspace] 切换工作区失败:', e);
        error.set(String(e));
        throw e;
      } finally {
        isLoading.set(false);
      }
    },
    
    // 从最近列表移除
    async removeFromRecent(path: string) {
      if (!bridge.hasTauri) return;
      
      try {
        await bridge.invoke('workspace_remove_from_recent', { path });
        await this.loadRecentWorkspaces();
      } catch (e) {
        console.error('[Workspace] 移除最近工作区失败:', e);
      }
    },
    
    // 选择文件夹创建/打开工作区
    async selectFolder() {
      if (!bridge.hasTauri) {
        throw new Error('不在 Tauri 环境中');
      }
      
      const result = await bridge.invoke<string | null>('file_select_folder_dialog', {
        title: '选择工作区文件夹',
      });
      
      return result;
    },
    
    // 清除错误
    clearError() {
      error.set(null);
    },
  };
}

// 导出单例
export const workspaceStore = createWorkspaceStore();
