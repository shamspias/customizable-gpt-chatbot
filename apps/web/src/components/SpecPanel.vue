<script setup lang="ts">
import { computed, ref } from "vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const showJson = ref(false);
const refineText = ref("");

const tools = computed(() =>
  (store.spec?.tools ?? []).map((t: any) => `${t.mcp_server}.${t.tool_name} (${t.permission_mode})`),
);

// The MVP runner is a fixed linear pipeline; render it as a small node list.
const graph = computed(() =>
  store.spec?.knowledge_bases?.length
    ? ["start", "kb_retrieve", "llm", "end"]
    : ["start", "llm", "end"],
);

function refine() {
  const t = refineText.value.trim();
  if (!t) return;
  store.proposeSelfMod(t);
  refineText.value = "";
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
        <button class="link" @click="showJson = !showJson">{{ showJson ? "view card" : "view JSON" }}</button>
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

        <section class="card">
          <h3>Knowledge bases</h3>
          <ul v-if="store.spec.knowledge_bases?.length">
            <li v-for="kb in store.spec.knowledge_bases" :key="kb" class="mono">{{ kb }}</li>
          </ul>
          <p v-else class="muted">none</p>
        </section>

        <section class="card">
          <h3>Workflow</h3>
          <div class="graph">
            <template v-for="(n, i) in graph" :key="n">
              <span class="node">{{ n }}</span>
              <span v-if="i < graph.length - 1" class="arrow">→</span>
            </template>
          </div>
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
.cards { display: flex; flex-direction: column; gap: 10px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
.card h3 { margin: 0 0 6px; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
.policy { margin: 0; white-space: pre-wrap; font-size: 14px; line-height: 1.5; }
.card.row { display: flex; gap: 18px; }
.card.row .k { display: block; font-size: 11px; color: var(--muted); }
.card.row .v { font-size: 14px; }
.card ul { margin: 0; padding-left: 18px; }
.mono, .json { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.json { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; font-size: 12px; overflow: auto; max-height: 60vh; }
.graph { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.node { background: var(--chip-bg); border: 1px solid var(--border); border-radius: 6px; padding: 3px 10px; font-size: 13px; }
.arrow { color: var(--muted); }
.refine { display: flex; gap: 8px; margin-top: auto; padding-top: 8px; }
.refine input { flex: 1; }
.muted { color: var(--muted); }
.link { background: none; border: none; color: var(--accent); cursor: pointer; font-size: 13px; padding: 0; }
</style>
