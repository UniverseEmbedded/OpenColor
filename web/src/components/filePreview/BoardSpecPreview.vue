<template>
  <div class="board-spec">
    <div class="board-spec-hd">
      <div class="board-spec-title">
        <i class="ti ti-grid-pattern"></i>
        <span>色盘规格</span>
      </div>
      <div class="board-spec-meta">
        <span class="pill"><i class="ti ti-layout-grid"></i>{{ boardSpec.rows }}×{{ boardSpec.cols }}</span>
        <span v-if="boardSpec.print_profile?.layers" class="pill"><i class="ti ti-layers"></i>{{ boardSpec.print_profile.layers }} 层</span>
        <span v-if="boardSpec.cell_size_mm" class="pill"><i class="ti ti-ruler"></i>{{ boardSpec.cell_size_mm }}mm</span>
      </div>
    </div>

    <div class="board-spec-grid">
      <div class="info">
        <div class="kv">
          <div class="k">名称</div>
          <div class="v">{{ boardSpec.name || '-' }}</div>
        </div>
        <div class="kv">
          <div class="k">ID</div>
          <div class="v mono" style="word-break:break-all">{{ boardSpec.board_id || '-' }}</div>
        </div>
        <div class="kv" v-if="boardSpec.print_profile?.layer_height_mm">
          <div class="k">层高</div>
          <div class="v">{{ boardSpec.print_profile.layer_height_mm }}mm</div>
        </div>
        <div class="kv" v-if="boardSpec.print_profile?.total_size_mm">
          <div class="k">总尺寸</div>
          <div class="v">{{ boardSpec.print_profile.total_size_mm[0] }}×{{ boardSpec.print_profile.total_size_mm[1] }}mm</div>
        </div>
        <div class="kv" v-if="boardSpec.markers">
          <div class="k">标记点</div>
          <div class="v mono">TL {{ formatMarker(boardSpec.markers?.TL) }} / TR {{ formatMarker(boardSpec.markers?.TR) }} / BR {{ formatMarker(boardSpec.markers?.BR) }} / BL {{ formatMarker(boardSpec.markers?.BL) }}</div>
        </div>
      </div>

      <div class="cells" v-if="boardSpecCells">
        <div class="cells-title"><i class="ti ti-squares"></i>格子配方（仅展示数据区）</div>
        <div class="cells-scroll">
          <div class="cells-grid" :style="{ gridTemplateColumns: `repeat(${boardSpecCells.cols}, 1fr)` }">
            <button
              v-for="cell in boardSpecCells.cells"
              :key="cell.key"
              class="cell"
              type="button"
              :title="cell.tooltip"
            >
              <div class="cell-idx">{{ cell.recipeIndex }}</div>
            </button>
          </div>
        </div>
      </div>
    </div>

    <details class="raw-json" style="margin-top:12px">
      <summary><i class="ti ti-file-code"></i>原始 JSON</summary>
      <pre class="mono" style="margin:0; white-space:pre-wrap"><code>{{ rawContent }}</code></pre>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  boardSpec: {
    type: Object,
    required: true
  },
  rawContent: {
    type: String,
    default: ''
  }
});

const formatMarker = (p) => {
  if (!p || !Array.isArray(p) || p.length < 2) return "-";
  return `(${p[0]},${p[1]})`;
};

const boardSpecCells = computed(() => {
  const spec = props.boardSpec;
  if (!spec) return null;
  const cellMap = spec.cell_map;
  if (!cellMap || typeof cellMap !== 'object') return null;

  const rows = Number(spec.rows || 0);
  const cols = Number(spec.cols || 0);

  const isCore17 = rows === 17 && cols === 17;
  const r0 = isCore17 ? 1 : 0;
  const c0 = isCore17 ? 1 : 0;
  const r1 = isCore17 ? 15 : Math.min(rows - 1, 19);
  const c1 = isCore17 ? 15 : Math.min(cols - 1, 19);

  const out = [];
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) {
      const key = `${r},${c}`;
      const raw = cellMap[key] || null;
      const idx = raw && typeof raw === 'object' ? raw.recipe_index : null;
      const layers = raw && typeof raw === 'object' ? raw.layers : null;
      const slotNames = raw && typeof raw === 'object' ? raw.slot_names : null;

      const recipeIndex = (idx === 0 || idx) ? String(idx) : "";
      const layerText = Array.isArray(slotNames) ? slotNames.join(' / ') : (Array.isArray(layers) ? layers.join(' ') : "");
      const tooltip = layerText ? `${key}\n${layerText}` : key;
      out.push({ key, recipeIndex: recipeIndex || '-', tooltip });
    }
  }

  return { rows: (r1 - r0 + 1), cols: (c1 - c0 + 1), cells: out };
});
</script>

<style scoped>
.board-spec-hd {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.board-spec-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}

.board-spec-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.board-spec-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.board-spec-grid .info {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  background: var(--bg-alpha2);
  border: 1px solid var(--border-alpha);
  border-radius: 12px;
  padding: 12px;
}

.board-spec-grid .kv {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 10px;
  align-items: baseline;
}

.board-spec-grid .k {
  color: var(--muted);
  font-size: 12px;
}

.board-spec-grid .v {
  color: var(--text);
  font-size: 13px;
}

.cells-title {
  font-size: 12px;
  color: var(--muted);
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 0 0 8px 0;
}

.cells-scroll {
  overflow: auto;
  border: 1px solid var(--border-alpha);
  border-radius: 12px;
  background: var(--bg-alpha2);
  padding: 10px;
}

.cells-grid {
  display: grid;
  gap: 6px;
  min-width: 520px;
}

.cell {
  appearance: none;
  border: 1px solid var(--border-alpha);
  border-radius: 10px;
  background: var(--bg-alpha);
  color: var(--text);
  cursor: default;
  padding: 8px 6px;
  min-height: 34px;
}

.cell-idx {
  font-size: 11px;
  opacity: 0.9;
  text-align: center;
}

.raw-json summary {
  cursor: pointer;
  color: var(--muted);
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--bg-alpha);
  border-radius: 4px;
  font-size: 11px;
  color: var(--muted);
}

.mono {
  font-family: 'Maple Mono', 'Fira Code', monospace;
}
</style>
