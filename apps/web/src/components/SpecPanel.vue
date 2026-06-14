<script setup lang="ts">
import { computed, ref } from "vue";
import Icon from "./Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const showJson = ref(false);
const refineText = ref("");

const tools = computed(() =>
  (store.spec?.tools ?? []).map((t: any) => `${t.name} (${t.permission_mode})`),
);

// Real workflow graph if the spec has one (ordered by traversing edges), else the
// inferred linear pipeline the agent loop runs.
const hasWorkflow = computed(() => !!store.spec?.workflow_graph?.nodes?.length);

const flow = computed(() => {
  const wf = store.spec?.workflow_graph;
  if (wf?.nodes?.length) {
    const byId: Record<string, any> = Object.fromEntries(wf.nodes.map((n: any) => [n.id, n]));
    const edges = wf.edges ?? [];
    const out: any[] = [];
    const seen = new Set<string>();
    let cur = byId[wf.entrypoint] ? wf.entrypoint : wf.nodes[0]?.id;
    let guard = 0;
    while (cur && byId[cur] && !seen.has(cur) && guard++ < 50) {
      seen.add(cur);
      out.push({ type: byId[cur].type, label: byId[cur].label || byId[cur].type });
      const e = edges.find((x: any) => x.source === cur && (x.when == null || x.when === "true"))
        ?? edges.find((x: any) => x.source === cur);
      cur = e?.target;
    }
    for (const n of wf.nodes) if (!seen.has(n.id)) out.push({ type: n.type, label: n.label || n.type });
    return out;
  }
  const types = store.spec?.knowledge_bases?.length
    ? ["start", "kb_search", "llm", "end"]
    : ["start", "llm", "end"];
  return types.map((t) => ({ type: t, label: t }));
});

const NODE_ICON: Record<string, string> = {
  start: "▶", end: "■", llm: "✦", classifier: "🏷", kb_search: "🔎", kb_retrieve: "🔎",
  condition: "⌥", if_else: "⎇", code: "λ", template: "❏", aggregator: "⊕", tool: "🔧", http: "🌐",
};

function refine() {
  const t = refineText.value.trim();
  if (!t) return;
  store.proposeSelfMod(t);
  refineText.value = "";
}
function openTestPage() {
  if (store.agentId) window.location.hash = `#/agent/${store.agentId}`;
}
</script>

