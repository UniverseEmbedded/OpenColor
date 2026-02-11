<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('library/models');
  });
</script>

<Placeholder 
  title={$_('nav.library.models')} 
  description="训练好的RT+GPR颜色预测模型"
  icon="ti-cube"
/>
