<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('calibrate/model-train');
  });
</script>

<Placeholder 
  title={$_('nav.calibrate.modelTrain')} 
  description="使用RT光学模型+GPR训练颜色预测模型"
  icon="ti-brain"
/>
