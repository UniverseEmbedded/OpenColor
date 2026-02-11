<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('settings/workspace');
  });
</script>

<Placeholder 
  title={$_('settings.workspace.title')} 
  description="工作区管理功能开发中"
  icon="ti-folder"
/>
