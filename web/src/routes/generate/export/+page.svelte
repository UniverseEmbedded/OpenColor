<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('generate/export');
  });
</script>

<Placeholder 
  title={$_('nav.generate.export')} 
  description="从SVG重建3D网格，导出STL和3MF格式"
  icon="ti-file-export"
/>
