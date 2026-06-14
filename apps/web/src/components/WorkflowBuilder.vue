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

// Grouped palette (logic + IO + transforms), matching the runtime node set.
const PALETTE: { group: string; types: string[] }[] = [
  { group: "Flow", types: ["start", "end"] },
  { group: "Reason", types: ["llm", "classifier", "kb_search"] },
  { group: "Logic", types: ["if_else", "condition"] },
  { group: "Transform", types: ["code", "template", "aggregator"] },
  { group: "Integrate", types: ["tool", "http"] },
];
const NODE_ICON: Record<string, string> = {
  start: "▶", end: "■", llm: "✦", classifier: "🏷", kb_search: "🔎",
  if_else: "⎇", condition: "⌥", code: "λ", template: "❏", aggregator: "⊕",
  tool: "🔧", http: "🌐",
};
const OPS = ["contains", "not_contains", "eq", "ne", "gt", "lt", "gte", "lte", "regex", "empty", "not_empty"];
const TOOLS = ["kb.search", "math.eval", "time.now", "http.fetch", "fs.read", "fs.write", "fs.list"];

function defaultConfig(t: string): any {
  switch (t) {
    case "kb_search": return { query: "{input}", k: 6, mode: "", output_var: "context" };
    case "llm": return { prompt: "Answer using the context.\n\nContext:\n{context}\n\nQuestion: {input}", model: "", output_var: "output" };
    case "classifier": return { var: "input", prompt: "Classify the input.", classes: ["sales", "support"], model: "", output_var: "class" };
    case "condition": return { var: "output", contains: "" };
    case "if_else": return { var: "input", op: "contains", value: "" };
    case "code": return { code: "len(input)", output_var: "result" };
    case "template": return { template: "{input}", output_var: "output" };
    case "aggregator": return { inputs: [{ name: "a", value: "{output}" }], output_var: "output" };
    case "tool": return { tool: "math.eval", inputs: [{ name: "expression", value: "{input}" }], output_var: "result" };
    case "http": return { method: "GET", url: "https://", body: "", headers: [], output_var: "response" };
    case "end": return { output_var: "output" };
    default: return {};
  }
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
      nodes.value.push(vnode(n.id, n.type, n.label, { ...defaultConfig(n.type), ...(n.config ?? {}) }, 60 + d * 240, 60 + row * 130));
    }
    for (const e of wf.edges ?? [])
      edges.value.push({ id: `e_${e.source}_${e.target}_${++counter}`, source: e.source, target: e.target,
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
  selectedId.value = id;
}

function onConnect(c: any) {
  const src = nodes.value.find((n) => n.id === c.source);
  let when: string | null = null;
  const existing = edges.value.filter((e) => e.source === c.source).length;
  if (src?.data.type === "condition" || src?.data.type === "if_else") {
    when = existing === 0 ? "true" : "false";
  } else if (src?.data.type === "classifier") {
    when = src.data.config.classes?.[existing] ?? null;
  }
  edges.value.push({ id: `e_${c.source}_${c.target}_${++counter}`, source: c.source,
                     target: c.target, label: when ?? undefined, data: { when } });
}

function onNodeClick(e: any) { selectedId.value = e.node.id; }
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
// helpers for list-valued config (inputs / headers / classes)
function addInput(list: any[]) { list.push({ name: "", value: "" }); }
function rmInput(list: any[], i: any) { list.splice(Number(i), 1); }
function addClass(c: any) { (c.classes ??= []).push("new_class"); }
function rmClass(c: any, i: any) { c.classes.splice(Number(i), 1); }

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
        <button class="primary sm" :disabled="store.busy" @click="store.saveWorkflow(toGraph())">Save workflow</button>
      </header>

      <div class="body">
        <div class="palette">
          <template v-for="g in PALETTE" :key="g.group">
            <div class="palette__h">{{ g.group }}</div>
            <button v-for="t in g.types" :key="t" class="palette__btn" @click="addNode(t)">
              <span class="ic">{{ NODE_ICON[t] || "•" }}</span> {{ t }}
            </button>
          </template>
          <p class="hint">Drag from a node handle to connect. Click a node to edit.</p>
        </div>

        <div class="canvas">
          <VueFlow v-model:nodes="nodes" v-model:edges="edges" :fit-view-on-init="true"
                   @connect="onConnect" @node-click="onNodeClick" />
        </div>

        <div class="inspector">
          <template v-if="selected">
            <div class="insp__h"><span class="ic">{{ NODE_ICON[selected.data.type] }}</span> {{ selected.data.type }}</div>
            <label>Label<input v-model="selected.data.label" @input="syncLabel" /></label>

            <template v-if="selected.data.type === 'kb_search'">
              <label>Query template<input v-model="selected.data.config.query" /></label>
              <div class="row2">
                <label>Top-k<input v-model.number="selected.data.config.k" type="number" min="1" max="20" /></label>
                <label>Mode
                  <select v-model="selected.data.config.mode">
                    <option value="">(KB default)</option><option>semantic</option>
                    <option>keyword</option><option>hybrid</option>
                  </select>
                </label>
              </div>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'llm'">
              <label>Prompt template<textarea v-model="selected.data.config.prompt" rows="6" /></label>
              <label>Model override<input v-model="selected.data.config.model" placeholder="(agent default)" /></label>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'classifier'">
              <label>Test variable<input v-model="selected.data.config.var" /></label>
              <label>Instruction<textarea v-model="selected.data.config.prompt" rows="3" /></label>
              <div class="listhdr">Classes <button class="link" @click="addClass(selected.data.config)">+ add</button></div>
              <div v-for="(_, i) in selected.data.config.classes" :key="i" class="kvrow">
                <input v-model="selected.data.config.classes[i]" placeholder="class name (= edge label)" />
                <button class="link danger" @click="rmClass(selected.data.config, i)">✕</button>
              </div>
              <p class="hint">Connect one outgoing edge per class — the edge label is the class.</p>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'if_else'">
              <label>Test variable<input v-model="selected.data.config.var" /></label>
              <label>Operator
                <select v-model="selected.data.config.op"><option v-for="o in OPS" :key="o">{{ o }}</option></select>
              </label>
              <label v-if="!['empty','not_empty'].includes(selected.data.config.op)">
                Value<input v-model="selected.data.config.value" />
              </label>
              <p class="hint">Wire a “true” edge and a “false” edge from this node.</p>
            </template>

            <template v-else-if="selected.data.type === 'condition'">
              <label>Test variable<input v-model="selected.data.config.var" /></label>
              <label>Routes to “true” if it contains<input v-model="selected.data.config.contains" /></label>
            </template>

            <template v-else-if="selected.data.type === 'code'">
              <label>Expression (sandboxed)</label>
              <textarea class="code" v-model="selected.data.config.code" rows="6"
                        spellcheck="false" placeholder="e.g. len(input)  ·  price*qty  ·  input.upper()" />
              <p class="hint">A safe single expression over variables. No imports/exec.</p>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'template'">
              <label>Template<textarea v-model="selected.data.config.template" rows="6"
                        placeholder="Render {vars} into text, e.g. Hello {input}" /></label>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'aggregator'">
              <div class="listhdr">Sources to merge <button class="link" @click="addInput(selected.data.config.inputs)">+ add</button></div>
              <div v-for="(inp, i) in selected.data.config.inputs" :key="i" class="kvrow">
                <input v-model="inp.value" placeholder="{var} or text" />
                <button class="link danger" @click="rmInput(selected.data.config.inputs, i)">✕</button>
              </div>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'tool'">
              <label>Tool
                <input v-model="selected.data.config.tool" list="tool-list" />
                <datalist id="tool-list"><option v-for="t in TOOLS" :key="t" :value="t" /></datalist>
              </label>
              <div class="listhdr">Arguments <button class="link" @click="addInput(selected.data.config.inputs)">+ add</button></div>
              <div v-for="(inp, i) in selected.data.config.inputs" :key="i" class="kvrow">
                <input v-model="inp.name" class="kname" placeholder="name" />
                <input v-model="inp.value" placeholder="value / {var}" />
                <button class="link danger" @click="rmInput(selected.data.config.inputs, i)">✕</button>
              </div>
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <template v-else-if="selected.data.type === 'http'">
              <div class="row2">
                <label>Method
                  <select v-model="selected.data.config.method">
                    <option>GET</option><option>POST</option><option>PUT</option>
                    <option>DELETE</option><option>PATCH</option>
                  </select>
                </label>
                <label>Output var<input v-model="selected.data.config.output_var" /></label>
              </div>
              <label>URL<input v-model="selected.data.config.url" placeholder="https://… {var}" /></label>
              <label>Body<textarea v-model="selected.data.config.body" rows="3" /></label>
              <div class="listhdr">Headers <button class="link" @click="addInput(selected.data.config.headers)">+ add</button></div>
              <div v-for="(h, i) in selected.data.config.headers" :key="i" class="kvrow">
                <input v-model="h.name" class="kname" placeholder="Header" />
                <input v-model="h.value" placeholder="value" />
                <button class="link danger" @click="rmInput(selected.data.config.headers, i)">✕</button>
              </div>
            </template>

            <template v-else-if="selected.data.type === 'end'">
              <label>Output var<input v-model="selected.data.config.output_var" /></label>
            </template>

            <p v-else class="hint">The start node has no settings.</p>
          </template>
          <p v-else class="hint">Select a node to edit its settings, or add one from the palette.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(8, 10, 14, 0.6); z-index: 60; display: flex; padding: 24px; }
