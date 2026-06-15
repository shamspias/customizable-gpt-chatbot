<script setup lang="ts">
import { computed, ref } from "vue";
import Icon from "./Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const showJson = ref(false);
const refineText = ref("");
const tab = ref<"agent" | "grow">("agent");
const teachText = ref("");
const teaching = ref(false);

// The agent's current version (a visible sign of growth over time).
const version = computed(
  () => store.agents.find((a: any) => a.id === store.agentId)?.current_version ?? null,
);

async function teach() {
  const t = teachText.value.trim();
  if (!t || teaching.value) return;
  teaching.value = true;
  try {
    await store.teachLesson(t);
    teachText.value = "";
  } finally {
    teaching.value = false;
  }
}

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
        </div>
      </header>

      <div class="tabs" role="tablist">
        <button role="tab" :class="{ on: tab === 'agent' }" @click="tab = 'agent'">Agent</button>
        <button role="tab" :class="{ on: tab === 'grow' }" @click="tab = 'grow'">
          ✦ Grow<span v-if="store.lessons.length" class="tabcount">{{ store.lessons.length }}</span>
        </button>
        <div class="grow-sp" />
        <button v-if="tab === 'agent'" class="link" @click="showJson = !showJson">{{ showJson ? "card" : "JSON" }}</button>
      </div>

      <!-- ── Agent tab ── -->
      <pre v-if="tab === 'agent' && showJson" class="json">{{ JSON.stringify(store.spec, null, 2) }}</pre>

      <div v-show="tab === 'agent' && !showJson" class="cards">
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

      </div>

      <div v-if="tab === 'agent'" class="refine">
        <input
          v-model="refineText"
          placeholder="Refine: e.g. ‘make answers more concise’"
          :disabled="store.busy"
          @keyup.enter="refine"
        />
        <button :disabled="store.busy || !refineText.trim()" @click="refine">Refine</button>
      </div>

      <!-- ── Grow tab — the agent that grows with you ── -->
      <div v-show="tab === 'grow'" class="grow">
        <div class="grow-hero">
          <div class="sprout">🌱</div>
          <p>This agent <strong>grows with you</strong>. Rate its answers, teach it directly, or
            let it learn on its own — what it learns sticks across every future chat.</p>
        </div>

        <div class="gstats">
          <div class="gstat"><span class="gv">v{{ version ?? 1 }}</span><span class="gl">version</span></div>
          <div class="gstat"><span class="gv">{{ store.lessons.length }}</span><span class="gl">lessons</span></div>
          <div class="gstat"><span class="gv" :class="{ ok: store.spec.auto_improve }">{{ store.spec.auto_improve ? "On" : "Off" }}</span><span class="gl">auto-learn</span></div>
        </div>

        <button class="autocard" :class="{ on: store.spec.auto_improve }"
                @click="store.setAutoImprove(!store.spec.auto_improve)">
          <span class="switch" :class="{ on: store.spec.auto_improve }"><span class="knob" /></span>
          <span class="actext">
            <strong>Auto-improve</strong>
            <small>When you rate an answer 👎, the agent reflects and learns a lesson automatically.</small>
          </span>
        </button>

        <div class="teach">
          <div class="seclabel">Teach it something</div>
          <div class="teachrow">
            <input v-model="teachText" placeholder="e.g. Always greet the customer by name"
                   :disabled="teaching" @keyup.enter="teach" />
            <button :disabled="teaching || !teachText.trim()" @click="teach">
              <Icon name="plus" :size="15" />Teach
            </button>
          </div>
          <p class="hint">It’s remembered as episodic memory and added to the agent’s instructions on every run.</p>
        </div>

        <div class="lessonsblk">
          <div class="seclabel">Lessons learned <span v-if="store.lessons.length" class="lc">{{ store.lessons.length }}</span></div>
          <div v-if="store.lessons.length" class="lessons">
            <div v-for="l in store.lessons" :key="l.id" class="lesson">
              <Icon name="graduation" :size="14" />
              <span class="ltext">{{ l.content }}</span>
              <button class="forget" aria-label="Forget this lesson" title="Forget" @click="store.forgetLesson(l.id)">
                <Icon name="x" :size="13" />
              </button>
            </div>
          </div>
          <div v-else class="grow-empty">
            <p>Nothing learned yet.</p>
            <p class="muted">Chat, then 👍/👎 the answers — or teach it above. It only gets better.</p>
          </div>
        </div>
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
.lesson { display: flex; gap: 8px; align-items: flex-start; font-size: 12.5px; line-height: 1.45; background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px; }
.lesson :deep(.icon) { color: var(--accent); margin-top: 2px; flex: none; }
.lesson .ltext { flex: 1; min-width: 0; }
.lesson .forget { background: none; border: none; color: var(--faint); padding: 2px; border-radius: 6px; box-shadow: none; flex: none; }
.lesson .forget:hover { color: var(--danger); background: var(--danger-soft); filter: none; }
.small { font-size: 12px; }

