<template>
  <div class="screen-calibrator" v-if="visible">
    <div id="stage" ref="stageRef">
      <canvas id="cv" ref="canvasRef" @pointerdown="onPointerDown" @wheel.prevent="onWheel"></canvas>
    </div>

    <div id="hud" ref="hudRef" :class="{ hidden: hudHidden }" :style="hudStyle">
      <div id="hudHeader" @pointerdown="hudDown">
        <div id="hudTitle">{{ $t('screenCalib.title') }}</div>
        <div class="pill" id="hdrBadge">{{ hdrBadgeText }}</div>
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.mode') }}</label>
        <select v-model="state.mode">
          <option value="sdr">{{ $t('screenCalib.sdrTip') }}</option>
          <option value="hdr">{{ $t('screenCalib.hdrDetect') }}</option>
        </select>
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.pattern') }}</label>
        <select v-model="state.pattern">
          <option value="continuous">{{ $t('screenCalib.continuous') }}</option>
          <option value="steps16">{{ $t('screenCalib.steps16') }}</option>
          <option value="both">{{ $t('screenCalib.both') }}</option>
        </select>
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.color') }}</label>
        <select v-model="state.color">
          <option value="white">{{ $t('screenCalib.white') }}</option>
          <option value="red">{{ $t('screenCalib.red') }}</option>
          <option value="green">{{ $t('screenCalib.green') }}</option>
          <option value="blue">{{ $t('screenCalib.blue') }}</option>
        </select>
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.widthPct') }}</label>
        <input v-model.number="state.widthPct" type="range" min="5" max="100" step="1" />
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.heightPct') }}</label>
        <input v-model.number="state.heightPct" type="range" min="5" max="100" step="1" />
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.showFrame') }}</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <label style="display:flex; gap:6px; align-items:center; cursor:pointer;">
            <input v-model="state.showFrame" type="checkbox" />
            <span>{{ $t('screenCalib.on') }}</span>
          </label>
          <label style="display:flex; gap:6px; align-items:center; cursor:pointer;">
            <input v-model="state.invert" type="checkbox" />
            <span>{{ $t('screenCalib.invert') }}</span>
          </label>
        </div>
      </div>

      <div class="row">
        <label>{{ $t('screenCalib.interaction') }}</label>
        <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
          <label style="display:flex; gap:6px; align-items:center; cursor:pointer;">
            <input v-model="state.rectLocked" type="checkbox" />
            <span>{{ $t('screenCalib.lockRect') }}</span>
          </label>
          <label style="display:flex; gap:6px; align-items:center; cursor:pointer;">
            <input v-model="state.hudLocked" type="checkbox" />
            <span>{{ $t('screenCalib.lockHud') }}</span>
          </label>
        </div>
      </div>

      <div class="btnRow">
        <button @click="toggleFullscreen">{{ $t('screenCalib.enterFullscreen') }}</button>
        <button @click="hudHidden = true">{{ $t('screenCalib.hideHud') }}</button>
        <button @click="reset">{{ $t('screenCalib.reset') }}</button>
        <button @click="$emit('close')" class="close-btn">{{ $t('screenCalib.exit') }}</button>
      </div>

    <div id="status" v-html="statusHtml"></div>
    </div>

    <button v-if="hudHidden" class="show-hud-btn" @click="hudHidden = false">
      {{ $t('screenCalib.showHud') }}
    </button>

    <div id="hint" v-if="!hudHidden">
      {{ $t('screenCalib.hint.action') }}
      <kbd>{{ $t('screenCalib.hint.dragRect') }}</kbd>{{ $t('screenCalib.hint.movePos') }}
      <kbd>{{ $t('screenCalib.hint.dragHandle') }}</kbd>{{ $t('screenCalib.hint.resizeSize') }}
      <kbd>{{ $t('screenCalib.hint.mouseWheel') }}</kbd>{{ $t('screenCalib.hint.wheelTip') }}
      <kbd>{{ $t('screenCalib.hint.fullscreen') }}</kbd>{{ $t('screenCalib.hint.fullscreenTip') }}
      <kbd>{{ $t('screenCalib.hint.toggleHud') }}</kbd>{{ $t('screenCalib.hint.toggleHudTip') }}
      <kbd>{{ $t('screenCalib.hint.reset') }}</kbd>{{ $t('screenCalib.hint.resetTip') }}
      <kbd>{{ $t('screenCalib.hint.switchColor') }}</kbd>{{ $t('screenCalib.hint.switchColorTip') }}
      <kbd>{{ $t('screenCalib.hint.exit') }}</kbd>{{ $t('screenCalib.hint.exitTip') }}
      <br/>{{ $t('screenCalib.hint.photoTip') }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, computed, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  visible: Boolean
});

