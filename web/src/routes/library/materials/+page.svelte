<script lang="ts">
  import { onMount } from 'svelte';
  import { navigate } from '$lib/stores/router.svelte';

  onMount(() => {
    navigate('library/materials/profiles');
  });
</script>

<div class="redirecting">
  <i class="ti ti-loader-2 spinning"></i>
  <span>Redirecting...</span>
</div>

<style>
  .redirecting {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    height: 100%;
    color: var(--text-muted);
  }

  .spinning {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
