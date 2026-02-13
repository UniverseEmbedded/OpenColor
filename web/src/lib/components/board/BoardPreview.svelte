<script lang="ts">
  import type { BoardCell, ColorProfile } from '$lib/types';
  import BoardGrid from './BoardGrid.svelte';
  import CellTooltip from './CellTooltip.svelte';
  import ColorLegend from './ColorLegend.svelte';

  interface Props {
    cells?: BoardCell[];
    profile?: ColorProfile | null;
    size?: 'small' | 'medium' | 'large';
    showLegend?: boolean;
  }

  let { cells = [], profile = null, size = 'medium', showLegend = true }: Props = $props();

  // Tooltip状态
  let tooltipCell = $state<BoardCell | null>(null);
  let tooltipX = $state(0);
  let tooltipY = $state(0);
  let tooltipVisible = $state(false);
  const gridSize = $derived(() => {
    if (cells.length === 0) return 0;
    let maxRow = -1;
    let maxCol = -1;
    for (const cell of cells) {
      if (cell.row > maxRow) maxRow = cell.row;
      if (cell.col > maxCol) maxCol = cell.col;
    }
    return Math.max(maxRow, maxCol) + 1;
  });
  const gridSizeValue = $derived(gridSize());

  function handleCellHover(cell: BoardCell | null, event: MouseEvent) {
    if (cell) {
      tooltipCell = cell;
      tooltipX = event.clientX;
      tooltipY = event.clientY;
      tooltipVisible = true;
    } else {
      tooltipVisible = false;
    }
  }
</script>

<div class="board-preview">
  <BoardGrid 
    {cells} 
    colors={profile?.colors || []} 
    {size} 
    onCellHover={handleCellHover}
  />
  
  {#if showLegend && profile}
    <ColorLegend colors={profile.colors} />
  {/if}
</div>

<CellTooltip 
  cell={tooltipCell} 
  colors={profile?.colors || []} 
  x={tooltipX} 
  y={tooltipY} 
  visible={tooltipVisible}
  gridSize={gridSizeValue}
/>

<style>
  .board-preview {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
    padding: 16px;
    background: var(--panel);
    border-radius: 12px;
    border: 1px solid var(--line);
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
  }
</style>
