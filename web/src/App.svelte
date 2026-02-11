<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  
  interface Props {
    children?: Snippet;
  }
  
  let { children }: Props = $props();
  
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
