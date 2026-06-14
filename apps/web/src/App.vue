<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import CommandPalette from "./components/CommandPalette.vue";
import ConfirmDialog from "./components/ConfirmDialog.vue";
import DiffModal from "./components/DiffModal.vue";
import FaustBot from "./components/FaustBot.vue";
import Icon from "./components/Icon.vue";
import SettingsPanel from "./components/SettingsPanel.vue";
import WorkflowBuilder from "./components/WorkflowBuilder.vue";
import { applyTheme } from "./theme";
import { useAgentStore } from "./stores/agent";
import AgentChatView from "./views/AgentChatView.vue";
import KnowledgeView from "./views/KnowledgeView.vue";
import LogsView from "./views/LogsView.vue";
import SkillsView from "./views/SkillsView.vue";
import StudioView from "./views/StudioView.vue";
import WorkflowsView from "./views/WorkflowsView.vue";

const store = useAgentStore();

// Minimal hash router: #/agent/<id> opens a standalone, shareable agent test page;
// everything else is the main app shell. No vue-router dependency needed.
function parseHash(): { name: "agent"; id: string } | { name: "app" } {
  const m = (window.location.hash || "").match(/^#\/agent\/(.+)$/);
  return m ? { name: "agent", id: decodeURIComponent(m[1]) } : { name: "app" };
}
const route = ref(parseHash());
function onHash() { route.value = parseHash(); }
function exitAgentChat() { window.location.hash = ""; }
onMounted(() => { applyTheme(); window.addEventListener("hashchange", onHash); });
onUnmounted(() => window.removeEventListener("hashchange", onHash));
const NAV = [
  { id: "studio", label: "Studio", icon: "sparkles" },
  { id: "knowledge", label: "Knowledge", icon: "book" },
  { id: "skills", label: "Skills", icon: "scroll" },
  { id: "workflows", label: "Agents", icon: "workflow" },
  { id: "activity", label: "Activity", icon: "activity" },
] as const;
const NAV_GROUPS = [
  { label: "Build", ids: ["studio", "knowledge", "skills"] },
  { label: "Manage", ids: ["workflows", "activity"] },
] as const;
const navItem = (id: string) => NAV.find((n) => n.id === id)!;

const current = computed(
  () =>
    (({ studio: StudioView, knowledge: KnowledgeView, skills: SkillsView,
        workflows: WorkflowsView, activity: LogsView }) as any)[store.view],
);
const title = computed(() => NAV.find((n) => n.id === store.view)?.label ?? "Veldra");
const palette = ref<InstanceType<typeof CommandPalette> | null>(null);
</script>

<template>
  <!-- standalone, shareable per-agent test chat at #/agent/<id> -->
  <AgentChatView v-if="route.name === 'agent'" :agent-id="route.id" @exit="exitAgentChat" />

  <div v-else class="app">
    <aside class="sidebar">
      <div class="brand">
        <span class="mark">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="7" r="2.4" fill="currentColor" />
            <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
            <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
            <path d="M5 7 19 9 M5 7 12 18 M19 9 12 18" stroke="currentColor" stroke-width="1.4" opacity="0.5" />
          </svg>
        </span>
        <span class="brand-text">
          <span class="word">Veldra</span>
          <span class="tagline">agent harness</span>
        </span>
      </div>

      <button class="cmdk" @click="palette?.show()">
        <Icon name="search" :size="14" /><span>Search & commands</span><kbd>⌘K</kbd>
      </button>

      <nav class="nav">
        <template v-for="g in NAV_GROUPS" :key="g.label">
          <div class="navgroup">{{ g.label }}</div>
          <button v-for="id in g.ids" :key="id" class="navbtn" :class="{ active: store.view === id }"
                  @click="store.view = id">
            <span class="bar" /><Icon :name="navItem(id).icon" :size="18" /><span class="lbl">{{ navItem(id).label }}</span>
          </button>
        </template>
      </nav>

      <div class="grow" />

      <button class="faustbtn" @click="store.faustOpen = true">
        <span class="favatar"><Icon name="bot" :size="15" /></span>
        <span class="fmeta"><strong>Faust</strong><small>platform assistant</small></span>
        <Icon name="sparkles" :size="14" class="fspark" />
      </button>
      <button class="cmdk" @click="store.openSettings()">
        <Icon name="settings" :size="14" /><span>Settings</span>
      </button>
      <div class="foot"><span class="dotlive" />local-first · the agent that grows with you</div>
    </aside>

    <main class="main">
      <header class="topbar">
        <span class="mark sm">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="7" r="2.4" fill="currentColor" />
            <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
            <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
          </svg>
        </span>
        <strong>{{ title }}</strong>
        <div class="grow" />
        <button class="tbtn" aria-label="Search & commands" @click="palette?.show()"><Icon name="search" :size="18" /></button>
        <button class="tbtn" aria-label="Faust assistant" @click="store.faustOpen = true"><Icon name="bot" :size="18" /></button>
        <button class="tbtn" aria-label="Settings" @click="store.openSettings()"><Icon name="settings" :size="18" /></button>
      </header>
      <component :is="current" />
    </main>

    <nav class="tabbar">
      <button v-for="n in NAV" :key="n.id" class="tab" :class="{ active: store.view === n.id }"
              @click="store.view = n.id">
        <Icon :name="n.icon" :size="21" /><span>{{ n.label }}</span>
      </button>
    </nav>
  </div>

  <!-- global overlays: mounted once, outside the route branch so they work on the
       standalone agent page too (builder, confirm dialogs, Faust, …). -->
  <DiffModal />
  <WorkflowBuilder />
  <FaustBot />
  <CommandPalette ref="palette" />
  <ConfirmDialog />
  <SettingsPanel />
</template>

<style scoped>
.app { height: 100vh; height: 100dvh; display: flex; }

.sidebar {
  width: 232px; flex-shrink: 0; background: var(--bg-soft); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 14px 12px 12px;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 6px 8px 14px; }
.mark { width: 32px; height: 32px; flex: none; display: grid; place-items: center; border-radius: 10px;
  background: linear-gradient(150deg, var(--accent-soft), color-mix(in srgb, var(--accent-strong) 22%, transparent));
  color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent-ring); }
