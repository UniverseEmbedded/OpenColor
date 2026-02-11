<script lang="ts">
  import { onMount } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  
  onMount(() => {
    navigationStore.toggleNav('settings');
  });
</script>

<div class="settings-layout">
  <slot />
</div>

<style>
  .settings-layout {
    height: 100%;
  }
</style>
