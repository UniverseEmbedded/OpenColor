<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { boardGenStore } from '$lib/stores/calibrate.svelte';
  import { workspaceStore } from '$lib/stores/workspace.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';
  import type { BoardItem } from '$lib/types';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('calibrate/board-gen');
    // 加载当前工作区的校准板列表
    const workspace = workspaceStore.currentWorkspace;
    if (workspace) {
      const boardDir = `${workspace.path}\\01_board_gen`;
      boardGenStore.loadBoards(boardDir);
    }
  });

  // 本地状态
  let isGenerating = $state(false);
  let progress = $state(0);
  let generatedBoards = $state<BoardItem[]>([]);
  let error = $state<string | null>(null);

  // 表单配置
  let config = $state({
    specName: '8-Color Board',
    numBoards: 8,
    shrink: 0.0,
    layerHeightMm: 0.2,
    includeApriltag: false,
    includeSideTriangles: false
  });

  // 订阅 store
  $effect(() => {
    const unsubscribe = boardGenStore.subscribe((value) => {
      isGenerating = value.isGenerating;
      progress = value.progress;
      generatedBoards = value.generatedBoards;
      error = value.error;
    });
    return unsubscribe;
  });

  // 生成校准板
  async function generateBoards() {
    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) {
      error = '请先选择工作区';
      return;
    }

    const outputDir = `${workspace.path}\\01_board_gen`;

    try {
      await boardGenStore.generateBoards({
        outputDir,
        ...config
      });
    } catch (e) {
      console.error('生成校准板失败:', e);
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

  // 格式化日期
  function formatDate(timestamp: string): string {
    return new Date(timestamp).toLocaleString('zh-CN');
  }
</script>

<div class="board-gen-page">
  <h1>{$_('nav.calibrate.boardGen')}</h1>
  <p class="description">生成8色校准板的规格文件和3MF打印文件</p>

  {#if error}
    <div class="error-message">
      <i class="ti ti-alert-circle"></i>
      <span>{error}</span>
      <button onclick={() => boardGenStore.clearError()} type="button" aria-label="关闭错误">
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}

  <div class="content-grid">
    <!-- 配置面板 -->
    <div class="config-panel">
      <h2>生成配置</h2>

      <div class="form-group">
        <label for="specName">规格名称</label>
        <input
          id="specName"
          type="text"
          bind:value={config.specName}
          placeholder="8-Color Board"
        />
      </div>

      <div class="form-group">
        <label for="numBoards">板子数量</label>
        <input
          id="numBoards"
          type="number"
          bind:value={config.numBoards}
          min="1"
          max="26"
        />
      </div>

      <div class="form-group">
        <label for="shrink">格子缩进量 (mm)</label>
        <input
          id="shrink"
          type="number"
          bind:value={config.shrink}
          min="0"
          max="1"
          step="0.1"
        />
      </div>

      <div class="form-group">
        <label for="layerHeightMm">层高 (mm)</label>
        <input
          id="layerHeightMm"
          type="number"
          bind:value={config.layerHeightMm}
          min="0.1"
          max="0.5"
          step="0.05"
        />
      </div>

      <div class="form-group checkbox">
        <label>
          <input
            type="checkbox"
            bind:checked={config.includeApriltag}
          />
          包含 AprilTag
        </label>
      </div>

      <div class="form-group checkbox">
        <label>
          <input
            type="checkbox"
            bind:checked={config.includeSideTriangles}
          />
          包含侧边白色三角形
        </label>
      </div>

      <button
        class="btn-primary generate-btn"
        onclick={generateBoards}
        disabled={isGenerating}
      >
        {#if isGenerating}
          <i class="ti ti-loader-2 spinning"></i>
          生成中... {Math.round(progress * 100)}%
        {:else}
          <i class="ti ti-play"></i>
          生成校准板
        {/if}
      </button>
    </div>

    <!-- 生成的文件列表 -->
    <div class="files-panel">
      <h2>生成的文件</h2>

      {#if generatedBoards.length === 0}
        <div class="empty-state">
          <i class="ti ti-grid-dots"></i>
          <span>尚未生成校准板</span>
          <p>配置参数后点击"生成校准板"按钮</p>
        </div>
      {:else}
        <div class="board-list">
          {#each generatedBoards as board}
            <div class="board-item">
              <div class="board-info">
                <i class="ti ti-grid-3x3"></i>
                <div class="info-text">
                  <span class="name">{board.name}</span>
                  <span class="details">{board.rows}×{board.cols} 格子</span>
                  <span class="date">{formatDate(board.modifiedAt)}</span>
                </div>
              </div>
              <button
                class="open-btn"
                title="在资源管理器中打开"
                onclick={() => openInExplorer(board.path)}
                type="button"
              >
                <i class="ti ti-folder-open"></i>
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .board-gen-page {
    max-width: 1200px;
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

  .error-message button {
    background: transparent;
    border: none;
    color: var(--error);
    cursor: pointer;
    padding: 4px;
    margin-left: auto;
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

  .config-panel,
  .files-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 24px;
  }

  .config-panel h2,
  .files-panel h2 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 20px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 6px;
  }

  .form-group input[type="text"],
  .form-group input[type="number"] {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
    transition: border-color 0.2s;
  }

  .form-group input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .form-group.checkbox label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: var(--text);
  }

  .form-group.checkbox input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: var(--accent);
  }

  .generate-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 24px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.2s;
    margin-top: 8px;
  }

  .generate-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .generate-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: var(--text-muted);
    text-align: center;
  }

  .empty-state i {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .empty-state span {
    font-size: 16px;
    font-weight: 500;
    margin-bottom: 8px;
  }

  .empty-state p {
    font-size: 13px;
    opacity: 0.7;
  }

  .board-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .board-item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    transition: background 0.2s;
  }

  .board-item:hover {
    background: var(--panel-elevated);
  }

  .board-info {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .board-info > i {
    font-size: 24px;
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

  .date {
    font-size: 11px;
    color: var(--text-muted);
    opacity: 0.7;
  }

  .open-btn {
    width: 36px;
    height: 36px;
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
</style>
