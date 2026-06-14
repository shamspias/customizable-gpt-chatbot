<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import CitationChips from "../components/CitationChips.vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

// A standalone, shareable chat page for ONE agent, mounted at #/agent/<id>.
// Deep-linkable: loads the agent by id on mount so the URL alone opens a working
// test surface. Reuses the store's ask()/rate() + message rendering.
const props = defineProps<{ agentId: string }>();
const emit = defineEmits<{ (e: "exit"): void }>();

const store = useAgentStore();
const input = ref("");
const scroller = ref<HTMLElement | null>(null);
const loadErr = ref<string | null>(null);
const loading = ref(true);
const copied = ref(false);

async function load(id: string) {
  loading.value = true;
  loadErr.value = null;
  try {
    await store.loadAgent(id);
  } catch (e: any) {
    loadErr.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
}
onMounted(() => load(props.agentId));
watch(() => props.agentId, (id) => id && load(id));

async function submit() {
  const t = input.value.trim();
  if (!t || store.busy || !store.agentId) return;
  input.value = "";
  await store.ask(t);
}
function grow(e: Event) {
  const el = e.target as HTMLTextAreaElement;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}
function openStudio() {
  // Keep the loaded agent; drop back into the full app shell on the Studio view.
  store.view = "studio";
  emit("exit");
}
async function copyLink() {
  try {
    await navigator.clipboard.writeText(window.location.href);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1400);
  } catch { /* clipboard blocked — no-op */ }
}

watch(
  () => [store.messages.length, store.busy, store.messages.at(-1)?.text],
  () => nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight)),
);
</script>

<template>
  <div class="page">
    <header class="bar">
      <button class="ghost sm" aria-label="Back to app" title="Back to app" @click="emit('exit')">
        <Icon name="x" :size="16" />
      </button>
      <span class="mark">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="5" cy="7" r="2.4" fill="currentColor" />
          <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
          <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
        </svg>
      </span>
      <div class="title">
        <strong>{{ store.spec?.name || "Agent" }}</strong>
        <small>test chat · standalone link</small>
      </div>
      <span v-if="store.phase" class="phase"><span class="dot" />{{ store.phase }}</span>
      <div class="grow" />
      <button class="ghost sm" title="Copy shareable link" @click="copyLink">
        <Icon :name="copied ? 'check' : 'globe'" :size="15" /><span class="hide-xs">{{ copied ? "Copied" : "Copy link" }}</span>
      </button>
      <button v-if="store.spec" class="ghost sm" title="Edit workflow" @click="store.showBuilder = true">
        <Icon name="workflow" :size="15" /><span class="hide-xs">Builder</span>
      </button>
      <button class="sm" title="Open in Studio" @click="openStudio">
        <Icon name="sparkles" :size="15" /><span class="hide-xs">Studio</span>
      </button>
    </header>

    <div ref="scroller" class="messages">
      <div v-if="loading" class="state"><span class="spin" /> Loading agent…</div>
      <div v-else-if="loadErr" class="state err">
        <Icon name="x" :size="22" />
        <p>Couldn’t load this agent.</p>
        <small>{{ loadErr }}</small>
        <button class="sm" @click="emit('exit')">Back to app</button>
      </div>

      <template v-else>
        <div v-if="!store.messages.length" class="hero">
          <div class="halo"><Icon name="bot" :size="26" /></div>
          <h1>{{ store.spec?.name }}</h1>
          <p v-if="store.spec?.description">{{ store.spec.description }}</p>
          <p v-else class="muted">Send a message to test this agent. This page has its own URL you can share.</p>
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
              <button class="ratebtn" aria-label="Good answer" title="Good answer" @click="store.rate(m, 1)"><Icon name="thumbsUp" :size="14" /></button>
              <button class="ratebtn" aria-label="Could be better" title="Could be better — the agent will learn" @click="store.rate(m, -1)"><Icon name="thumbsDown" :size="14" /></button>
            </template>
            <span v-else class="rated"><Icon name="check" :size="13" /> feedback recorded</span>
          </div>
        </div>
      </template>
    </div>

    <div v-if="!loadErr" class="composer">
      <textarea v-model="input" rows="1" placeholder="Message this agent…"
        :disabled="store.busy || loading" @input="grow" @keydown.enter.exact.prevent="submit" />
      <button class="sendbtn" :disabled="store.busy || loading || !input.trim()" @click="submit" title="Send">
        <Icon name="send" :size="18" />
      </button>
    </div>
    <div v-if="store.error" class="err-bar">{{ store.error }}</div>
  </div>
</template>

<style scoped>
.page { height: 100vh; height: 100dvh; display: flex; flex-direction: column; background: var(--bg); }
.bar { display: flex; align-items: center; gap: 10px; padding: 11px 16px; border-bottom: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(8px); }
.mark { width: 28px; height: 28px; flex: none; display: grid; place-items: center; border-radius: 9px; background: var(--accent-soft); color: var(--accent); }
.mark svg { width: 17px; height: 17px; }
.title { display: flex; flex-direction: column; line-height: 1.15; min-width: 0; }
.title strong { font-size: 15px; }
.title small { font-size: 11px; color: var(--faint); }
.phase { display: flex; align-items: center; gap: 6px; color: var(--accent); font-size: 12.5px; text-transform: capitalize; }
.phase .dot { width: 7px; height: 7px; border-radius: 99px; background: var(--accent); animation: veldra-pulse 1s ease-in-out infinite; }
.grow { flex: 1; }

.messages { flex: 1; overflow: auto; padding: 24px 18px; display: flex; flex-direction: column; gap: 14px; max-width: 860px; width: 100%; margin: 0 auto; }
.state { margin: auto; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 10px; font-size: 14px; }
.state.err { color: var(--danger); }
.state.err small { color: var(--faint); max-width: 40ch; text-align: center; word-break: break-word; }
.spin { width: 18px; height: 18px; border-radius: 99px; border: 2px solid var(--border-strong); border-top-color: var(--accent); animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.hero { margin: auto; text-align: center; max-width: 460px; color: var(--muted); animation: veldra-rise 0.3s ease both; }
.halo { width: 60px; height: 60px; margin: 0 auto 16px; display: grid; place-items: center; border-radius: 18px; color: var(--accent); background: var(--accent-soft); box-shadow: 0 0 0 8px color-mix(in srgb, var(--accent) 7%, transparent); }
.hero h1 { color: var(--ink); font-size: 22px; letter-spacing: -0.02em; margin: 0 0 8px; }
.hero p { line-height: 1.6; margin: 0; }
.muted { color: var(--muted); }

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

.composer { display: flex; gap: 10px; padding: 14px 18px; border-top: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(8px); align-items: flex-end; max-width: 860px; width: 100%; margin: 0 auto; box-sizing: border-box; }
.composer textarea { flex: 1; resize: none; min-height: 44px; max-height: 160px; border-radius: var(--radius); }
.sendbtn { width: 44px; height: 44px; padding: 0; border-radius: var(--radius); flex: none; }
.err-bar { padding: 0 18px 12px; color: var(--danger); font-size: 13px; max-width: 860px; width: 100%; margin: 0 auto; }

@media (max-width: 640px) { .hide-xs { display: none; } }
</style>
