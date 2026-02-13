<script lang="ts">
  import { onMount } from 'svelte';

  // 加载层显示状态
  let isVisible = $state(true);
  let isAppReady = $state(false);
  let isFadingOut = $state(false);
  let hideTimer: number | undefined = undefined;

  const clearHideTimer = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = undefined;
    }
  };

  const startHide = () => {
    clearHideTimer();
    isFadingOut = true;
    hideTimer = window.setTimeout(() => {
      isVisible = false;
    }, 300);
  };

  onMount(() => {
    // 监听应用就绪事件
    const handleAppReady = () => {
      isAppReady = true;
      startHide();
    };

    window.addEventListener('app:ready', handleAppReady);

    // 检查是否已经有就绪标记
    if ((window as any).__appReady) {
      handleAppReady();
    }

    return () => {
      window.removeEventListener('app:ready', handleAppReady);
      clearHideTimer();
    };
  });

  // 全局函数：显示加载层
  (window as any).showLoadingOverlay = () => {
    clearHideTimer();
    isVisible = true;
    isFadingOut = false;
  };

  // 全局函数：隐藏加载层
  (window as any).hideLoadingOverlay = () => {
    startHide();
  };
</script>

<div id="loading-screen" class:fade-out={isFadingOut} class:hidden={!isVisible && isAppReady}>
  <img src="/loading.svg" alt="Loading..." />
  <span class="loading-text">OpenColor</span>
</div>

<style>
  #loading-screen {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background-color: #0b0d10;
    z-index: 99999;
    transition: opacity 0.3s ease-out;
  }

  #loading-screen.fade-out {
    opacity: 0;
    pointer-events: none;
  }

  #loading-screen.hidden {
    display: none;
  }

  #loading-screen img {
    width: 80px;
    height: 80px;
    animation: pulse 2s ease-in-out infinite;
  }

  #loading-screen .loading-text {
    margin-top: 20px;
    color: #8b949e;
    font-size: 14px;
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.6; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.05); }
  }
</style>
