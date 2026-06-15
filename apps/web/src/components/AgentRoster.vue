<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Icon from "./Icon.vue";
import { useAgentStore } from "../stores/agent";

// Left column of the Studio workspace: pick an agent (or a team — an agent with
// sub-agents) to chat with. Mirrors aura-proto's agent-centric roster.
const store = useAgentStore();
const q = ref("");

onMounted(() => { if (!store.agents.length) store.listAgents(); });

const teams = computed(() => store.agents.filter((a: any) => (a.n_sub_agents || 0) > 0));
const solo = computed(() => store.agents.filter((a: any) => !(a.n_sub_agents || 0)));
function match(a: any) {
  const s = q.value.trim().toLowerCase();
  if (!s) return true;
  return (a.name + " " + (a.tags || []).join(" ") + " " + (a.description || "")).toLowerCase().includes(s);
}
const fTeams = computed(() => teams.value.filter(match));
const fSolo = computed(() => solo.value.filter(match));

// Theme-aware deterministic avatar tint per agent.
const HUES = ["--accent", "--ok", "--warn", "--danger"];
function hue(name: string) {
  let h = 0;
  for (const c of name || "·") h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return HUES[h % HUES.length];
}
function initial(name: string) {
  return (name || "·").trim().charAt(0).toUpperCase();
}

async function pick(id: string) {
  if (store.agentId === id) return;
  await store.loadAgent(id);
}
function newAgent() {
  store.agentId = null;
  store.spec = null;
  store.messages = [] as any;
}
</script>

<template>
  <aside class="roster">
    <div class="search">
      <Icon name="search" :size="15" />
      <input v-model="q" placeholder="Search agents…" aria-label="Search agents" />
    </div>

    <div class="scroll">
      <!-- Teams (agents that coordinate sub-agents) -->
      <section v-if="fTeams.length">
        <div class="seclabel">Teams <span class="muted">· coordinate sub-agents</span><span class="count">{{ fTeams.length }}</span></div>
        <button v-for="a in fTeams" :key="a.id" class="card" :class="{ on: store.agentId === a.id }" @click="pick(a.id)">
          <span class="ava team" :style="{ background: `color-mix(in srgb, var(${hue(a.name)}) 16%, transparent)`, color: `var(${hue(a.name)})` }">
            <Icon name="workflow" :size="16" />
          </span>
          <span class="body">
            <span class="name">{{ a.name }}</span>
            <span class="meta">
              <span class="badge">team · {{ a.n_sub_agents }}</span>
              <span v-if="a.auto_improve" class="grow" title="Self-improving — learns from feedback">✦ grows</span>
            </span>
          </span>
        </button>
      </section>

      <!-- Standalone agents -->
      <section>
        <div class="seclabel">Agents <span class="muted">· pick one to chat</span><span class="count">{{ fSolo.length }}</span></div>
        <div v-if="!store.agents.length" class="empty">No agents yet. Describe one in the chat →</div>
        <div v-else-if="!fSolo.length && !fTeams.length" class="empty">No matches.</div>
        <button v-for="a in fSolo" :key="a.id" class="card" :class="{ on: store.agentId === a.id }" @click="pick(a.id)">
          <span class="ava" :style="{ background: `color-mix(in srgb, var(${hue(a.name)}) 16%, transparent)`, color: `var(${hue(a.name)})` }">
            {{ initial(a.name) }}
          </span>
          <span class="body">
            <span class="name">{{ a.name }}</span>
            <span class="meta">
              <span class="tier">{{ (a.model || "").replace("claude-", "").replace("-", " ") || "—" }}</span>
              <template v-if="a.n_skills"><span class="dot" />{{ a.n_skills }} skill{{ a.n_skills > 1 ? "s" : "" }}</template>
              <template v-if="a.n_tools"><span class="dot" />{{ a.n_tools }} tool{{ a.n_tools > 1 ? "s" : "" }}</template>
              <template v-if="a.n_kbs"><span class="dot" />{{ a.n_kbs }} KB</template>
              <span v-if="a.auto_improve" class="grow" title="Self-improving — learns from feedback">✦</span>
            </span>
          </span>
        </button>
      </section>
    </div>

    <div class="foot">
      <button class="newbtn" @click="newAgent">
        <Icon name="plus" :size="15" />New agent
      </button>
      <p class="hint">Describe it in plain words — Veldra designs the policy, tools & workflow.</p>
    </div>
  </aside>
</template>

<style scoped>
.roster { display: flex; flex-direction: column; min-height: 0; height: 100%; background: var(--bg-soft); }
.search { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--border); color: var(--muted); }
.search input { flex: 1; border: none; background: none; padding: 0; font-size: 13.5px; color: var(--ink); box-shadow: none !important; }
.scroll { flex: 1; overflow: auto; padding: 12px 10px; display: flex; flex-direction: column; gap: 14px; }
section { display: flex; flex-direction: column; gap: 3px; }
.seclabel { display: flex; align-items: baseline; gap: 6px; font-size: 10px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--muted); padding: 2px 8px 6px; }
.seclabel .muted { font-weight: 500; letter-spacing: 0; text-transform: none; font-style: italic; color: var(--faint); }
.seclabel .count { margin-left: auto; color: var(--faint); }
.empty { font-size: 12.5px; color: var(--faint); padding: 8px; }

.card { width: 100%; display: flex; align-items: center; gap: 11px; text-align: left; background: none; border: 1px solid transparent; border-radius: var(--radius-sm); padding: 9px 10px; box-shadow: none; }
.card:hover { background: var(--surface); border-color: var(--border); filter: none; }
.card.on { background: var(--surface); border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-ring); }
.ava { width: 34px; height: 34px; flex: none; display: grid; place-items: center; border-radius: 999px; font-size: 14px; font-weight: 700; }
.ava.team { border-radius: 10px; }
.body { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.name { font-size: 14px; font-weight: 600; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { display: flex; align-items: center; gap: 5px; font-size: 10.5px; color: var(--faint); }
.tier { text-transform: capitalize; }
.dot { width: 3px; height: 3px; border-radius: 99px; background: var(--faint); display: inline-block; }
.badge { font-size: 10px; font-weight: 600; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 0 7px; }
.grow { color: var(--ok); font-weight: 600; }

.foot { padding: 12px 12px calc(12px + env(safe-area-inset-bottom)); border-top: 1px solid var(--border); }
.newbtn { width: 100%; justify-content: center; gap: 7px; }
.hint { margin: 8px 2px 0; font-size: 10.5px; color: var(--faint); line-height: 1.5; text-align: center; }
</style>
