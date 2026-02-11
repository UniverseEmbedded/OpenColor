<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { workspaceStore, type WorkspaceInfo } from '$lib/stores/workspace.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('settings/workspace');
    workspaceStore.init();
  });
  
  // 本地状态
  let currentWorkspace = $state<WorkspaceInfo | null>(null);
  let recentWorkspaces = $state<WorkspaceInfo[]>([]);
  let isLoading = $state(false);
  let error = $state<string | null>(null);
  
  // 订阅 store
  $effect(() => {
    const unsubscribe = workspaceStore.subscribe((value) => {
      currentWorkspace = value.currentWorkspace;
      recentWorkspaces = value.recentWorkspaces;
      isLoading = value.isLoading;
      error = value.error;
    });
    return unsubscribe;
  });
  
  // 创建新工作区
  async function createWorkspace() {
    try {
      await workspaceStore.create();
    } catch (e) {
      console.error('创建工作区失败:', e);
    }
  }
  
  // 选择文件夹打开工作区
  async function openWorkspace() {
    try {
      const path = await workspaceStore.selectFolder();
      if (path) {
        await workspaceStore.switchTo(path);
      }
    } catch (e) {
      console.error('打开工作区失败:', e);
    }
  }
  
  // 切换到指定工作区
  async function switchToWorkspace(path: string) {
    try {
      await workspaceStore.switchTo(path);
    } catch (e) {
      console.error('切换工作区失败:', e);
    }
  }
  
  // 从最近列表移除
  async function removeFromRecent(path: string) {
    try {
      await workspaceStore.removeFromRecent(path);
    } catch (e) {
      console.error('移除最近工作区失败:', e);
    }
  }
  
  // 格式化日期
  function formatDate(timestamp: number): string {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  }

  // 在资源管理器中打开工作区
  async function openInExplorer(path: string, event: Event) {
    event.stopPropagation();
    try {
      await bridge.revealInExplorer(path);
    } catch (e) {
      console.error('在资源管理器中打开失败:', e);
    }
  }
</script>

