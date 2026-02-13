<script lang="ts">
  import { _ } from '$lib/i18n';
  import { workspaceStore, type WorkspaceInfo } from '$lib/stores/workspace.svelte';
  import { onMount } from 'svelte';

  // Props
  interface Props {
    direction?: 'up' | 'down';
  }
  let { direction = 'up' }: Props = $props();

  // 本地状态
  let isOpen = $state(false);
  let currentWorkspace = $state<WorkspaceInfo | null>(null);
  let recentWorkspaces = $state<WorkspaceInfo[]>([]);
  let isLoading = $state(false);
  let buttonRef = $state<HTMLButtonElement | null>(null);
  let dropdownPosition = $state({ top: 0, left: 0, width: 0 });
  
  // 订阅 store
  $effect(() => {
    const unsubscribe = workspaceStore.subscribe((value) => {
      currentWorkspace = value.currentWorkspace;
      recentWorkspaces = value.recentWorkspaces;
      isLoading = value.isLoading;
    });
    return unsubscribe;
  });
  
  // 初始化
  onMount(() => {
    workspaceStore.init();
  });
  
  // 计算下拉框位置
  function calculatePosition() {
    if (buttonRef) {
      const rect = buttonRef.getBoundingClientRect();
      const dropdownWidth = 280; // 下拉框最小宽度
      const padding = 16; // 窗口边距
      const gap = 4; // 按钮与下拉框的间距
      
      // 计算右侧边界，确保不超出窗口
      let left = rect.left;
      if (left + dropdownWidth > window.innerWidth - padding) {
        left = window.innerWidth - dropdownWidth - padding;
      }
      
      // 根据方向计算垂直位置
      let top: number;
      if (direction === 'up') {
        // 向上展开：从按钮顶部向上，紧贴按钮
        // 先计算实际内容高度（估算）
        const itemCount = Math.max(recentWorkspaces.length, 1);
        const estimatedHeight = Math.min(320, 60 + itemCount * 44 + 100);
        top = rect.top - estimatedHeight - gap;
        
        // 如果向上会超出窗口顶部，则改为向下展开
        if (top < padding) {
          top = rect.bottom + gap;
        }
      } else {
        // 向下展开：从按钮底部向下，紧贴按钮
        top = rect.bottom + gap;
      }
      
      dropdownPosition = {
        top: Math.max(padding, top),
        left: Math.max(padding, left),
        width: Math.max(rect.width, dropdownWidth)
      };
    }
  }
  
  // 切换下拉菜单
  function toggleDropdown() {
    if (!isOpen) {
      calculatePosition();
    }
    isOpen = !isOpen;
  }
  
  // 关闭下拉菜单
  function closeDropdown() {
    isOpen = false;
  }
  
  // 切换工作区
  async function switchWorkspace(path: string) {
    closeDropdown();
    try {
      await workspaceStore.switchTo(path);
    } catch (e) {
      console.error('切换工作区失败:', e);
    }
  }
  
  // 创建新工作区
  async function createWorkspace() {
    closeDropdown();
    try {
      await workspaceStore.create();
    } catch (e) {
      console.error('创建工作区失败:', e);
    }
  }
  
  // 选择文件夹打开/创建工作区
  async function selectFolder() {
    closeDropdown();
    try {
      const path = await workspaceStore.selectFolder();
      if (path) {
        // 检查是否已经是工作区（有 index.json）
        await workspaceStore.switchTo(path);
      }
    } catch (e) {
      console.error('选择文件夹失败:', e);
    }
  }
  
  // 从最近列表移除
  async function removeFromRecent(path: string, event: Event) {
    event.stopPropagation();
    try {
      await workspaceStore.removeFromRecent(path);
    } catch (e) {
      console.error('移除最近工作区失败:', e);
    }
  }
  
  // 点击外部关闭
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.workspace-selector')) {
      closeDropdown();
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="workspace-selector">
  <button class="workspace-btn" onclick={toggleDropdown} disabled={isLoading} bind:this={buttonRef}>
    <i class="ti ti-folder"></i>
    <span class="workspace-name">
      {currentWorkspace?.name || $_('workspace.default')}
    </span>
    <i class="ti ti-chevron-up" class:open={isOpen}></i>
  </button>
  
  {#if isOpen}
    <div class="workspace-dropdown" class:direction-down={direction === 'down'} style="top: {dropdownPosition.top}px; left: {dropdownPosition.left}px; width: {dropdownPosition.width}px;">
      <div class="dropdown-header">
        <span>{$_('workspace.recent')}</span>
      </div>
      
      <div class="workspace-list">
        {#if recentWorkspaces.length === 0}
          <div class="empty-state">{$_('workspace.noRecent')}</div>
        {:else}
          {#each recentWorkspaces as ws}
            <div 
              class="workspace-item" 
              class:active={currentWorkspace?.path === ws.path}
            >
              <div class="item-content" onclick={() => switchWorkspace(ws.path)} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && switchWorkspace(ws.path)}>
                <i class="ti ti-folder"></i>
                <span class="item-name">{ws.name}</span>
                <span class="item-path">{ws.path}</span>
              </div>
              {#if currentWorkspace?.path !== ws.path && ws.name !== 'default'}
                <button 
                  class="remove-btn" 
                  title={$_('workspace.remove')}
                  onclick={(e) => removeFromRecent(ws.path, e)}
                  type="button"
                >
                  <i class="ti ti-x"></i>
                </button>
              {/if}
            </div>
          {/each}
        {/if}
      </div>
      
      <div class="dropdown-divider"></div>
      
      <button class="action-item" onclick={createWorkspace} type="button">
        <i class="ti ti-plus"></i>
        <span>{$_('workspace.createNew')}</span>
      </button>
      
      <button class="action-item" onclick={selectFolder} type="button">
        <i class="ti ti-folder-plus"></i>
        <span>{$_('workspace.openOther')}</span>
      </button>
    </div>
  {/if}
</div>

<style>
  .workspace-selector {
    position: relative;
  }
  
  .workspace-btn {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .workspace-btn:hover {
    background: var(--line);
  }
  
  .workspace-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .workspace-btn i:first-child {
    font-size: 16px;
    color: var(--accent);
  }
  
  .workspace-name {
    flex: 1;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .ti-chevron-up {
    font-size: 14px;
    transition: transform 0.2s;
  }
  
  .ti-chevron-up.open {
    transform: rotate(180deg);
  }
  
  .workspace-dropdown {
    position: fixed;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 8px 0;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    z-index: 10000;
    max-height: 400px;
    overflow-y: auto;
  }

  .workspace-dropdown.direction-down {
    /* 向下展开时不需要额外样式，位置已通过JS计算 */
    top: 100%;
  }
  
  .dropdown-header {
    padding: 8px 16px;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .workspace-list {
    max-height: 200px;
    overflow-y: auto;
  }
  
  .empty-state {
    padding: 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }
  
  .workspace-item {
    display: flex;
    align-items: center;
    padding: 0;
    background: transparent;
    transition: all 0.2s;
  }
  
  .workspace-item:hover {
    background: var(--panel);
  }
  
  .workspace-item.active {
    background: var(--accent);
    color: white;
  }
  
  .item-content {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    cursor: pointer;
    min-width: 0;
  }
  
  .item-content:focus {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  
  .item-content i {
    font-size: 16px;
    color: var(--accent);
    flex-shrink: 0;
  }
  
  .workspace-item.active .item-content i {
    color: white;
  }
  
  .item-name {
    flex-shrink: 1;
    min-width: 0;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .item-path {
    flex: 1;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text-muted);
    font-size: 11px;
    margin-left: 4px;
  }
  
  .workspace-item.active .item-path {
    color: rgba(255, 255, 255, 0.7);
  }
  
  .remove-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    opacity: 0;
    transition: all 0.2s;
    flex-shrink: 0;
    margin-right: 8px;
  }
  
  .workspace-item:hover .remove-btn {
    opacity: 1;
  }
  
  .remove-btn:hover {
    background: var(--error);
    color: white;
  }
  
  .dropdown-divider {
    height: 1px;
    background: var(--line);
    margin: 8px 0;
  }
  
  .action-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: transparent;
    border: none;
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .action-item:hover {
    background: var(--panel);
  }
  
  .action-item i {
    font-size: 16px;
    color: var(--accent);
  }
</style>
