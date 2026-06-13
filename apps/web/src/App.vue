<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import CitationChips from "./components/CitationChips.vue";
import DiffModal from "./components/DiffModal.vue";
import SpecPanel from "./components/SpecPanel.vue";
import { useAgentStore } from "./stores/agent";

const store = useAgentStore();
const input = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const scroller = ref<HTMLElement | null>(null);
const mode = computed(() => (store.agentId ? "ask" : "build"));

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
}

function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) store.upload(f);
  (e.target as HTMLInputElement).value = "";
}

watch(
  () => [store.messages.length, store.busy],
  () => nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight)),
);
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="brand">Loom</div>
      <div class="tagline">talk an agent into existence</div>
      <div class="grow" />
      <div v-if="store.phase" class="phase">{{ store.phase }}…</div>
      <button v-if="store.agentId" class="link" @click="newAgent">＋ new agent</button>
    </header>

    <main class="layout">
      <section class="left">
        <div class="docs">
          <button class="ghost" :disabled="store.busy" @click="fileInput?.click()">
            ＋ Upload document
          </button>
          <input ref="fileInput" type="file" hidden accept=".pdf,.txt,.md" @change="onFile" />
          <span v-for="d in store.docs" :key="d.document_id" class="doc">
            {{ d.filename }} · {{ d.num_chunks }} chunks
          </span>
        </div>

        <div ref="scroller" class="messages">
          <div v-if="!store.messages.length" class="hint">
            <p>Upload a document or two, then describe the agent you want — e.g.</p>
            <p class="example">“Answer questions from these docs and always cite the page.”</p>
          </div>
          <div v-for="(m, i) in store.messages" :key="i" class="msg" :class="m.role">
            <div class="bubble" :class="{ spec: m.kind === 'spec', error: m.kind === 'error' }">
              <div class="text">{{ m.text }}</div>
              <CitationChips v-if="m.citations" :citations="m.citations" />
            </div>
          </div>
        </div>

        <div class="composer">
          <textarea
            v-model="input"
            rows="1"
            :placeholder="mode === 'build' ? 'Describe the agent you want…' : 'Ask your agent…'"
            :disabled="store.busy"
            @keydown.enter.exact.prevent="submit"
          />
          <button :disabled="store.busy || !input.trim()" @click="submit">
            {{ mode === "build" ? "Build" : "Send" }}
          </button>
        </div>
        <div v-if="store.error" class="err">{{ store.error }}</div>
      </section>

      <SpecPanel class="right" />
    </main>

    <DiffModal />
  </div>
</template>

<style scoped>
.app { height: 100vh; display: flex; flex-direction: column; }
.topbar {
  display: flex; align-items: center; gap: 12px; padding: 12px 20px;
  border-bottom: 1px solid var(--border); background: var(--bg);
}
.brand { font-weight: 700; font-size: 18px; letter-spacing: -0.01em; }
.tagline { color: var(--muted); font-size: 13px; }
.grow { flex: 1; }
.phase { color: var(--accent); font-size: 13px; }
.layout {
  flex: 1; display: grid; grid-template-columns: 1fr 420px; gap: 1px;
  background: var(--border); overflow: hidden;
}
.left { background: var(--bg); display: flex; flex-direction: column; min-height: 0; }
.right { background: var(--bg); padding: 16px; }
.docs { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.doc { font-size: 12px; color: var(--muted); background: var(--chip-bg); border: 1px solid var(--border); border-radius: 999px; padding: 2px 10px; }
.messages { flex: 1; overflow: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.hint { color: var(--muted); margin: auto; text-align: center; max-width: 360px; }
.example { color: var(--ink); font-style: italic; }
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 76%; padding: 10px 14px; border-radius: 14px; line-height: 1.5; }
.msg.user .bubble { background: var(--accent); color: white; border-bottom-right-radius: 4px; }
.msg.assistant .bubble { background: var(--card); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.bubble.spec { background: var(--ok-bg); border-color: var(--ok-border); }
.bubble.error { background: #fdecea; border-color: #f5c6c0; color: #b3261e; }
.text { white-space: pre-wrap; }
.composer { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border); }
.composer textarea { flex: 1; resize: none; }
.err { padding: 0 16px 12px; color: #b3261e; font-size: 13px; }
.link { background: none; border: none; color: var(--accent); cursor: pointer; font-size: 13px; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } .right { display: none; } }
</style>
