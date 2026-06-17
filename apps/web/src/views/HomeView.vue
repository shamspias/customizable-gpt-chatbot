<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

// The landing: a smart composer (route to an agent, or build one), your agent board,
// recent activity, quick links.
const store = useAgentStore();
onMounted(() => {
  if (!store.agents.length) store.listAgents();
  store.listRuns();
});

const firstRun = computed(() => !store.agents.length);

// smart composer
const draft = ref("");
const buildMode = ref(false);
const routing = ref(false);
async function send() {
  const text = draft.value.trim();
  if (!text || routing.value) return;
  draft.value = "";
  routing.value = true;
  try {
    await store.smartSend(text, buildMode.value);
  } finally {
    routing.value = false;
  }
}
const recent = computed(() => (store.runs || []).filter((r: any) => r.kind === "ask").slice(0, 5));

const HUES = ["--accent", "--ok", "--warn", "--danger"];
function hue(name: string) {
  let h = 0;
  for (const c of name || "·") h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return HUES[h % HUES.length];
}
function initial(n: string) { return (n || "·").trim().charAt(0).toUpperCase(); }
function tierOf(m: string) { return (m || "").replace("claude-", "").replace(/-/g, " ") || "—"; }

function ago(iso: string) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
function openAgent(id: string) { store.loadAgent(id); }
const QUICK = [
  { id: "knowledge", label: "Knowledge", icon: "book", hint: "Docs your agents cite" },
  { id: "skills", label: "Skills", icon: "scroll", hint: "Reusable playbooks" },
  { id: "insights", label: "Insights", icon: "chart", hint: "Usage, cost & quality" },
];
</script>

<template>
  <div class="home">
    <div class="inner">
      <!-- Hero + smart composer -->
      <section class="hero">
        <h1>{{ firstRun ? "Welcome to Veldra 👋" : "What do you need done?" }}</h1>
        <p>{{ firstRun
          ? "Describe what you need — Veldra builds an agent for it. Then chat and teach it to grow."
          : "Type a task and we’ll route it to the right agent — or build a new one for it." }}</p>

        <form class="composer" @submit.prevent="send">
          <textarea
            v-model="draft" rows="2" :disabled="routing"
            :placeholder="buildMode
              ? 'Describe an agent to build — e.g. “a support agent that answers from my docs and always cites the page”'
              : 'Ask anything, or describe an agent — e.g. “summarize this PDF” or “build a SQL helper”'"
            @keydown.enter.exact.prevent="send"
          />
          <div class="crow">
            <label class="bmode" :class="{ on: buildMode }">
              <input type="checkbox" v-model="buildMode" />
              <Icon name="sparkles" :size="14" /> Build new agent
            </label>
            <div class="grow" />
            <button type="button" class="ghost sm" @click="store.openCreate()">Advanced…</button>
            <button class="send" :disabled="!draft.trim() || routing">
              <Icon :name="routing ? 'refresh' : (buildMode ? 'sparkles' : 'send')" :size="16" />
              {{ routing ? "Working…" : (buildMode ? "Build" : "Send") }}
            </button>
          </div>
        </form>

        <div v-if="firstRun" class="steps">
          <span class="step"><b>1</b> Describe</span><span class="arr">→</span>
          <span class="step"><b>2</b> Chat &amp; test</span><span class="arr">→</span>
          <span class="step"><b>3</b> Grow it 🌱</span>
        </div>
      </section>

      <!-- Your agents -->
      <section v-if="store.agents.length" class="block">
        <div class="bhead"><h2>Your agents</h2><span class="count">{{ store.agents.length }}</span></div>
        <div class="grid">
          <button v-for="a in store.agents" :key="a.id" class="card" @click="openAgent(a.id)">
            <span class="ava" :style="{ background: `color-mix(in srgb, var(${hue(a.name)}) 16%, transparent)`, color: `var(${hue(a.name)})` }">
              <Icon v-if="a.n_sub_agents" name="workflow" :size="18" />
              <template v-else>{{ initial(a.name) }}</template>
            </span>
            <span class="cbody">
              <span class="cname">{{ a.name }}</span>
              <span class="cmeta">
                <span v-if="a.n_sub_agents" class="badge">team · {{ a.n_sub_agents }}</span>
                <span v-else>{{ tierOf(a.model) }}</span>
                <template v-if="a.n_tools"><span class="dot" />{{ a.n_tools }} tool{{ a.n_tools > 1 ? "s" : "" }}</template>
                <span v-if="a.auto_improve" class="grow" title="Self-improving">✦</span>
              </span>
            </span>
            <Icon name="send" :size="15" class="go" />
          </button>
          <button class="card newcard" @click="store.openCreate()">
            <span class="ava plus"><Icon name="plus" :size="18" /></span>
            <span class="cbody"><span class="cname">New agent</span><span class="cmeta">Describe or build manually</span></span>
          </button>
        </div>
      </section>

      <!-- Recent activity -->
      <section v-if="recent.length" class="block">
        <div class="bhead"><h2>Recent</h2><button class="link" @click="store.view = 'activity'">View all →</button></div>
        <div class="recent">
          <div v-for="r in recent" :key="r.id" class="rrow">
            <span class="rstatus" :class="r.status" />
            <span class="rname">{{ r.agent_name || "—" }}</span>
            <span class="rkind">chat</span>
            <span class="rtime">{{ ago(r.created_at) }}</span>
          </div>
        </div>
      </section>

      <!-- Quick links -->
      <section class="block">
        <div class="quick">
          <button v-for="q in QUICK" :key="q.id" class="qcard" @click="store.view = q.id as any">
            <span class="qic"><Icon :name="q.icon" :size="17" /></span>
            <span class="qbody"><strong>{{ q.label }}</strong><small>{{ q.hint }}</small></span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.home { flex: 1; overflow: auto; background: var(--bg); }
