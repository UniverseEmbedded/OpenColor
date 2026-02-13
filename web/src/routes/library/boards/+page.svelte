<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { boardsStore } from '$lib/stores/boards.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';
  import type { BoardItem, BoardSpec, ColorProfile } from '$lib/types';
  import BoardPreview from '$lib/components/board/BoardPreview.svelte';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('library/boards');
    boardsStore.loadBoards();

    const handleDocumentClick = () => {
      handleClickOutside();
    };

    const handleDocumentKeydown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return;
      }
      handleClickOutside();
    };

    document.addEventListener('click', handleDocumentClick);
    document.addEventListener('keydown', handleDocumentKeydown);

    return () => {
      document.removeEventListener('click', handleDocumentClick);
      document.removeEventListener('keydown', handleDocumentKeydown);
    };
  });

  // 从 store 订阅状态
  let boards = $state<BoardItem[]>([]);
  let selectedBoard = $state<BoardItem | null>(null);
  let boardSpec = $state<BoardSpec | null>(null);
  let isLoading = $state(false);
  const detailProfile = $derived(() => {
    if (!selectedBoard?.profileColors || selectedBoard.profileColors.length === 0) return null;
    return {
      id: selectedBoard.profileId || '',
      name: selectedBoard.profileName || '耗材组',
      description: '',
      colors: selectedBoard.profileColors,
      marker_tl: '',
      marker_tr: '',
      marker_br: '',
      marker_bl: ''
    } as ColorProfile;
  });
  const detailProfileValue = $derived(detailProfile());

  boardsStore.subscribe((state) => {
    boards = state.boards;
    selectedBoard = state.selectedBoard;
    boardSpec = state.boardSpec;
    isLoading = state.isLoading;
  });

  // 更多菜单状态
  let activeMenuPath = $state<string | null>(null);
  let showDeleteConfirm = $state(false);
  let boardToDelete = $state<BoardItem | null>(null);
  let showRenameDialog = $state(false);
  let boardToRename = $state<BoardItem | null>(null);
  let newName = $state('');

  // 查看校准板详情
  async function viewBoardDetail(board: BoardItem) {
    await boardsStore.selectBoard(board);
    activeMenuPath = null;
  }

  function handleBoardKeydown(event: KeyboardEvent, board: BoardItem) {
    if (event.target !== event.currentTarget) {
      return;
    }
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    event.preventDefault();
    viewBoardDetail(board);
  }

  // 在资源管理器中打开
  async function openInExplorer(path: string, e: Event) {
    e.stopPropagation();
    try {
      await bridge.revealInExplorer(path);
    } catch (e) {
      console.error('打开资源管理器失败:', e);
    }
    activeMenuPath = null;
  }

  // 关闭详情
  function closeDetail() {
    boardsStore.selectBoard(null);
  }

  // 显示更多菜单
  function showMoreMenu(path: string, e: Event) {
    e.stopPropagation();
    activeMenuPath = activeMenuPath === path ? null : path;
  }

  // 点击其他地方关闭菜单
  function handleClickOutside() {
    activeMenuPath = null;
  }

  // 删除相关
  function confirmDelete(board: BoardItem, e: Event) {
    e.stopPropagation();
    boardToDelete = board;
    showDeleteConfirm = true;
    activeMenuPath = null;
  }

  async function handleDelete() {
    if (!boardToDelete) return;
    try {
      await boardsStore.deleteBoard(boardToDelete.path);
      showDeleteConfirm = false;
      boardToDelete = null;
    } catch (e) {
      console.error('删除失败:', e);
      alert('删除失败: ' + e);
    }
  }

  // 重命名相关
  function startRename(board: BoardItem, e: Event) {
    e.stopPropagation();
    boardToRename = board;
    // 提取当前名称（去掉 _board_spec 后缀）
    const nameMatch = board.name.match(/^(.+)_board_spec$/);
    newName = nameMatch ? nameMatch[1] : board.name;
    showRenameDialog = true;
    activeMenuPath = null;
  }

  async function handleRename() {
    if (!boardToRename || !newName.trim()) return;
    try {
      await boardsStore.renameBoard(boardToRename.path, newName.trim());
      showRenameDialog = false;
      boardToRename = null;
      newName = '';
    } catch (e) {
      console.error('重命名失败:', e);
      alert('重命名失败: ' + e);
    }
  }

  function cancelRename() {
    showRenameDialog = false;
    boardToRename = null;
    newName = '';
  }
</script>

