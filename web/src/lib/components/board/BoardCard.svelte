<script lang="ts">
  import type { BoardItem, ColorProfile } from '$lib/types';

  interface Props {
    board: BoardItem;
    profile: ColorProfile | null;
    isActive?: boolean;
    onClick?: () => void;
  }

  let { board, profile, isActive = false, onClick }: Props = $props();

  // 优先使用生成时保存的耗材组颜色，如果没有则使用当前选中的耗材组
  const displayColors = $derived(board.profileColors || profile?.colors || []);
  const displayColorCount = $derived(displayColors.length);
</script>

<div class="board-card" class:active={isActive} onclick={onClick} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onClick?.()}>
  <div class="name">{board.name}</div>
  <div class="info">
    <span>颜色数: {displayColorCount}</span>
    <span>格子: {board.rows}×{board.cols}</span>
  </div>
  {#if displayColors.length > 0}
    <div class="color-preview">
      {#each displayColors.slice(0, 4) as color}
        <div class="color-dot" style="background-color: rgb({color.r}, {color.g}, {color.b})" title={color.name}></div>
      {/each}
      {#if displayColors.length > 4}
        <span class="more-colors">+{displayColors.length - 4}</span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .board-card {
    background: var(--panel);
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    border: 2px solid transparent;
    transition: all 0.2s;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .board-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
  }

  .board-card.active {
    border-color: var(--accent);
    background: var(--panel-elevated);
  }

  .name {
    font-weight: 600;
    font-size: 15px;
    color: var(--text);
    margin-bottom: 8px;
  }

  .info {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-bottom: 8px;
  }

  .info span {
    display: inline-block;
    margin-right: 12px;
  }

  .color-preview {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .color-dot {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid var(--line);
  }

  .more-colors {
    font-size: 11px;
    color: var(--text-muted);
  }
</style>
