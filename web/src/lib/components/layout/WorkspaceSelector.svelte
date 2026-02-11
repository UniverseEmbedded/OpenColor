<script lang="ts">
  import { _ } from '$lib/i18n';
  
  let isOpen = $state(false);
  let currentWorkspace = $state('default');
  
  // 模拟最近工作区
  const recentWorkspaces = [
    { id: 'default', name: '默认工作区', path: 'C:\\Users\\xxx\\Documents\\OpenColor\\default' },
  ];
  
  function toggleOpen() {
    isOpen = !isOpen;
  }
  
  function handleCreate() {
    alert('新建工作区功能开发中');
    isOpen = false;
  }
  
  function handleOpen() {
    alert('打开其他工作区功能开发中');
    isOpen = false;
  }
  
  function selectWorkspace(id: string) {
    currentWorkspace = id;
    isOpen = false;
  }
</script>

<div class="workspace-selector">
  <button class="trigger" onclick={toggleOpen}>
    <i class="ti ti-folder"></i>
    <span class="name">{recentWorkspaces.find(w => w.id === currentWorkspace)?.name || 'default'}</span>
    <i class="ti ti-chevron-up" class:open={isOpen}></i>
  </button>
  
  {#if isOpen}
    <div class="dropdown">
      <div class="current">
        <div class="label">{$_('workspace.current')}</div>
        <div class="workspace-item current-item">
          <i class="ti ti-folder"></i>
          <div class="info">
            <div class="name">{recentWorkspaces.find(w => w.id === currentWorkspace)?.name}</div>
            <div class="path">{recentWorkspaces.find(w => w.id === currentWorkspace)?.path}</div>
          </div>
        </div>
      </div>
      
      {#if recentWorkspaces.length > 1}
        <div class="recent">
          <div class="label">{$_('workspace.recent')}</div>
          {#each recentWorkspaces.filter(w => w.id !== currentWorkspace) as workspace}
            <button class="workspace-item" onclick={() => selectWorkspace(workspace.id)}>
              <i class="ti ti-folder"></i>
              <div class="info">
                <div class="name">{workspace.name}</div>
                <div class="path">{workspace.path}</div>
              </div>
            </button>
          {/each}
        </div>
      {/if}
      
      <div class="actions">
        <button class="action-btn" onclick={handleCreate}>
          <i class="ti ti-plus"></i>
          {$_('workspace.create')}
        </button>
        <button class="action-btn" onclick={handleOpen}>
          <i class="ti ti-folder-open"></i>
          {$_('workspace.open')}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .workspace-selector {
    position: relative;
  }
  
  .trigger {
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
  
  .trigger:hover {
    background: var(--line);
  }
  
  .trigger i {
    font-size: 16px;
    color: var(--text-muted);
  }
  
  .trigger .name {
    flex: 1;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .trigger .ti-chevron-up {
    transition: transform 0.2s;
  }
  
  .trigger .ti-chevron-up.open {
    transform: rotate(180deg);
  }
  
  .dropdown {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    right: 0;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    z-index: 100;
  }
  
  .label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }
  
  .workspace-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: var(--text);
    cursor: pointer;
    width: 100%;
    text-align: left;
  }
  
  .workspace-item:hover {
    background: var(--panel);
  }
  
  .workspace-item.current-item {
    background: var(--accent);
    color: white;
  }
  
  .workspace-item i {
    font-size: 18px;
    margin-top: 2px;
  }
  
  .workspace-item .info {
    flex: 1;
    min-width: 0;
  }
  
  .workspace-item .name {
    font-size: 13px;
    font-weight: 500;
  }
  
  .workspace-item .path {
    font-size: 11px;
    opacity: 0.7;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .recent {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }
  
  .actions {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .action-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .action-btn:hover {
    background: var(--panel);
  }
  
  .action-btn i {
    font-size: 16px;
    color: var(--accent);
  }
</style>
