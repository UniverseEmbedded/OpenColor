<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { photoWarpStore, sampleExtractStore } from '$lib/stores/calibrate.svelte';
  import { workspaceStore } from '$lib/stores/workspace.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';
  import WarpCanvas from '$lib/components/canvas/WarpCanvas.svelte';
  import type { Point, BoardItem } from '$lib/types';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('calibrate/photo-warp');
    loadBoardSpecs();
  });

  // 本地状态
  let isProcessing = $state(false);
  let cornerPoints = $state<Point[]>([]);
  let rotationCount = $state(0);
  let warpedImage = $state<string | null>(null);
  let overlayImage = $state<string | null>(null);
  let error = $state<string | null>(null);

  // 文件选择
  let selectedPhoto = $state<string | null>(null);
  let selectedSpec = $state<string | null>(null);
  let availableSpecs = $state<BoardItem[]>([]);

  // 样本提取结果
  let datasetPath = $state<string | null>(null);
  let cellCount = $state(0);
  let enabledCellCount = $state(0);

  // 订阅 store
  $effect(() => {
    const unsubscribe = photoWarpStore.subscribe((value) => {
      isProcessing = value.isProcessing;
      cornerPoints = value.cornerPoints;
      rotationCount = value.rotationCount;
      warpedImage = value.warpedImage;
      overlayImage = value.overlayImage;
      error = value.error;
      selectedPhoto = value.selectedPhoto;
      selectedSpec = value.selectedSpec;
    });
    return unsubscribe;
  });

  // 加载校准板规格列表
  async function loadBoardSpecs() {
    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) return;

    try {
      const result = await bridge.invoke<{ boards: BoardItem[] }>('library_list_boards', {
        workspacePath: workspace.path
      });
      availableSpecs = result.boards.filter(b => b.path.endsWith('_board_spec.json'));
    } catch (e) {
      console.error('加载规格列表失败:', e);
    }
  }

  // 选择照片
  async function selectPhoto() {
    try {
      const result = await bridge.invoke<string[] | null>('file_select_dialog', {
        title: '选择校准照片',
        multiple: false,
        filters: [
          { name: '图片文件', extensions: ['png', 'jpg', 'jpeg', 'bmp'] }
        ]
      });

      if (result && result.length > 0) {
        photoWarpStore.selectPhoto(result[0]);
      }
    } catch (e) {
      console.error('选择照片失败:', e);
    }
  }

  // 执行透视校正
  async function warpPhoto() {
    if (!selectedPhoto || !selectedSpec || cornerPoints.length !== 4) {
      error = '请完成所有必要选择（照片、规格文件、4个角点）';
      return;
    }

    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) {
      error = '请先选择工作区';
      return;
    }

    const outputDir = `${workspace.path}\\02_photo_warp`;

    try {
      const result = await photoWarpStore.warpPhoto({
        specPath: selectedSpec,
        photoPath: selectedPhoto,
        cornerPoints,
        rotationCount,
        outputDir
      });

      // 自动执行样本提取
      await extractSamples(result.warpedPath, result.warpParamsPath);
    } catch (e) {
      console.error('透视校正失败:', e);
    }
  }

  // 执行样本提取
  async function extractSamples(warpedPath: string, warpParamsPath: string) {
    if (!selectedSpec) return;

    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) return;

    const outputDir = `${workspace.path}\\03_sample_build`;

    try {
      const result = await sampleExtractStore.extractSamples({
        warpedPath,
        specPath: selectedSpec,
        warpParamsPath,
        outputDir
      });

      datasetPath = result.datasetPath;
      cellCount = result.cellCount;
      enabledCellCount = result.enabledCellCount;
    } catch (e) {
      console.error('样本提取失败:', e);
    }
  }

  // 旋转
  function rotate(clockwise: boolean) {
    photoWarpStore.rotate(clockwise);
  }

  // 清空角点
  function clearPoints() {
    photoWarpStore.clearCornerPoints();
  }

  // 处理角点变化
  function handlePointsChange(points: Point[]) {
    photoWarpStore.setCornerPoints(points);
  }

  // 获取照片URL
  function getPhotoUrl(): string | null {
    if (!selectedPhoto) return null;
    // 在Tauri环境中，需要将本地路径转换为可访问的URL
    return selectedPhoto;
  }
</script>

