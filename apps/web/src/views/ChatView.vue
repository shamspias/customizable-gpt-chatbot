<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import CitationChips from "../components/CitationChips.vue";
import Icon from "../components/Icon.vue";
import SpecPanel from "../components/SpecPanel.vue";
import UsageFooter from "../components/UsageFooter.vue";
import { useAgentStore } from "../stores/agent";

// The focused, full-width chat for one agent. Back returns Home; an agent panel
// (spec + grow) slides in from the header — no permanent side columns.
const store = useAgentStore();
const input = ref("");
const scroller = ref<HTMLElement | null>(null);
const panel = ref(false);  // agent details drawer

function back() { store.view = "home"; }
async function submit() {
  const t = input.value.trim();
  if (!t || store.busy || !store.agentId) return;
  input.value = "";
  await store.ask(t);
}
function grow(e: Event) {
  const el = e.target as HTMLTextAreaElement;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 180) + "px";
}
function testPage() {
  if (store.agentId) window.location.hash = `#/agent/${store.agentId}`;
}
function tierOf(m: string) { return (m || "").replace("claude-", "").replace(/-/g, " "); }

// Coalesce stream-driven scrolls into one write per animation frame so a long
// answer doesn't force a synchronous reflow on every streamed token.
let raf = 0;
function scrollToBottom() {
  if (raf) return;
  raf = requestAnimationFrame(() => {
    raf = 0;
    const el = scroller.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}
watch(() => [store.messages.length, store.busy, store.messages.at(-1)?.text], scrollToBottom);
onUnmounted(() => raf && cancelAnimationFrame(raf));
</script>

<template>
  <div class="chat">
    <header class="bar">
      <button class="ib" aria-label="Back to home" title="Home" @click="back"><Icon name="chevron" :size="18" class="flip" /></button>
      <span class="mark"><Icon name="bot" :size="17" /></span>
      <div class="who">
        <strong>{{ store.spec?.name || "Agent" }}</strong>
        <small>{{ tierOf(store.spec?.model || "") || "ready" }}</small>
      </div>
      <span v-if="store.phase" class="phase"><span class="dot" />{{ store.phase }}</span>
      <div class="grow" />
      <button class="ib" title="Edit workflow" aria-label="Workflow" @click="store.showBuilder = true"><Icon name="workflow" :size="17" /></button>
      <button class="ib" title="Shareable test page" aria-label="Test page" @click="testPage"><Icon name="globe" :size="17" /></button>
      <button class="details" :class="{ on: panel }" @click="panel = !panel">
        <Icon name="sparkles" :size="15" /><span class="hide-xs">Agent</span>
      </button>
    </header>

    <div class="body">
      <div ref="scroller" class="messages">
        <div v-if="!store.messages.length" class="empty">
          <div class="halo"><Icon name="bot" :size="24" /></div>
          <h2>{{ store.spec?.name }}</h2>
          <p v-if="store.spec?.description">{{ store.spec.description }}</p>
          <p v-else class="muted">Ask anything to get started.</p>
        </div>

        <div v-for="m in store.messages" :key="m.id" class="msg" :class="m.role">
          <div class="bubble" :class="{ spec: m.kind === 'spec', error: m.kind === 'error' }">
            <details v-if="m.thinking" class="thinking">
              <summary><Icon name="brain" :size="13" /> thinking</summary>
              <pre>{{ m.thinking }}</pre>
            </details>
            <div v-if="m.text" class="text">{{ m.text }}</div>
            <div v-else-if="m.role === 'assistant' && store.busy" class="typing"><span /><span /><span /></div>
            <CitationChips v-if="m.citations" :citations="m.citations" />
            <UsageFooter v-if="m.usage" :usage="m.usage" />
          </div>
          <div v-if="m.role === 'assistant' && m.runId && !m.kind && m.text" class="rate">
            <template v-if="m.rated == null">
              <button class="rb" aria-label="Good answer" title="Good answer" @click="store.rate(m, 1)"><Icon name="thumbsUp" :size="14" /></button>
              <button class="rb" aria-label="Could be better" title="Could be better — it'll learn" @click="store.rate(m, -1)"><Icon name="thumbsDown" :size="14" /></button>
            </template>
            <span v-else class="rated"><Icon name="check" :size="13" /> thanks — noted</span>
          </div>
        </div>
      </div>

      <div class="composer-wrap">
        <div class="composer">
          <textarea v-model="input" rows="1" placeholder="Message your agent…"
            :disabled="store.busy" @input="grow" @keydown.enter.exact.prevent="submit" />
          <button class="send" :disabled="store.busy || !input.trim()" @click="submit" aria-label="Send"><Icon name="send" :size="18" /></button>
        </div>
        <div v-if="store.error" class="err">{{ store.error }}</div>
      </div>
    </div>

    <!-- agent details drawer (spec + grow) -->
    <transition name="dr">
      <div v-if="panel" class="dwrap" @click.self="panel = false">
        <aside class="drawer"><SpecPanel /></aside>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.chat { height: 100vh; height: 100dvh; display: flex; flex-direction: column; background: var(--bg); }
.bar { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(8px); }
.ib { background: none; border: none; color: var(--muted); padding: 7px; border-radius: var(--radius-sm); box-shadow: none; }
.ib:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.flip { transform: scaleX(1); }
.mark { width: 30px; height: 30px; flex: none; display: grid; place-items: center; border-radius: 9px; background: var(--accent-soft); color: var(--accent); }
.who { display: flex; flex-direction: column; line-height: 1.15; min-width: 0; }
.who strong { font-size: 15px; }
.who small { font-size: 11px; color: var(--faint); text-transform: capitalize; }
.phase { display: flex; align-items: center; gap: 6px; color: var(--accent); font-size: 12.5px; text-transform: capitalize; margin-left: 8px; }
.phase .dot { width: 7px; height: 7px; border-radius: 99px; background: var(--accent); animation: veldra-pulse 1s ease-in-out infinite; }
.grow { flex: 1; }
.details { gap: 7px; }
.details.on { background: var(--accent-soft); color: var(--accent); border-color: transparent; }

.body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.messages { flex: 1; overflow: auto; padding: 24px 18px; display: flex; flex-direction: column; gap: 14px; width: 100%; max-width: 800px; margin: 0 auto; }
.empty { margin: auto; text-align: center; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 8px; animation: veldra-rise 0.3s ease both; }
.halo { width: 56px; height: 56px; display: grid; place-items: center; border-radius: 16px; color: var(--accent); background: var(--accent-soft); margin-bottom: 6px; }
.empty h2 { margin: 0; color: var(--ink); font-size: 19px; }
.empty p { margin: 0; }

.msg { display: flex; animation: veldra-rise 0.18s ease both; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 84%; padding: 11px 15px; border-radius: var(--radius); line-height: 1.55; font-size: 14.5px; box-shadow: var(--shadow-sm); }
.msg.user .bubble { background: var(--accent-grad); color: #fff; border-bottom-right-radius: 5px; }
.msg.assistant .bubble { background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 5px; }
.bubble.spec { background: var(--ok-soft); border: 1px solid var(--ok-border); }
.bubble.error { background: var(--danger-soft); border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent); color: var(--danger); }
.text { white-space: pre-wrap; word-break: break-word; }
.thinking { margin-bottom: 8px; font-size: 12px; color: var(--muted); }
.thinking summary { cursor: pointer; color: var(--accent); display: inline-flex; align-items: center; gap: 5px; }
.thinking pre { white-space: pre-wrap; margin: 6px 0 0; padding: 8px; background: var(--surface-2); border-radius: 8px; max-height: 220px; overflow: auto; }
.rate { display: flex; align-items: center; gap: 6px; margin-top: 5px; }
.rb { background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); padding: 4px 9px; border-radius: 8px; box-shadow: none; }
.rb:hover { border-color: var(--accent); color: var(--accent); filter: none; }
.rated { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--ok); }
.typing { display: flex; gap: 5px; padding: 4px 2px; }
.typing span { width: 7px; height: 7px; border-radius: 99px; background: var(--faint); animation: veldra-pulse 1.1s ease-in-out infinite; }
.typing span:nth-child(2) { animation-delay: 0.18s; }
.typing span:nth-child(3) { animation-delay: 0.36s; }

