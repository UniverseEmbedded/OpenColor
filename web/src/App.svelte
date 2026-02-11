<script lang="ts">
  import { onMount } from 'svelte';
  
  onMount(() => {
    console.log('[OpenColor] Svelte 5 应用已启动');
  });
</script>

{@render children?.()}

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  
  :global(html, body) {
    height: 100%;
    font-family: 'Maple Mono Normal NF CN', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  
  :global(#app) {
    height: 100%;
  }
</style>
