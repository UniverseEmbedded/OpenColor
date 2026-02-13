<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';

  onMount(() => {
    navigationStore.setCurrentNav('settings/debug');
  });

  const bridge = getTauriBridge();

  // @ts-ignore - Vite 环境变量
  const isDev = import.meta.env.DEV;
  const isBrowser = !bridge.hasTauri;
  const isDesktop = bridge.hasTauri;

  // API 连接测试状态
  let apiStatus = $state<'idle' | 'testing' | 'success' | 'error'>('idle');
  let apiResults = $state<{ name: string; status: 'pending' | 'success' | 'error'; message?: string }[]>([
    { name: 'Web → Rust', status: 'pending' },
    { name: 'Rust → Python', status: 'pending' },
    { name: 'Rust → CPP → GPU', status: 'pending' },
  ]);

  // 窗口大小提示
  let showSizeHint = $state(true);

  // 错误信息
  let error = $state<string | null>(null);

  // 测试 API 连接
  async function testApiConnection() {
    apiStatus = 'testing';
    apiResults = apiResults.map(r => ({ ...r, status: 'pending' }));

    // 测试 Web → Rust
    try {
      if (bridge.hasTauri) {
        await bridge.invoke<string>('ping', { message: 'test' });
        apiResults[0] = { name: 'Web → Rust', status: 'success', message: 'Connected' };
      } else {
        apiResults[0] = { name: 'Web → Rust', status: 'error', message: 'Not in Tauri' };
      }
    } catch (e) {
      apiResults[0] = { name: 'Web → Rust', status: 'error', message: String(e) };
    }

    // 测试 Rust → Python
    try {
      if (bridge.hasTauri) {
        const result = await bridge.invoke<{ result?: string }>('engine_request', {
          method: 'ping',
          params: {}
        });
        apiResults[1] = {
          name: 'Rust → Python',
          status: 'success',
          message: result.result || 'Connected'
        };
      } else {
        apiResults[1] = {
          name: 'Rust → Python',
          status: 'error',
          message: 'Not in Tauri'
        };
      }
    } catch (e) {
      apiResults[1] = {
        name: 'Rust → Python',
        status: 'error',
        message: String(e)
      };
    }

    // 测试 Rust → CPP → GPU
    try {
      if (bridge.hasTauri) {
        const result = await bridge.invoke<{
          available: boolean;
          device_count: number;
          device_names?: string[];
          message?: string;
        }>('check_gpu');
        if (result.available) {
          apiResults[2] = {
            name: 'Rust → CPP → GPU',
            status: 'success',
            message: `${result.device_count} GPU(s): ${result.device_names?.join(', ') || 'Vulkan Compute Ready'}`
          };
        } else {
          apiResults[2] = {
            name: 'Rust → CPP → GPU',
            status: 'error',
            message: result.message || 'No GPU detected'
          };
        }
      } else {
        apiResults[2] = {
          name: 'Rust → CPP → GPU',
          status: 'error',
          message: 'Not in Tauri'
        };
      }
    } catch (e) {
      apiResults[2] = {
        name: 'Rust → CPP → GPU',
        status: 'error',
        message: String(e)
      };
    }

    // 更新整体状态
    const hasError = apiResults.some(r => r.status === 'error');
    apiStatus = hasError ? 'error' : 'success';
  }

  // 触发系统通知
  async function triggerNotification() {
    if (!bridge.hasTauri) {
      alert('系统通知仅在桌面应用中可用');
      return;
    }
    try {
      // 动态导入通知插件
      const { isPermissionGranted, requestPermission, sendNotification } = await import('@tauri-apps/plugin-notification');

      // 检查并请求权限
      let permissionGranted = await isPermissionGranted();
      if (!permissionGranted) {
        const permission = await requestPermission();
        permissionGranted = permission === 'granted';
      }

      if (permissionGranted) {
        sendNotification({
          title: 'OpenColor',
          body: '这是一条测试通知',
        });
      } else {
        error = '通知权限被拒绝';
      }
    } catch (e) {
      error = '发送通知失败: ' + String(e);
      console.error('发送通知失败:', e);
    }
  }

  // 重启Python引擎
  let restartStatus = $state<'idle' | 'restarting' | 'success' | 'error'>('idle');

  async function restartEngine() {
    if (!bridge.hasTauri) {
      alert('引擎重启仅在桌面应用中可用');
      return;
    }

    restartStatus = 'restarting';
    try {
      await bridge.invoke('engine_restart');
      restartStatus = 'success';
      // 3秒后重置状态
      setTimeout(() => {
        restartStatus = 'idle';
      }, 3000);
    } catch (e) {
      restartStatus = 'error';
      error = '重启引擎失败: ' + String(e);
      console.error('重启引擎失败:', e);
      // 3秒后重置状态
      setTimeout(() => {
        restartStatus = 'idle';
      }, 3000);
    }
  }

  // 清除错误
  function clearError() {
    error = null;
  }

  // 关闭窗口大小提示
  function closeSizeHint() {
    showSizeHint = false;
  }

  // 触发加载覆盖层测试（显示3秒）
  function triggerLoadingOverlay() {
    // 使用全局函数显示加载层
    if ((window as any).showLoadingOverlay) {
      (window as any).showLoadingOverlay();
      setTimeout(() => {
        if ((window as any).hideLoadingOverlay) {
          (window as any).hideLoadingOverlay();
        }
      }, 3000);
    }
  }