const emit = defineEmits(['close']);
const { t } = useI18n();

const canvasRef = ref(null);
const hudRef = ref(null);
const hudHidden = ref(false);
const hdrBadgeText = ref(t('screenCalib.hdrBadge.detecting'));

const hudPos = reactive({ left: 12, top: 12 });
const hudStyle = computed(() => ({
  left: `${hudPos.left}px`,
  top: `${hudPos.top}px`
}));

const state = reactive({
  W: 0, H: 0, dpr: 1,
  rect: { x: 0, y: 0, w: 0, h: 0 },
  widthPct: 80,
  heightPct: 45,
  pattern: 'continuous',
  color: 'white',
  mode: 'sdr',
  showFrame: true,
  invert: false,
  dynamicRangeHigh: false,
  gamutP3: false,
  gamut2020: false,
  rectLocked: false,
  hudLocked: false
});

let ctx = null;

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const ptInRect = (px, py, r) => px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h;

function getHandles(r) {
  const x0 = r.x, y0 = r.y, x1 = r.x + r.w, y1 = r.y + r.h, xm = x0 + r.w / 2, ym = y0 + r.h / 2;
  return [
    { id: 'nw', x: x0, y: y0 }, { id: 'n', x: xm, y: y0 }, { id: 'ne', x: x1, y: y0 },
    { id: 'w', x: x0, y: ym }, { id: 'e', x: x1, y: ym },
    { id: 'sw', x: x0, y: y1 }, { id: 's', x: xm, y: y1 }, { id: 'se', x: x1, y: y1 },
  ];
}

function hitHandle(px, py, r) {
  const handles = getHandles(r);
  const rad = 10;
  for (const h of handles) {
    if (Math.hypot(px - h.x, py - h.y) <= rad) return h.id;
  }
  return null;
}

function resize() {
  state.dpr = Math.max(1, Math.floor(window.devicePixelRatio || 1));
  state.W = window.innerWidth;
  state.H = window.innerHeight;
  if (canvasRef.value) {
    const cv = canvasRef.value;
    cv.width = state.W * state.dpr;
    cv.height = state.H * state.dpr;
    cv.style.width = state.W + 'px';
    cv.style.height = state.H + 'px';
    ctx = cv.getContext('2d', { alpha: false });
    ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
  }
  state.rect.x = clamp(state.rect.x, 0, state.W - state.rect.w);
  state.rect.y = clamp(state.rect.y, 0, state.H - state.rect.h);
  render();
}

function detectHDR() {
  state.dynamicRangeHigh = !!window.matchMedia?.('(dynamic-range: high)')?.matches;
  state.gamutP3 = !!window.matchMedia?.('(color-gamut: p3)')?.matches;
  state.gamut2020 = !!window.matchMedia?.('(color-gamut: rec2020)')?.matches;

  let badge = t('screenCalib.hdrBadge.sdr');
  if (state.dynamicRangeHigh) badge = t('screenCalib.hdrBadge.hdrSuspected');
  if (state.dynamicRangeHigh && state.gamut2020) badge = t('screenCalib.hdrBadge.hdrRec2020');
  else if (state.dynamicRangeHigh && state.gamutP3) badge = t('screenCalib.hdrBadge.hdrP3');
  hdrBadgeText.value = badge;
}

function getColor(v, colorName) {
  if (colorName === 'red') return `rgb(${v},0,0)`;
  if (colorName === 'green') return `rgb(0,${v},0)`;
  if (colorName === 'blue') return `rgb(0,0,${v})`;
  return `rgb(${v},${v},${v})`;
}

function drawContinuousGradient(x, y, w, h, invert, colorName) {
  const g = ctx.createLinearGradient(x, 0, x + w, 0);
  if (!invert) {
    g.addColorStop(0, getColor(0, colorName));
    g.addColorStop(1, getColor(255, colorName));
  } else {
    g.addColorStop(0, getColor(255, colorName));
    g.addColorStop(1, getColor(0, colorName));
  }
  ctx.fillStyle = g;
  ctx.fillRect(x, y, w, h);
}

