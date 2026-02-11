<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { boardGenStore } from '$lib/stores/calibrate.svelte';
  import { workspaceStore } from '$lib/stores/workspace.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';
  import type { BoardItem, BoardSpec } from '$lib/types';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('library/boards');
    loadBoards();
  });

  // 本地状态
  let boards = $state<BoardItem[]>([]);
  let selectedBoard = $state<BoardItem | null>(null);
  let boardSpec = $state<BoardSpec | null>(null);
  let isLoading = $state(false);

  // 加载校准板列表
  async function loadBoards() {
    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) return;

    isLoading = true;
    try {
      const boardDir = `${workspace.path}\\01_board_gen`;
      await boardGenStore.loadBoards(boardDir);
      
      // 订阅 store 获取数据
      const unsubscribe = boardGenStore.subscribe((value) => {
        boards = value.generatedBoards;
      });
      unsubscribe();
    } catch (e) {
      console.error('加载校准板列表失败:', e);
    } finally {
      isLoading = false;
    }
  }

  // 查看校准板详情
  async function viewBoardDetail(board: BoardItem) {
    selectedBoard = board;
    
    try {
      // 读取规格文件内容
      const content = await bridge.invoke<string>('file_read_text', {
        path: board.path
      });
      boardSpec = JSON.parse(content);
    } catch (e) {
      console.error('读取规格文件失败:', e);
      boardSpec = null;
    }
  }

  // 在资源管理器中打开
  async function openInExplorer(path: string) {
    try {
      await bridge.revealInExplorer(path);
    } catch (e) {
      console.error('打开资源管理器失败:', e);
    }
  }

  // 关闭详情
  function closeDetail() {
    selectedBoard = null;
    boardSpec = null;
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
        <button class="btn-icon" onclick={loadBoards} title="刷新列表">
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
            >
              <div class="board-info">
                <i class="ti ti-grid-3x3"></i>
                <div class="info-text">
                  <span class="name">{board.name}</span>
                  <span class="details">{board.rows}×{board.cols} 格子</span>
                </div>
              </div>
              <button
                class="open-btn"
                title="在资源管理器中打开"
                onclick={(e) => { e.stopPropagation(); openInExplorer(board.path); }}
                type="button"
              >
                <i class="ti ti-folder-open"></i>
              </button>
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
          <button class="btn-icon" onclick={closeDetail}>
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
            <div class="grid-preview">
              {#each Array(boardSpec.rows) as _, row}
                <div class="grid-row">
                  {#each Array(boardSpec.cols) as _, col}
                    {@const cell = boardSpec.cells.find(c => c.row === row && c.col === col)}
                    <div 
                      class="grid-cell"
                      style="background-color: {cell ? `rgb(${cell.targetRgb.r}, ${cell.targetRgb.g}, ${cell.targetRgb.b})` : '#333'}"
                      title="{cell ? `Row ${row}, Col ${col}` : 'Empty'}"
                    ></div>
                  {/each}
                </div>
              {/each}
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
    grid-template-columns: 360px 1fr;
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
  }

  .board-info > i {
    font-size: 20px;
    color: var(--accent);
  }

  .info-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
  }

  .details {
    font-size: 12px;
    color: var(--text-muted);
  }

  .open-btn {
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

  .grid-preview {
    display: flex;
    flex-direction: column;
    gap: 1px;
    background: var(--line);
    border-radius: 8px;
    overflow: hidden;
    max-width: 300px;
  }

  .grid-row {
    display: flex;
    gap: 1px;
  }

  .grid-cell {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
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
</style>