<div class="settings-page">
  <h1>{$_('settings.workspace.title')}</h1>
  
  {#if error}
    <div class="error-message">
      <i class="ti ti-alert-circle"></i>
      <span>{error}</span>
      <button onclick={() => workspaceStore.clearError()} type="button" aria-label="关闭错误">
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}
  
  <!-- 当前工作区 -->
  <div class="settings-section">
    <h2>{$_('settings.workspace.current')}</h2>
    <div class="current-workspace">
      {#if currentWorkspace}
        <div class="workspace-info">
          <i class="ti ti-folder"></i>
          <div class="info-text">
            <span class="name">{currentWorkspace.name}</span>
            <span class="path">{currentWorkspace.path}</span>
          </div>
          <button
            class="open-explorer-btn"
            title={$_('workspace.openInExplorer')}
            onclick={(e) => currentWorkspace && openInExplorer(currentWorkspace.path, e)}
            type="button"
          >
            <i class="ti ti-folder-open"></i>
          </button>
        </div>
      {:else}
        <div class="empty-state">
          <i class="ti ti-folder-off"></i>
          <span>{$_('workspace.noCurrent')}</span>
        </div>
      {/if}
    </div>
  </div>
  
  <!-- 操作按钮 -->
  <div class="settings-section">
    <h2>{$_('settings.workspace.actions')}</h2>
    <div class="actions">
      <button class="btn-primary" onclick={createWorkspace} disabled={isLoading}>
        <i class="ti ti-plus"></i>
        {$_('workspace.createNew')}
      </button>
      <button class="btn-secondary" onclick={openWorkspace} disabled={isLoading}>
        <i class="ti ti-folder-plus"></i>
        {$_('workspace.openOther')}
      </button>
    </div>
  </div>
  
  <!-- 最近工作区 -->
  <div class="settings-section">
    <h2>{$_('workspace.recent')}</h2>
    <div class="recent-list">
      {#if recentWorkspaces.length === 0}
        <div class="empty-state">
          <i class="ti ti-history-off"></i>
          <span>{$_('workspace.noRecent')}</span>
        </div>
      {:else}
        {#each recentWorkspaces as ws}
          <div class="recent-item" class:active={currentWorkspace?.path === ws.path}>
            <button class="item-info" onclick={() => switchToWorkspace(ws.path)} type="button">
              <i class="ti ti-folder"></i>
              <div class="info-text">
                <span class="name">{ws.name}</span>
                <span class="path">{ws.path}</span>
                <span class="date">{$_('workspace.lastOpened')}: {formatDate(ws.last_opened)}</span>
              </div>
            </button>
            {#if currentWorkspace?.path === ws.path}
              <span class="current-badge">{$_('workspace.current')}</span>
            {:else if ws.name !== 'default'}
              <button 
                class="remove-btn" 
                title={$_('workspace.remove')}
                onclick={() => removeFromRecent(ws.path)}
                type="button"
              >
                <i class="ti ti-trash"></i>
              </button>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  </div>
</div>

<style>
  .settings-page {
    max-width: 800px;
  }
  
  h1 {
    font-size: 24px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 32px;
  }
  
  .error-message {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error);
    border-radius: 8px;
    color: var(--error);
    margin-bottom: 24px;
  }
  
  .error-message i {
    font-size: 20px;
  }
  
  .error-message span {
    flex: 1;
  }
  
  .error-message button {
    background: transparent;
    border: none;
    color: var(--error);
    cursor: pointer;
    padding: 4px;
  }
  
  .settings-section {
    margin-bottom: 32px;
  }
  
  .settings-section h2 {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
  }
  
  .current-workspace {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
    overflow: hidden;
  }
  
  .workspace-info {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
  }
  
  .workspace-info > i {
    font-size: 32px;
    color: var(--accent);
  }
  
  .info-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
    overflow: hidden;
  }
  
  .name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
  }
  
  .path {
    font-size: 13px;
    color: var(--text-muted);
    font-family: 'Maple Mono Normal NF CN', monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .date {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
  }
  
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 32px;
    color: var(--text-muted);
  }
  
  .empty-state i {
    font-size: 24px;
  }
  
  .actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  
  .btn-primary,
  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
  }
  
  .btn-primary {
    background: var(--accent);
    color: white;
  }
  
  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }
  
  .btn-secondary {
    background: var(--panel);
    border: 1px solid var(--line);
    color: var(--text);
  }
  
  .btn-secondary:hover:not(:disabled) {
    background: var(--panel-elevated);
  }
  
  .btn-primary:disabled,
  .btn-secondary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .recent-list {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
  }
  
  .recent-item {
    display: flex;
    align-items: flex-start;
    padding: 16px 20px;
    border-bottom: 1px solid var(--line);
    transition: all 0.2s;
    position: relative;
    padding-right: 100px; /* 为标签预留空间 */
  }
  
  .recent-item:last-child {
    border-bottom: none;
  }
  
  .recent-item:hover {
    background: var(--panel-elevated);
  }
  
  .recent-item.active {
    background: rgba(0, 89, 132, 0.1);
  }
  
  .item-info {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    background: transparent;
    border: none;
    color: var(--text);
    text-align: left;
    padding: 0;
    font-size: inherit;
  }
  
  .item-info > i {
    font-size: 20px;
    color: var(--accent);
  }
  
  .remove-btn {
    position: absolute;
    top: 12px;
    right: 16px;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    font-size: 20px;
  }

  .remove-btn:hover {
    background: var(--error);
    color: white;
  }
  
  .current-badge {
    position: absolute;
    top: 16px;
    right: 20px;
    padding: 4px 12px;
    background: var(--accent);
    color: white;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
  }

  .open-explorer-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    margin-left: auto;
    flex-shrink: 0;
  }

  .open-explorer-btn:hover {
    background: var(--accent);
    color: white;
  }
</style>
