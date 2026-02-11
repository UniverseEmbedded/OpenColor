<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('library/materials');
  });
</script>

<Placeholder 
  title={$_('nav.library.materials')} 
  description="耗材配置和材料组管理"
  icon="ti-palette"
/>
