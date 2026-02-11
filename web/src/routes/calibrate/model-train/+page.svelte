<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { modelTrainStore } from '$lib/stores/calibrate.svelte';
  import { workspaceStore } from '$lib/stores/workspace.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';
  import type { TrainingConfig, ModelItem } from '$lib/types';

  const bridge = getTauriBridge();

  onMount(() => {
    navigationStore.setCurrentNav('calibrate/model-train');
    modelTrainStore.setupEventListeners();
    
    // 加载模型列表
    const workspace = workspaceStore.currentWorkspace;
    if (workspace) {
      modelTrainStore.loadModels(workspace.path);
    }
  });

  // 本地状态
  let isTraining = $state(false);
  // @ts-expect-error jobId is stored but not directly used in template
  let jobId = $state<string | null>(null);
  let progress = $state<{ epoch: number; totalEpochs: number; loss: number; avgDeltaE: number } | null>(null);
  let logs = $state<string[]>([]);
  let trainedModels = $state<ModelItem[]>([]);
  let error = $state<string | null>(null);

  // 训练配置
  let config = $state<TrainingConfig>({
    datasetPaths: [],
    materialGroupId: 'default',
    layerHeightMm: 0.2,
    opticalModel: 'rts',
    useVulkan: true,
    gprParams: {
      kernel: 'rbf',
      lengthScale: 1.0,
      noiseLevel: 0.1
    }
  });

  // 订阅 store
  $effect(() => {
    const unsubscribe = modelTrainStore.subscribe((value) => {
      isTraining = value.isTraining;
      jobId = value.jobId;
      progress = value.progress;
      logs = value.logs;
      trainedModels = value.trainedModels;
      error = value.error;
    });
    return unsubscribe;
  });

  // 开始训练
  async function startTraining() {
    const workspace = workspaceStore.currentWorkspace;
    if (!workspace) {
      error = '请先选择工作区';
      return;
    }

    const outputDir = `${workspace.path}\\04_model_train`;

    try {
      await modelTrainStore.startTraining({
        trainingConfig: config,
        outputDir
      });
    } catch (e) {
      console.error('启动训练失败:', e);
    }
  }

  // 取消训练
  async function cancelTraining() {
    try {
      await modelTrainStore.cancelTraining();
    } catch (e) {
      console.error('取消训练失败:', e);
    }
  }

  // 选择数据集
  async function selectDatasets() {
    try {
      const result = await bridge.invoke<string[] | null>('file_select_dialog', {
        title: '选择数据集文件',
        multiple: true,
        filters: [
          { name: 'JSON文件', extensions: ['json'] }
        ]
      });

      if (result && result.length > 0) {
        config = { ...config, datasetPaths: result };
      }
    } catch (e) {
      console.error('选择数据集失败:', e);
    }
  }

  // 格式化日期
  function formatDate(timestamp: string): string {
    return new Date(timestamp).toLocaleString('zh-CN');
  }

  // 清空日志
  function clearLogs() {
    modelTrainStore.clearLogs();
  }
</script>

