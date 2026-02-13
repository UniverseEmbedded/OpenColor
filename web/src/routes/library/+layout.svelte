<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();
  
  onMount(() => {
    navigationStore.toggleNav('library');
  });
</script>

<div class="library-layout">
  {@render children?.()}
</div>

<style>
  .library-layout {
    height: 100%;
  }
</style>