.composer-wrap { width: 100%; max-width: 800px; margin: 0 auto; padding: 0 18px 16px; }
.composer { display: flex; gap: 10px; align-items: flex-end; background: var(--surface); border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 8px 8px 8px 14px; box-shadow: var(--shadow-sm); transition: border-color 0.14s ease, box-shadow 0.14s ease; }
.composer:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-ring); }
.composer textarea { flex: 1; resize: none; min-height: 26px; max-height: 180px; border: none; background: none; padding: 6px 0; box-shadow: none !important; }
.send { width: 40px; height: 40px; padding: 0; border-radius: var(--radius-sm); flex: none; }
.err { padding: 8px 4px 0; color: var(--danger); font-size: 13px; }
.hide-xs { display: inline; }

.dwrap { position: fixed; inset: 0; z-index: 50; background: rgba(27,34,55,0.4); backdrop-filter: blur(2px); display: flex; justify-content: flex-end; }
.drawer { width: min(440px, 92vw); height: 100%; background: var(--bg); border-left: 1px solid var(--border); padding: 16px; overflow: auto; box-shadow: var(--shadow-lg); }
.dr-enter-active, .dr-leave-active { transition: opacity 0.2s; }
.dr-enter-active .drawer, .dr-leave-active .drawer { transition: transform 0.22s ease; }
.dr-enter-from, .dr-leave-to { opacity: 0; }
.dr-enter-from .drawer, .dr-leave-to .drawer { transform: translateX(100%); }

@media (max-width: 600px) { .details .hide-xs { display: none; } }
</style>