function drawSteps16(x, y, w, h, invert, colorName) {
  const n = 16, bw = w / n;
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    const v = invert ? Math.round(255 * (1 - t)) : Math.round(255 * t);
    ctx.fillStyle = getColor(v, colorName);
    ctx.fillRect(x + i * bw, y, Math.ceil(bw + 1), h);
  }
}

function drawFrame(r) {
  ctx.save();
  // 1. 绘制矩形边框（保持在最上层）
  ctx.lineWidth = 3;
  ctx.strokeStyle = 'rgba(255,255,255,0.90)';
  ctx.strokeRect(r.x + 0.5, r.y + 0.5, r.w - 1, r.h - 1);

  // 2. 准备绘制控制点，使用剪裁确保不遮挡矩形内部
  ctx.setLineDash([]);
  const handles = getHandles(r);

  ctx.save(); // 为剪裁创建子状态
  ctx.beginPath();
  // 覆盖全屏的大矩形
  ctx.rect(0, 0, state.W, state.H);
  // 挖掉中间的矩形（逆时针绘制实现挖空）
  ctx.moveTo(r.x, r.y);
  ctx.lineTo(r.x, r.y + r.h);
  ctx.lineTo(r.x + r.w, r.y + r.h);
  ctx.lineTo(r.x + r.w, r.y);
  ctx.closePath();
  ctx.clip();

  for (const h of handles) {
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.beginPath(); ctx.arc(h.x, h.y, 9, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(h.x, h.y, 9, 0, Math.PI * 2); ctx.stroke();
  }
  ctx.restore(); // 恢复剪裁之前的状态

  ctx.restore();
}

function render() {
  if (!ctx) return;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, state.W, state.H);
  const r = state.rect;
  // 先画渐变，再画边框和控制点，确保边框在最上层且不被遮挡
  if (state.pattern === 'continuous') {
    drawContinuousGradient(r.x, r.y, r.w, r.h, state.invert, state.color);
  } else if (state.pattern === 'steps16') {
    drawSteps16(r.x, r.y, r.w, r.h, state.invert, state.color);
  } else {
    const hTop = Math.round(r.h * 0.42);
    const gap = Math.max(10, Math.round(r.h * 0.04));
    const hBot = r.h - hTop - gap;
    drawSteps16(r.x, r.y, r.w, hTop, state.invert, state.color);
    drawContinuousGradient(r.x, r.y + hTop + gap, r.w, hBot, state.invert, state.color);
  }
  if (state.showFrame) drawFrame(r);
}

const statusHtml = computed(() => {
  const dr = state.dynamicRangeHigh ? t('screenCalib.status.hdrPossible') : t('screenCalib.status.hdrNone');
  const gamut = state.gamut2020 ? t('screenCalib.status.rec2020') : (state.gamutP3 ? t('screenCalib.status.p3') : t('screenCalib.status.srgb'));
  const rec = (state.mode === 'sdr')
    ? t('screenCalib.status.sdrRec')
    : t('screenCalib.status.hdrRec');

  return `${t('screenCalib.status.detect')}<b>${dr}</b>, ${t('screenCalib.status.gamut')}<b>${gamut}</b><br/>` +
    `${t('screenCalib.status.rect')}x=${Math.round(state.rect.x)}, y=${Math.round(state.rect.y)}, w=${Math.round(state.rect.w)}, h=${Math.round(state.rect.h)} ${t('screenCalib.status.pixels')}<br/>` +
    `${rec}`;
});

function rectFromPercents(centered = true) {
  const w = Math.round(state.W * state.widthPct / 100);
  const h = Math.round(state.H * state.heightPct / 100);
  if (centered) {
    state.rect.w = w; state.rect.h = h;
    state.rect.x = Math.round((state.W - w) / 2);
    state.rect.y = Math.round((state.H - h) / 2);
  } else {
    const cx = state.rect.x + state.rect.w / 2;
    const cy = state.rect.y + state.rect.h / 2;
    state.rect.w = w; state.rect.h = h;
    state.rect.x = clamp(cx - w / 2, 0, state.W - w);
    state.rect.y = clamp(cy - h / 2, 0, state.H - h);
  }
}

function percentsFromRect() {
  state.widthPct = clamp(Math.round((state.rect.w / state.W) * 100), 5, 100);
  state.heightPct = clamp(Math.round((state.rect.h / state.H) * 100), 5, 100);
}

