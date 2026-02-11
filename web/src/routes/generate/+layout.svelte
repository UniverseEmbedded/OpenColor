<script lang="ts">
  import { onMount } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  
  onMount(() => {
    navigationStore.toggleNav('generate');
  });
</script>

<div class="generate-layout">
  <slot />
</div>

<style>
  .generate-layout {
    height: 100%;
  }
</style>
