/**
 * 导航状态管理
 */

import { writable, get } from 'svelte/store';
import type { NavItem } from '$lib/types';

// 导航结构定义
export const navItems: NavItem[] = [
  {
    id: 'calibrate',
    label: 'nav.calibrate',
    icon: 'ti-ruler-2',
    children: [
      { id: 'calibrate/board-gen', label: 'nav.calibrate.boardGen', icon: 'ti-grid-dots' },
      { id: 'calibrate/photo-warp', label: 'nav.calibrate.photoWarp', icon: 'ti-photo-edit' },
      { id: 'calibrate/model-train', label: 'nav.calibrate.modelTrain', icon: 'ti-brain' },
    ],
  },
  {
    id: 'generate',
    label: 'nav.generate',
    icon: 'ti-wand',
    children: [
      { id: 'generate/mask-gen', label: 'nav.generate.maskGen', icon: 'ti-layers-intersect' },
      { id: 'generate/vectorize', label: 'nav.generate.vectorize', icon: 'ti-vector-bezier' },
      { id: 'generate/export', label: 'nav.generate.export', icon: 'ti-file-export' },
    ],
  },
  {
    id: 'library',
    label: 'nav.library',
    icon: 'ti-library',
    children: [
      { id: 'library/boards', label: 'nav.library.boards', icon: 'ti-grid-dots' },
      { id: 'library/photos', label: 'nav.library.photos', icon: 'ti-photo' },
      { id: 'library/models', label: 'nav.library.models', icon: 'ti-cube' },
      { id: 'library/materials', label: 'nav.library.materials', icon: 'ti-palette' },
      { id: 'library/exports', label: 'nav.library.exports', icon: 'ti-files' },
    ],
  },
  {
    id: 'settings',
    label: 'nav.settings',
    icon: 'ti-settings',
    children: [
      { id: 'settings/general', label: 'nav.settings.general', icon: 'ti-adjustments' },
      { id: 'settings/workspace', label: 'nav.settings.workspace', icon: 'ti-folder' },
      { id: 'settings/engine', label: 'nav.settings.engine', icon: 'ti-engine' },
      { id: 'settings/project', label: 'nav.settings.project', icon: 'ti-file-settings' },
    ],
  },
];

// 使用 writable store
const currentNav = writable<string>('calibrate/board-gen');
const expandedNavs = writable<Set<string>>(new Set(['calibrate']));
const isMobile = writable<boolean>(false);

// 创建导航 store
function createNavigationStore() {
  return {
    subscribe: (callback: (value: { currentNav: string; expandedNavs: Set<string>; isMobile: boolean }) => void) => {
      const unsubscribeNav = currentNav.subscribe(nav => {
        const unsubscribeExpanded = expandedNavs.subscribe(expanded => {
          const unsubscribeMobile = isMobile.subscribe(mobile => {
            callback({ currentNav: nav, expandedNavs: expanded, isMobile: mobile });
          });
          return unsubscribeMobile;
        });
        return unsubscribeExpanded;
      });
      return unsubscribeNav;
    },
    
    get currentNav() { return get(currentNav); },
    get expandedNavs() { return get(expandedNavs); },
    get isMobile() { return get(isMobile); },
    
    // 设置当前导航
    setCurrentNav(navId: string) {
      currentNav.set(navId);
      // 自动展开父级
      const parentId = navId.split('/')[0];
      if (parentId) {
        expandedNavs.update(set => {
          set.add(parentId);
          return new Set(set);
        });
      }
    },
    
    // 切换导航展开状态
    toggleNav(navId: string) {
      expandedNavs.update(set => {
        if (set.has(navId)) {
          set.delete(navId);
        } else {
          set.add(navId);
        }
        return new Set(set);
      });
    },
    
    // 检查导航是否展开
    isExpanded(navId: string): boolean {
      return get(expandedNavs).has(navId);
    },
    
    // 设置移动端状态
    setMobile(mobile: boolean) {
      isMobile.set(mobile);
    },
    
    // 获取当前页面的面包屑
    getBreadcrumbs(): NavItem[] {
      const current = get(currentNav);
      const parts = current.split('/');
      const breadcrumbs: NavItem[] = [];
      
      let parent = navItems.find(n => n.id === parts[0]);
      if (parent) {
        breadcrumbs.push(parent);
        if (parts[1] && parent.children) {
          const child = parent.children.find(c => c.id === current);
          if (child) {
            breadcrumbs.push(child);
          }
        }
      }
      
      return breadcrumbs;
    },
  };
}

// 导出单例
export const navigationStore = createNavigationStore();