function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
}

function reset() {
  state.mode = 'sdr';
  state.pattern = 'continuous';
  state.color = 'white';
  state.showFrame = true;
  state.invert = false;
  state.rectLocked = false;
  state.hudLocked = false;
  state.widthPct = 80;
  state.heightPct = 45;
  rectFromPercents(true);
  render();
}

const drag = reactive({
  active: false,
  kind: null,
  startX: 0, startY: 0,
  startRect: null
});

function onPointerDown(e) {
  if (state.rectLocked) return;
  const px = e.clientX, py = e.clientY;
  const r = state.rect;
  const handle = state.showFrame ? hitHandle(px, py, r) : null;
  if (handle) {
    drag.active = true;
    drag.kind = handle;
    drag.startX = px; drag.startY = py;
    drag.startRect = { ...r };
    canvasRef.value.setPointerCapture(e.pointerId);
    return;
  }
  if (ptInRect(px, py, r)) {
    drag.active = true;
    drag.kind = 'move';
    drag.startX = px; drag.startY = py;
    drag.startRect = { ...r };
    canvasRef.value.setPointerCapture(e.pointerId);
  }
}

function onPointerMove(e) {
  if (!drag.active) return;
  const px = e.clientX, py = e.clientY;
  const dx = px - drag.startX, dy = py - drag.startY;
  if (drag.kind === 'move') {
    const r0 = drag.startRect;
    state.rect.x = clamp(r0.x + dx, 0, state.W - r0.w);
    state.rect.y = clamp(r0.y + dy, 0, state.H - r0.h);
  } else {
    resizeRectByHandle(drag.kind, dx, dy);
  }
  percentsFromRect();
  render();
}

function resizeRectByHandle(handle, dx, dy) {
  const r0 = drag.startRect;
  let x = r0.x, y = r0.y, w = r0.w, h = r0.h;
  const minW = Math.max(40, state.W * 0.05);
  const minH = Math.max(40, state.H * 0.05);
  const left = (handle === 'w' || handle === 'nw' || handle === 'sw');
  const right = (handle === 'e' || handle === 'ne' || handle === 'se');
  const top = (handle === 'n' || handle === 'nw' || handle === 'ne');
  const bottom = (handle === 's' || handle === 'sw' || handle === 'se');
  if (left) { x = r0.x + dx; w = r0.w - dx; }
  if (right) { w = r0.w + dx; }
  if (top) { y = r0.y + dy; h = r0.h - dy; }
  if (bottom) { h = r0.h + dy; }
  w = clamp(w, minW, state.W);
  h = clamp(h, minH, state.H);
  if (left) x = r0.x + (r0.w - w);
  if (top) y = r0.y + (r0.h - h);
  x = clamp(x, 0, state.W - w);
  y = clamp(y, 0, state.H - h);
  state.rect.x = x; state.rect.y = y; state.rect.w = w; state.rect.h = h;
}

function onPointerUp() {
  drag.active = false;
  drag.kind = null;
}

function onWheel(e) {
  if (state.rectLocked) return;
  const px = e.clientX, py = e.clientY;
  if (!ptInRect(px, py, state.rect)) return;
  const step = (e.deltaY > 0) ? -10 : 10;
  const r = state.rect;
  const cy = r.y + r.h / 2;
  let newH = clamp(r.h + step, Math.max(40, state.H * 0.05), state.H);
  let newY = clamp(cy - newH / 2, 0, state.H - newH);
  state.rect.h = newH;
  state.rect.y = newY;
  percentsFromRect();
  render();
}

const hudDrag = reactive({ active: false, ox: 0, oy: 0, startL: 0, startT: 0 });
function hudDown(e) {
  if (state.hudLocked) return;
  hudDrag.active = true;
  hudDrag.startL = hudPos.left;
  hudDrag.startT = hudPos.top;
  hudDrag.ox = e.clientX;
  hudDrag.oy = e.clientY;
}

function hudMove(e) {
  if (!hudDrag.active) return;
  const dx = e.clientX - hudDrag.ox;
  const dy = e.clientY - hudDrag.oy;
  hudPos.left = clamp(hudDrag.startL + dx, 0, window.innerWidth - (hudRef.value?.offsetWidth || 0));
  hudPos.top = clamp(hudDrag.startT + dy, 0, window.innerHeight - (hudRef.value?.offsetHeight || 0));
}

function hudUp() {
  hudDrag.active = false;
}