.inner { max-width: 880px; margin: 0 auto; padding: 40px 22px 60px; display: flex; flex-direction: column; gap: 30px; }

.hero { text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px; padding-top: 12px; animation: veldra-rise 0.3s ease both; }
.hero h1 { margin: 0; font-size: 28px; letter-spacing: -0.02em; }
.hero p { margin: 0 0 8px; color: var(--muted); font-size: 15px; max-width: 52ch; line-height: 1.55; }
.cta { padding: 13px 24px; font-size: 15px; font-weight: 650; border-radius: var(--radius); }

.composer { width: 100%; max-width: 640px; margin-top: 6px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow);
  padding: 12px 12px 10px; text-align: left; transition: border-color 0.14s, box-shadow 0.14s; }
.composer:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-ring), var(--shadow); }
.composer textarea { width: 100%; border: none; background: none; resize: none; padding: 4px 6px;
  font-size: 15px; line-height: 1.5; color: var(--ink); box-shadow: none; }
.composer textarea:focus { box-shadow: none; }
.crow { display: flex; align-items: center; gap: 8px; padding-top: 6px; }
.bmode { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted);
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px;
  padding: 5px 11px; cursor: pointer; user-select: none; }
.bmode.on { color: var(--accent); background: var(--accent-soft); border-color: var(--accent-ring); }
.bmode input { display: none; }
.send { padding: 8px 16px; font-weight: 600; }
.crow .grow { flex: 1; }

.steps { display: flex; align-items: center; gap: 10px; margin-top: 12px; color: var(--muted); font-size: 13px; flex-wrap: wrap; justify-content: center; }
.steps .step b { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 11px; margin-right: 5px; }
.steps .arr { color: var(--faint); }

.block { display: flex; flex-direction: column; gap: 12px; }
.bhead { display: flex; align-items: baseline; gap: 9px; }
.bhead h2 { margin: 0; font-size: 16px; letter-spacing: -0.01em; }
.bhead .count { font-size: 12px; font-weight: 650; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 1px 9px; }
.bhead .link { margin-left: auto; background: none; border: none; color: var(--accent); font-size: 13px; box-shadow: none; padding: 0; }
.bhead .link:hover { filter: none; text-decoration: underline; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.card { display: flex; align-items: center; gap: 12px; text-align: left; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; box-shadow: none; transition: border-color 0.14s, box-shadow 0.14s, transform 0.12s; }
.card:hover { border-color: var(--accent); box-shadow: var(--shadow); filter: none; transform: translateY(-2px); }
.ava { width: 40px; height: 40px; flex: none; display: grid; place-items: center; border-radius: 11px; font-size: 16px; font-weight: 700; }
.ava.plus { background: var(--accent-soft); color: var(--accent); }
.cbody { min-width: 0; display: flex; flex-direction: column; gap: 3px; flex: 1; }
.cname { font-size: 14.5px; font-weight: 650; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cmeta { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--faint); text-transform: capitalize; }
.cmeta .dot { width: 3px; height: 3px; border-radius: 99px; background: var(--faint); }
.cmeta .badge { font-size: 10.5px; font-weight: 600; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 0 7px; text-transform: none; }
.cmeta .grow { color: var(--ok); }
.go { color: var(--faint); flex: none; opacity: 0; transition: opacity 0.14s; }
.card:hover .go { opacity: 1; }
.newcard { border-style: dashed; }

.recent { display: flex; flex-direction: column; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.rrow { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-top: 1px solid var(--border); font-size: 13.5px; }
.rrow:first-child { border-top: none; }
.rstatus { width: 8px; height: 8px; border-radius: 99px; background: var(--faint); flex: none; }
.rstatus.done { background: var(--ok); }
.rstatus.error { background: var(--danger); }
.rname { font-weight: 600; }
.rkind { color: var(--muted); }
.rtime { margin-left: auto; color: var(--faint); font-size: 12px; }

.quick { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.qcard { display: flex; align-items: center; gap: 11px; text-align: left; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 13px; box-shadow: none; }
.qcard:hover { border-color: var(--accent); filter: none; }
.qic { width: 34px; height: 34px; flex: none; display: grid; place-items: center; border-radius: 9px; background: var(--accent-soft); color: var(--accent); }
.qbody { display: flex; flex-direction: column; line-height: 1.25; }
.qbody strong { font-size: 14px; }
.qbody small { font-size: 11.5px; color: var(--faint); }

@media (max-width: 640px) { .quick { grid-template-columns: 1fr; } .inner { padding: 28px 16px 80px; } }
</style>