<div class="boards-page">
  <h1>{$_('nav.library.boards')}</h1>
  <p class="description">管理校准板规格文件和3MF打印文件</p>

  <div class="content-grid">
    <!-- 左侧列表 -->
    <div class="list-panel">
      <div class="list-header">
        <h2>校准板列表</h2>
        <button class="btn-icon" onclick={() => boardsStore.refresh()} title="刷新列表">
          <i class="ti ti-refresh"></i>
        </button>
      </div>

      {#if isLoading}
        <div class="loading-state">
          <i class="ti ti-loader-2 spinning"></i>
          <span>加载中...</span>
        </div>
      {:else if boards.length === 0}
        <div class="empty-state">
          <i class="ti ti-grid-dots"></i>
          <span>暂无校准板</span>
          <p>在"校准板生成"页面创建校准板</p>
        </div>
      {:else}
        <div class="board-list">
          {#each boards as board}
            <div 
              class="board-item" 
              class:active={selectedBoard?.path === board.path}
              onclick={() => viewBoardDetail(board)}
              onkeydown={(e) => handleBoardKeydown(e, board)}
              role="button"
              tabindex="0"
            >
              <div class="board-info">
                <i class="ti ti-grid-3x3"></i>
                <div class="info-text">
                  <span class="name">{board.name}</span>
                  <span class="details">{board.rows}×{board.cols} 格子</span>
                </div>
              </div>
              <div class="actions">
                <button
                  class="open-btn"
                  title="在资源管理器中打开"
                  onclick={(e) => openInExplorer(board.path, e)}
                  type="button"
                >
                  <i class="ti ti-folder-open"></i>
                </button>
                <div class="more-menu-container">
                  <button
                    class="more-btn"
                    title="更多操作"
                    onclick={(e) => showMoreMenu(board.path, e)}
                    type="button"
                  >
                    <i class="ti ti-dots-vertical"></i>
                  </button>
                  {#if activeMenuPath === board.path}
                    <div class="dropdown-menu">
                      <button onclick={(e) => startRename(board, e)}>
                        <i class="ti ti-edit"></i>
                        重命名
                      </button>
                      <button class="danger" onclick={(e) => confirmDelete(board, e)}>
                        <i class="ti ti-trash"></i>
                        删除
                      </button>
                    </div>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- 右侧详情 -->
    <div class="detail-panel">
      {#if selectedBoard && boardSpec}
        <div class="detail-header">
          <h2>{boardSpec.name}</h2>
          <button class="btn-icon" onclick={closeDetail} aria-label="关闭">
            <i class="ti ti-x"></i>
          </button>
        </div>

        <div class="detail-content">
          <!-- 基本信息 -->
          <div class="info-section">
            <h3>基本信息</h3>
            <div class="info-grid">
              <div class="info-item">
                <span class="label">行数</span>
                <span class="value">{boardSpec.rows}</span>
              </div>
              <div class="info-item">
                <span class="label">列数</span>
                <span class="value">{boardSpec.cols}</span>
              </div>
              <div class="info-item">
                <span class="label">格子尺寸</span>
                <span class="value">{boardSpec.cellSizeMm}mm</span>
              </div>
              <div class="info-item">
                <span class="label">层高</span>
                <span class="value">{boardSpec.layerHeightMm}mm</span>
              </div>
            </div>
          </div>

          <!-- 格子预览 -->
          <div class="preview-section">
            <h3>格子预览</h3>
            <div class="grid-preview-wrapper">
              <BoardPreview
                cells={boardSpec.cells}
                profile={detailProfileValue}
                size="small"
                showLegend={false}
              />
            </div>
          </div>

          <!-- 文件路径 -->
          <div class="path-section">
            <h3>文件路径</h3>
            <code class="file-path">{selectedBoard.path}</code>
          </div>
        </div>
      {:else}
        <div class="empty-detail">
          <i class="ti ti-grid-dots"></i>
          <span>选择一个校准板查看详情</span>
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- 删除确认对话框 -->
{#if showDeleteConfirm}
  <div class="modal-overlay">
    <div class="modal">
      <h3>确认删除</h3>
      <p>确定要删除校准板 "{boardToDelete?.name}" 吗？</p>
      <p class="warning">此操作将同时删除规格文件和3MF打印文件，不可恢复。</p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick={() => { showDeleteConfirm = false; boardToDelete = null; }}>取消</button>
        <button class="btn-danger" onclick={handleDelete}>删除</button>
      </div>
    </div>
  </div>
{/if}

<!-- 重命名对话框 -->
{#if showRenameDialog}
  <div class="modal-overlay">
    <div class="modal">
      <h3>重命名校准板</h3>
      <input 
        type="text" 
        bind:value={newName} 
        placeholder="输入新名称"
        onkeydown={(e) => e.key === 'Enter' && handleRename()}
      />
      <div class="modal-actions">
        <button class="btn-secondary" onclick={cancelRename}>取消</button>
        <button class="btn-primary" onclick={handleRename} disabled={!newName.trim()}>确定</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .boards-page {
    max-width: 1400px;
  }

  h1 {
    font-size: 24px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 8px;
  }

  .description {
    color: var(--text-muted);
    margin-bottom: 24px;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 400px 1fr;
    gap: 24px;
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }

  .list-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
  }

  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--line);
  }

  .list-header h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
  }

  .btn-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s;
  }

  .btn-icon:hover {
    background: var(--panel-elevated);
    color: var(--text);
  }

  .loading-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: var(--text-muted);
    text-align: center;
  }

  .loading-state i,
  .empty-state i {
    font-size: 32px;
    margin-bottom: 12px;
    opacity: 0.5;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .board-list {
    max-height: 600px;
    overflow-y: auto;
  }

  .board-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-bottom: 1px solid var(--line);
    cursor: pointer;
    transition: background 0.2s;
  }

  .board-item:hover {
    background: var(--panel-elevated);
  }

  .board-item.active {
    background: rgba(0, 89, 132, 0.1);
  }

  .board-info {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .board-info > i {
    font-size: 20px;
    color: var(--accent);
    flex-shrink: 0;
  }

  .info-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    overflow: hidden;
  }

  .name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .details {
    font-size: 12px;
    color: var(--text-muted);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .open-btn,
  .more-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s;
  }

  .open-btn:hover {
    background: var(--accent);
    color: white;
  }

  .more-btn:hover {
    background: var(--panel-elevated);
    color: var(--text);
  }

  .more-menu-container {
    position: relative;
  }

  .dropdown-menu {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 4px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 100;
    min-width: 140px;
    overflow: hidden;
  }

  .dropdown-menu button {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 16px;
    background: transparent;
    border: none;
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: background 0.2s;
    text-align: left;
  }

  .dropdown-menu button:hover {
    background: var(--panel-elevated);
  }

  .dropdown-menu button.danger {
    color: #ff4444;
  }

  .dropdown-menu button.danger:hover {
    background: rgba(255, 68, 68, 0.1);
  }

  .detail-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--line);
  }

  .detail-header h2 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
  }

  .detail-content {
    padding: 20px;
  }

  .info-section,
  .preview-section,
  .path-section {
    margin-bottom: 24px;
  }

  .info-section h3,
  .preview-section h3,
  .path-section h3 {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
  }

  .info-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .info-item {
    display: flex;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--bg);
    border-radius: 8px;
  }

  .info-item .label {
    font-size: 12px;
    color: var(--text-muted);
  }

  .info-item .value {
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
  }

  .grid-preview-wrapper {
    background: var(--bg);
    border-radius: 8px;
    padding: 16px;
    max-height: 400px;
    overflow: auto;
  }

  .grid-preview-wrapper :global(.board-grid-wrapper) {
    min-height: 300px;
  }

  .file-path {
    display: block;
    padding: 12px 16px;
    background: var(--bg);
    border-radius: 8px;
    font-family: 'Maple Mono Normal NF CN', monospace;
    font-size: 12px;
    color: var(--text-muted);
    word-break: break-all;
  }

  .empty-detail {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 24px;
    color: var(--text-muted);
    text-align: center;
  }

  .empty-detail i {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.3;
  }

  /* 模态框样式 */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 24px;
    min-width: 360px;
    max-width: 90vw;
  }

  .modal h3 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 16px;
  }

  .modal p {
    color: var(--text);
    margin-bottom: 8px;
  }

  .modal p.warning {
    color: #ff4444;
    font-size: 13px;
  }

  .modal input {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 6px;
    color: var(--text);
    font-size: 14px;
    margin-bottom: 16px;
  }

  .modal input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .modal-actions button {
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--text);
  }

  .btn-secondary:hover {
    background: var(--panel-elevated);
  }

  .btn-primary {
    background: var(--accent);
    border: 1px solid var(--accent);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-danger {
    background: #ff4444;
    border: 1px solid #ff4444;
    color: white;
  }

  .btn-danger:hover {
    opacity: 0.9;
  }
</style>
