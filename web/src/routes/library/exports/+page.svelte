<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('library/exports');
  });
</script>

<Placeholder 
  title={$_('nav.library.exports')} 
  description="叠色像素图、SVG、STL、3MF等生成结果"
  icon="ti-files"
/>
