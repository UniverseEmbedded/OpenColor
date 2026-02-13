<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();
  
  onMount(() => {
    navigationStore.toggleNav('generate');
  });
</script>

<div class="generate-layout">
  {@render children?.()}
</div>

<style>
  .generate-layout {
    height: 100%;
  }
</style>
