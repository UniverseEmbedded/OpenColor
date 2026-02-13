<script lang="ts">
  import { _ } from '$lib/i18n';
  import { settingsStore, appSettings } from '$lib/stores/settings.svelte';
  import { onMount, onDestroy } from 'svelte';

  // 本地状态
  let isWindowSmall = $state(false);

  // 检查窗口尺寸
  function checkWindowSize() {
    isWindowSmall = window.innerWidth <= 640 || window.innerHeight <= 480;
  }

  // 不再显示（同时关闭设置）
  function hideForever() {
    settingsStore.setShowWindowSizeOverlay(false);
  }

  onMount(() => {
    checkWindowSize();
    window.addEventListener('resize', checkWindowSize);
  });

  onDestroy(() => {
    window.removeEventListener('resize', checkWindowSize);
  });
</script>

{#if isWindowSmall && $appSettings.showWindowSizeOverlay !== false}
  <div class="window-size-overlay">
    <div class="overlay-content">
      <img src="/icon.svg" alt="Logo" class="overlay-logo" />
      <p>{$_('hint.windowTooSmall')}</p>
      <button class="btn-secondary" onclick={hideForever} type="button">
        <i class="ti ti-eye-off"></i>
        <span>{$_('btn.neverShow')}</span>
      </button>
    </div>
  </div>
{/if}

<style>
  .window-size-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: var(--bg);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 20px;
  }

  .overlay-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }

  .overlay-logo {
    width: 80px;
    height: 80px;
    opacity: 0.8;
    filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.2));
  }

  .window-size-overlay p {
    font-size: 16px;
    color: var(--text-muted);
    margin: 0;
    font-weight: 500;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border-radius: 8px;
    background: var(--panel);
    border: 1px solid var(--line);
    color: var(--text);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 10px;
  }

  .btn-secondary:hover {
    background: var(--panel-elevated);
  }

  .btn-secondary i {
    font-size: 16px;
  }
</style>
