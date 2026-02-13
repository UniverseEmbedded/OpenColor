import { writable } from 'svelte/store';
import { getTauriBridge } from '$lib/tauri/bridge';
import type { ColorProfile } from '$lib/types';

const bridge = getTauriBridge();

// 耗材组管理状态
interface MaterialsState {
  profiles: ColorProfile[];
  selectedProfile: ColorProfile | null;
  isLoading: boolean;
  error: string | null;
}

// 创建耗材组管理 store
function createMaterialsStore() {
  const state = writable<MaterialsState>({
    profiles: [],
    selectedProfile: null,
    isLoading: false,
    error: null
  });

  return {
    subscribe: state.subscribe,

    // 加载耗材组列表
    async loadProfiles() {
      if (!bridge.hasTauri) {
        state.update(s => ({ ...s, error: '不在 Tauri 环境中' }));
        return;
      }

      state.update(s => ({ ...s, isLoading: true, error: null }));

      try {
        const result = await bridge.invoke<{ profiles: ColorProfile[] }>('list_profiles');
        state.update(s => ({
          ...s,
          profiles: result.profiles,
          selectedProfile: result.profiles[0] || null,
          isLoading: false
        }));
      } catch (e) {
        const errorMsg = String(e);
        state.update(s => ({ ...s, isLoading: false, error: errorMsg }));
        throw e;
      }
    },

    // 选择耗材组
    selectProfile(profileId: string) {
      state.update(s => {
        const profile = s.profiles.find(p => p.id === profileId) || null;
        return { ...s, selectedProfile: profile };
      });
    },

    // 创建耗材组
    async createProfile(profile: Omit<ColorProfile, 'id'>) {
      if (!bridge.hasTauri) return;

      try {
        // TODO: 调用后端 API 创建耗材组
        const newProfile: ColorProfile = {
          ...profile,
          id: `custom_${Date.now()}`
        };
        state.update(s => ({
          ...s,
          profiles: [...s.profiles, newProfile],
          selectedProfile: newProfile
        }));
      } catch (e) {
        console.error('创建耗材组失败:', e);
        throw e;
      }
    },

    // 更新耗材组
    async updateProfile(profileId: string, updates: Partial<ColorProfile>) {
      if (!bridge.hasTauri) return;

      try {
        // TODO: 调用后端 API 更新耗材组
        state.update(s => ({
          ...s,
          profiles: s.profiles.map(p =>
            p.id === profileId ? { ...p, ...updates } : p
          ),
          selectedProfile: s.selectedProfile?.id === profileId
            ? { ...s.selectedProfile, ...updates }
            : s.selectedProfile
        }));
      } catch (e) {
        console.error('更新耗材组失败:', e);
        throw e;
      }
    },

    // 删除耗材组
    async deleteProfile(profileId: string) {
      if (!bridge.hasTauri) return;

      try {
        // TODO: 调用后端 API 删除耗材组
        state.update(s => ({
          ...s,
          profiles: s.profiles.filter(p => p.id !== profileId),
          selectedProfile: s.selectedProfile?.id === profileId
            ? s.profiles[0] || null
            : s.selectedProfile
        }));
      } catch (e) {
        console.error('删除耗材组失败:', e);
        throw e;
      }
    },

    // 导出耗材组
    async exportProfile(profileId: string, outputPath: string) {
      if (!bridge.hasTauri) return;

      try {
        // TODO: 调用后端 API 导出耗材组
        console.log('导出耗材组:', profileId, '到', outputPath);
      } catch (e) {
        console.error('导出耗材组失败:', e);
        throw e;
      }
    },

    // 导入耗材组
    async importProfile(filePath: string) {
      if (!bridge.hasTauri) return;

      try {
        // TODO: 调用后端 API 导入耗材组
        console.log('从文件导入耗材组:', filePath);
      } catch (e) {
        console.error('导入耗材组失败:', e);
        throw e;
      }
    },

    clearError() {
      state.update(s => ({ ...s, error: null }));
    }
  };
}

export const materialsStore = createMaterialsStore();