const onKeydown = (e) => {
  const k = e.key.toLowerCase();
  if (k === 'f') toggleFullscreen();
  if (k === 'h') hudHidden.value = !hudHidden.value;
  if (k === 'r' && !e.ctrlKey) reset();
  if (k === '1') state.color = 'white';
  if (k === '2') state.color = 'red';
  if (k === '3') state.color = 'green';
  if (k === '4') state.color = 'blue';
  if (k === 'escape') emit('close');
};

watch(() => [state.mode, state.pattern, state.color, state.widthPct, state.heightPct, state.showFrame, state.invert], () => {
  if (state.widthPct !== clamp(Math.round((state.rect.w / state.W) * 100), 5, 100) || 
      state.heightPct !== clamp(Math.round((state.rect.h / state.H) * 100), 5, 100)) {
    rectFromPercents(false);
  }
  render();
});

watch(() => props.visible, async (val) => {
  if (!val) return;
  await nextTick();
  detectHDR();
  resize();
  if (!state.rect.w || !state.rect.h) {
    rectFromPercents(true);
  }
  percentsFromRect();
  render();
});

onMounted(() => {
  detectHDR();
  resize();
  rectFromPercents(true);
  percentsFromRect();
  render(); // 确保初始矩形正确渲染
  window.addEventListener('resize', resize);
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointermove', hudMove);
  window.addEventListener('pointerup', hudUp);
  window.addEventListener('keydown', onKeydown);
});

onUnmounted(() => {
  window.removeEventListener('resize', resize);
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerup', onPointerUp);
  window.removeEventListener('pointermove', hudMove);
  window.removeEventListener('pointerup', hudUp);
  window.removeEventListener('keydown', onKeydown);
});
</script>

<style scoped>
.screen-calibrator {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #000;
  color: rgba(255, 255, 255, 0.92);
  font-family: var(--sans);
}

#stage {
  position: absolute;
  inset: 0;
  overflow: hidden;
  touch-action: none;
  user-select: none;
}

canvas {
  display: block;
}

#hud {
  position: absolute;
  width: min(520px, calc(100vw - 24px));
  background: rgba(20, 20, 20, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  padding: 10px 12px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  cursor: default;
}

#hud.hidden {
  display: none;
}

#hudHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px;
  margin: -4px -6px 6px -6px;
  border-radius: 10px;
  cursor: grab;
}

#hudHeader:active {
  cursor: grabbing;
}

#hudTitle {
  font-size: 14px;
  font-weight: 650;
  letter-spacing: .2px;
}

.pill {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(0, 0, 0, 0.25);
  color: rgba(255, 255, 255, 0.7);
  white-space: nowrap;
}

.row {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 10px;
  align-items: center;
  margin: 7px 0;
}

label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

input[type="range"] {
  width: 100%;
}

select,
button {
  font-size: 12px;
}

select {
  width: 100%;
  border-radius: 10px;
  padding: 7px 10px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(0, 0, 0, 0.35);
  color: rgba(255, 255, 255, 0.92);
  outline: none;
}

button {
  border-radius: 12px;
  padding: 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.20);
  background: rgba(0, 0, 0, 0.35);
  color: rgba(255, 255, 255, 0.92);
  cursor: pointer;
}

button:hover {
  border-color: rgba(255, 255, 255, 0.35);
}

.btnRow {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

#status {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 8px;
  line-height: 1.35;
}

#status b {
  color: rgba(255, 255, 255, 0.92);
}

#hint {
  position: fixed;
  right: 12px;
  bottom: 12px;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 12px;
  padding: 10px 12px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  max-width: min(560px, calc(100vw - 24px));
}

#hint kbd {
  font-family: var(--mono);
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.10);
  margin: 0 2px;
}

.close-btn {
  background: rgba(255, 80, 80, 0.3);
  border-color: rgba(255, 80, 80, 0.5);
}

.close-btn:hover {
  background: rgba(255, 80, 80, 0.5);
  border-color: rgba(255, 80, 80, 0.7);
}

.show-hud-btn {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  z-index: 10000;
  padding: 10px 20px;
  background: rgba(20, 20, 20, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 12px;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.2s;
}

.show-hud-btn:hover {
  background: rgba(40, 40, 40, 0.9);
  border-color: rgba(255, 255, 255, 0.5);
  transform: translateX(-50%) translateY(-2px);
}
</style>