.builder { background: var(--bg); border: 1px solid var(--border); border-radius: 14px; flex: 1; display: flex; flex-direction: column; overflow: hidden; box-shadow: var(--shadow); }
header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
header h3 { margin: 0; font-size: 16px; }
.grow { flex: 1; }
button.sm { padding: 6px 12px; font-size: 13px; }
.primary { background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer; }
.primary:disabled { opacity: .5; }
.body { flex: 1; display: grid; grid-template-columns: 184px 1fr 312px; min-height: 0; }
.palette { border-right: 1px solid var(--border); padding: 12px; display: flex; flex-direction: column; gap: 6px; overflow: auto; }
.palette__h, .insp__h { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); margin-top: 6px; }
.insp__h { margin-top: 0; font-size: 13px; color: var(--ink); display: flex; align-items: center; gap: 6px; }
.palette__btn { background: var(--surface-2); color: var(--ink); border: 1px solid var(--border); text-align: left; border-radius: var(--radius-sm); padding: 7px 10px; cursor: pointer; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.palette__btn:hover { border-color: var(--accent); }
.ic { display: inline-block; width: 16px; text-align: center; }
.canvas { min-width: 0; background: var(--bg-soft); }
.canvas :deep(.vue-flow__node) { background: var(--surface); border: 1px solid var(--border-strong); border-radius: 9px; color: var(--ink); font-size: 12.5px; padding: 8px 12px; box-shadow: var(--shadow-sm); }
.canvas :deep(.vue-flow__node.selected) { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-ring); }
.canvas :deep(.vue-flow__edge-path) { stroke: var(--border-strong); }
.canvas :deep(.vue-flow__edge-text) { fill: var(--muted); font-size: 10px; }
.inspector { border-left: 1px solid var(--border); padding: 14px; display: flex; flex-direction: column; gap: 10px; overflow: auto; }
.inspector label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.inspector input, .inspector textarea, .inspector select { font-size: 13px; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.listhdr { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--muted); margin-top: 4px; }
.kvrow { display: flex; gap: 6px; align-items: center; }
.kvrow input { flex: 1; }
.kvrow .kname { max-width: 38%; }
.code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; background: var(--bg-soft); border: 1px solid var(--border-strong); border-radius: var(--radius-sm); color: var(--ink); padding: 9px; line-height: 1.5; tab-size: 2; }
.code:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-ring); outline: none; }
.link { background: none; border: none; cursor: pointer; font-size: 12px; color: var(--accent); padding: 0; }
.link.danger { color: var(--danger); }
.muted { color: var(--muted); font-size: 13px; }
.hint { color: var(--faint); font-size: 12px; line-height: 1.5; }
</style>