<div class="photo-warp-page">
  <h1>{$_('nav.calibrate.photoWarp')}</h1>
  <p class="description">手动4点透视校正色盘照片，提取颜色样本</p>

  {#if error}
    <div class="error-message">
      <i class="ti ti-alert-circle"></i>
      <span>{error}</span>
      <button onclick={() => photoWarpStore.clearError()} type="button" aria-label="关闭错误">
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}

  <div class="content-grid">
    <!-- 左侧面板 -->
    <div class="left-panel">
      <!-- 文件选择 -->
      <div class="section">
        <h2>文件选择</h2>

        <div class="form-group">
          <label>校准板规格</label>
          <select
            value={selectedSpec || ''}
            onchange={(e) => photoWarpStore.selectSpec(e.currentTarget.value)}
          >
            <option value="">请选择规格文件</option>
            {#each availableSpecs as spec}
              <option value={spec.path}>{spec.name}</option>
            {/each}
          </select>
        </div>

        <div class="form-group">
          <label>照片</label>
          <button class="btn-secondary select-btn" onclick={selectPhoto}>
            <i class="ti ti-photo"></i>
            {selectedPhoto ? '更换照片' : '选择照片'}
          </button>
          {#if selectedPhoto}
            <span class="file-path">{selectedPhoto}</span>
          {/if}
        </div>
      </div>

      <!-- 角点控制 -->
      <div class="section">
        <h2>角点控制</h2>

        <div class="rotation-controls">
          <button class="btn-secondary" onclick={() => rotate(false)}>
            <i class="ti ti-rotate-counterclockwise"></i>
            逆时针 90°
          </button>
          <span class="rotation-display">{rotationCount * 90}°</span>
          <button class="btn-secondary" onclick={() => rotate(true)}>
            <i class="ti ti-rotate-clockwise"></i>
            顺时针 90°
          </button>
        </div>

        <button class="btn-secondary" onclick={clearPoints}>
          <i class="ti ti-trash"></i>
          清空角点
        </button>

        <button
          class="btn-primary warp-btn"
          onclick={warpPhoto}
          disabled={isProcessing || cornerPoints.length !== 4 || !selectedPhoto || !selectedSpec}
        >
          {#if isProcessing}
            <i class="ti ti-loader-2 spinning"></i>
            处理中...
          {:else}
            <i class="ti ti-transform"></i>
            执行校正
          {/if}
        </button>
      </div>

      <!-- 样本提取结果 -->
      {#if datasetPath}
        <div class="section result-section">
          <h2>样本提取结果</h2>
          <div class="result-stats">
            <div class="stat">
              <span class="label">总格子数</span>
              <span class="value">{cellCount}</span>
            </div>
            <div class="stat">
              <span class="label">启用格子</span>
              <span class="value">{enabledCellCount}</span>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- 右侧画布 -->
    <div class="right-panel">
      <div class="canvas-section">
        <h2>照片校正</h2>
        <WarpCanvas
          imageUrl={getPhotoUrl()}
          cornerPoints={cornerPoints}
          onPointsChange={handlePointsChange}
          rows={17}
          cols={17}
        />
      </div>

      {#if warpedImage || overlayImage}
        <div class="preview-section">
          <h2>校正结果</h2>
          <div class="preview-grid">
            {#if warpedImage}
              <div class="preview-item">
                <span class="label">校正后图像</span>
                <img src={warpedImage} alt="校正后" />
              </div>
            {/if}
            {#if overlayImage}
              <div class="preview-item">
                <span class="label">网格叠加</span>
                <img src={overlayImage} alt="网格叠加" />
              </div>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .photo-warp-page {
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
    grid-template-columns: 320px 1fr;
    gap: 24px;
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }

  .left-panel {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .section {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
  }

  .section h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 16px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 6px;
  }

  .form-group select {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
  }

  .file-path {
    display: block;
    margin-top: 8px;
    font-size: 11px;
    color: var(--text-muted);
    font-family: 'Maple Mono Normal NF CN', monospace;
    word-break: break-all;
  }

  .select-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .rotation-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .rotation-display {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    min-width: 50px;
    text-align: center;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 16px;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary:hover {
    background: var(--line);
  }

  .warp-btn {
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
    margin-top: 12px;
  }

  .warp-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .warp-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .result-section {
    background: rgba(0, 89, 132, 0.1);
    border-color: var(--accent);
  }

  .result-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px;
    background: var(--panel);
    border-radius: 8px;
  }

  .stat .label {
    font-size: 11px;
    color: var(--text-muted);
    margin-bottom: 4px;
  }

  .stat .value {
    font-size: 20px;
    font-weight: 600;
    color: var(--accent);
  }

  .right-panel {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .canvas-section,
  .preview-section {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
  }

  .canvas-section h2,
  .preview-section h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 16px;
  }

  .preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
  }

  .preview-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .preview-item .label {
    font-size: 12px;
    color: var(--text-muted);
  }

  .preview-item img {
    width: 100%;
    border-radius: 8px;
    border: 1px solid var(--line);
  }
</style>