</script>

<div class="settings-page">
  <h1>{$_('settings.debug.title')}</h1>

  {#if error}
    <div class="error-message">
      <i class="ti ti-alert-circle"></i>
      <span>{error}</span>
      <button onclick={clearError} type="button" aria-label={$_('app.close')}>
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}

  <!-- 窗口大小提示 -->
  {#if showSizeHint}
    <div class="size-hint">
      <div class="size-hint-content">
        <i class="ti ti-ruler-measure"></i>
        <span>Window: {typeof window !== 'undefined' ? `${window.innerWidth}×${window.innerHeight}` : '-'}</span>
      </div>
      <button class="btn-icon" onclick={closeSizeHint} aria-label={$_('app.close')}>
        <i class="ti ti-x"></i>
      </button>
    </div>
  {/if}

  <!-- 模式信息 -->
  <div class="settings-section">
    <h2>{$_('settings.debug.modeInfo')}</h2>
    <div class="mode-grid">
      <div class="mode-item">
        <span class="mode-label">{$_('settings.debug.buildMode')}</span>
        <span class="mode-value" class:dev={isDev} class:prod={!isDev}>
          {isDev ? 'Development' : 'Production'}
        </span>
      </div>
      <div class="mode-item">
        <span class="mode-label">{$_('settings.debug.runtimeMode')}</span>
        <span class="mode-value" class:browser={isBrowser} class:desktop={isDesktop}>
          {isBrowser ? 'Browser' : 'Desktop'}
        </span>
      </div>
      <div class="mode-item">
        <span class="mode-label">{$_('settings.debug.tauriAvailable')}</span>
        <span class="mode-value" class:yes={bridge.hasTauri} class:no={!bridge.hasTauri}>
          {bridge.hasTauri ? 'Yes' : 'No'}
        </span>
      </div>
    </div>
  </div>

  <!-- API 连接测试 -->
  <div class="settings-section">
    <h2>{$_('settings.debug.apiTest')}</h2>
    <div class="api-test-panel">
      {#each apiResults as result}
        <div class="api-test-item" class:success={result.status === 'success'} class:error={result.status === 'error'}>
          <div class="api-test-name">{result.name}</div>
          <div class="api-test-status">
            {#if result.status === 'pending'}
              <i class="ti ti-loader-2 spinning"></i>
            {:else if result.status === 'success'}
              <i class="ti ti-check"></i>
            {:else if result.status === 'error'}
              <i class="ti ti-x"></i>
            {/if}
            <span>{result.message || result.status}</span>
          </div>
        </div>
      {/each}
      <button class="btn-primary" onclick={testApiConnection} disabled={apiStatus === 'testing'}>
        {#if apiStatus === 'testing'}
          <i class="ti ti-loader-2 spinning"></i>
          {$_('settings.debug.testing')}
        {:else}
          <i class="ti ti-refresh"></i>
          {$_('settings.debug.testApi')}
        {/if}
      </button>
    </div>
  </div>

  <!-- 系统通知测试 -->
  <div class="settings-section">
    <h2>{$_('settings.debug.notification')}</h2>
    <p class="section-desc">{$_('settings.debug.notificationDesc')}</p>
    <button class="btn-primary" onclick={triggerNotification}>
      <i class="ti ti-bell"></i>
      {$_('settings.debug.sendNotification')}
    </button>
  </div>

  <!-- 引擎重启 -->
  <div class="settings-section">
    <h2>{$_('settings.debug.engineManagement')}</h2>
    <p class="section-desc">{$_('settings.debug.engineRestartDesc')}</p>
    <button
      class="btn-primary"
      onclick={restartEngine}
      disabled={restartStatus === 'restarting'}
      class:success={restartStatus === 'success'}
      class:error={restartStatus === 'error'}
    >
      {#if restartStatus === 'restarting'}
        <i class="ti ti-loader-2 spinning"></i>
        {$_('settings.debug.restarting')}
      {:else if restartStatus === 'success'}
        <i class="ti ti-check"></i>
        {$_('settings.debug.restartSuccess')}
      {:else if restartStatus === 'error'}
        <i class="ti ti-x"></i>
        {$_('settings.debug.restartFailed')}
      {:else}
        <i class="ti ti-refresh"></i>
        {$_('settings.debug.restartEngine')}
      {/if}
    </button>
  </div>

  <!-- 加载覆盖层测试 -->
  <div class="settings-section">
    <h2>{$_('settings.debug.loadingOverlay')}</h2>
    <p class="section-desc">{$_('settings.debug.loadingOverlayDesc')}</p>
    <button class="btn-primary" onclick={triggerLoadingOverlay}>
      <i class="ti ti-loader"></i>
      {$_('settings.debug.triggerLoadingOverlay')}
    </button>
  </div>
</div>

<style>
  .settings-page {
    max-width: 600px;
  }

  h1 {
    font-size: 24px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 32px;
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

  .section-desc {
    font-size: 14px;
    color: var(--text-muted);
    margin-bottom: 16px;
  }

  /* 窗口大小提示 */
  .size-hint {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    margin-bottom: 24px;
  }

  .size-hint-content {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    color: var(--text);
  }

  .size-hint-content i {
    color: var(--accent);
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

  /* 模式信息网格 */
  .mode-grid {
    display: grid;
    gap: 12px;
  }

  .mode-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
  }

  .mode-label {
    font-size: 14px;
    color: var(--text-muted);
  }

  .mode-value {
    font-size: 13px;
    padding: 4px 10px;
    border-radius: 4px;
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  .mode-value.dev {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .mode-value.prod {
    background: rgba(59, 130, 246, 0.1);
    color: var(--accent2);
  }

  .mode-value.browser {
    background: rgba(251, 97, 4, 0.1);
    color: var(--accent);
  }

  .mode-value.desktop {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .mode-value.yes {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .mode-value.no {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  /* API 测试面板 */
  .api-test-panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px;
  }

  .api-test-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid var(--line);
  }

  .api-test-item:last-of-type {
    border-bottom: none;
    margin-bottom: 16px;
  }

  .api-test-name {
    font-size: 14px;
    color: var(--text);
  }

  .api-test-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .api-test-item.success .api-test-status {
    color: var(--success);
  }

  .api-test-item.error .api-test-status {
    color: var(--error);
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* 按钮 */
  .btn-primary {
    width: 100%;
    padding: 12px 20px;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary.success {
    background: var(--success);
  }

  .btn-primary.error {
    background: var(--error);
  }
</style>
