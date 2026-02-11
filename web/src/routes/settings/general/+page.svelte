<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte';
  import { settingsStore } from '$lib/stores/settings.svelte';
  import type { Theme, Locale } from '$lib/types';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('settings/general');
  });
  
  // 本地状态
  let appSettings = $state(settingsStore.appSettings);
  
  // 订阅 settings store
  $effect(() => {
    const unsubscribe = settingsStore.subscribe((value) => {
      appSettings = value.appSettings;
    });
    return unsubscribe;
  });
  
  const themes: { value: Theme; label: string }[] = [
    { value: 'dark', label: 'settings.general.theme.dark' },
    { value: 'light', label: 'settings.general.theme.light' },
    { value: 'auto', label: 'settings.general.theme.auto' },
  ];
  
  const locales: { value: Locale; label: string }[] = [
    { value: 'zh-CN', label: 'settings.general.language.zh' },
    { value: 'en-US', label: 'settings.general.language.en' },
    { value: 'auto', label: 'settings.general.language.auto' },
  ];
  
  const logLevels = ['debug', 'info', 'warn', 'error'] as const;
</script>

<div class="settings-page">
  <h1>{$_('settings.general.title')}</h1>
  
  <div class="settings-section">
    <h2>{$_('settings.general.language')}</h2>
    <div class="options">
      {#each locales as loc}
        <button 
          class="option" 
          class:active={appSettings.locale === loc.value}
          onclick={() => settingsStore.setLocale(loc.value)}
        >
          {$_(loc.label)}
        </button>
      {/each}
    </div>
  </div>
  
  <div class="settings-section">
    <h2>{$_('settings.general.theme')}</h2>
    <div class="options">
      {#each themes as theme}
        <button 
          class="option" 
          class:active={appSettings.theme === theme.value}
          onclick={() => settingsStore.setTheme(theme.value)}
        >
          {$_(theme.label)}
        </button>
      {/each}
    </div>
  </div>
  
  <div class="settings-section">
    <h2>{$_('settings.general.logLevel')}</h2>
    <div class="options">
      {#each logLevels as level}
        <button 
          class="option" 
          class:active={appSettings.logLevel === level}
          onclick={() => settingsStore.updateAppSettings({ logLevel: level })}
        >
          {level}
        </button>
      {/each}
    </div>
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
  
  .options {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  
  .option {
    padding: 10px 20px;
    border-radius: 8px;
    background: var(--panel);
    border: 1px solid var(--line);
    color: var(--text);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .option:hover {
    background: var(--panel-elevated);
  }
  
  .option.active {
    background: var(--accent);
    border-color: var(--accent);
    color: white;
  }
</style>
