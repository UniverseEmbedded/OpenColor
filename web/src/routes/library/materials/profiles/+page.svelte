<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { materialsStore } from '$lib/stores/materials.svelte';
  import { navigate } from '$lib/stores/router.svelte';
  import { onMount } from 'svelte';
  import type { ColorProfile } from '$lib/types';

  onMount(() => {
    navigationStore.setCurrentNav('library/materials/profiles');
    materialsStore.loadProfiles();
  });

  // 本地状态
  let profiles = $state<ColorProfile[]>([]);
  let selectedProfile = $state<ColorProfile | null>(null);
  let isLoading = $state(false);
  let showRawJson = $state(false);
  let currentNav = $state('library/materials/profiles');

  // 订阅 store
  $effect(() => {
    const unsubscribe = materialsStore.subscribe((value) => {
      profiles = value.profiles;
      selectedProfile = value.selectedProfile;
      isLoading = value.isLoading;
    });
    return unsubscribe;
  });

  $effect(() => {
    const unsubscribe = navigationStore.subscribe((value) => {
      currentNav = value.currentNav;
    });
    return unsubscribe;
  });

  // 选择耗材组
  function handleProfileClick(profileId: string) {
    materialsStore.selectProfile(profileId);
  }

  // 切换原始 JSON 显示
  function toggleRawJson() {
    showRawJson = !showRawJson;
  }

  // 获取颜色样式
  function getColorStyle(color: { r: number; g: number; b: number }) {
    return `rgb(${color.r}, ${color.g}, ${color.b})`;
  }

  // 获取标记颜色
  function getMarkerColor(profile: ColorProfile, position: string): string {
    const colorName = (profile as any)[`marker_${position}`];
    const color = profile.colors.find(c => c.name === colorName);
    return color ? getColorStyle(color) : '#666';
  }
</script>

