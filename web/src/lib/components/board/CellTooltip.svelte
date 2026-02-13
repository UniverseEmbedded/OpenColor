<script lang="ts">
  import type { BoardCell, ColorDef } from '$lib/types';
  import { _ } from '$lib/i18n';

  interface Props {
    cell: BoardCell | null;
    colors: ColorDef[];
    x: number;
    y: number;
    visible: boolean;
    gridSize: number;
  }

  let { cell, colors, x, y, visible, gridSize }: Props = $props();

  // 获取颜色名称
  function getColorName(colorIndex: number): string {
    if (colorIndex >= 0 && colorIndex < colors.length) {
      return colors[colorIndex].name;
    }
    return `${$_('cellTooltip.color')}${colorIndex}`;
  }

  // 获取颜色定义
  function getColorDef(colorIndex: number): ColorDef | null {
    if (colorIndex >= 0 && colorIndex < colors.length) {
      return colors[colorIndex];
    }
    return null;
  }

  // 从配方中提取颜色索引数组
  function getRecipeColorIndices(): number[] {
    if (!cell?.recipe) return [];
    // recipe是Record<string, number>，键是层索引，值是颜色索引
    const indices: number[] = [];
    const entries = Object.entries(cell.recipe);
    // 按层排序
    entries.sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
    for (const [, colorIndex] of entries) {
      indices.push(colorIndex);
    }
    return indices;
  }

  // 判断是否是标记区
  function isMarker(): boolean {
    if (!cell) return false;
    const last = Math.max(0, gridSize - 1);
    const isBorder = cell.row === 0 || cell.row === last || cell.col === 0 || cell.col === last;
    if (!isBorder) return false;
    // 四个角是标记区
    const isCorner = (cell.row === 0 && cell.col === 0) ||
                     (cell.row === 0 && cell.col === last) ||
                     (cell.row === last && cell.col === last) ||
                     (cell.row === last && cell.col === 0);
    return isCorner;
  }

  // 判断是否是边框
  function isBorder(): boolean {
    if (!cell) return false;
    const last = Math.max(0, gridSize - 1);
    return cell.row === 0 || cell.row === last || cell.col === 0 || cell.col === last;
  }

  // 计算tooltip位置，防止超出屏幕
  function getPositionStyle(): string {
    let left = x + 10;
    let top = y + 10;
    
    // 简单的边界检查（假设tooltip最大宽度280px，高度200px）
    if (typeof window !== 'undefined') {
      if (left + 280 > window.innerWidth) {
        left = x - 290;
      }
      if (top + 200 > window.innerHeight) {
        top = y - 210;
      }
    }
    
    return `left: ${left}px; top: ${top}px`;
  }
</script>

{#if visible && cell}
  <div class="cell-tooltip" style={getPositionStyle()}
       role="tooltip">
    <div class="tooltip-title">{$_('cellTooltip.position')}: {$_('cellTooltip.row')}{cell.row + 1} {$_('cellTooltip.col')}{cell.col + 1}</div>

    <div class="tooltip-row">
      <span class="tooltip-label">{$_('cellTooltip.type')}:</span>
      <span class="tooltip-value">
        {#if isMarker()}
          {$_('cellTooltip.type.marker')}
        {:else if isBorder()}
          {$_('cellTooltip.type.border')}
        {:else}
          {$_('cellTooltip.type.data')}
        {/if}
      </span>
    </div>

    <div class="tooltip-row">
      <span class="tooltip-label">{$_('cellTooltip.targetRgb')}:</span>
      <span class="tooltip-value">{cell.targetRgb.r}, {cell.targetRgb.g}, {cell.targetRgb.b}</span>
    </div>

    {#if cell.recipe}
      <div class="tooltip-row">
        <span class="tooltip-label">{$_('cellTooltip.recipe')}:</span>
        <span class="tooltip-value">{getRecipeColorIndices().join(', ')}</span>
      </div>

      <div class="tooltip-row">
        <span class="tooltip-label">{$_('cellTooltip.layerSequence')}:</span>
        <span class="tooltip-value">{getRecipeColorIndices().map(i => getColorName(i)).join('-')}</span>
      </div>

      <div class="layers-visual">
        {#each getRecipeColorIndices() as colorIndex, i}
          {@const colorDef = getColorDef(colorIndex)}
          {#if colorDef}
            <div class="layer-dot"
                 style="background-color: rgb({colorDef.r}, {colorDef.g}, {colorDef.b})"
                 title="{colorDef.name} ({$_('cellTooltip.layer')}{i + 1})">
            </div>
          {/if}
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .cell-tooltip {
    position: fixed;
    background: rgba(0, 0, 0, 0.9);
    color: white;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 13px;
    pointer-events: none;
    z-index: 1000;
    max-width: 280px;
    line-height: 1.6;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  .tooltip-title {
    font-weight: 600;
    margin-bottom: 6px;
    color: #fff;
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    padding-bottom: 4px;
  }

  .tooltip-row {
    display: flex;
    justify-content: space-between;
    margin: 3px 0;
  }

  .tooltip-label {
    color: #aaa;
    margin-right: 12px;
  }

  .tooltip-value {
    color: #fff;
    font-family: 'Maple Mono Normal NF CN', monospace;
  }

  .layers-visual {
    display: flex;
    gap: 3px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
  }

  .layer-dot {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.3);
  }
</style>
