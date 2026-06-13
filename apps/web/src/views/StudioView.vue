<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import CitationChips from "../components/CitationChips.vue";
import SpecPanel from "../components/SpecPanel.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const input = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const scroller = ref<HTMLElement | null>(null);
const mode = computed(() => (store.agentId ? "ask" : "build"));

const EXAMPLES = [
  "Answer questions from these docs and always cite the page.",
  "Triage support emails and draft replies grounded in our docs.",
  "A workflow that searches my docs, then summarizes with citations.",
];

async function submit() {
  const t = input.value.trim();
  if (!t || store.busy) return;
  input.value = "";
  if (!store.agentId) await store.build(t);
  else await store.ask(t);
}

function newAgent() {
  store.agentId = null;
  store.spec = null;
  store.messages = [] as any;
}

function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) store.upload(f);
  (e.target as HTMLInputElement).value = "";
}

watch(
  () => [store.messages.length, store.busy, store.messages.at(-1)?.text],
  () => nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight)),
);
</script>

<template>
  <div class="studio">
    <section class="left">
      <div class="subbar">
        <strong>{{ store.spec ? store.spec.name : "New agent" }}</strong>
        <span v-if="store.phase" class="phase"><span class="dot" />{{ store.phase }}</span>
        <div class="grow" />
        <button class="ghost sm" :disabled="store.busy" @click="fileInput?.click()">＋ Document</button>
        <input ref="fileInput" type="file" hidden accept=".pdf,.txt,.md" @change="onFile" />
        <button v-if="store.agentId" class="ghost sm" @click="newAgent">＋ New agent</button>
      </div>
      <div v-if="store.docs.length" class="docs">
        <span v-for="d in store.docs" :key="d.document_id" class="doc">📄 {{ d.filename }} · {{ d.num_chunks }} chunks</span>
      </div>

      <div ref="scroller" class="messages">
        <div v-if="!store.messages.length" class="hero">
          <h1>Build an agent by describing it</h1>
          <p>Upload a document, then tell Veldra what you want. It designs the policy,
            tools, knowledge, and even a workflow — then you chat with it.</p>
          <div class="examples">
            <button v-for="ex in EXAMPLES" :key="ex" class="example" @click="input = ex">{{ ex }}</button>
          </div>
        </div>

        <div v-for="(m, i) in store.messages" :key="i" class="msg" :class="m.role">
          <div class="bubble" :class="{ spec: m.kind === 'spec', error: m.kind === 'error' }">
            <details v-if="m.thinking" class="thinking">
              <summary>thinking</summary>
              <pre>{{ m.thinking }}</pre>
            </details>
            <div v-if="m.text" class="text">{{ m.text }}</div>
            <div v-else-if="m.role === 'assistant' && store.busy" class="typing"><span /><span /><span /></div>
            <CitationChips v-if="m.citations" :citations="m.citations" />
          </div>
        </div>
      </div>

      <div class="composer">
        <textarea v-model="input" rows="1"
          :placeholder="mode === 'build' ? 'Describe the agent you want…' : 'Message your agent…'"
          :disabled="store.busy" @keydown.enter.exact.prevent="submit" />
        <button :disabled="store.busy || !input.trim()" @click="submit">{{ mode === "build" ? "Build" : "Send" }}</button>
      </div>
      <div v-if="store.error" class="err">{{ store.error }}</div>
    </section>

    <SpecPanel class="right" />
  </div>
</template>

<style scoped>
.studio { flex: 1; display: grid; grid-template-columns: minmax(0, 1fr) 440px; gap: 1px; background: var(--border); overflow: hidden; }
.left { background: var(--bg); display: flex; flex-direction: column; min-height: 0; }
.right { background: var(--bg); padding: 18px; overflow: auto; }
.subbar { display: flex; align-items: center; gap: 10px; padding: 10px 18px; border-bottom: 1px solid var(--border); }
.subbar .grow { flex: 1; }
.phase { display: flex; align-items: center; gap: 6px; color: var(--accent); font-size: 12.5px; }
.phase .dot { width: 7px; height: 7px; border-radius: 99px; background: var(--accent); animation: veldra-pulse 1s ease-in-out infinite; }
button.sm { padding: 6px 11px; font-size: 13px; }
.docs { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 18px; border-bottom: 1px solid var(--border); }
.doc { font-size: 12px; color: var(--muted); background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; padding: 4px 11px; }
.messages { flex: 1; overflow: auto; padding: 22px 18px; display: flex; flex-direction: column; gap: 14px; }
.hero { margin: auto; text-align: center; max-width: 460px; color: var(--muted); }
.hero h1 { color: var(--ink); font-size: 22px; letter-spacing: -0.02em; margin: 0 0 8px; }
.hero p { line-height: 1.6; margin: 0 0 18px; }
.examples { display: flex; flex-direction: column; gap: 8px; }
.example { background: var(--surface); color: var(--ink); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 13px; text-align: left; font-size: 13.5px; }
.example:hover { border-color: var(--accent); background: var(--surface-2); filter: none; }
.msg { display: flex; animation: veldra-rise 0.18s ease both; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 80%; padding: 11px 15px; border-radius: var(--radius); line-height: 1.55; font-size: 14.5px; box-shadow: var(--shadow-sm); }
.msg.user .bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 5px; }
.msg.assistant .bubble { background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 5px; }
.bubble.spec { background: var(--ok-soft); border: 1px solid var(--ok-border); }
.bubble.error { background: var(--danger-soft); border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent); color: var(--danger); }
.text { white-space: pre-wrap; word-break: break-word; }
.thinking { margin-bottom: 8px; font-size: 12px; color: var(--muted); }
.thinking summary { cursor: pointer; color: var(--accent); }
.thinking pre { white-space: pre-wrap; margin: 6px 0 0; padding: 8px; background: var(--surface-2); border-radius: 8px; max-height: 220px; overflow: auto; }
.typing { display: flex; gap: 5px; padding: 4px 2px; }
.typing span { width: 7px; height: 7px; border-radius: 99px; background: var(--faint); animation: veldra-pulse 1.1s ease-in-out infinite; }
.typing span:nth-child(2) { animation-delay: 0.18s; }
.typing span:nth-child(3) { animation-delay: 0.36s; }
.composer { display: flex; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--bg-soft); }
.composer textarea { flex: 1; resize: none; min-height: 42px; max-height: 160px; }
.err { padding: 0 18px 12px; color: var(--danger); font-size: 13px; }
@media (max-width: 900px) { .studio { grid-template-columns: 1fr; } .right { display: none; } }
</style>
