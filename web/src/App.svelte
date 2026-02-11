<script lang="ts">
  import { onMount } from "svelte";

  let count = $state(0);

  onMount(() => {
    console.log("[OpenColor] Svelte 应用已启动");
  });
</script>

<main>
  <h1>OpenColor</h1>
  <p>Svelte 5 重构版本</p>
  <button onclick={() => count++}>
    点击次数: {count}
  </button>
</main>

<style>
  main {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    gap: 1rem;
  }

  h1 {
    font-size: 2rem;
    color: var(--text, #e7edf5);
  }

  button {
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    background: var(--accent, #005984);
    color: white;
    border: none;
    cursor: pointer;
  }

  button:hover {
    opacity: 0.9;
  }
</style>
