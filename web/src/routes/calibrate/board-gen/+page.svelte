<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('calibrate/board-gen');
  });
</script>

<Placeholder 
  title={$_('nav.calibrate.boardGen')} 
  description="生成8色校准板的规格文件和3MF打印文件"
  icon="ti-grid-dots"
/>
