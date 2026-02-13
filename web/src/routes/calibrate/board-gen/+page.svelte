<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { boardGenStore } from '$lib/stores/calibrate.svelte';
  import { workspaceStore } from '$lib/stores/workspace.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';
  import type { BoardItem, ColorProfile, BoardCell } from '$lib/types';
  import BoardPreview from '$lib/components/board/BoardPreview.svelte';
  import BoardCard from '$lib/components/board/BoardCard.svelte';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('calibrate/board-gen');
    boardGenStore.loadProfiles();
  });

  // 本地状态
  let isGenerating = $state(false);
  let progress = $state(0);
  let progressInfo = $state<import('$lib/stores/calibrate.svelte').ProgressInfo | null>(null);
  let generatedBoards = $state<BoardItem[]>([]);
  let profiles = $state<ColorProfile[]>([]);
  let selectedProfile = $state<ColorProfile | null>(null);
  let selectedBoard = $state<BoardItem | null>(null);
  let previewCells = $state<BoardCell[]>([]);
  let error = $state<string | null>(null);

  // 表单配置 - 使用新的默认值
  let config = $state({
    numBoards: 8,
    shrink: 0.0,
    layers: 5,
    layerHeightMm: 0.12,
    cellSizeMm: 4.0,      // 默认4mm格子尺寸
    dataRows: 24,         // 默认24行数据格
    dataCols: 24          // 默认24列数据格
  });

  const MIN_LAYER_HEIGHT = 0.08;
  const MAX_LAYER_HEIGHT = 0.2;
  const MIN_CELL_SIZE = 2.0;
  const MAX_CELL_SIZE = 10.0;
  const MIN_DATA_GRID = 10;
  const MAX_DATA_GRID = 50;
  const MIN_LAYERS = 1;
  const MAX_LAYERS = 20;

  // 订阅 store
  $effect(() => {
    const unsubscribe = boardGenStore.subscribe((value) => {
      isGenerating = value.isGenerating;
      progress = value.progress;
      progressInfo = value.progressInfo;
      generatedBoards = value.generatedBoards;
      profiles = value.profiles;
      selectedProfile = value.selectedProfile;
      selectedBoard = value.selectedBoard;
      previewCells = value.previewCells;
      error = value.error;
    });
    return unsubscribe;
  });

  // 计算总格子数（数据格+边框）
  function getTotalRows(): number {
    return config.dataRows + 2; // 上下各1格边框
  }

  function getTotalCols(): number {
    return config.dataCols + 2; // 左右各1格边框
  }

  // 格式化时间为 mm:ss
  function formatTime(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function handleProfileChange(event: Event) {
    const select = event.target as HTMLSelectElement;
    boardGenStore.selectProfile(select.value);
  }

  async function handleBoardSelect(board: BoardItem) {
    await boardGenStore.selectBoard(board);
  }

  async function generateBoards() {
    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) {
      error = $_('boardGen.selectWorkspaceFirst');
      return;
    }

    if (!selectedProfile) {
      error = $_('boardGen.selectProfileFirst');
      return;
    }

    try {
      await boardGenStore.generateBoards({
        profileId: selectedProfile.id,
        numBoards: config.numBoards,
        shrink: config.shrink,
        layers: config.layers,
        layerHeightMm: config.layerHeightMm,
        cellSizeMm: config.cellSizeMm,
        dataRows: config.dataRows,
        dataCols: config.dataCols,
        workspacePath: workspace.path
      });
    } catch (e) {
      console.error('生成校准板失败:', e);
    }
  }

  async function openInExplorer(path: string) {
    try {
      await bridge.revealInExplorer(path);
    } catch (e) {
      console.error('打开资源管理器失败:', e);
    }
  }

  // 获取数据格数量显示文本
  function getDataCellCountText(board: BoardItem | null): string {
    if (!board) return '';
    const dataRows = board.dataRows || Math.max(0, board.rows - 2);
    const dataCols = board.dataCols || Math.max(0, board.cols - 2);
    return `${dataRows}×${dataCols}=${dataRows * dataCols}`;
  }
</script>

