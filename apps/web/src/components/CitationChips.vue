<script setup lang="ts">
import type { Citation } from "../stores/agent";
defineProps<{ citations: Citation[] }>();
</script>

<template>
  <div v-if="citations && citations.length" class="citations">
    <span class="citations__label">Sources</span>
    <span
      v-for="c in citations"
      :key="c.index"
      class="chip"
      :title="c.snippet"
    >
      [{{ c.index }}] {{ c.filename }}<template v-if="c.page"> · p.{{ c.page }}</template>
    </span>
  </div>
</template>

<style scoped>
.citations { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.citations__label { font-size: 12px; color: var(--muted); margin-right: 2px; }
.chip {
  font-size: 12px; padding: 2px 8px; border-radius: 999px;
  background: var(--chip-bg); border: 1px solid var(--border); color: var(--ink);
  cursor: default; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
</style>
