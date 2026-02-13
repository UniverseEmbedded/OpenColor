<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    children?: Snippet;
  }
  
  let { children }: Props = $props();
  
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
