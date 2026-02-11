<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import Header from '$lib/components/layout/Header.svelte';
  import MobileSubNav from '$lib/components/layout/MobileSubNav.svelte';
  import WindowSizeOverlay from '$lib/components/layout/WindowSizeOverlay.svelte';
  import { settingsStore } from '$lib/stores/settings.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { initRouter, getRouter } from '$lib/stores/router.svelte';
  
  const router = getRouter();
  
  // 本地状态
  let CurrentComponent: any = $state(null);
  let isMobile: boolean = $state(false);
  
  // 订阅 router store
  $effect(() => {
    const unsubscribe = router.subscribe((value) => {
      CurrentComponent = value.currentComponent;
    });
    return unsubscribe;
  });
  
  // 订阅 navigation store
  $effect(() => {
    const unsubscribe = navigationStore.subscribe((value) => {
      isMobile = value.isMobile;
    });
    return unsubscribe;
  });
  
  // 移除启动加载屏幕
  function removeLoadingScreen() {
    const loadingScreen = document.getElementById('loading-screen');
    if (loadingScreen) {
      loadingScreen.style.opacity = '0';
      setTimeout(() => {
        loadingScreen.remove();
      }, 300);
    }
  }

  // 初始化设置和路由
  onMount(() => {
    settingsStore.init();
    initRouter();

    // 检测窗口大小
    const checkMobile = () => {
      navigationStore.setMobile(window.innerWidth < 1024);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);

    // 移除启动加载屏幕
    removeLoadingScreen();

    return () => {
      window.removeEventListener('resize', checkMobile);
    };
  });
</script>

<WindowSizeOverlay />

<div class="app-layout" class:mobile={isMobile}>
  <Sidebar />

  <main class="main">
    {#if isMobile}
      <MobileSubNav />
    {/if}
    <Header />
    <div class="content">
      {#if CurrentComponent}
        <CurrentComponent />
      {:else}
        <div class="loading">加载中...</div>
      {/if}
    </div>
  </main>
</div>

<style>
  .app-layout {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }
  
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    background: var(--bg);
    overflow: hidden;
  }
  
  .content {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px;
    min-height: 0;
  }
  
  /* 自定义滚动条 */
  .content::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  
  .content::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .content::-webkit-scrollbar-thumb {
    background: var(--line);
    border-radius: 4px;
  }
  
  .content::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
  }
  
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
  }
  
  /* 移动端布局 */
  .app-layout.mobile {
    flex-direction: column;
  }
  
  .app-layout.mobile :global(.sidebar) {
    width: 100%;
    height: auto;
    flex-direction: row;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }
  
  /* 移动端：Logo已在Header中，Sidebar中隐藏 */
  .app-layout.mobile :global(.sidebar .logo) {
    display: none;
  }
  
  .app-layout.mobile :global(.sidebar .nav) {
    display: flex;
    flex-direction: row;
    overflow-x: auto;
  }
  
  .app-layout.mobile :global(.sidebar .nav-group) {
    margin-bottom: 0;
  }
  
  /* 移动端：文本横向显示，不换行 */
  .app-layout.mobile :global(.sidebar .nav-item span) {
    white-space: nowrap;
    flex: none;
  }
  
  /* 移动端：移除下拉箭头 */
  .app-layout.mobile :global(.sidebar .arrow) {
    display: none;
  }
  
  /* 移动端：移除下拉菜单 */
  .app-layout.mobile :global(.sidebar .nav-children) {
    display: none;
  }
  
  .app-layout.mobile :global(.sidebar .workspace-area) {
    display: none;
  }
</style>