<template>
  <aside class="panel">
    <div v-if="!store.spec" class="panel__empty">
      <p>No agent yet.</p>
      <p class="muted">Describe what you want on the left, and the orchestrator will design one here.</p>
    </div>

    <template v-else>
      <header class="panel__head">
        <h2>{{ store.spec.name }}</h2>
        <div class="head-actions">
          <button v-if="store.agentId" class="link" title="Open this agent on its own shareable test page"
                  @click="openTestPage">↗ test page</button>
          <button class="link" @click="store.showBuilder = true">⚒ builder</button>
          <button class="link" @click="showJson = !showJson">{{ showJson ? "view card" : "view JSON" }}</button>
        </div>
      </header>

      <pre v-if="showJson" class="json">{{ JSON.stringify(store.spec, null, 2) }}</pre>

      <div v-else class="cards">
        <section class="card">
          <h3>Policy</h3>
          <p class="policy">{{ store.spec.system_prompt }}</p>
        </section>

        <section class="card row">
          <div><span class="k">model</span><span class="v">{{ store.spec.model }}</span></div>
          <div><span class="k">effort</span><span class="v">{{ store.spec.effort }}</span></div>
          <div><span class="k">thinking</span><span class="v">{{ store.spec.thinking_method }}</span></div>
        </section>

        <section class="card">
          <h3>Tools</h3>
          <ul v-if="tools.length"><li v-for="t in tools" :key="t">{{ t }}</li></ul>
          <p v-else class="muted">none</p>
        </section>

        <section class="card" v-if="store.spec.skills?.length">
          <h3>Skills</h3>
          <ul><li v-for="s in store.spec.skills" :key="s">{{ s }}</li></ul>
        </section>

        <section class="card">
          <h3>Knowledge bases</h3>
          <ul v-if="store.spec.knowledge_bases?.length">
            <li v-for="kb in store.spec.knowledge_bases" :key="kb" class="mono">{{ kb }}</li>
          </ul>
          <p v-else class="muted">none</p>
        </section>

        <section class="card" v-if="store.spec.sub_agents?.length">
          <h3>Team (delegates to)</h3>
          <ul><li v-for="a in store.spec.sub_agents" :key="a">{{ a }}</li></ul>
        </section>

        <section class="card">
          <h3>Workflow <span v-if="hasWorkflow" class="badge">graph</span></h3>
          <div class="flow">
            <template v-for="(n, i) in flow" :key="i">
              <div class="fnode">
                <span class="ficon">{{ NODE_ICON[n.type] || "•" }}</span>
                <span class="ftype">{{ n.type }}</span>
                <span v-if="n.label && n.label !== n.type" class="flabel">{{ n.label }}</span>
              </div>
              <span v-if="i < flow.length - 1" class="fdown">↓</span>
            </template>
          </div>
        </section>

        <section class="card">
          <h3>Self-improvement</h3>
          <label class="toggle" @click="store.setAutoImprove(!store.spec.auto_improve)">
            <span class="switch" :class="{ on: store.spec.auto_improve }"><span class="knob" /></span>
            <span>Auto-improve <small class="muted">— learn from 👎 feedback automatically</small></span>
          </label>
          <div v-if="store.lessons.length" class="lessons">
            <div v-for="l in store.lessons" :key="l.id" class="lesson">
              <Icon name="graduation" :size="13" /><span>{{ l.content }}</span>
            </div>
          </div>
          <p v-else class="muted small">No lessons yet — rate answers 👍/👎 to teach it.</p>
        </section>
      </div>

      <div class="refine">
        <input
          v-model="refineText"
          placeholder="Refine: e.g. ‘make answers more concise’"
          :disabled="store.busy"
          @keyup.enter="refine"
        />
        <button :disabled="store.busy || !refineText.trim()" @click="refine">Refine</button>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 12px; height: 100%; overflow: auto; }
.panel__empty { color: var(--muted); margin-top: 40px; text-align: center; }
.panel__head { display: flex; justify-content: space-between; align-items: baseline; }
.panel__head h2 { font-size: 18px; margin: 0; }
.head-actions { display: flex; gap: 12px; }
.cards { display: flex; flex-direction: column; gap: 10px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
.card h3 { margin: 0 0 6px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
.policy { margin: 0; white-space: pre-wrap; font-size: 14px; line-height: 1.5; }
.card.row { display: flex; gap: 18px; }
.card.row .k { display: block; font-size: 11px; color: var(--muted); }
.card.row .v { font-size: 14px; }
.card ul { margin: 0; padding-left: 18px; }
.toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 13.5px; }
.switch { width: 38px; height: 22px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); position: relative; transition: background .15s; flex: none; }
.switch.on { background: var(--accent); border-color: var(--accent); }
.switch .knob { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: left .15s; }
.switch.on .knob { left: 18px; }
.lessons { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
.lesson { display: flex; gap: 7px; align-items: flex-start; font-size: 12.5px; line-height: 1.45; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; }
.lesson :deep(.icon) { color: var(--accent); margin-top: 2px; flex: none; }
.small { font-size: 12px; }
.mono, .json { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.json { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; font-size: 12px; overflow: auto; max-height: 60vh; }
.badge { font-size: 10px; text-transform: none; letter-spacing: 0; color: var(--accent); background: var(--accent-soft); border-radius: 6px; padding: 1px 6px; margin-left: 6px; }
.flow { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
.fnode { display: flex; align-items: center; gap: 8px; background: var(--chip-bg); border: 1px solid var(--border); border-radius: 8px; padding: 6px 11px; font-size: 13px; }
.ficon { opacity: 0.85; }
.ftype { font-weight: 550; }
.flabel { color: var(--muted); font-size: 12px; }
.fdown { color: var(--faint); margin-left: 14px; line-height: 1; }
.refine { display: flex; gap: 8px; margin-top: auto; padding-top: 8px; }
.refine input { flex: 1; }
.muted { color: var(--muted); }
.link { background: none; border: none; color: var(--accent); cursor: pointer; font-size: 13px; padding: 0; }
</style>
