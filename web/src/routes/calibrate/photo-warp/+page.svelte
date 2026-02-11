<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('calibrate/photo-warp');
  });
</script>

<Placeholder 
  title={$_('nav.calibrate.photoWarp')} 
  description="手动4点透视校正色盘照片，提取颜色样本"
  icon="ti-photo-edit"
/>
