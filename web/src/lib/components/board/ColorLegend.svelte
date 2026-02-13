<script lang="ts">
  import type { ColorDef } from '$lib/types';

  interface Props {
    colors: ColorDef[];
  }

  let { colors }: Props = $props();
</script>

<div class="color-legend">
  {#each colors as color}
    <div class="legend-item">
      <div class="legend-color" style="background-color: rgb({color.r}, {color.g}, {color.b})"></div>
      <span class="legend-name">{color.name}</span>
    </div>
  {/each}
</div>

<style>
  .color-legend {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    justify-content: center;
    padding-top: 16px;
    border-top: 1px solid var(--line);
    width: 100%;
    box-sizing: border-box;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .legend-color {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid var(--line);
  }

  .legend-name {
    white-space: nowrap;
  }
</style>
