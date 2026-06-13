<script setup lang="ts">
import { onMounted } from "vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
onMounted(() => store.listAgents());

async function openBuilder(id: string) {
  await store.loadAgent(id);
  store.showBuilder = true;
}
</script>

<template>
  <div class="wf">
    <div class="head">
      <h2>Agents &amp; Workflows</h2>
      <div class="grow" />
      <button class="ghost sm" @click="store.listAgents()">Refresh</button>
    </div>
    <div v-if="store.agents.length" class="grid">
      <div v-for="a in store.agents" :key="a.id" class="card">
        <strong>{{ a.name }}</strong>
        <div class="muted">version {{ a.current_version }}</div>
        <div class="actions">
          <button class="ghost sm" @click="store.loadAgent(a.id)">Open chat</button>
          <button class="sm" @click="openBuilder(a.id)">⚒ Builder</button>
        </div>
      </div>
    </div>
    <p v-else class="muted empty">No agents yet — build one in Studio.</p>
  </div>
</template>

<style scoped>
.wf { flex: 1; background: var(--bg); padding: 18px; overflow: auto; }
.head { display: flex; align-items: center; margin-bottom: 16px; }
.head h2 { margin: 0; font-size: 18px; }
.head .grow { flex: 1; }
button.sm { padding: 6px 12px; font-size: 13px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.card .actions { display: flex; gap: 8px; margin-top: 10px; }
.muted { color: var(--muted); font-size: 13px; }
.empty { margin: 60px auto; text-align: center; }
</style>
