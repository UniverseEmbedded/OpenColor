<script lang="ts">
  import { onMount } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  
  onMount(() => {
    // 确保校准导航展开
    navigationStore.toggleNav('calibrate');
  });
</script>

<div class="calibrate-layout">
  <slot />
</div>

<style>
  .calibrate-layout {
    height: 100%;
  }
</style>
