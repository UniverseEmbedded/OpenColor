<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { settingsStore } from '$lib/stores/settings.svelte';
  import { getTauriBridge } from '$lib/tauri/bridge';
  import { onMount } from 'svelte';

  onMount(() => {
    navigationStore.setCurrentNav('settings/engine');
  });

  const bridge = getTauriBridge();

  // 本地状态
  let appSettings = $state(settingsStore.appSettings);

  // 订阅 settings store
  $effect(() => {
    const unsubscribe = settingsStore.subscribe((value) => {
      appSettings = value.appSettings;
    });
    return unsubscribe;
  });

  // API测试状态
  let testStatus = $state({
    webToRust: 'idle' as 'idle' | 'success' | 'error',
    rustToPython: 'idle' as 'idle' | 'success' | 'error',
    pythonResponse: '',
  });

  let isTesting = $state(false);

  // 运行API测试
  async function runTest() {
    isTesting = true;
    testStatus = {
      webToRust: 'idle',
      rustToPython: 'idle',
      pythonResponse: '',
    };

    try {
      // 测试1: Web → Rust
      console.log('[API测试] 测试 Web → Rust...');
      if (bridge.hasTauri) {
        testStatus.webToRust = 'success';

        // 测试2: Rust → Python (通过invoke调用Rust命令)
        console.log('[API测试] 测试 Rust → Python...');
        try {
          // 调用Rust的ping命令
          const result = await bridge.invoke<string>('ping', { message: 'Hello from Web' });
          testStatus.rustToPython = 'success';
          testStatus.pythonResponse = result;
        } catch (e) {
          testStatus.rustToPython = 'error';
          testStatus.pythonResponse = String(e);
        }
      } else {
        testStatus.webToRust = 'error';
        testStatus.pythonResponse = '不在Tauri环境中';
      }
    } catch (e) {
      testStatus.webToRust = 'error';
      testStatus.pythonResponse = String(e);
    } finally {
      isTesting = false;
    }
  }
</script>

