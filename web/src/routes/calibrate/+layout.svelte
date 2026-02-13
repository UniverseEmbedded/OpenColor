<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();
  
  onMount(() => {
    navigationStore.toggleNav('calibrate');
  });
</script>

<div class="calibrate-layout">
  {@render children?.()}
</div>

<style>
  .calibrate-layout {
    height: 100%;
  }
</style>