/* ── tabs ── */
.tabs { display: flex; align-items: center; gap: 4px; border-bottom: 1px solid var(--border); padding-bottom: 2px; }
.tabs [role="tab"] { background: none; border: none; box-shadow: none; color: var(--muted); font-weight: 600; font-size: 13px; padding: 7px 11px; border-radius: var(--radius-sm) var(--radius-sm) 0 0; display: inline-flex; align-items: center; gap: 6px; position: relative; }
.tabs [role="tab"]:hover { color: var(--ink); background: var(--surface-2); filter: none; }
.tabs [role="tab"].on { color: var(--accent); }
.tabs [role="tab"].on::after { content: ""; position: absolute; left: 8px; right: 8px; bottom: -3px; height: 2px; border-radius: 2px; background: var(--accent); }
.tabcount, .lc { font-size: 10.5px; font-weight: 700; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 0 6px; }
.tabs .grow-sp { flex: 1; }

/* ── grow tab ── */
.grow { display: flex; flex-direction: column; gap: 14px; }
.grow-hero { display: flex; gap: 11px; align-items: flex-start; background: var(--accent-soft); border: 1px solid var(--accent-ring); border-radius: var(--radius); padding: 13px 14px; }
.grow-hero .sprout { font-size: 24px; line-height: 1; }
.grow-hero p { margin: 0; font-size: 13px; line-height: 1.55; color: var(--ink); }
.gstats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }
.gstat { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 11px; display: flex; flex-direction: column; gap: 2px; align-items: center; }
.gstat .gv { font-size: 19px; font-weight: 700; letter-spacing: -0.02em; }
.gstat .gv.ok { color: var(--ok); }
.gstat .gl { font-size: 11px; color: var(--muted); }

.autocard { width: 100%; display: flex; align-items: center; gap: 12px; text-align: left; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 13px; box-shadow: none; }
.autocard:hover { border-color: var(--accent); filter: none; }
.autocard.on { border-color: var(--accent); background: var(--accent-soft); }
.autocard .actext { display: flex; flex-direction: column; gap: 2px; }
.autocard .actext strong { font-size: 14px; }
.autocard .actext small { font-size: 11.5px; color: var(--muted); line-height: 1.45; }

.seclabel { font-size: 10px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--muted); display: flex; align-items: center; gap: 7px; margin-bottom: 8px; }
.teachrow { display: flex; gap: 8px; }
.teachrow input { flex: 1; }
.hint { margin: 8px 0 0; font-size: 11px; color: var(--faint); line-height: 1.5; }
.grow-empty { text-align: center; padding: 18px 12px; border: 1px dashed var(--border-strong); border-radius: var(--radius); }
.grow-empty p { margin: 0; font-size: 13px; }
.grow-empty .muted { margin-top: 4px; font-size: 12px; }
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
