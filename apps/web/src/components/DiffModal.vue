<script setup lang="ts">
import Icon from "./Icon.vue";
import { useAgentStore } from "../stores/agent";
const store = useAgentStore();
</script>

<template>
  <div v-if="store.diff" class="overlay" @click.self="store.dismissDiff()">
    <div class="modal">
      <header>
        <h3>Proposed change</h3>
        <span class="tag" :class="store.diff.capability_class">{{ store.diff.capability_class }}</span>
      </header>
      <p class="summary">“{{ store.diff.summary }}”</p>

      <p v-if="store.diff.blocked" class="blocked">
        <Icon name="x" :size="15" /> Blocked: {{ store.diff.reasons.join("; ") }}
        <br /><span class="muted">(adding tools / code requires the v1 sandbox)</span>
      </p>

      <pre class="patch">{{ JSON.stringify(store.diff.patch, null, 2) }}</pre>

      <footer>
        <button class="ghost" @click="store.dismissDiff()">Cancel</button>
        <button :disabled="store.diff.blocked || store.busy" @click="store.applySelfMod()">
          Approve &amp; apply
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.55);
  display: flex; align-items: center; justify-content: center; z-index: 50; padding: 16px;
  animation: veldra-fade 0.15s ease;
}
.modal {
  background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: 20px; width: min(620px, 96vw); max-height: 84vh; display: flex; flex-direction: column; gap: 11px;
  box-shadow: var(--shadow-lg); animation: veldra-pop 0.2s ease both;
}
header { display: flex; align-items: center; gap: 10px; }
header h3 { margin: 0; font-size: 17px; }
.tag { font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--border); text-transform: capitalize; }
.tag.cosmetic { color: var(--ok); background: var(--ok-soft); border-color: var(--ok-border); }
.tag.sensitive { color: var(--danger); background: var(--danger-soft); border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
.summary { margin: 0; color: var(--muted); }
.blocked { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; color: var(--danger); font-size: 14px; background: var(--danger-soft); border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent); border-radius: var(--radius-sm); padding: 10px 12px; }
.patch {
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px; overflow: auto; font-size: 12px; font-family: ui-monospace, Menlo, monospace; max-height: 50vh;
}
footer { display: flex; justify-content: flex-end; gap: 8px; }
.ghost { background: none; }
.muted { color: var(--muted); font-size: 12px; }
</style>