<div class="model-train-page">
  <h1>{$_('nav.calibrate.modelTrain')}</h1>
  <p class="description">使用RT光学模型+GPR训练颜色预测模型</p>

  {#if error}
    <div class="error-message">
      <i class="ti ti-alert-circle"></i>
      <span>{error}</span>
      <button onclick={() => modelTrainStore.clearError()} type="button" aria-label="关闭错误">
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}

  <div class="content-grid">
    <!-- 配置面板 -->
    <div class="config-panel">
      <h2>训练配置</h2>

      <!-- 数据集选择 -->
      <div class="form-group">
        <label>数据集</label>
        <button class="btn-secondary select-btn" onclick={selectDatasets}>
          <i class="ti ti-file-upload"></i>
          选择数据集
        </button>
        {#if config.datasetPaths.length > 0}
          <span class="file-count">已选择 {config.datasetPaths.length} 个文件</span>
        {/if}
      </div>

      <!-- 材料组 -->
      <div class="form-group">
        <label for="materialGroup">材料组</label>
        <input
          id="materialGroup"
          type="text"
          bind:value={config.materialGroupId}
          placeholder="default"
        />
      </div>

      <!-- 层高 -->
      <div class="form-group">
        <label for="layerHeight">层高 (mm)</label>
        <input
          id="layerHeight"
          type="number"
          bind:value={config.layerHeightMm}
          min="0.1"
          max="0.5"
          step="0.05"
        />
      </div>

      <!-- 光学模型 -->
      <div class="form-group">
        <label for="opticalModel">光学模型</label>
        <select id="opticalModel" bind:value={config.opticalModel}>
          <option value="rts">RTS (推荐)</option>
          <option value="four_flux">Four-Flux</option>
          <option value="tmm">TMM</option>
        </select>
      </div>

      <!-- GPU加速 -->
      <div class="form-group checkbox">
        <label>
          <input
            type="checkbox"
            bind:checked={config.useVulkan}
          />
          使用 Vulkan GPU加速
        </label>
      </div>

      <!-- GPR参数 -->
      <div class="form-group">
        <label>GPR核函数</label>
        <select bind:value={config.gprParams!.kernel}>
          <option value="rbf">RBF</option>
          <option value="matern">Matérn</option>
          <option value="rational_quadratic">Rational Quadratic</option>
        </select>
      </div>

      <!-- 训练控制按钮 -->
      <div class="train-controls">
        {#if isTraining}
          <button class="btn-danger" onclick={cancelTraining}>
            <i class="ti ti-player-stop"></i>
            停止训练
          </button>
        {:else}
          <button
            class="btn-primary train-btn"
            onclick={startTraining}
            disabled={config.datasetPaths.length === 0}
          >
            <i class="ti ti-player-play"></i>
            开始训练
          </button>
        {/if}
      </div>

      <!-- 进度显示 -->
      {#if isTraining && progress}
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" style="width: {(progress.epoch / progress.totalEpochs) * 100}%"></div>
          </div>
          <div class="progress-stats">
            <span>轮次: {progress.epoch}/{progress.totalEpochs}</span>
            <span>损失: {progress.loss.toFixed(4)}</span>
            <span>ΔE: {progress.avgDeltaE.toFixed(2)}</span>
          </div>
        </div>
      {/if}
    </div>

    <!-- 右侧面板 -->
    <div class="right-panel">
      <!-- 日志面板 -->
      <div class="logs-panel">
        <div class="logs-header">
          <h2>训练日志</h2>
          <button class="btn-icon" onclick={clearLogs} title="清空日志">
            <i class="ti ti-trash"></i>
          </button>
        </div>
        <div class="logs-content">
          {#if logs.length === 0}
            <div class="empty-logs">等待训练开始...</div>
          {:else}
            {#each logs as log}
              <div class="log-line">{log}</div>
            {/each}
          {/if}
        </div>
      </div>

      <!-- 模型列表 -->
      <div class="models-panel">
        <h2>训练好的模型</h2>
        {#if trainedModels.length === 0}
          <div class="empty-state">
            <i class="ti ti-brain"></i>
            <span>尚未训练任何模型</span>
          </div>
        {:else}
          <div class="model-list">
            {#each trainedModels as model}
              <div class="model-item">
                <div class="model-info">
                  <i class="ti ti-brain"></i>
                  <div class="info-text">
                    <span class="name">{model.name}</span>
                    <span class="details">{model.materialGroup} · {model.layerHeightMm}mm</span>
                    <span class="metrics">ΔE: {model.avgDeltaE.toFixed(2)}</span>
                  </div>
                </div>
                <span class="date">{formatDate(model.trainedAt)}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .model-train-page {
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
    grid-template-columns: 360px 1fr;
    gap: 24px;
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }

  .config-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 24px;
    height: fit-content;
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

  .form-group label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    margin-bottom: 6px;
  }

  .form-group input,
  .form-group select {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
  }

  .form-group.checkbox label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: var(--text);
  }

  .form-group.checkbox input[type="checkbox"] {
    width: auto;
    accent-color: var(--accent);
  }

  .select-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .file-count {
    display: block;
    margin-top: 8px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .train-controls {
    margin-top: 24px;
  }

  .btn-primary,
  .btn-secondary,
  .btn-danger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
    width: 100%;
  }

  .btn-primary {
    background: var(--accent);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    color: var(--text);
  }

  .btn-secondary:hover {
    background: var(--line);
  }

  .btn-danger {
    background: var(--error);
    color: white;
  }

  .btn-danger:hover {
    opacity: 0.9;
  }

  .progress-section {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
  }

  .progress-bar {
    height: 8px;
    background: var(--bg);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.3s ease;
  }

  .progress-stats {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .right-panel {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .logs-panel,
  .models-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
  }

  .logs-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .logs-header h2 {
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

  .logs-content {
    height: 300px;
    overflow-y: auto;
    background: var(--bg);
    border-radius: 8px;
    padding: 12px;
    font-family: 'Maple Mono Normal NF CN', monospace;
    font-size: 12px;
    line-height: 1.6;
  }

  .log-line {
    color: var(--text-muted);
    padding: 2px 0;
    border-bottom: 1px solid var(--line);
  }

  .log-line:last-child {
    border-bottom: none;
  }

  .empty-logs {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
  }

  .models-panel h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 16px;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px;
    color: var(--text-muted);
    text-align: center;
  }

  .empty-state i {
    font-size: 32px;
    margin-bottom: 12px;
    opacity: 0.5;
  }

  .model-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .model-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
  }

  .model-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .model-info > i {
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

  .metrics {
    font-size: 12px;
    color: var(--accent);
    font-weight: 500;
  }

  .date {
    font-size: 11px;
    color: var(--text-muted);
  }
</style>
