<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useAgentStore } from "../stores/agent";
import Icon from "./Icon.vue";

const store = useAgentStore();
const open = ref(false);
const query = ref("");
const active = ref(0);
const inputEl = ref<HTMLInputElement | null>(null);

interface Cmd { id: string; label: string; hint?: string; icon: string; run: () => void; }

function go(view: string) { store.view = view as any; }

const COMMANDS = computed<Cmd[]>(() => [
  { id: "home", label: "Go to Home", hint: "Agents & overview", icon: "sparkles", run: () => go("home") },
  { id: "workflows", label: "All agents", hint: "Manage, tag, export", icon: "workflow", run: () => go("workflows") },
  { id: "knowledge", label: "Go to Knowledge", hint: "Documents & retrieval", icon: "book", run: () => go("knowledge") },
  { id: "skills", label: "Go to Skills", hint: "Markdown playbooks", icon: "scroll", run: () => go("skills") },
  { id: "insights", label: "Go to Insights", hint: "Usage, cost & reliability", icon: "chart", run: () => go("insights") },
  { id: "activity", label: "Go to Activity", hint: "Run logs & traces", icon: "activity", run: () => go("activity") },
  { id: "new", label: "Create an agent", hint: "Describe · Team · Manual", icon: "plus", run: () => store.openCreate() },
  { id: "company", label: "Set up a team for a company", hint: "Auto-build a team", icon: "layers", run: () => store.openCreate() },
  { id: "faust", label: "Open Faust", hint: "Platform assistant", icon: "bot", run: () => { store.faustOpen = true; } },
  { id: "settings", label: "Open Settings", hint: "Theme, accent, config", icon: "settings", run: () => store.openSettings() },
]);

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return COMMANDS.value;
  return COMMANDS.value.filter((c) => (c.label + " " + (c.hint || "")).toLowerCase().includes(q));
});

let lastFocused: HTMLElement | null = null;
function show() {
  lastFocused = document.activeElement as HTMLElement | null;
  open.value = true;
  query.value = "";
  active.value = 0;
  nextTick(() => inputEl.value?.focus());
}
function hide() {
  open.value = false;
  lastFocused?.focus?.();  // restore focus to the trigger
}
function pick(c?: Cmd) {
  const cmd = c || filtered.value[active.value];
  if (!cmd) return;
  hide();
  cmd.run();
}
watch(filtered, () => { active.value = 0; });

function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    open.value ? hide() : show();
    return;
  }
  if (!open.value) return;
  if (e.key === "Escape") { e.preventDefault(); hide(); }
  else if (e.key === "ArrowDown") { e.preventDefault(); active.value = (active.value + 1) % filtered.value.length; }
  else if (e.key === "ArrowUp") { e.preventDefault(); active.value = (active.value - 1 + filtered.value.length) % filtered.value.length; }
  else if (e.key === "Enter") { e.preventDefault(); pick(); }
}
onMounted(() => window.addEventListener("keydown", onKey));
onUnmounted(() => window.removeEventListener("keydown", onKey));
defineExpose({ show });
</script>

<template>
  <transition name="cp">
    <div v-if="open" class="cp-wrap" @click.self="hide">
      <div class="cp" role="dialog" aria-modal="true" aria-label="Command palette">
        <div class="cp-search">
          <Icon name="search" :size="17" />
          <input ref="inputEl" v-model="query" aria-label="Search commands"
                 role="combobox" aria-expanded="true" aria-controls="cp-listbox"
                 placeholder="Type a command or search…" />
          <kbd>esc</kbd>
        </div>
        <div id="cp-listbox" class="cp-list" role="listbox" aria-label="Commands">
          <button v-for="(c, i) in filtered" :key="c.id" class="cp-item" :class="{ on: i === active }"
                  role="option" :aria-selected="i === active"
                  @mousemove="active = i" @click="pick(c)">
            <span class="cp-ic"><Icon :name="c.icon" :size="16" /></span>
            <span class="cp-lbl">{{ c.label }}</span>
            <span v-if="c.hint" class="cp-hint">{{ c.hint }}</span>
          </button>
          <div v-if="!filtered.length" class="cp-empty">No matching commands.</div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.cp-wrap { position: fixed; inset: 0; z-index: 80; background: rgba(0, 0, 0, 0.5); display: flex; justify-content: center; align-items: flex-start; padding-top: 14vh; backdrop-filter: blur(2px); }
.cp { width: min(560px, 92vw); background: var(--bg); border: 1px solid var(--border-strong); border-radius: var(--radius); box-shadow: var(--shadow-lg); overflow: hidden; animation: veldra-pop 0.14s ease both; }
.cp-search { display: flex; align-items: center; gap: 10px; padding: 13px 15px; border-bottom: 1px solid var(--border); color: var(--muted); }
.cp-search input { flex: 1; border: none; background: none; padding: 0; font-size: 15px; color: var(--ink); box-shadow: none !important; }
.cp-search kbd { font-size: 10.5px; color: var(--faint); border: 1px solid var(--border); border-radius: 5px; padding: 1px 6px; background: var(--surface-2); }
.cp-list { max-height: 52vh; overflow: auto; padding: 6px; }
.cp-item { width: 100%; display: flex; align-items: center; gap: 11px; background: none; border: none; box-shadow: none; padding: 10px 11px; border-radius: var(--radius-sm); color: var(--ink); text-align: left; }
.cp-item.on { background: var(--accent-soft); }
.cp-ic { width: 28px; height: 28px; flex: none; display: grid; place-items: center; border-radius: 7px; background: var(--surface-2); color: var(--muted); }
.cp-item.on .cp-ic { color: var(--accent); }
.cp-lbl { font-size: 14px; font-weight: 500; }
.cp-hint { margin-left: auto; font-size: 12px; color: var(--faint); }
.cp-empty { padding: 18px; text-align: center; color: var(--faint); font-size: 13px; }
.cp-enter-active, .cp-leave-active { transition: opacity 0.14s ease; }
.cp-enter-from, .cp-leave-to { opacity: 0; }
</style>
