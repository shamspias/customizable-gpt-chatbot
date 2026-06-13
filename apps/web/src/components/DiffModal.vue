<script setup lang="ts">
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
        ⚠ Blocked: {{ store.diff.reasons.join("; ") }}
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
  position: fixed; inset: 0; background: rgba(20, 22, 28, 0.5);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal {
  background: var(--bg); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px; width: min(620px, 92vw); max-height: 84vh; display: flex; flex-direction: column; gap: 10px;
}
header { display: flex; align-items: center; gap: 10px; }
header h3 { margin: 0; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); }
.tag.cosmetic { color: #2e7d32; }
.tag.sensitive { color: #b3261e; }
.summary { margin: 0; color: var(--muted); }
.blocked { color: #b3261e; font-size: 14px; }
.patch {
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px; overflow: auto; font-size: 12px; font-family: ui-monospace, Menlo, monospace; max-height: 50vh;
}
footer { display: flex; justify-content: flex-end; gap: 8px; }
.ghost { background: none; }
.muted { color: var(--muted); font-size: 12px; }
</style>
