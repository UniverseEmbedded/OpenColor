<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { navigate } from '$lib/stores/router.svelte';
  import { onMount } from 'svelte';

  onMount(() => {
    navigationStore.setCurrentNav('library/materials/filaments');
  });

  let currentNav = $state('library/materials/filaments');

  $effect(() => {
    const unsubscribe = navigationStore.subscribe((value) => {
      currentNav = value.currentNav;
    });
    return unsubscribe;
  });

  // 示例耗材数据
  const filaments = [
    { id: 'pla-red', name: 'PLA 红色', brand: '未知', color: { r: 255, g: 0, b: 0 }, type: 'PLA' },
    { id: 'pla-green', name: 'PLA 绿色', brand: '未知', color: { r: 0, g: 255, b: 0 }, type: 'PLA' },
    { id: 'pla-blue', name: 'PLA 蓝色', brand: '未知', color: { r: 0, g: 0, b: 255 }, type: 'PLA' },
    { id: 'pla-white', name: 'PLA 白色', brand: '未知', color: { r: 255, g: 255, b: 255 }, type: 'PLA' },
    { id: 'pla-black', name: 'PLA 黑色', brand: '未知', color: { r: 30, g: 30, b: 30 }, type: 'PLA' },
    { id: 'petg-yellow', name: 'PETG 黄色', brand: '未知', color: { r: 255, g: 255, b: 0 }, type: 'PETG' },
  ];

  function getColorStyle(color: { r: number; g: number; b: number }) {
    return `rgb(${color.r}, ${color.g}, ${color.b})`;
  }
</script>

<div class="filaments-page">
  <div class="materials-subnav">
    <button
      class="subnav-item"
      class:active={currentNav === 'library/materials/filaments'}
      onclick={() => navigate('library/materials/filaments')}
      type="button"
    >
      {$_('nav.library.filaments')}
    </button>
    <button
      class="subnav-item"
      class:active={currentNav === 'library/materials/profiles'}
      onclick={() => navigate('library/materials/profiles')}
      type="button"
    >
      {$_('nav.library.profiles')}
    </button>
  </div>
  <div class="filaments-body">
    <header class="page-header">
      <h1>{$_('nav.library.filaments')}</h1>
      <button class="btn-primary">
        <i class="ti ti-plus"></i>
        {$_('app.create')}
      </button>
    </header>

    <div class="filaments-grid">
      {#each filaments as filament}
        <div class="filament-card">
          <div class="filament-color" style="background-color: {getColorStyle(filament.color)}"></div>
          <div class="filament-info">
            <h3 class="filament-name">{filament.name}</h3>
            <div class="filament-meta">
              <span class="filament-brand">{filament.brand}</span>
              <span class="filament-type">{filament.type}</span>
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .filaments-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .materials-subnav {
    display: flex;
    gap: 8px;
    padding: 12px 24px;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
  }

  .subnav-item {
    padding: 8px 16px;
    border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--panel);
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .subnav-item:hover {
    border-color: var(--accent);
    color: var(--text);
  }

  .subnav-item.active {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
  }

  .filaments-body {
    flex: 1;
    padding: 24px;
    overflow-y: auto;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  .page-header h1 {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
  }

  .btn-primary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 14px;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .filaments-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
  }

  @media (max-width: 768px) {
    .filaments-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 480px) {
    .filaments-grid {
      grid-template-columns: 1fr;
    }
  }

  .filament-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s;
  }

  .filament-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .filament-color {
    height: 80px;
    width: 100%;
  }

  .filament-info {
    padding: 16px;
  }

  .filament-name {
    font-size: 14px;
    font-weight: 500;
    margin: 0 0 8px;
  }

  .filament-meta {
    display: flex;
    gap: 8px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .filament-brand {
    background: var(--panel-elevated);
    padding: 2px 8px;
    border-radius: 4px;
  }

  .filament-type {
    background: var(--accent);
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
  }
</style>
