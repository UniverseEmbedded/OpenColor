<script lang="ts">
  import type { BoardCell, ColorDef } from '$lib/types';

  interface Props {
    cells: BoardCell[];
    colors: ColorDef[];
    size?: 'small' | 'medium' | 'large';
    onCellHover?: (cell: BoardCell | null, event: MouseEvent) => void;
  }

  let { cells, colors, size = 'medium', onCellHover }: Props = $props();

  // 根据 size 设置最小格子尺寸（像素）
  const MIN_CELL_SIZE = $derived(() => {
    switch (size) {
      case 'small': return 8;
      case 'large': return 20;
      default: return 12;
    }
  });
  const GAP = 1;

  // 计算网格尺寸（支持矩形网格）
  const gridRows = $derived(() => {
    if (!cells || cells.length === 0) return 0;
    let maxRow = -1;
    for (const cell of cells) {
      if (cell.row > maxRow) maxRow = cell.row;
    }
    return maxRow + 1;
  });

  const gridCols = $derived(() => {
    if (!cells || cells.length === 0) return 0;
    let maxCol = -1;
    for (const cell of cells) {
      if (cell.col > maxCol) maxCol = cell.col;
    }
    return maxCol + 1;
  });

  const grid = $derived(() => {
    const result: (BoardCell | null)[][] = [];
    const rows = gridRows();
    const cols = gridCols();
    if (rows === 0 || cols === 0 || !cells) return result;
    for (let row = 0; row < rows; row++) {
      const rowCells: (BoardCell | null)[] = [];
      for (let col = 0; col < cols; col++) {
        const cell = cells.find(c => c.row === row && c.col === col);
        rowCells.push(cell || null);
      }
      result.push(rowCells);
    }
    return result;
  });

  function handleMouseEnter(cell: BoardCell | null, event: MouseEvent) {
    if (onCellHover && cell) {
      onCellHover(cell, event);
    }
  }

  function handleMouseLeave() {
    if (onCellHover) {
      onCellHover(null, new MouseEvent('mouseleave'));
    }
  }

  function getCellStyle(cell: BoardCell | null): string {
    if (!cell) return '';
    
    // 优先使用 targetRgb
    if (cell.targetRgb) {
      const { r, g, b } = cell.targetRgb;
      return `background-color: rgb(${r}, ${g}, ${b})`;
    }
    
    // 如果没有 targetRgb，尝试从 recipe 和 colors 计算
    const entries = Object.entries(cell.recipe || {});
    if (entries.length === 0 || !colors || colors.length === 0) return '';
    
    entries.sort((a, b) => Number(a[0]) - Number(b[0]));
    const last = entries[entries.length - 1];
    const idx = Math.round(Number(last?.[1] ?? 0));
    const c = colors[idx] || colors[0];
    if (!c) return '';
    
    return `background-color: rgb(${c.r}, ${c.g}, ${c.b})`;
  }

  function isBorderCell(cell: BoardCell | null): boolean {
    if (!cell) return false;
    return cell.row === 0 || cell.row === gridRows() - 1 || 
           cell.col === 0 || cell.col === gridCols() - 1;
  }
</script>

<div class="board-grid-wrapper">
  <div 
    class="board-grid-container" 
    style="--min-cell-size: {MIN_CELL_SIZE()}px; --gap: {GAP}px; --grid-rows: {gridRows()}; --grid-cols: {gridCols()};"
  >
    <div class="grid">
      {#each grid() as row, rowIndex}
        {#each row as cell, colIndex}
          <div
            class="grid-cell"
            class:border-cell={isBorderCell(cell)}
            style={getCellStyle(cell)}
            data-row={rowIndex}
            data-col={colIndex}
            role="button"
            tabindex="0"
            onmouseenter={(e) => handleMouseEnter(cell, e)}
            onmouseleave={handleMouseLeave}
          ></div>
        {/each}
      {/each}
    </div>
  </div>
</div>

<style>
  .board-grid-wrapper {
    width: 100%;
    height: 100%;
    overflow: auto;
    display: flex;
    justify-content: center;
    align-items: center;
  }

  .board-grid-wrapper::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  .board-grid-wrapper::-webkit-scrollbar-track {
    background: var(--bg);
    border-radius: 4px;
  }

  .board-grid-wrapper::-webkit-scrollbar-thumb {
    background: var(--line);
    border-radius: 4px;
  }

  .board-grid-wrapper::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
  }

  .board-grid-container {
    background: var(--line);
    padding: var(--gap);
    border-radius: 4px;
    /* 使用容器查询或基于父容器尺寸计算 */
    width: 100%;
    height: 100%;
    max-width: min(
      calc(100% - 16px),
      calc((100vh - 300px))
    );
    max-height: min(
      calc(100% - 16px),
      calc(100vh - 300px)
    );
    aspect-ratio: 1 / 1;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(var(--grid-cols), minmax(var(--min-cell-size), 1fr));
    grid-template-rows: repeat(var(--grid-rows), minmax(var(--min-cell-size), 1fr));
    gap: var(--gap);
    width: 100%;
    height: 100%;
  }

  .grid-cell {
    width: 100%;
    height: 100%;
    min-width: var(--min-cell-size);
    min-height: var(--min-cell-size);
    cursor: pointer;
    position: relative;
    transition: transform 0.1s;
  }

  .grid-cell:hover {
    transform: scale(1.3);
    z-index: 10;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .grid-cell.border-cell {
    border: 1px solid rgba(0, 0, 0, 0.1);
  }
</style>
