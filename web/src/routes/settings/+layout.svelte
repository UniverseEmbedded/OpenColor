<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';

  interface Props {
    children?: Snippet;
  }

  let { children }: Props = $props();
  
  onMount(() => {
    navigationStore.toggleNav('settings');
  });
</script>

<div class="settings-layout">
  {@render children?.()}
</div>

<style>
  .settings-layout {
    height: 100%;
  }
</style>
