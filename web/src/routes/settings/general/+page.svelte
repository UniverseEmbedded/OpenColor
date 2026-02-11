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

  // 语言列表（不包括 auto）
  const locales: { value: Exclude<Locale, 'auto'>; label: string }[] = [
    { value: 'zh-CN', label: 'settings.general.language.zh' },
    { value: 'en-US', label: 'settings.general.language.en' },
  ];

  const logLevels = ['debug', 'info', 'warn', 'error'] as const;

  // 是否启用自动语言
  let isAutoLocale = $state(appSettings.locale === 'auto');

  // 当前选中的语言（非 auto 时）
  let selectedLocale = $state<Exclude<Locale, 'auto'>>(
    appSettings.locale === 'auto' ? 'zh-CN' : (appSettings.locale as Exclude<Locale, 'auto'>)
  );

  // 处理自动开关变化
  function handleAutoChange(e: Event) {
    const checked = (e.target as HTMLInputElement).checked;
    isAutoLocale = checked;
    if (checked) {
      settingsStore.setLocale('auto');
    } else {
      settingsStore.setLocale(selectedLocale);
    }
  }

  // 处理语言选择变化
  function handleLocaleChange(e: Event) {
    const value = (e.target as HTMLSelectElement).value as Exclude<Locale, 'auto'>;
    selectedLocale = value;
    if (!isAutoLocale) {
      settingsStore.setLocale(value);
    }
  }
</script>

<div class="settings-page">
  <h1>{$_('settings.general.title')}</h1>

  <div class="settings-section">
    <h2>{$_('settings.general.language')}</h2>
    <div class="language-control">
      <label class="toggle">
        <input
          type="checkbox"
          checked={isAutoLocale}
          onchange={handleAutoChange}
        />
        <span class="toggle-slider"></span>
        <span class="toggle-label">{$_('settings.general.language.auto')}</span>
      </label>
      <select
        class="locale-select"
        value={selectedLocale}
        onchange={handleLocaleChange}
        disabled={isAutoLocale}
      >
        {#each locales as loc}
          <option value={loc.value}>{$_(loc.label)}</option>
        {/each}
      </select>
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

  <div class="settings-section">
    <h2>{$_('settings.general.windowSizeOverlay')}</h2>
    <label class="toggle">
      <input
        type="checkbox"
        checked={appSettings.showWindowSizeOverlay}
        onchange={(e) => settingsStore.setShowWindowSizeOverlay(e.currentTarget.checked)}
      />
      <span class="toggle-slider"></span>
      <span class="toggle-label">{$_('settings.general.showWindowSizeOverlay')}</span>
    </label>
    <p class="setting-description">{$_('settings.general.windowSizeOverlayDesc')}</p>
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

  .language-control {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  /* Toggle开关 */
  .toggle {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
  }

  .toggle input {
    display: none;
  }

  .toggle-slider {
    width: 48px;
    height: 24px;
    background: var(--line);
    border-radius: 12px;
    position: relative;
    transition: all 0.2s;
    flex-shrink: 0;
  }

  .toggle-slider::after {
    content: '';
    position: absolute;
    width: 20px;
    height: 20px;
    background: white;
    border-radius: 50%;
    top: 2px;
    left: 2px;
    transition: all 0.2s;
  }

  .toggle input:checked + .toggle-slider {
    background: var(--accent);
  }

  .toggle input:checked + .toggle-slider::after {
    left: 26px;
  }

  .toggle-label {
    font-size: 14px;
    color: var(--text);
  }

  /* 下拉框 */
  .locale-select {
    padding: 10px 16px;
    border-radius: 8px;
    background: var(--panel);
    border: 1px solid var(--line);
    color: var(--text);
    font-size: 14px;
    font-family: 'Maple Mono Normal NF CN', monospace;
    cursor: pointer;
    transition: all 0.2s;
    min-width: 150px;
  }

  .locale-select:hover:not(:disabled) {
    background: var(--panel-elevated);
  }

  .locale-select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .locale-select:focus {
    outline: none;
    border-color: var(--accent);
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

  .setting-description {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 8px;
    margin-left: 60px;
  }
</style>
