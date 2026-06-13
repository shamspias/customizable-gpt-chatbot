<script setup lang="ts">
import { VueFlow } from "@vue-flow/core";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import { computed, onMounted, ref } from "vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const nodes = ref<any[]>([]);
const edges = ref<any[]>([]);
const selectedId = ref<string | null>(null);
let counter = 0;

const PALETTE = ["kb_search", "llm", "condition", "end", "start"];
const NODE_ICON: Record<string, string> = {
  start: "▶", kb_search: "🔎", llm: "✦", condition: "⌥", end: "■",
};

function defaultConfig(t: string): any {
  if (t === "kb_search") return { query: "{input}", k: 6, output_var: "context" };
  if (t === "llm") return { prompt: "Answer the question using the context.\n\nContext:\n{context}\n\nQuestion: {input}", output_var: "output" };
  if (t === "condition") return { var: "output", contains: "" };
  if (t === "end") return { output_var: "output" };
  return {};
}

function vnode(id: string, type: string, label: string, config: any, x: number, y: number) {
  return { id, position: { x, y }, label: `${NODE_ICON[type] || "•"}  ${label || type}`,
           data: { type, label: label || type, config } };
}

function loadFromSpec() {
  nodes.value = [];
  edges.value = [];
  const wf = store.spec?.workflow_graph;
  if (wf?.nodes?.length) {
    // layered layout by BFS depth from entrypoint
    const byId: Record<string, any> = Object.fromEntries(wf.nodes.map((n: any) => [n.id, n]));
    const adj: Record<string, string[]> = {};
    for (const e of wf.edges ?? []) (adj[e.source] ??= []).push(e.target);
    const depth: Record<string, number> = {};
    const queue = [wf.entrypoint && byId[wf.entrypoint] ? wf.entrypoint : wf.nodes[0].id];
    depth[queue[0]] = 0;
    while (queue.length) {
      const cur = queue.shift()!;
      for (const t of adj[cur] ?? []) if (depth[t] === undefined) { depth[t] = depth[cur] + 1; queue.push(t); }
    }
    const perDepth: Record<number, number> = {};
    for (const n of wf.nodes) {
      const d = depth[n.id] ?? 0;
      const row = perDepth[d] ?? 0;
      perDepth[d] = row + 1;
      nodes.value.push(vnode(n.id, n.type, n.label, n.config ?? defaultConfig(n.type), 60 + d * 240, 60 + row * 130));
    }
    for (const e of wf.edges ?? [])
      edges.value.push({ id: `e_${e.source}_${e.target}`, source: e.source, target: e.target,
                         label: e.when ?? undefined, data: { when: e.when ?? null } });
  } else {
    nodes.value.push(vnode("start", "start", "Input", {}, 60, 120));
    nodes.value.push(vnode("end", "end", "Done", defaultConfig("end"), 360, 120));
    edges.value.push({ id: "e_start_end", source: "start", target: "end", data: { when: null } });
  }
}

onMounted(loadFromSpec);

function addNode(type: string) {
  const id = `${type}_${++counter}`;
  nodes.value.push(vnode(id, type, type, defaultConfig(type), 120 + (nodes.value.length % 4) * 60,
                         100 + nodes.value.length * 36));
}

function onConnect(c: any) {
  const src = nodes.value.find((n) => n.id === c.source);
  let when: string | null = null;
  if (src?.data.type === "condition") {
    const existing = edges.value.filter((e) => e.source === c.source).length;
    when = existing === 0 ? "true" : "false";
  }
  edges.value.push({ id: `e_${c.source}_${c.target}_${++counter}`, source: c.source,
                     target: c.target, label: when ?? undefined, data: { when } });
}

function onNodeClick(e: any) {
  selectedId.value = e.node.id;
}

const selected = computed(() => nodes.value.find((n) => n.id === selectedId.value));

function syncLabel() {
  const n = selected.value;
  if (n) n.label = `${NODE_ICON[n.data.type] || "•"}  ${n.data.label || n.data.type}`;
}

function removeSelected() {
  if (!selectedId.value) return;
  nodes.value = nodes.value.filter((n) => n.id !== selectedId.value);
  edges.value = edges.value.filter((e) => e.source !== selectedId.value && e.target !== selectedId.value);
  selectedId.value = null;
}

