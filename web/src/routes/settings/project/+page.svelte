<script lang="ts">
  import { _ } from '$lib/i18n';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('settings/project');
  });
</script>

<Placeholder 
  title={$_('settings.project.title')} 
  description="项目设置功能开发中"
  icon="ti-config"
/>