.mark svg { width: 19px; height: 19px; }
.brand-text { display: flex; flex-direction: column; line-height: 1.1; min-width: 0; }
.word { font-weight: 700; font-size: 18px; letter-spacing: -0.02em; color: var(--ink); }
.tagline { font-size: 10.5px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }

.nav { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.navgroup { font-size: 10px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--muted); padding: 12px 12px 5px; }
.navgroup:first-child { padding-top: 4px; }
.navbtn {
  position: relative; display: flex; align-items: center; gap: 11px; background: none; border: none;
  color: var(--muted); text-align: left; padding: 9px 12px; border-radius: var(--radius-sm);
  font-weight: 550; font-size: 14px;
}
.navbtn .bar { position: absolute; left: 3px; top: 50%; width: 3px; height: 0; border-radius: 99px;
  background: var(--accent); transform: translateY(-50%); transition: height 0.16s ease; }
.navbtn:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.navbtn.active { background: var(--accent-soft); color: var(--accent); }
.navbtn.active .bar { height: 18px; }
.grow { flex: 1; }

.cmdk { width: 100%; justify-content: flex-start; gap: 8px; background: var(--surface); border: 1px solid var(--border); color: var(--muted); font-size: 12.5px; font-weight: 500; padding: 8px 10px; margin-bottom: 8px; }
.cmdk:hover { border-color: var(--border-strong); color: var(--ink); filter: none; }
.cmdk kbd { margin-left: auto; font-size: 10.5px; border: 1px solid var(--border); border-radius: 5px; padding: 1px 5px; background: var(--surface-2); color: var(--faint); }

.faustbtn { width: 100%; justify-content: flex-start; gap: 10px; background: var(--surface);
  border: 1px solid var(--border); color: var(--ink); padding: 8px 10px; margin-bottom: 8px; text-align: left; }
.faustbtn:hover { border-color: var(--accent); filter: none; }
.favatar { width: 26px; height: 26px; flex: none; display: grid; place-items: center; border-radius: 8px;
  background: var(--accent-soft); color: var(--accent); }
.fmeta { display: flex; flex-direction: column; line-height: 1.2; min-width: 0; }
.fmeta strong { font-size: 13px; font-weight: 650; }
.fmeta small { font-size: 10.5px; color: var(--faint); }
.fspark { margin-left: auto; color: var(--faint); }
.faustbtn:hover .fspark { color: var(--accent); }

.foot { color: var(--faint); font-size: 11px; line-height: 1.5; padding: 6px 8px; display: flex; align-items: center; gap: 7px; }
.dotlive { width: 7px; height: 7px; border-radius: 99px; background: var(--ok); box-shadow: 0 0 0 3px var(--ok-soft); flex: none; }

.main { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.topbar { display: none; align-items: center; gap: 10px; padding: 10px 14px;
  border-bottom: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(10px); }
.topbar .mark.sm { width: 26px; height: 26px; flex: none; }
.topbar strong { font-size: 16px; }
.topbar .grow { flex: 1; }
.tbtn { background: none; border: none; color: var(--muted); padding: 7px; border-radius: var(--radius-sm); box-shadow: none; }
.tbtn:hover { background: var(--surface-2); color: var(--ink); filter: none; }

.tabbar { display: none; }

/* ── mobile ── */
@media (max-width: 760px) {
  .app { flex-direction: column; }
  .sidebar { display: none; }
  .topbar { display: flex; position: sticky; top: 0; z-index: 20; }
  /* spacer must include the safe-area inset the fixed tabbar reserves, else it overlaps content */
  .main { padding-bottom: calc(66px + env(safe-area-inset-bottom)); }
  .tabbar {
    display: flex; position: fixed; bottom: 0; left: 0; right: 0; z-index: 30;
    background: var(--bg-glass); backdrop-filter: blur(14px); border-top: 1px solid var(--border);
    padding: 6px 6px calc(6px + env(safe-area-inset-bottom));
  }
  .tab {
    flex: 1; flex-direction: column; gap: 3px; background: none; border: none; color: var(--faint);
    font-size: 11px; font-weight: 600; padding: 7px 0; border-radius: var(--radius-sm);
  }
  .tab.active { color: var(--accent); background: var(--accent-soft); }
}
</style>