function toGraph() {
  const start = nodes.value.find((n) => n.data.type === "start");
  return {
    entrypoint: start ? start.id : nodes.value[0]?.id ?? "start",
    nodes: nodes.value.map((n) => ({ id: n.id, type: n.data.type, label: n.data.label || "", config: n.data.config })),
    edges: edges.value.map((e) => ({ source: e.source, target: e.target, when: e.data?.when ?? null })),
  };
}
</script>

<template>
  <div v-if="store.showBuilder" class="overlay">
    <div class="builder">
      <header>
        <h3>Workflow builder</h3>
        <span class="muted">{{ store.spec?.name }}</span>
        <div class="grow" />
        <button class="ghost sm" :disabled="!selectedId" @click="removeSelected">Delete node</button>
        <button class="ghost sm" @click="store.showBuilder = false">Close</button>
        <button class="sm" :disabled="store.busy" @click="store.saveWorkflow(toGraph())">Save workflow</button>
      </header>

      <div class="body">
        <div class="palette">
          <div class="palette__h">Add node</div>
          <button v-for="t in PALETTE" :key="t" class="palette__btn" @click="addNode(t)">
            {{ NODE_ICON[t] || "•" }} {{ t }}
          </button>
          <p class="hint">Drag from a node's edge to connect. Click a node to edit it.</p>
        </div>

        <div class="canvas">
          <VueFlow v-model:nodes="nodes" v-model:edges="edges" :fit-view-on-init="true"
                   @connect="onConnect" @node-click="onNodeClick" />
        </div>

        <div class="inspector">
          <template v-if="selected">
            <div class="insp__h">{{ selected.data.type }}</div>
            <label>Label<input v-model="selected.data.label" @input="syncLabel" /></label>
            <template v-if="selected.data.type === 'kb_search'">
              <label>Query template<input v-model="selected.data.config.query" /></label>
              <label>Top-k<input v-model.number="selected.data.config.k" type="number" /></label>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>
            <template v-else-if="selected.data.type === 'llm'">
              <label>Prompt template<textarea v-model="selected.data.config.prompt" rows="6" /></label>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>
            <template v-else-if="selected.data.type === 'condition'">
              <label>Test variable<input v-model="selected.data.config.var" /></label>
              <label>Routes to “true” if it contains<input v-model="selected.data.config.contains" /></label>
            </template>
            <template v-else-if="selected.data.type === 'end'">
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>
            <p v-else class="hint">The start node has no settings.</p>
          </template>
          <p v-else class="hint">Select a node to edit its settings.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(8, 10, 14, 0.6); z-index: 60; display: flex; padding: 24px; }
.builder { background: var(--bg); border: 1px solid var(--border); border-radius: 14px; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
header h3 { margin: 0; font-size: 16px; }
.grow { flex: 1; }
button.sm { padding: 6px 12px; font-size: 13px; }
.body { flex: 1; display: grid; grid-template-columns: 170px 1fr 280px; min-height: 0; }
.palette { border-right: 1px solid var(--border); padding: 12px; display: flex; flex-direction: column; gap: 8px; overflow: auto; }
.palette__h, .insp__h { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
.palette__btn { background: var(--surface-2); color: var(--ink); border: 1px solid var(--border); text-align: left; }
.palette__btn:hover { border-color: var(--accent); filter: none; }
.canvas { min-width: 0; background: var(--bg-soft); }
.canvas :deep(.vue-flow__node) { background: var(--surface); border: 1px solid var(--border-strong); border-radius: 9px; color: var(--ink); font-size: 12.5px; padding: 8px 12px; box-shadow: var(--shadow-sm); }
.canvas :deep(.vue-flow__node.selected) { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-ring); }
.canvas :deep(.vue-flow__edge-path) { stroke: var(--border-strong); }
.canvas :deep(.vue-flow__edge-text) { fill: var(--muted); font-size: 10px; }
.inspector { border-left: 1px solid var(--border); padding: 14px; display: flex; flex-direction: column; gap: 10px; overflow: auto; }
.inspector label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.inspector input, .inspector textarea { font-size: 13px; }
.muted { color: var(--muted); font-size: 13px; }
.hint { color: var(--faint); font-size: 12px; line-height: 1.5; }
</style>
