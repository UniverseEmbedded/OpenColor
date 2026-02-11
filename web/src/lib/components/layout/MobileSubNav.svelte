<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navItems, navigationStore } from '$lib/stores/navigation.svelte';
  import { navigate } from '$lib/stores/router.svelte';
  
  // 本地状态
  let currentNav: string = $state('calibrate/board-gen');
  
  // 订阅 navigation store
  $effect(() => {
    const unsubscribe = navigationStore.subscribe((value) => {
      currentNav = value.currentNav;
    });
    return unsubscribe;
  });
  
  // 获取当前一级导航的子项
  const currentNavItem = $derived(
    navItems.find(item => currentNav.startsWith(item.id))
  );
  
  const children = $derived(currentNavItem?.children || []);
  
  function handleChildClick(childId: string) {
    navigate(childId);
  }
</script>

{#if children.length > 0}
  <div class="mobile-subnav">
    <div class="subnav-items">
      {#each children as child}
        <button 
          class="subnav-item" 
          class:active={currentNav === child.id}
          onclick={() => handleChildClick(child.id)}
        >
          <i class="ti {child.icon}"></i>
          <span>{$_(child.label)}</span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .mobile-subnav {
    height: 48px;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
    flex-shrink: 0;
  }
  
  .subnav-items {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 0 16px;
    gap: 8px;
    overflow-x: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  
  .subnav-items::-webkit-scrollbar {
    display: none;
  }
  
  .subnav-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .subnav-item:hover {
    background: var(--panel-elevated);
    color: var(--text);
  }
  
  .subnav-item.active {
    background: var(--accent);
    color: white;
  }
  
  .subnav-item i {
    font-size: 16px;
  }
</style>
