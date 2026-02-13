<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import Header from '$lib/components/layout/Header.svelte';
  import MobileSubNav from '$lib/components/layout/MobileSubNav.svelte';
  import WindowSizeOverlay from '$lib/components/layout/WindowSizeOverlay.svelte';
  import LoadingOverlay from '$lib/components/LoadingOverlay.svelte';
  import { settingsStore } from '$lib/stores/settings.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { workspaceStore } from '$lib/stores/workspace.svelte';
  import { initRouter, getRouter } from '$lib/stores/router.svelte';

  const router = getRouter();

  // 本地状态
  let CurrentComponent: any = $state(null);
  let isMobile: boolean = $state(false);
  let isAppReady: boolean = $state(false);

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

  // 触发应用就绪事件，通知加载层组件
  function notifyAppReady() {
    (window as any).__appReady = true;
    window.dispatchEvent(new CustomEvent('app:ready'));
  }

  // 初始化应用
  async function initApp() {
    console.log('[启动] WebUI 初始化开始');

    // 初始化设置
    settingsStore.init();
    console.log('[启动] 设置初始化完成');

    // 初始化路由
    initRouter();
    console.log('[启动] 路由初始化完成');

    // 检测窗口大小
    const checkMobile = () => {
      navigationStore.setMobile(window.innerWidth < 1024);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    console.log('[启动] 窗口尺寸监听已就绪');

    // 等待关键数据加载完成
    try {
      // 等待工作区初始化完成
      console.log('[启动] 工作区初始化开始');
      await workspaceStore.init();
      console.log('[启动] 工作区初始化完成');

      // 标记应用已就绪
      isAppReady = true;

      // 通知加载层组件应用已就绪
      notifyAppReady();
      console.log('[启动] 应用就绪事件已发送');
    } catch (e) {
      console.error('[启动] 应用初始化失败:', e);
      // 即使失败也标记就绪，避免卡住
      notifyAppReady();
      console.log('[启动] 应用就绪事件已发送（异常情况下）');
    }

    return () => {
      window.removeEventListener('resize', checkMobile);
    };
  }

  onMount(() => {
    initApp();
  });
</script>

<LoadingOverlay />
<WindowSizeOverlay />

<div class="app-layout" class:mobile={isMobile}>
  <Sidebar />

  <main class="main">
    {#if isMobile}
      <MobileSubNav />
    {/if}
    <Header />
    <div class="content">
      {#if !isAppReady}
        <div class="loading">
          <i class="ti ti-loader-2 spinning"></i>
          <span>初始化中...</span>
        </div>
      {:else if CurrentComponent}
        <CurrentComponent />
      {:else}
        <div class="loading">
          <i class="ti ti-loader-2 spinning"></i>
          <span>加载中...</span>
        </div>
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
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    gap: 12px;
  }

  .loading i {
    font-size: 32px;
  }

  .loading span {
    font-size: 14px;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
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
