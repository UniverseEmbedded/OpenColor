<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('library/boards');
  });
</script>

<Placeholder 
  title={$_('nav.library.boards')} 
  description="管理的校准板规格文件和3MF文件"
  icon="ti-grid-dots"
/>
