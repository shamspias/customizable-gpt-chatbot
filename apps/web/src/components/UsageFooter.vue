<script setup lang="ts">
import type { Usage } from "../stores/agent";

const props = defineProps<{ usage: Usage }>();

function fmtTokens(n: number): string {
  if (!n) return "0";
  return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n);
}
function fmtCost(c: number): string | null {
  if (!c) return null;
  return c < 0.01 ? "<$0.01" : "$" + c.toFixed(c < 1 ? 3 : 2);
}
</script>

<template>
  <div class="usage" aria-label="token usage and cost">
    <span class="chip" :title="`model: ${usage.model}`">{{ usage.model }}</span>
    <span class="chip" :title="`${usage.input_tokens} in · ${usage.output_tokens} out`">
      {{ fmtTokens(usage.total_tokens) }} tok
    </span>
    <span v-if="fmtCost(usage.cost_usd)" class="chip cost" title="estimated cost (USD)">
      {{ fmtCost(usage.cost_usd) }}
    </span>
    <span v-if="usage.cache_hit_rate" class="chip" title="prompt-cache hit rate">
      {{ Math.round(usage.cache_hit_rate * 100) }}% cached
    </span>
  </div>
</template>

<style scoped>
.usage { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.chip {
  font-size: 11px; color: var(--faint); background: var(--surface-2);
  border: 1px solid var(--border); border-radius: 999px; padding: 1px 8px;
}
.chip.cost { color: var(--accent); font-weight: 600; }
</style>
