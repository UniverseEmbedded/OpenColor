<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navItems, navigationStore } from '$lib/stores/navigation.svelte';
  import WorkspaceSelector from './WorkspaceSelector.svelte';
  import { navigate } from '$lib/stores/router.svelte';
  
  // 本地状态
  let isMobile: boolean = $state(false);
  let currentNav: string = $state('calibrate/board-gen');
  let expandedNavs: Set<string> = $state(new Set(['calibrate']));
  
  // 订阅 navigation store
  $effect(() => {
    const unsubscribe = navigationStore.subscribe((value) => {
      isMobile = value.isMobile;
      currentNav = value.currentNav;
      expandedNavs = value.expandedNavs;
    });
    return unsubscribe;
  });
  
  // 处理导航点击
  function handleNavClick(item: typeof navItems[0]) {
    if (item.children && item.children.length > 0) {
      if (isMobile) {
        // 移动端：直接跳转到第一个子页面
        navigate(item.children[0].id);
      } else {
        // 桌面端：展开/收起
        navigationStore.toggleNav(item.id);
      }
    } else {
      navigationStore.setCurrentNav(item.id);
    }
  }
  
  // 处理子导航点击
  function handleChildClick(childId: string) {
    navigate(childId);
  }
</script>

<aside class="sidebar">
  <!-- Logo区域 - 桌面端显示 -->
  {#if !isMobile}
    <div class="logo">
      <img src="/icon.svg" alt="OpenColor" class="logo-icon" />
      <span class="logo-text">{$_('app.name')}</span>
    </div>
  {/if}
  
  <!-- 导航区域 -->
  <nav class="nav">
    {#each navItems as item}
      <div class="nav-group" class:expanded={expandedNavs.has(item.id)}>
        <button 
          class="nav-item" 
          class:active={currentNav.startsWith(item.id)}
          onclick={() => handleNavClick(item)}
        >
          <i class="ti {item.icon}"></i>
          <span>{$_(item.label)}</span>
          {#if item.children && !isMobile}
            <i class="ti ti-chevron-down arrow"></i>
          {/if}
        </button>
        
        {#if item.children && expandedNavs.has(item.id) && !isMobile}
          <div class="nav-children">
            {#each item.children as child}
              <button 
                class="nav-child" 
                class:active={currentNav === child.id}
                onclick={() => handleChildClick(child.id)}
              >
                <i class="ti {child.icon}"></i>
                <span>{$_(child.label)}</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </nav>
  
  <!-- 工作区选择器 -->
  <div class="workspace-area">
    <WorkspaceSelector />
  </div>
</aside>

<style>
  .sidebar {
    width: 240px;
    height: 100vh;
    background: var(--panel);
    border-right: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  
  .logo {
    height: 64px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 20px;
    border-bottom: 1px solid var(--line);
  }
  
  .logo-icon {
    width: 32px;
    height: 32px;
  }
  
  .logo-text {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
  }
  
  .nav {
    flex: 1;
    overflow-y: auto;
    padding: 12px 8px;
  }
  
  .nav-group {
    margin-bottom: 4px;
  }
  
  .nav-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .nav-item:hover {
    background: var(--panel-elevated);
    color: var(--text);
  }
  
  .nav-item.active {
    background: var(--accent);
    color: white;
  }
  
  .nav-item i {
    font-size: 18px;
  }
  
  .nav-item span {
    flex: 1;
    text-align: left;
  }
  
  .arrow {
    transition: transform 0.2s;
  }
  
  .nav-group.expanded .arrow {
    transform: rotate(180deg);
  }
  
  .nav-children {
    padding-left: 16px;
    margin-top: 4px;
  }
  
  .nav-child {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .nav-child:hover {
    background: var(--panel-elevated);
    color: var(--text);
  }
  
  .nav-child.active {
    color: var(--accent);
  }
  
  .nav-child i {
    font-size: 16px;
  }
  
  .nav-child span {
    flex: 1;
    text-align: left;
  }
  
  .workspace-area {
    padding: 12px;
    border-top: 1px solid var(--line);
  }
</style>
