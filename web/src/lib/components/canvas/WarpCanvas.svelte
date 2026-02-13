<script lang="ts">
  import type { Point } from '$lib/types';

  interface Props {
    imageUrl: string | null;
    cornerPoints: Point[];
    onPointsChange: (points: Point[]) => void;
    rows?: number;
    cols?: number;
  }

  let { 
    imageUrl, 
    cornerPoints, 
    onPointsChange, 
    rows = 17, 
    cols = 17 
  }: Props = $props();

  let canvas = $state<HTMLCanvasElement | null>(null);
  let ctx: CanvasRenderingContext2D | null = null;
  let image: HTMLImageElement | null = null;
  let isDragging = false;
  let dragIndex = -1;
  let scale = $state(1);

  // 初始化画布
  $effect(() => {
    if (canvas && !ctx) {
      ctx = canvas.getContext('2d');
    }
    
    if (imageUrl) {
      loadImage(imageUrl);
    }
  });

  // 当角点变化时重绘
  $effect(() => {
    if (ctx && image) {
      draw();
    }
  });

  function loadImage(url: string) {
    image = new Image();
    image.onload = () => {
      if (!canvas || !image) return;
      
      // 计算缩放比例，使图片适应画布
      const maxWidth = canvas.parentElement?.clientWidth || 800;
      const maxHeight = 600;
      
      scale = Math.min(
        maxWidth / image.naturalWidth,
        maxHeight / image.naturalHeight,
        1
      );
      
      canvas.width = image.naturalWidth * scale;
      canvas.height = image.naturalHeight * scale;
      
      // 如果没有角点，初始化默认角点
      if (cornerPoints.length === 0) {
        const defaultPoints: Point[] = [
          { x: image.naturalWidth * 0.2, y: image.naturalHeight * 0.2 },
          { x: image.naturalWidth * 0.8, y: image.naturalHeight * 0.2 },
          { x: image.naturalWidth * 0.8, y: image.naturalHeight * 0.8 },
          { x: image.naturalWidth * 0.2, y: image.naturalHeight * 0.8 }
        ];
        onPointsChange(defaultPoints);
      }
      
      draw();
    };
    image.src = url;
  }

  function draw() {
    if (!ctx || !canvas || !image) return;

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 绘制图片
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

    // 绘制网格预览
    if (cornerPoints.length === 4) {
      drawGridPreview();
    }

    // 绘制角点
    cornerPoints.forEach((point, index) => {
      drawCornerPoint(point, index);
    });

    // 绘制连接线
    if (cornerPoints.length > 1) {
      drawConnections();
    }
  }

  function drawCornerPoint(point: Point, index: number) {
    if (!ctx) return;

    const x = point.x * scale;
    const y = point.y * scale;
    const radius = 8;

    // 外圈
    ctx.beginPath();
    ctx.arc(x, y, radius + 2, 0, Math.PI * 2);
    ctx.fillStyle = 'white';
    ctx.fill();

    // 内圈
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = index === dragIndex ? '#00ff00' : '#005984';
    ctx.fill();

    // 序号
    ctx.fillStyle = 'white';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(index + 1), x, y);
  }

  function drawConnections() {
    if (!ctx || cornerPoints.length < 2) return;

    ctx.strokeStyle = 'rgba(0, 89, 132, 0.6)';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);

    ctx.beginPath();
    for (let i = 0; i < cornerPoints.length; i++) {
      const current = cornerPoints[i];
      
      if (i === 0) {
        ctx.moveTo(current.x * scale, current.y * scale);
      } else {
        ctx.lineTo(current.x * scale, current.y * scale);
      }
    }
    // 闭合路径
    if (cornerPoints.length > 0) {
      ctx.lineTo(cornerPoints[0].x * scale, cornerPoints[0].y * scale);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);
  }

  function drawGridPreview() {
    if (!ctx || cornerPoints.length !== 4) return;

    // 简单的网格预览 - 在实际应用中应该使用透视变换
    ctx.strokeStyle = 'rgba(0, 255, 0, 0.4)';
    ctx.lineWidth = 1;

    // 获取四边形边界
    const minX = Math.min(...cornerPoints.map(p => p.x * scale));
    const maxX = Math.max(...cornerPoints.map(p => p.x * scale));
    const minY = Math.min(...cornerPoints.map(p => p.y * scale));
    const maxY = Math.max(...cornerPoints.map(p => p.y * scale));

    // 绘制网格线
    for (let i = 0; i <= cols; i++) {
      const x = minX + (maxX - minX) * (i / cols);
      ctx.beginPath();
      ctx.moveTo(x, minY);
      ctx.lineTo(x, maxY);
      ctx.stroke();
    }

    for (let i = 0; i <= rows; i++) {
      const y = minY + (maxY - minY) * (i / rows);
      ctx.beginPath();
      ctx.moveTo(minX, y);
      ctx.lineTo(maxX, y);
      ctx.stroke();
    }
  }

  function handleMouseDown(event: MouseEvent) {
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / scale;
    const y = (event.clientY - rect.top) / scale;

    // 检查是否点击了现有角点
    const clickRadius = 15;
    dragIndex = cornerPoints.findIndex(p => 
      Math.abs(p.x - x) < clickRadius && Math.abs(p.y - y) < clickRadius
    );

    if (dragIndex !== -1) {
      isDragging = true;
    } else if (cornerPoints.length < 4) {
      // 添加新角点
      onPointsChange([...cornerPoints, { x, y }]);
    }
  }

  function handleMouseMove(event: MouseEvent) {
    if (!isDragging || dragIndex === -1 || !canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / scale;
    const y = (event.clientY - rect.top) / scale;

    const newPoints = [...cornerPoints];
    newPoints[dragIndex] = { x, y };
    onPointsChange(newPoints);
  }

  function handleMouseUp() {
    isDragging = false;
    dragIndex = -1;
  }

  function handleMouseLeave() {
    isDragging = false;
    dragIndex = -1;
  }
</script>

<div class="warp-canvas">
  {#if imageUrl}
    <canvas
      bind:this={canvas}
      onmousedown={handleMouseDown}
      onmousemove={handleMouseMove}
      onmouseup={handleMouseUp}
      onmouseleave={handleMouseLeave}
      class="canvas"
    ></canvas>
    <div class="hint">
      {#if cornerPoints.length < 4}
        点击画布添加角点 ({cornerPoints.length}/4)
      {:else}
        拖拽角点调整位置 (1:左上 2:右上 3:右下 4:左下)
      {/if}
    </div>
  {:else}
    <div class="placeholder">
      <i class="ti ti-photo"></i>
      <span>请先选择照片</span>
    </div>
  {/if}
</div>

<style>
  .warp-canvas {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .canvas {
    border: 2px solid var(--line);
    border-radius: 8px;
    cursor: crosshair;
    max-width: 100%;
    background: var(--bg);
  }

  .hint {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
  }

  .placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 100%;
    height: 400px;
    background: var(--panel);
    border: 2px dashed var(--line);
    border-radius: 8px;
    color: var(--text-muted);
  }

  .placeholder i {
    font-size: 48px;
    opacity: 0.5;
  }
</style>
