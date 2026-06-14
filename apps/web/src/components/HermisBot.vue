<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { useAgentStore } from "../stores/agent";
import Icon from "./Icon.vue";

const store = useAgentStore();
const input = ref("");
const scroller = ref<HTMLElement | null>(null);

const SUGGESTIONS = [
  "List all agents",
  "Rename the X agent to Y",
  "Tag the X agent with sales, priority",
  "Delete the build logs",
];

async function send() {
  const t = input.value.trim();
  if (!t || store.hermisBusy) return;
  input.value = "";
  await store.askHermis(t);
}

watch(
  () => [store.hermisMsgs.length, store.hermisBusy, store.hermisMsgs.at(-1)?.text],
  () => nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight)),
);
</script>

<template>
  <!-- launcher -->
  <button class="fab" :class="{ open: store.hermisOpen }" title="Hermis — platform assistant"
          @click="store.hermisOpen = !store.hermisOpen">
    <Icon :name="store.hermisOpen ? 'x' : 'bot'" :size="22" />
  </button>

  <transition name="pop">
    <section v-if="store.hermisOpen" class="panel">
      <header class="phead">
        <span class="mark"><Icon name="bot" :size="17" /></span>
        <div class="who"><strong>Hermis</strong><span class="sub">platform assistant · learns from feedback</span></div>
        <div class="grow" />
        <span v-if="store.hermisBusy" class="busy"><span class="dot" />{{ store.phase || "working" }}</span>
        <button class="ghost sm icon" aria-label="Close" @click="store.hermisOpen = false"><Icon name="x" :size="15" /></button>
      </header>

      <div ref="scroller" class="body">
        <div v-if="!store.hermisMsgs.length" class="intro">
          <div class="halo"><Icon name="bot" :size="22" /></div>
          <p>I manage your platform. I can rename, tag, re-policy, or delete agents,
            inspect &amp; clear activity logs, and delete documents — just ask.</p>
          <div class="sugs">
            <button v-for="s in SUGGESTIONS" :key="s" class="sug" @click="input = s">{{ s }}</button>
          </div>
        </div>
        <div v-for="(m, i) in store.hermisMsgs" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <details v-if="m.thinking" class="thinking"><summary>thinking</summary><pre>{{ m.thinking }}</pre></details>
            <div v-if="m.text" class="text">{{ m.text }}</div>
            <div v-else-if="m.role === 'assistant' && store.hermisBusy" class="typing"><span /><span /><span /></div>
          </div>
          <div v-if="m.role === 'assistant' && m.runId && m.text" class="rate">
            <template v-if="m.rated == null">
              <button class="rb" title="Good" @click="store.rate(m, 1)"><Icon name="thumbsUp" :size="13" /></button>
              <button class="rb" title="Could be better — Hermis will learn" @click="store.rate(m, -1)"><Icon name="thumbsDown" :size="13" /></button>
            </template>
            <span v-else class="rated"><Icon name="check" :size="12" /> noted</span>
          </div>
        </div>
      </div>

      <div class="composer">
        <input v-model="input" placeholder="Ask Hermis to manage anything…"
               :disabled="store.hermisBusy" @keyup.enter="send" />
        <button class="sb" :disabled="store.hermisBusy || !input.trim()" @click="send" aria-label="Send">
          <Icon name="send" :size="17" />
        </button>
      </div>
    </section>
  </transition>
</template>

<style scoped>
.fab { position: fixed; right: 22px; bottom: 22px; z-index: 60; width: 54px; height: 54px; border-radius: 50%; padding: 0; box-shadow: var(--shadow-lg); }
.fab.open { background: var(--surface-2); color: var(--ink); border: 1px solid var(--border); }
@media (max-width: 760px) { .fab { bottom: 78px; } }

.panel { position: fixed; right: 22px; bottom: 86px; z-index: 60; width: min(400px, calc(100vw - 32px));
  height: min(560px, calc(100vh - 130px)); background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); display: flex; flex-direction: column; overflow: hidden; }
@media (max-width: 760px) { .panel { right: 16px; left: 16px; width: auto; bottom: 140px; } }

.phead { display: flex; align-items: center; gap: 9px; padding: 12px 14px; border-bottom: 1px solid var(--border); background: var(--bg-glass); }
.mark { width: 30px; height: 30px; flex: none; display: grid; place-items: center; border-radius: 9px; color: var(--accent); background: var(--accent-soft); }
.who { display: flex; flex-direction: column; line-height: 1.2; }
.who strong { font-size: 14px; }
.who .sub { font-size: 11px; color: var(--faint); }
.grow { flex: 1; }
.busy { display: flex; align-items: center; gap: 5px; font-size: 11.5px; color: var(--accent); text-transform: capitalize; }
.busy .dot { width: 6px; height: 6px; border-radius: 99px; background: var(--accent); animation: veldra-pulse 1s infinite; }
.icon { padding: 5px; box-shadow: none; }

.body { flex: 1; overflow: auto; padding: 14px; display: flex; flex-direction: column; gap: 11px; }
.intro { margin: auto; text-align: center; color: var(--muted); }
.intro .halo { width: 46px; height: 46px; margin: 0 auto 12px; display: grid; place-items: center; border-radius: 13px; color: var(--accent); background: var(--accent-soft); }
.intro p { font-size: 13px; line-height: 1.55; margin: 0 0 14px; }
.sugs { display: flex; flex-direction: column; gap: 7px; }
.sug { background: var(--surface); border: 1px solid var(--border); color: var(--ink); border-radius: var(--radius-sm); padding: 9px 11px; font-size: 12.5px; text-align: left; box-shadow: none; }
.sug:hover { border-color: var(--accent); background: var(--surface-2); filter: none; }
.msg { display: flex; animation: veldra-rise .16s ease both; }
.msg.user { justify-content: flex-end; }
.bubble { max-width: 86%; padding: 9px 13px; border-radius: var(--radius); font-size: 13.5px; line-height: 1.5; }
.msg.user .bubble { background: var(--accent-grad); color: #fff; border-bottom-right-radius: 5px; }
.msg.assistant .bubble { background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 5px; }
.text { white-space: pre-wrap; word-break: break-word; }
.thinking { margin-bottom: 6px; font-size: 11.5px; color: var(--muted); }
.thinking summary { cursor: pointer; color: var(--accent); }
.thinking pre { white-space: pre-wrap; margin: 5px 0 0; padding: 7px; background: var(--surface-2); border-radius: 7px; max-height: 160px; overflow: auto; }
.typing { display: flex; gap: 4px; padding: 3px 1px; }
.typing span { width: 6px; height: 6px; border-radius: 99px; background: var(--faint); animation: veldra-pulse 1.1s infinite; }
.typing span:nth-child(2) { animation-delay: .18s; } .typing span:nth-child(3) { animation-delay: .36s; }
.rate { display: flex; align-items: center; gap: 5px; margin: 4px 0 0 4px; }
.rb { background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); padding: 3px 8px; border-radius: 7px; box-shadow: none; }
.rb:hover { border-color: var(--accent); color: var(--accent); filter: none; }
.rated { font-size: 11px; color: var(--ok); display: inline-flex; align-items: center; gap: 4px; }
.composer { display: flex; gap: 8px; padding: 12px 14px; border-top: 1px solid var(--border); background: var(--bg-glass); }
.composer input { flex: 1; }
.sb { width: 40px; height: 40px; padding: 0; flex: none; }

.pop-enter-active, .pop-leave-active { transition: opacity .16s ease, transform .16s ease; transform-origin: bottom right; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: scale(.96) translateY(8px); }
</style>
