<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import CitationChips from "../components/CitationChips.vue";
import Icon from "../components/Icon.vue";
import SpecPanel from "../components/SpecPanel.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const input = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const scroller = ref<HTMLElement | null>(null);
const showSpec = ref(false); // mobile spec drawer
const buildMode = ref<"single" | "company">("single"); // empty-state build target
const mode = computed(() => (store.agentId ? "ask" : "build"));

const EXAMPLES = [
  "Answer questions from these docs and always cite the page.",
  "Triage support emails and draft replies grounded in our docs.",
  "A research assistant that searches my docs, then summarizes with citations.",
];
const COMPANY_EXAMPLES = [
  "A digital marketing agency: strategy, content, and client-support agents.",
  "An online store: a sales agent, an order-support agent, and a returns agent.",
  "A clinic: reception/booking, billing, and a patient-FAQ agent from our docs.",
];
const examples = computed(() => (buildMode.value === "company" ? COMPANY_EXAMPLES : EXAMPLES));

async function submit() {
  const t = input.value.trim();
  if (!t || store.busy) return;
  input.value = "";
  if (store.agentId) {
    await store.ask(t);
  } else if (buildMode.value === "company") {
    // Frame as a team build so the orchestrator creates a coordinator + role agents.
    await store.build(`Set up a team of agents for this company: ${t}`);
  } else {
    await store.build(t);
  }
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
function grow(e: Event) {
  const el = e.target as HTMLTextAreaElement;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
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
        <strong class="name">{{ store.spec ? store.spec.name : "New agent" }}</strong>
        <span v-if="store.phase" class="phase"><span class="dot" />{{ store.phase }}</span>
        <div class="grow" />
        <button class="ghost sm" :disabled="store.busy" @click="fileInput?.click()" title="Upload document">
          <Icon name="upload" :size="15" /><span class="hide-xs">Document</span>
        </button>
        <input ref="fileInput" type="file" hidden accept=".pdf,.txt,.md" @change="onFile" />
        <button v-if="store.agentId" class="ghost sm" @click="newAgent" title="New agent">
          <Icon name="plus" :size="15" /><span class="hide-xs">New</span>
        </button>
        <button v-if="store.spec" class="ghost sm show-mobile" @click="showSpec = true" title="View spec">
          <Icon name="layers" :size="15" />
        </button>
      </div>

      <div v-if="store.docs.length" class="docs">
        <span v-for="d in store.docs" :key="d.document_id" class="doc">
          <Icon name="file" :size="13" />{{ d.filename }} · {{ d.num_chunks }} chunks
        </span>
      </div>

      <div ref="scroller" class="messages">
        <div v-if="!store.messages.length" class="hero">
          <div class="seg">
            <button :class="{ on: buildMode === 'single' }" @click="buildMode = 'single'">
              <Icon name="bot" :size="15" />Single agent
            </button>
            <button :class="{ on: buildMode === 'company' }" @click="buildMode = 'company'">
              <Icon name="layers" :size="15" />Company team
            </button>
          </div>
          <div class="halo"><Icon :name="buildMode === 'company' ? 'layers' : 'sparkles'" :size="26" /></div>
          <h1>{{ buildMode === 'company' ? 'Set up agents for your company' : 'Build an agent by describing it' }}</h1>
          <p v-if="buildMode === 'company'">Describe your company and what it does. Veldra designs a
            <strong>team</strong> — a coordinator plus specialist agents for each role — and wires them together.</p>
          <p v-else>Upload a document, then tell Veldra what you want. It designs the policy,
            tools, knowledge, and even a workflow — then you chat with it.</p>
          <div class="examples">
            <button v-for="ex in examples" :key="ex" class="example" @click="input = ex">
              <Icon name="spark" :size="15" />{{ ex }}
            </button>
          </div>
        </div>

        <div v-for="(m, i) in store.messages" :key="i" class="msg" :class="m.role">
          <div class="bubble" :class="{ spec: m.kind === 'spec', error: m.kind === 'error' }">
            <details v-if="m.thinking" class="thinking">
              <summary><Icon name="brain" :size="13" /> thinking</summary>
              <pre>{{ m.thinking }}</pre>
            </details>
            <div v-if="m.text" class="text">{{ m.text }}</div>
            <div v-else-if="m.role === 'assistant' && store.busy" class="typing"><span /><span /><span /></div>
            <CitationChips v-if="m.citations" :citations="m.citations" />
          </div>
          <div v-if="m.role === 'assistant' && m.runId && !m.kind && m.text" class="rate">
            <template v-if="m.rated == null">
              <button class="ratebtn" title="Good answer" @click="store.rate(m, 1)"><Icon name="thumbsUp" :size="14" /></button>
              <button class="ratebtn" title="Could be better — the agent will learn" @click="store.rate(m, -1)"><Icon name="thumbsDown" :size="14" /></button>
            </template>
            <span v-else class="rated"><Icon name="check" :size="13" /> feedback recorded</span>
          </div>
        </div>
      </div>

      <div class="composer">
        <textarea v-model="input" rows="1"
          :placeholder="mode === 'ask' ? 'Message your agent…' : buildMode === 'company' ? 'Describe your company…' : 'Describe the agent you want…'"
          :disabled="store.busy" @input="grow" @keydown.enter.exact.prevent="submit" />
        <button class="sendbtn" :disabled="store.busy || !input.trim()" @click="submit"
                :title="mode === 'build' ? 'Build' : 'Send'">
          <Icon :name="mode === 'build' ? 'sparkles' : 'send'" :size="18" />
        </button>
      </div>
      <div v-if="store.error" class="err">{{ store.error }}</div>
    </section>

    <SpecPanel class="right" />

    <!-- mobile spec drawer -->
    <transition name="drawer">
      <div v-if="showSpec" class="drawer-wrap" @click.self="showSpec = false">
        <div class="drawer">
          <div class="drawer-h">
            <strong>Agent spec</strong><div class="grow" />
            <button class="ghost sm" aria-label="Close" title="Close" @click="showSpec = false"><Icon name="x" :size="16" /></button>
          </div>
          <SpecPanel />
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.studio { flex: 1; display: grid; grid-template-columns: minmax(0, 1fr) 440px; gap: 1px; background: var(--border); overflow: hidden; }
.left { background: var(--bg); display: flex; flex-direction: column; min-height: 0; }
.right { background: var(--bg); padding: 18px; overflow: auto; }
.subbar { display: flex; align-items: center; gap: 9px; padding: 11px 18px; border-bottom: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(8px); }
.name { font-size: 15px; }
.subbar .grow { flex: 1; }
.phase { display: flex; align-items: center; gap: 6px; color: var(--accent); font-size: 12.5px; text-transform: capitalize; }
.phase .dot { width: 7px; height: 7px; border-radius: 99px; background: var(--accent); animation: veldra-pulse 1s ease-in-out infinite; }
.docs { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 18px; border-bottom: 1px solid var(--border); }
.doc { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--muted); background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; padding: 4px 11px; }
.messages { flex: 1; overflow: auto; padding: 24px 18px; display: flex; flex-direction: column; gap: 14px; }
.hero { margin: auto; text-align: center; max-width: 500px; color: var(--muted); animation: veldra-rise 0.3s ease both; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 999px; padding: 3px; margin-bottom: 22px; background: var(--surface); }
.seg button { background: none; border: none; box-shadow: none; color: var(--muted); border-radius: 999px; padding: 7px 15px; font-size: 13px; font-weight: 550; }
.seg button.on { background: var(--accent-soft); color: var(--accent); }
.halo { width: 60px; height: 60px; margin: 0 auto 18px; display: grid; place-items: center; border-radius: 18px; color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 8px color-mix(in srgb, var(--accent) 7%, transparent); }
.hero h1 { color: var(--ink); font-size: 23px; letter-spacing: -0.02em; margin: 0 0 10px; }
.hero p { line-height: 1.65; margin: 0 0 20px; }
.examples { display: flex; flex-direction: column; gap: 9px; }
.example { display: flex; align-items: center; gap: 10px; background: var(--surface); color: var(--ink); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; text-align: left; font-size: 13.5px; font-weight: 500; transition: transform 0.1s, border-color 0.15s, background 0.15s; }
.example :deep(.icon) { color: var(--accent); }
.example:hover { border-color: var(--accent); background: var(--surface-2); filter: none; transform: translateY(-1px); }
.msg { display: flex; animation: veldra-rise 0.18s ease both; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 82%; padding: 11px 15px; border-radius: var(--radius); line-height: 1.55; font-size: 14.5px; box-shadow: var(--shadow-sm); }
.msg.user .bubble { background: var(--accent-grad); color: #fff; border-bottom-right-radius: 5px; }
.msg.assistant .bubble { background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 5px; }
.bubble.spec { background: var(--ok-soft); border: 1px solid var(--ok-border); }
.bubble.error { background: var(--danger-soft); border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent); color: var(--danger); }
.text { white-space: pre-wrap; word-break: break-word; }
.thinking { margin-bottom: 8px; font-size: 12px; color: var(--muted); }
.thinking summary { cursor: pointer; color: var(--accent); display: inline-flex; align-items: center; gap: 5px; }
.thinking pre { white-space: pre-wrap; margin: 6px 0 0; padding: 8px; background: var(--surface-2); border-radius: 8px; max-height: 220px; overflow: auto; }
.rate { display: flex; align-items: center; gap: 6px; margin-top: 5px; }
.ratebtn { background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); padding: 4px 9px; border-radius: 8px; box-shadow: none; }
.ratebtn:hover { border-color: var(--accent); color: var(--accent); filter: none; }
.rated { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--ok); }
.typing { display: flex; gap: 5px; padding: 4px 2px; }
.typing span { width: 7px; height: 7px; border-radius: 99px; background: var(--faint); animation: veldra-pulse 1.1s ease-in-out infinite; }
.typing span:nth-child(2) { animation-delay: 0.18s; }
.typing span:nth-child(3) { animation-delay: 0.36s; }
.composer { display: flex; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(8px); align-items: flex-end; }
.composer textarea { flex: 1; resize: none; min-height: 44px; max-height: 160px; border-radius: var(--radius); }
.sendbtn { width: 44px; height: 44px; padding: 0; border-radius: var(--radius); flex: none; }
.err { padding: 0 18px 12px; color: var(--danger); font-size: 13px; }
.show-mobile { display: none; }

/* mobile spec drawer */
.drawer-wrap { position: fixed; inset: 0; z-index: 50; background: rgba(0, 0, 0, 0.5); display: flex; justify-content: flex-end; }
.drawer { width: min(440px, 92vw); background: var(--bg); height: 100%; overflow: auto; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; }
.drawer-h { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s; }
.drawer-enter-active .drawer, .drawer-leave-active .drawer { transition: transform 0.22s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer, .drawer-leave-to .drawer { transform: translateX(100%); }

@media (max-width: 900px) {
  .studio { grid-template-columns: 1fr; }
  .right { display: none; }
  .show-mobile { display: inline-flex; }
  .hide-xs { display: none; }
}
</style>
