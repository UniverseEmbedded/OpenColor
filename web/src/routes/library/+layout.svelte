<script lang="ts">
  import { onMount } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  
  onMount(() => {
    navigationStore.toggleNav('library');
  });
</script>

<div class="library-layout">
  <slot />
</div>

<style>
  .library-layout {
    height: 100%;
  }
</style>