<div class="board-gen-page">
  <div class="header">
    <h1>{$_('nav.calibrate.boardGen')}</h1>
    <button class="btn btn-primary" onclick={() => {
      const workspace = workspaceStore.currentWorkspace;
      if (workspace) {
        openInExplorer(`${workspace.path}\\01_board_gen`);
      }
    }}>
      <i class="ti ti-folder-open"></i>
      {$_('workspace.openInExplorer')}
    </button>
  </div>
  <p class="description">{$_('boardGen.description')}</p>

  {#if error}
    <div class="error-message">
      <i class="ti ti-alert-circle"></i>
      <span>{error}</span>
      <button onclick={() => boardGenStore.clearError()} type="button" aria-label={$_('app.close')}>
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}

  <!-- 卡片列表 - 只在有生成板子时显示 -->
  {#if generatedBoards.length > 0}
    <div class="cards-section">
      <h2>{$_('boardGen.generatedBoards')}</h2>
      <div class="cards-container">
        {#each generatedBoards as board}
          <BoardCard 
            {board} 
            profile={selectedProfile} 
            isActive={selectedBoard?.path === board.path}
            onClick={() => handleBoardSelect(board)}
          />
        {/each}
      </div>
    </div>
  {/if}

  <div class="content-grid">
    <!-- 配置面板 -->
    <div class="config-panel">
      <h2>{$_('boardGen.configTitle')}</h2>

      <div class="form-group">
        <label for="profile">{$_('boardGen.profile')}</label>
        <select
          id="profile"
          value={selectedProfile?.id || ''}
          onchange={handleProfileChange}
          disabled={profiles.length === 0}
        >
          {#if profiles.length === 0}
            <option value="">{$_('app.loading')}</option>
          {:else}
            {#each profiles as profile}
              <option value={profile.id}>{profile.name} ({profile.colors.length}{$_('boardGen.colors')})</option>
            {/each}
          {/if}
        </select>
        {#if selectedProfile}
          <div class="profile-colors">
            {#each selectedProfile.colors as color}
              <div class="color-dot" style="background-color: rgb({color.r}, {color.g}, {color.b})" title={color.name}></div>
            {/each}
          </div>
          <p class="profile-description">{selectedProfile.description}</p>
        {/if}
      </div>

      <div class="form-group">
        <label for="layerHeight">
          {$_('boardGen.layerHeight')}: {config.layerHeightMm.toFixed(2)}mm
        </label>
        <input
          id="layerHeight"
          type="range"
          bind:value={config.layerHeightMm}
          min={MIN_LAYER_HEIGHT}
          max={MAX_LAYER_HEIGHT}
          step="0.01"
        />
        <div class="range-labels">
          <span>{MIN_LAYER_HEIGHT}mm</span>
          <span>{MAX_LAYER_HEIGHT}mm</span>
        </div>
      </div>

      <div class="form-group">
        <label for="layers">{$_('boardGen.layerCount')}: {config.layers}</label>
        <input
          id="layers"
          type="number"
          bind:value={config.layers}
          min={MIN_LAYERS}
          max={MAX_LAYERS}
        />
      </div>

      <div class="form-group">
        <label for="cellSize">
          {$_('boardGen.cellSize')}: {config.cellSizeMm.toFixed(1)}mm
        </label>
        <input
          id="cellSize"
          type="range"
          bind:value={config.cellSizeMm}
          min={MIN_CELL_SIZE}
          max={MAX_CELL_SIZE}
          step="0.5"
        />
        <div class="range-labels">
          <span>{MIN_CELL_SIZE}mm</span>
          <span>{MAX_CELL_SIZE}mm</span>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group half">
          <label for="dataRows">数据行数</label>
          <input
            id="dataRows"
            type="number"
            bind:value={config.dataRows}
            min={MIN_DATA_GRID}
            max={MAX_DATA_GRID}
          />
        </div>
        <div class="form-group half">
          <label for="dataCols">数据列数</label>
          <input
            id="dataCols"
            type="number"
            bind:value={config.dataCols}
            min={MIN_DATA_GRID}
            max={MAX_DATA_GRID}
          />
        </div>
      </div>

      <div class="form-group">
        <div class="info-label">
          总格子数: {getTotalRows()}×{getTotalCols()}={getTotalRows() * getTotalCols()}格
          （含边框）
        </div>
      </div>

      <div class="form-group">
        <label for="numBoards">{$_('boardGen.numBoards')}</label>
        <input
          id="numBoards"
          type="number"
          bind:value={config.numBoards}
          min="1"
          max="26"
        />
      </div>

      <div class="form-group">
        <label for="shrink">{$_('boardGen.shrink')} (mm)</label>
        <input
          id="shrink"
          type="number"
          bind:value={config.shrink}
          min="0"
          max="1"
          step="0.1"
        />
      </div>

      <button
        class="btn-primary generate-btn"
        onclick={generateBoards}
        disabled={isGenerating}
      >
        {#if isGenerating}
          <i class="ti ti-loader-2 spinning"></i>
          {$_('boardGen.generating')} {Math.round(progress * 100)}%
        {:else}
          <i class="ti ti-play"></i>
          {$_('boardGen.generate')}
        {/if}
      </button>

      {#if isGenerating && progressInfo}
        <div class="progress-detail">
          <div class="progress-bar">
            <div class="progress-fill" style="width: {progressInfo.percentage}%"></div>
          </div>
          <div class="progress-info">
            <span class="stage">{progressInfo.stageDescription}</span>
            <span class="count">{progressInfo.current}/{progressInfo.total}</span>
          </div>
          <div class="time-info">
            <span>已用: {formatTime(progressInfo.elapsedMs)}</span>
            <span>预计剩余: {formatTime(progressInfo.estimatedRemainingMs)}</span>
          </div>
        </div>
      {/if}
    </div>

    <!-- 主面板 -->
    <div class="main-panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">{selectedBoard?.name || $_('boardGen.selectBoard')}</div>
          <div class="panel-subtitle">
            {#if selectedProfile && selectedBoard}
              {selectedProfile.name} | {selectedProfile.colors.length}{$_('boardGen.colors')} |
               {selectedBoard.layers || 5}{$_('boardGen.layers')} |
               {getDataCellCountText(selectedBoard)}{$_('boardGen.dataCells')}
            {:else}
              {$_('boardGen.clickCardToView')}
            {/if}
          </div>
        </div>
      </div>
      
      {#if previewCells.length > 0 && selectedProfile}
        <div class="grid-wrapper">
          <BoardPreview cells={previewCells} profile={selectedProfile} size="large" />
        </div>
      {:else}
        <div class="empty-preview">
          <i class="ti ti-grid-dots"></i>
          <span>{$_('boardGen.selectBoard')}</span>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .board-gen-page {
    max-width: 1400px;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  h1 {
    font-size: 24px;
    font-weight: 600;
    color: var(--text);
  }

  .description {
    color: var(--text-muted);
    margin-bottom: 24px;
  }

  .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-primary {
    background: var(--accent);
    color: white;
  }

  .btn-primary:hover {
    opacity: 0.9;
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

  /* 卡片列表区域 */
  .cards-section {
    margin-bottom: 20px;
  }

  .cards-section h2 {
    font-size: 16px;
    color: var(--text-muted);
    margin-bottom: 12px;
  }

  .cards-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
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
  .main-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 24px;
  }

  .config-panel h2 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 20px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-row {
    display: flex;
    gap: 12px;
  }

  .form-group.half {
    flex: 1;
  }

  .form-group label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 6px;
  }

  .form-group .info-label {
    color: var(--text);
    font-weight: 600;
    background: var(--bg);
    padding: 8px 12px;
    border-radius: 6px;
    text-align: center;
  }

  .form-group input[type="number"],
  .form-group select {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
    font-family: 'Maple Mono Normal NF CN', monospace;
    transition: border-color 0.2s;
  }

  .form-group input:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .form-group select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .profile-colors {
    display: flex;
    gap: 6px;
    margin-top: 8px;
    flex-wrap: wrap;
  }

  .color-dot {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 1px solid var(--line);
  }

  .profile-description {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
    margin-bottom: 0;
  }

  .form-group input[type="range"] {
    width: 100%;
    margin-top: 8px;
    margin-bottom: 4px;
  }

  .range-labels {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-muted);
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

  /* 进度详情 */
  .progress-detail {
    margin-top: 16px;
    padding: 12px;
    background: var(--bg);
    border-radius: 8px;
    border: 1px solid var(--line);
  }

  .progress-bar {
    width: 100%;
    height: 6px;
    background: var(--line);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 8px;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .progress-info .stage {
    font-size: 13px;
    color: var(--text);
    font-weight: 500;
  }

  .progress-info .count {
    font-size: 12px;
    color: var(--text-muted);
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  .time-info {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-muted);
  }

  /* 主面板 */
  .main-panel {
    display: flex;
    flex-direction: column;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--line);
  }

  .panel-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
  }

  .panel-subtitle {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  .grid-wrapper {
    display: flex;
    justify-content: center;
    flex: 1;
  }

  .empty-preview {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: var(--text-muted);
    text-align: center;
    flex: 1;
  }

  .empty-preview i {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .empty-preview span {
    font-size: 16px;
    font-weight: 500;
  }
</style>
