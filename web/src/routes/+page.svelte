<script lang="ts">
  import { onMount } from 'svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  
  // 默认跳转到校准板生成页面
  onMount(() => {
    navigationStore.setCurrentNav('calibrate/board-gen');
  });
</script>

<Placeholder 
  title="OpenColor" 
  description="基于Svelte 5 + Tauri 2的全新WebUI重构版本"
  icon="ti-color-swatch"
/>
