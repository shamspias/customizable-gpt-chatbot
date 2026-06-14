<script setup lang="ts">
import { onMounted } from "vue";
import Icon from "../components/Icon.vue";
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
      <button class="ghost sm" @click="store.listAgents()"><Icon name="refresh" :size="15" />Refresh</button>
    </div>

    <div v-if="store.agents.length" class="grid">
      <div v-for="a in store.agents" :key="a.id" class="card">
        <div class="top">
          <span class="avatar"><Icon name="bot" :size="20" /></span>
          <div class="meta">
            <strong>{{ a.name }}</strong>
            <span class="ver">v{{ a.current_version }}</span>
          </div>
        </div>
        <div class="actions">
          <button class="ghost sm" @click="store.loadAgent(a.id)"><Icon name="sparkles" :size="14" />Chat</button>
          <button class="sm" @click="openBuilder(a.id)"><Icon name="workflow" :size="14" />Builder</button>
        </div>
      </div>
    </div>

    <div v-else class="empty">
      <div class="halo"><Icon name="bot" :size="26" /></div>
      <p>No agents yet — build one in <strong>Studio</strong>.</p>
      <button class="sm" @click="store.view = 'studio'"><Icon name="sparkles" :size="15" />Go to Studio</button>
    </div>
  </div>
</template>

<style scoped>
.wf { flex: 1; background: var(--bg); padding: 22px; overflow: auto; }
.head { display: flex; align-items: center; margin-bottom: 18px; }
.head h2 { margin: 0; font-size: 19px; letter-spacing: -0.01em; }
.head .grow { flex: 1; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; display: flex; flex-direction: column; gap: 14px; transition: transform 0.12s, border-color 0.15s, box-shadow 0.15s; animation: veldra-rise 0.2s ease both; }
.card:hover { transform: translateY(-2px); border-color: var(--border-strong); box-shadow: var(--shadow); }
.top { display: flex; align-items: center; gap: 12px; }
.avatar { width: 42px; height: 42px; flex: none; display: grid; place-items: center; border-radius: 12px; color: var(--accent); background: var(--accent-soft); }
.meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.meta strong { font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ver { font-size: 12px; color: var(--faint); }
.actions { display: flex; gap: 8px; }
.actions button { flex: 1; }
.empty { margin: 70px auto; text-align: center; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 14px; }
.empty .halo { width: 60px; height: 60px; display: grid; place-items: center; border-radius: 18px; color: var(--accent); background: var(--accent-soft); }
.empty p { margin: 0; }
@media (max-width: 640px) { .wf { padding: 16px; } .grid { grid-template-columns: 1fr; } }
</style>