<div class="profiles-page">
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

  <div class="profiles-body">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">{$_('nav.library.profiles')}</h2>
        <button class="btn-icon" title={$_('app.create')}>
          <i class="ti ti-plus"></i>
        </button>
      </div>

      <div class="profile-list">
        {#if isLoading}
          <div class="loading">{$_('app.loading')}</div>
        {:else if profiles.length === 0}
          <div class="empty">{$_('workspace.noRecent')}</div>
        {:else}
          {#each profiles as profile}
            <div
              class="profile-item"
              class:active={selectedProfile?.id === profile.id}
              onclick={() => handleProfileClick(profile.id)}
              role="button"
              tabindex="0"
              onkeydown={(e) => e.key === 'Enter' && handleProfileClick(profile.id)}
            >
              <div class="profile-name">{profile.name}</div>
              <div class="profile-meta">
                <span class="profile-colors-count">{profile.colors.length}{$_('boardGen.colors')}</span>
                <span class="profile-id">{profile.id}</span>
              </div>
              <div class="profile-colors-preview">
                {#each profile.colors as color}
                  <div
                    class="color-dot"
                    style="background-color: {getColorStyle(color)}"
                    title={color.name}
                  ></div>
                {/each}
              </div>
            </div>
          {/each}
        {/if}
      </div>
    </aside>

    <main class="main">
      {#if selectedProfile}
        <header class="header">
          <h1 class="header-title">{selectedProfile.name}</h1>
          <div class="header-actions">
            <button class="btn" onclick={toggleRawJson}>
              {showRawJson ? $_('app.close') + ' JSON' : $_('app.open') + ' JSON'}
            </button>
            <button class="btn primary">{$_('app.export')}</button>
          </div>
        </header>

        <div class="content" class:show-json={showRawJson}>
          <div class="blueprint-viewer">
            <section class="bp-section">
              <h3 class="bp-section-title">{$_('profile.basicInfo')}</h3>
              <div class="bp-field">
                <span class="bp-label">{$_('profile.id')}</span>
                <span class="bp-value bp-string">{selectedProfile.id}</span>
              </div>
              <div class="bp-field">
                <span class="bp-label">{$_('profile.name')}</span>
                <span class="bp-value bp-string">{selectedProfile.name}</span>
              </div>
              <div class="bp-field">
                <span class="bp-label">{$_('profile.description')}</span>
                <span class="bp-value bp-string">{selectedProfile.description}</span>
              </div>
              <div class="bp-field">
                <span class="bp-label">{$_('profile.colorCount')}</span>
                <span class="bp-value bp-number">{selectedProfile.colors.length}</span>
              </div>
            </section>

            <section class="bp-section">
              <h3 class="bp-section-title">{$_('profile.colorConfig')}</h3>
              <div class="colors-grid">
                {#each selectedProfile.colors as color}
                  <div class="color-card">
                    <div class="color-card-preview" style="background-color: {getColorStyle(color)}"></div>
                    <div class="color-card-info">
                      <span class="color-card-name">{color.name}</span>
                      <span class="color-card-rgb">{color.r}, {color.g}, {color.b}</span>
                    </div>
                  </div>
                {/each}
              </div>
            </section>

            <section class="bp-section">
              <h3 class="bp-section-title">{$_('profile.markerConfig')}</h3>
              <div class="markers-config">
                <div class="marker-item">
                  <span class="marker-label">{$_('profile.markerTL')}</span>
                  <div class="marker-color">
                    <div class="marker-dot" style="background-color: {getMarkerColor(selectedProfile, 'tl')}"></div>
                    <span class="marker-name">{selectedProfile.marker_tl}</span>
                  </div>
                </div>
                <div class="marker-item">
                  <span class="marker-label">{$_('profile.markerTR')}</span>
                  <div class="marker-color">
                    <div class="marker-dot" style="background-color: {getMarkerColor(selectedProfile, 'tr')}"></div>
                    <span class="marker-name">{selectedProfile.marker_tr}</span>
                  </div>
                </div>
                <div class="marker-item">
                  <span class="marker-label">{$_('profile.markerBR')}</span>
                  <div class="marker-color">
                    <div class="marker-dot" style="background-color: {getMarkerColor(selectedProfile, 'br')}"></div>
                    <span class="marker-name">{selectedProfile.marker_br}</span>
                  </div>
                </div>
                <div class="marker-item">
                  <span class="marker-label">{$_('profile.markerBL')}</span>
                  <div class="marker-color">
                    <div class="marker-dot" style="background-color: {getMarkerColor(selectedProfile, 'bl')}"></div>
                    <span class="marker-name">{selectedProfile.marker_bl}</span>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {#if showRawJson}
            <div class="raw-json-panel">
              <div class="raw-json-header">JSON</div>
              <div class="raw-json-content">
                <pre>{JSON.stringify(selectedProfile, null, 2)}</pre>
              </div>
            </div>
          {/if}
        </div>
      {:else}
        <div class="empty-state">
          <i class="ti ti-palette"></i>
          <p>{$_('workspace.noRecent')}</p>
        </div>
      {/if}
    </main>
  </div>
</div>

<style>
  .profiles-page {
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

  .profiles-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* 左侧边栏 */
  .sidebar {
    width: 280px;
    min-width: 200px;
    max-width: 320px;
    background: var(--panel);
    border-right: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  /* 小窗模式：侧边栏变为顶部横向滚动 */
  @media (max-width: 768px) {
    .profiles-body {
      flex-direction: column;
    }

    .sidebar {
      width: 100%;
      max-width: none;
      height: auto;
      max-height: 200px;
      border-right: none;
      border-bottom: 1px solid var(--line);
    }

    .profile-list {
      display: flex;
      flex-direction: row;
      gap: 8px;
      overflow-x: auto;
      padding: 12px;
    }

    .profile-item {
      min-width: 160px;
      margin-bottom: 0;
      flex-shrink: 0;
    }
  }

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--line);
  }

  .sidebar-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0;
  }

  .btn-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    border-radius: 6px;
    color: var(--text);
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-icon:hover {
    border-color: var(--accent);
  }

  .profile-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
  }

  .profile-item {
    padding: 12px;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 8px;
  }

  .profile-item:hover {
    border-color: var(--accent);
  }

  .profile-item.active {
    background: var(--accent);
    border-color: var(--accent);
  }

  .profile-name {
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
  }

  .profile-meta {
    display: flex;
    gap: 8px;
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .profile-id {
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  .profile-colors-preview {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .color-dot {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .loading,
  .empty {
    padding: 20px;
    text-align: center;
    color: var(--text-muted);
  }

  /* 主内容区 */
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .header {
    height: 56px;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
    display: flex;
    align-items: center;
    padding: 0 24px;
    justify-content: space-between;
  }

  .header-title {
    font-size: 18px;
    font-weight: 600;
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: 12px;
  }

  .btn {
    padding: 8px 16px;
    background: var(--panel-elevated);
    border: 1px solid var(--line);
    border-radius: 6px;
    color: var(--text);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn:hover {
    border-color: var(--accent);
  }

  .btn.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
  }

  .content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .content.show-json {
    display: grid;
    grid-template-columns: 1fr 400px;
  }

  @media (max-width: 1024px) {
    .content.show-json {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr 300px;
    }
  }

  /* 蓝图查看器 */
  .blueprint-viewer {
    flex: 1;
    padding: 24px;
    overflow-y: auto;
  }

  .bp-section {
    margin-bottom: 32px;
  }

  .bp-section-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
  }

  .bp-field {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    margin-bottom: 8px;
  }

  .bp-label {
    width: 100px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .bp-value {
    flex: 1;
    font-size: 14px;
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  .bp-string {
    color: var(--text);
  }

  .bp-number {
    color: var(--accent2);
  }

  /* 颜色网格 */
  .colors-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 12px;
  }

  .color-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
  }

  .color-card-preview {
    height: 60px;
  }

  .color-card-info {
    padding: 8px 12px;
  }

  .color-card-name {
    display: block;
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 2px;
  }

  .color-card-rgb {
    display: block;
    font-size: 11px;
    color: var(--text-muted);
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  /* 标记配置 */
  .markers-config {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  @media (max-width: 640px) {
    .markers-config {
      grid-template-columns: 1fr;
    }
  }

  .marker-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
  }

  .marker-label {
    font-size: 13px;
    color: var(--text-muted);
  }

  .marker-color {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .marker-dot {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 2px solid var(--line);
  }

  .marker-name {
    font-size: 13px;
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  /* 原始 JSON 面板 */
  .raw-json-panel {
    background: var(--panel);
    border-left: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .raw-json-header {
    padding: 12px 16px;
    background: var(--panel-elevated);
    border-bottom: 1px solid var(--line);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
  }

  .raw-json-content {
    flex: 1;
    padding: 16px;
    overflow: auto;
  }

  .raw-json-content pre {
    margin: 0;
    font-size: 12px;
    line-height: 1.6;
    font-family: 'Maple Mono Normal NF CN', monospace;
    color: var(--text);
  }

  /* 空状态 */
  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    gap: 16px;
  }

  .empty-state i {
    font-size: 48px;
    opacity: 0.5;
  }

  .empty-state p {
    font-size: 14px;
  }
</style>