<div class="settings-page">
  <h1>{$_('settings.engine.title')}</h1>

  {#if !bridge.hasTauri}
    <!-- Dev 模式提示 -->
    <div class="dev-mode-banner">
      <i class="ti ti-device-desktop-code"></i>
      <span>开发模式 - 引擎功能仅在 Tauri 环境中可用</span>
    </div>
  {/if}

  <div class="settings-section">
    <h2>{$_('settings.engine.path')}</h2>
    {#if bridge.hasTauri}
      <!-- Prod 模式：显示输入框和浏览按钮 -->
      <div class="input-group">
        <input
          type="text"
          class="engine-path-input"
          value={appSettings.enginePath}
          placeholder="auto"
          readonly
        />
        <button class="btn-secondary">浏览</button>
      </div>
    {:else}
      <!-- Dev 模式：显示占位符 -->
      <div class="dev-placeholder">
        <i class="ti ti-info-circle"></i>
        <span>引擎路径配置在桌面应用中可用</span>
      </div>
    {/if}
  </div>

  <div class="settings-section">
    <h2>{$_('settings.engine.gpu')}</h2>
    <label class="toggle" class:disabled={!bridge.hasTauri}>
      <input
        type="checkbox"
        checked={appSettings.gpuAcceleration}
        onchange={(e) => settingsStore.updateAppSettings({ gpuAcceleration: e.currentTarget.checked })}
        disabled={!bridge.hasTauri}
      />
      <span class="toggle-slider"></span>
      <span class="toggle-label">{$_('settings.engine.gpuAcceleration')}</span>
    </label>
  </div>

  <!-- API连通性测试 -->
  <div class="settings-section">
    <h2>{$_('api.test.title')}</h2>

    <div class="api-test">
      <div class="test-item">
        <span class="test-label">{$_('api.test.webToRust')}</span>
        <span class="test-status" class:success={testStatus.webToRust === 'success'} class:error={testStatus.webToRust === 'error'}>
          {#if testStatus.webToRust === 'idle'}
            <i class="ti ti-circle-dashed"></i>
          {:else if testStatus.webToRust === 'success'}
            <i class="ti ti-check"></i> {$_('api.test.success')}
          {:else}
            <i class="ti ti-x"></i> {$_('api.test.failed')}
          {/if}
        </span>
      </div>

      <div class="test-item">
        <span class="test-label">{$_('api.test.rustToPython')}</span>
        <span class="test-status" class:success={testStatus.rustToPython === 'success'} class:error={testStatus.rustToPython === 'error'}>
          {#if testStatus.rustToPython === 'idle'}
            <i class="ti ti-circle-dashed"></i>
          {:else if testStatus.rustToPython === 'success'}
            <i class="ti ti-check"></i> {$_('api.test.success')}
          {:else}
            <i class="ti ti-x"></i> {$_('api.test.failed')}
          {/if}
        </span>
      </div>

      {#if testStatus.pythonResponse}
        <div class="test-response">
          <span class="test-label">{$_('api.test.pythonResponse')}:</span>
          <code>{testStatus.pythonResponse}</code>
        </div>
      {/if}

      <button class="btn-primary" onclick={runTest} disabled={isTesting}>
        {#if isTesting}
          <i class="ti ti-loader-2 spinning"></i> 测试中...
        {:else}
          <i class="ti ti-player-play"></i> {$_('api.test.run')}
        {/if}
      </button>
    </div>
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

  /* Dev 模式横幅 */
  .dev-mode-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(251, 97, 4, 0.1);
    border: 1px solid var(--accent);
    border-radius: 8px;
    color: var(--accent);
    margin-bottom: 24px;
    font-size: 14px;
  }

  .dev-mode-banner i {
    font-size: 20px;
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

  .input-group {
    display: flex;
    gap: 12px;
  }

  /* 引擎路径输入框 - 使用 Maple Mono 字体 */
  .engine-path-input {
    flex: 1;
    padding: 10px 16px;
    border-radius: 8px;
    background: var(--panel);
    border: 1px solid var(--line);
    color: var(--text);
    font-size: 14px;
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  /* Dev 模式占位符 */
  .dev-placeholder {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: var(--panel);
    border: 1px dashed var(--line);
    border-radius: 8px;
    color: var(--text-muted);
    font-size: 14px;
  }

  .dev-placeholder i {
    font-size: 20px;
    color: var(--accent);
  }

  .btn-secondary {
    padding: 10px 20px;
    border-radius: 8px;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    color: var(--text);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary:hover {
    background: var(--line);
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 8px;
    background: var(--accent);
    border: none;
    color: white;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 16px;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Toggle开关 */
  .toggle {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
  }

  .toggle.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .toggle input {
    display: none;
  }

  .toggle-slider {
    width: 48px;
    height: 24px;
    background: var(--line);
    border-radius: 12px;
    position: relative;
    transition: all 0.2s;
  }

  .toggle-slider::after {
    content: '';
    position: absolute;
    width: 20px;
    height: 20px;
    background: white;
    border-radius: 50%;
    top: 2px;
    left: 2px;
    transition: all 0.2s;
  }

  .toggle input:checked + .toggle-slider {
    background: var(--accent);
  }

  .toggle input:checked + .toggle-slider::after {
    left: 26px;
  }

  .toggle input:disabled + .toggle-slider {
    background: var(--line);
    opacity: 0.5;
  }

  .toggle-label {
    font-size: 14px;
    color: var(--text);
  }

  /* API测试 */
  .api-test {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 20px;
  }

  .test-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid var(--line);
  }

  .test-item:last-of-type {
    border-bottom: none;
  }

  .test-label {
    font-size: 14px;
    color: var(--text);
  }

  .test-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    color: var(--text-muted);
  }

  .test-status.success {
    color: var(--success);
  }

  .test-status.error {
    color: var(--error);
  }

  .test-response {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--line);
  }

  .test-response code {
    display: block;
    margin-top: 8px;
    padding: 12px;
    background: var(--bg);
    border-radius: 6px;
    font-family: 'Maple Mono Normal NF CN', monospace;
    font-size: 12px;
    color: var(--text);
    word-break: break-all;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
