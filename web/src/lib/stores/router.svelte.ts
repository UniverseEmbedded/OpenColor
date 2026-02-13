/**
 * 简单路由管理
 * 基于hash的路由实现
 */

import { writable, get } from 'svelte/store';
import { navigationStore } from './navigation.svelte';
import type { Component } from 'svelte';

// 路由配置 - 使用导航ID作为键
const routes: Record<string, () => Promise<{ default: Component }>> = {
  'calibrate-board-gen': () => import('../../routes/calibrate/board-gen/+page.svelte'),
  'calibrate-photo-warp': () => import('../../routes/calibrate/photo-warp/+page.svelte'),
  'calibrate-model-train': () => import('../../routes/calibrate/model-train/+page.svelte'),
  'generate-mask-gen': () => import('../../routes/generate/mask-gen/+page.svelte'),
  'generate-vectorize': () => import('../../routes/generate/vectorize/+page.svelte'),
  'generate-export': () => import('../../routes/generate/export/+page.svelte'),
  'library-boards': () => import('../../routes/library/boards/+page.svelte'),
  'library-photos': () => import('../../routes/library/photos/+page.svelte'),
  'library-models': () => import('../../routes/library/models/+page.svelte'),
  'library-materials': () => import('../../routes/library/materials/+page.svelte'),
  'library-materials-filaments': () => import('../../routes/library/materials/filaments/+page.svelte'),
  'library-materials-profiles': () => import('../../routes/library/materials/profiles/+page.svelte'),
  'library-exports': () => import('../../routes/library/exports/+page.svelte'),
  'settings-general': () => import('../../routes/settings/general/+page.svelte'),
  'settings-workspace': () => import('../../routes/settings/workspace/+page.svelte'),
  'settings-engine': () => import('../../routes/settings/engine/+page.svelte'),
  'settings-project': () => import('../../routes/settings/project/+page.svelte'),
  'settings-debug': () => import('../../routes/settings/debug/+page.svelte'),
};

// 使用 writable store 替代 $state
const currentRoute = writable('calibrate-board-gen');
const currentComponent = writable<any>(null);

// 导航到指定路由
export async function navigate(path: string) {
  // 将路径格式转换为路由键格式 (例如: calibrate/board-gen -> calibrate-board-gen)
  const routeKey = path.replace(/\//g, '-');
  
  if (routes[routeKey]) {
    console.log('[路由] 开始导航:', path);
    currentRoute.set(routeKey);
    const module = await routes[routeKey]();
    currentComponent.set(module.default);
    
    // 更新导航状态
    navigationStore.setCurrentNav(path);
    
    // 更新URL hash
    window.location.hash = path;
    console.log('[路由] 导航完成:', path);
  } else {
    console.error(`[路由] 路由不存在: ${path} (键: ${routeKey})`);
  }
}

// 根据hash初始化路由
export function initRouter() {
  const hash = window.location.hash.slice(1) || 'calibrate/board-gen';
  console.log('[路由] 初始化开始:', hash);
  navigate(hash);
  
  // 监听hash变化
  window.addEventListener('hashchange', () => {
    const newHash = window.location.hash.slice(1);
    const newRouteKey = newHash.replace(/\//g, '-');
    if (newRouteKey !== get(currentRoute)) {
      console.log('[路由] Hash 变化触发导航:', newHash);
      navigate(newHash);
    }
  });
  console.log('[路由] 初始化完成');
}

// 导出路由状态
export function getRouter() {
  return {
    subscribe: (callback: (value: { currentRoute: string; currentComponent: any }) => void) => {
      const unsubscribeRoute = currentRoute.subscribe(route => {
        const unsubscribeComponent = currentComponent.subscribe(component => {
          callback({ currentRoute: route, currentComponent: component });
        });
        return unsubscribeComponent;
      });
      return unsubscribeRoute;
    },
    get currentRoute() { return get(currentRoute); },
    get currentComponent() { return get(currentComponent); },
    navigate,
  };
}
