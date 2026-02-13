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

  // 三种模式检测
  // @ts-ignore - Vite 环境变量
  const isDev = import.meta.env.DEV;        // 开发构建
  const isBrowser = !bridge.hasTauri;       // 浏览器模式
  const isDesktop = bridge.hasTauri;        // 桌面应用模式

  // 本地状态
  let appSettings = $state(settingsStore.appSettings);

  // 订阅 settings store
  $effect(() => {
    const unsubscribe = settingsStore.subscribe((value) => {
      appSettings = value.appSettings;
    });
    return unsubscribe;
  });
</script>

<div class="settings-page">
  <h1>{$_('settings.engine.title')}</h1>

  {#if isBrowser}
    <!-- 浏览器环境提示 -->
    <div class="browser-mode-banner">
      <i class="ti ti-browser"></i>
      <span>
        {isDev ? $_('settings.engine.devMode') : $_('settings.engine.browserMode')} - 
        {$_('settings.engine.desktopOnly')}
      </span>
    </div>
  {/if}

  {#if isDev && isDesktop}
    <!-- 开发构建标识（仅在桌面开发环境显示） -->
    <div class="dev-build-badge">
      <i class="ti ti-code"></i>
      <span>{$_('settings.engine.devBuild')}</span>
    </div>
  {/if}

  <div class="settings-section">
    <h2>{$_('settings.engine.path')}</h2>
    {#if isDesktop}
      <!-- 桌面模式：显示输入框和浏览按钮 -->
      <div class="input-group">
        <input
          type="text"
          class="engine-path-input"
          value={appSettings.enginePath}
          placeholder="auto"
          readonly
        />
        <button class="btn-secondary">{$_('app.browse')}</button>
      </div>
    {:else}
      <!-- 浏览器模式：显示占位符 -->
      <div class="browser-placeholder">
        <i class="ti ti-info-circle"></i>
        <span>{$_('settings.engine.pathUnavailable')}</span>
      </div>
    {/if}
  </div>

  <div class="settings-section">
    <h2>{$_('settings.engine.gpu')}</h2>
    <label class="toggle" class:disabled={isBrowser}>
      <input
        type="checkbox"
        checked={appSettings.gpuAcceleration}
        onchange={(e) => settingsStore.updateAppSettings({ gpuAcceleration: e.currentTarget.checked })}
        disabled={isBrowser}
      />
      <span class="toggle-slider"></span>
      <span class="toggle-label">{$_('settings.engine.gpuAcceleration')}</span>
    </label>
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

  /* 浏览器模式横幅 */
  .browser-mode-banner {
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

  .browser-mode-banner i {
    font-size: 20px;
  }

  /* 开发构建标识 */
  .dev-build-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid var(--success);
    border-radius: 6px;
    color: var(--success);
    font-size: 12px;
    margin-bottom: 24px;
  }

  .dev-build-badge i {
    font-size: 14px;
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

  /* 浏览器模式占位符 */
  .browser-placeholder {
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

  .browser-placeholder i {
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
</style>
