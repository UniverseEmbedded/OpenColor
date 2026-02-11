<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('generate/mask-gen');
  });
</script>

<Placeholder 
  title={$_('nav.generate.maskGen')} 
  description="基于训练好的模型计算每个像素的颜色配方"
  icon="ti-layers-intersect"
/>
