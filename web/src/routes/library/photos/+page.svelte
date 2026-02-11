<script lang="ts">
  import { _ } from '$lib/i18n';
  import Placeholder from '$lib/components/ui/Placeholder.svelte';
  import { navigationStore } from '$lib/stores/navigation.svelte.ts';
  import { onMount } from 'svelte';
  
  onMount(() => {
    navigationStore.setCurrentNav('library/photos');
  });
</script>

<Placeholder 
  title={$_('nav.library.photos')} 
  description="管理的色盘照片和校正结果"
  icon="ti-photo"
/>
