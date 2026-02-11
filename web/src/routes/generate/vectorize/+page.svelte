<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('generate/vectorize');
  });
</script>

<Placeholder 
  title={$_('nav.generate.vectorize')} 
  description="将像素掩码转换为SVG矢量多边形"
  icon="ti-vector-bezier"
/>
