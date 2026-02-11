<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  
  // 本地状态
  let isMobile: boolean = $state(false);
  let breadcrumbs: { label: string }[] = $state([]);
  
  // 订阅 navigation store
  $effect(() => {
    const unsubscribe = navigationStore.subscribe((value) => {
      isMobile = value.isMobile;
      breadcrumbs = navigationStore.getBreadcrumbs();
    });
    return unsubscribe;
  });
</script>

<header class="header" class:mobile={isMobile}>
  <div class="breadcrumbs">
    {#each breadcrumbs as crumb, i}
      {#if i > 0}
        <span class="separator">/</span>
      {/if}
      <span class="crumb" class:active={i === breadcrumbs.length - 1}>
        {$_(crumb.label)}
      </span>
    {/each}
  </div>
  
  <div class="right-section">
    {#if isMobile}
      <!-- 移动端：Logo 放在右侧 -->
      <div class="logo">
        <img src="/icon.svg" alt="OpenColor" class="logo-icon" />
        <span class="logo-text">{$_('app.name')}</span>
      </div>
    {/if}
    
    <div class="actions">
      <button class="action-btn" title={$_('app.help')}>
        <i class="ti ti-help-circle"></i>
      </button>
      <button class="action-btn" title={$_('app.about')}>
        <i class="ti ti-info-circle"></i>
      </button>
    </div>
  </div>
</header>

<style>
  .header {
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
    flex-shrink: 0;
    min-width: 0; /* 允许 header 收缩 */
  }
  
  .breadcrumbs {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    flex-shrink: 0; /* 防止面包屑收缩 */
    white-space: nowrap; /* 防止文本换行 */
    overflow: hidden; /* 隐藏溢出内容 */
  }
  
  .separator {
    color: var(--text-muted);
    flex-shrink: 0; /* 分隔符不收缩 */
  }
  
  .crumb {
    color: var(--text-muted);
    white-space: nowrap; /* 防止文本换行 */
    flex-shrink: 0; /* 面包屑项不收缩 */
  }
  
  .crumb.active {
    color: var(--text);
    font-weight: 500;
  }
  
  .right-section {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0; /* 右侧区域不收缩 */
  }
  
  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0; /* Logo 不收缩 */
  }
  
  .logo-icon {
    width: 24px;
    height: 24px;
    flex-shrink: 0;
  }
  
  .logo-text {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap; /* 防止文本换行 */
    flex-shrink: 0;
  }
  
  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0; /* 操作按钮区域不收缩 */
  }
  
  .action-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0; /* 按钮不收缩 */
  }
  
  .action-btn:hover {
    background: var(--panel-elevated);
    color: var(--text);
  }
  
  .action-btn i {
    font-size: 20px;
  }
</style>
