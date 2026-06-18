<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref } from "vue";
import CommandPalette from "./components/CommandPalette.vue";
import ConfirmDialog from "./components/ConfirmDialog.vue";
import CreateAgentModal from "./components/CreateAgentModal.vue";
import DiffModal from "./components/DiffModal.vue";
import FaustBot from "./components/FaustBot.vue";
import Icon from "./components/Icon.vue";
import SettingsPanel from "./components/SettingsPanel.vue";
// Lazy: pulls in @vue-flow/core (large) — load it only when the builder opens,
// keeping it out of the initial bundle.
const WorkflowBuilder = defineAsyncComponent(() => import("./components/WorkflowBuilder.vue"));
import { applyTheme, getMode, setMode } from "./theme";
import { initial } from "./colors";
import { useAgentStore } from "./stores/agent";
import AcceptInviteView from "./views/AcceptInviteView.vue";
import AgentChatView from "./views/AgentChatView.vue";
import ChatView from "./views/ChatView.vue";
import HomeView from "./views/HomeView.vue";
import InsightsView from "./views/InsightsView.vue";
import KnowledgeView from "./views/KnowledgeView.vue";
import LogsView from "./views/LogsView.vue";
import PluginsView from "./views/PluginsView.vue";
import SetupView from "./views/SetupView.vue";
import SignInView from "./views/SignInView.vue";
import SkillsView from "./views/SkillsView.vue";
import WorkflowsView from "./views/WorkflowsView.vue";

const store = useAgentStore();

// Minimal hash router: #/agent/<id> = standalone test page, #/accept/<token> = invite.
function parseHash(): { name: "agent" | "accept"; id: string } | { name: "app" } {
  const h = window.location.hash || "";
  let m = h.match(/^#\/agent\/(.+)$/);
  if (m) return { name: "agent", id: decodeURIComponent(m[1]) };
  m = h.match(/^#\/accept\/(.+)$/);
  if (m) return { name: "accept", id: decodeURIComponent(m[1]) };
  return { name: "app" };
}
const route = ref(parseHash());
function onHash() { route.value = parseHash(); }
function exitAgentChat() { window.location.hash = ""; }
function exitAccept() { window.location.hash = ""; }
function onUnauth() { store.onUnauthorized(); }

const mode = ref(getMode());
function toggleTheme() {
  mode.value = mode.value === "dark" ? "light" : "dark";
  setMode(mode.value);
}

async function doLogout() {
  menuOpen.value = false;
  await store.logout();
}

onMounted(async () => {
  applyTheme();
  window.addEventListener("hashchange", onHash);
  window.addEventListener("veldra:unauthorized", onUnauth);
  await store.boot();
  if (store.me || !store.authEnabled) store.ensureConfig();
  // dev-only: ?demo=<view> jumps straight to a shell view for design QA / screenshots
  if (import.meta.env.DEV) {
    const d = new URLSearchParams(location.search).get("demo");
    if (d && SHELL[d]) store.view = d as any;
  }
});
onUnmounted(() => {
  window.removeEventListener("hashchange", onHash);
  window.removeEventListener("veldra:unauthorized", onUnauth);
});

const menuOpen = ref(false);
const userMenuOpen = ref(false);
const railCollapsed = ref(localStorage.getItem("veldra.rail") === "1");
function toggleRail() {
  railCollapsed.value = !railCollapsed.value;
  localStorage.setItem("veldra.rail", railCollapsed.value ? "1" : "0");
}
const MENU = [
  { id: "home", label: "Home", icon: "sparkles" },
  { id: "workflows", label: "All agents", icon: "workflow" },
  { id: "knowledge", label: "Knowledge", icon: "book" },
  { id: "skills", label: "Skills", icon: "scroll" },
  { id: "plugins", label: "Plugins", icon: "plug" },
  { id: "insights", label: "Insights", icon: "chart" },
  { id: "activity", label: "Activity", icon: "activity" },
] as const;
function navTo(id: string) { store.view = id as any; menuOpen.value = false; }

const SHELL: Record<string, any> = {
  home: HomeView, knowledge: KnowledgeView, skills: SkillsView,
  workflows: WorkflowsView, insights: InsightsView, activity: LogsView,
  plugins: PluginsView,
};
const current = computed(() => SHELL[store.view] || HomeView);
const title = computed(() => MENU.find((m) => m.id === store.view)?.label ?? "Veldra");
const palette = ref<InstanceType<typeof CommandPalette> | null>(null);
</script>

<template>
  <!-- boot splash while we decide install / sign-in / app -->
  <div v-if="!store.authReady" class="bootsplash">
    <span class="bmark">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="5" cy="7" r="2.4" fill="currentColor" />
        <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
        <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
      </svg>
    </span>
  </div>

  <!-- first-run install wizard -->
  <SetupView v-else-if="store.setupNeeded" />

  <!-- invite acceptance (#/accept/<token>) -->
  <AcceptInviteView v-else-if="route.name === 'accept'" :token="route.id" @exit="exitAccept" />

  <!-- sign-in gate -->
  <SignInView v-else-if="store.authEnabled && !store.me" />

  <!-- authenticated app -->
  <template v-else>
  <!-- standalone, shareable per-agent test chat at #/agent/<id> -->
  <AgentChatView v-if="route.name === 'agent'" :agent-id="route.id" @exit="exitAgentChat" />

  <!-- focused single-agent chat screen -->
  <ChatView v-else-if="store.view === 'chat'" />

  <!-- main shell: persistent workspace rail + body + (mobile) slide-in menu -->
  <div v-else class="app">
    <aside class="rail" :class="{ collapsed: railCollapsed }">
      <button class="rbrand" @click="navTo('home')" title="Home">
        <span class="mark">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="7" r="2.4" fill="currentColor" />
            <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
            <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
            <path d="M5 7 19 9 M5 7 12 18 M19 9 12 18" stroke="currentColor" stroke-width="1.4" opacity="0.5" />
          </svg>
        </span>
        <span class="rword">{{ store.workspace?.name || "Veldra" }}</span>
      </button>

      <button class="newbtn rcreate" @click="store.openCreate()" :title="railCollapsed ? 'Create' : ''">
        <Icon name="plus" :size="16" /><span class="rlabel">Create</span>
      </button>

      <nav class="rnav">
        <button v-for="m in MENU" :key="m.id" class="rlink" :class="{ on: store.view === m.id }"
                @click="navTo(m.id)" :title="m.label">
          <Icon :name="m.icon" :size="18" /><span class="rlabel">{{ m.label }}</span>
        </button>
      </nav>

      <div class="grow" />
      <button class="rlink" @click="store.faustOpen = true" title="Faust assistant">
        <Icon name="bot" :size="18" /><span class="rlabel">Faust</span></button>
      <button class="rlink" @click="store.openSettings()" title="Settings">
        <Icon name="settings" :size="18" /><span class="rlabel">Settings</span></button>

      <div v-if="store.me" class="ruser">
        <button class="uchip" @click="userMenuOpen = !userMenuOpen">
          <span class="uava">{{ initial(store.me.name || store.me.email) }}</span>
          <span class="rlabel uinfo">
            <strong>{{ store.me.name || store.me.email }}</strong><small>{{ store.me.role }}</small>
          </span>
        </button>
        <transition name="pop">
          <div v-if="userMenuOpen" class="umenu" @click="userMenuOpen = false">
            <button class="umitem" @click="doLogout"><Icon name="x" :size="15" />Sign out</button>
          </div>
        </transition>
      </div>

      <button class="rcollapse" @click="toggleRail" :title="railCollapsed ? 'Expand' : 'Collapse'">
        <Icon name="chevron" :size="16" />
      </button>
    </aside>

    <div class="body">
      <header class="topbar">
        <button class="ib only-mobile" aria-label="Menu" @click="menuOpen = true"><Icon name="menu" :size="20" /></button>
        <h1 class="ptitle">{{ title }}</h1>
        <div class="grow" />
        <button class="ib" aria-label="Search (⌘K)" title="Search (⌘K)" @click="palette?.show()"><Icon name="search" :size="19" /></button>
        <button class="ib" aria-label="Toggle theme" title="Light / dark" @click="toggleTheme"><Icon name="sparkles" :size="19" /></button>
        <button class="newbtn only-mobile" @click="store.openCreate()"><Icon name="plus" :size="16" /></button>
      </header>
      <main class="main"><KeepAlive><component :is="current" /></KeepAlive></main>
    </div>

    <!-- slide-in nav menu -->
    <transition name="menu">
      <div v-if="menuOpen" class="menuwrap" @click.self="menuOpen = false">
        <aside class="menu">
          <div class="mhead">
            <span class="mark"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="5" cy="7" r="2.4" fill="currentColor"/><circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78"/><circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58"/></svg></span>
            <strong>Veldra</strong>
            <div class="grow" />
            <button class="ib" aria-label="Close menu" @click="menuOpen = false"><Icon name="x" :size="18" /></button>
          </div>
          <nav class="mnav">
            <button v-for="m in MENU" :key="m.id" class="mlink" :class="{ on: store.view === m.id }" @click="navTo(m.id)">
              <Icon :name="m.icon" :size="18" /><span>{{ m.label }}</span>
            </button>
          </nav>
          <div class="grow" />
          <button class="mlink" @click="store.faustOpen = true; menuOpen = false"><Icon name="bot" :size="18" /><span>Faust assistant</span></button>
          <button class="mlink" @click="store.openSettings(); menuOpen = false"><Icon name="settings" :size="18" /><span>Settings</span></button>
          <button v-if="store.me" class="mlink" @click="doLogout"><Icon name="x" :size="18" /><span>Sign out</span></button>
          <div class="mfoot">
            <span class="dot" />
            <span v-if="store.me">{{ store.me.name || store.me.email }} · {{ store.workspace?.name || "Veldra" }}</span>
            <span v-else>{{ store.config?.llm_provider || "local-first" }} · grows with you</span>
          </div>
        </aside>
      </div>
    </transition>
  </div>

  <!-- global overlays (only inside the authenticated app) -->
  <DiffModal />
  <WorkflowBuilder v-if="store.showBuilder" />
  <FaustBot />
  <CommandPalette ref="palette" />
  <ConfirmDialog />
  <SettingsPanel />
  <CreateAgentModal />
  </template>
</template>

<style scoped>
.bootsplash { min-height: 100vh; min-height: 100dvh; display: grid; place-items: center; background: var(--bg); }
.bmark { width: 52px; height: 52px; display: grid; place-items: center; border-radius: 15px; color: var(--accent);
  background: linear-gradient(150deg, var(--accent-soft), color-mix(in srgb, var(--accent-strong) 22%, transparent));
  box-shadow: inset 0 0 0 1px var(--accent-ring); animation: veldra-pulse 1.3s ease-in-out infinite; }
.bmark svg { width: 30px; height: 30px; }

.app { height: 100vh; height: 100dvh; display: flex; overflow: hidden; }

/* ── persistent workspace rail ── */
.rail { width: 232px; flex: none; display: flex; flex-direction: column; gap: 3px;
  padding: 12px 10px; background: var(--rail-bg); border-right: 1px solid var(--border);
  transition: width 0.16s ease; }
.rail.collapsed { width: 64px; }
.rbrand { display: flex; align-items: center; gap: 10px; padding: 4px 6px 10px; background: none; border: none;
  color: var(--ink); cursor: pointer; box-shadow: none; width: 100%; justify-content: flex-start; }
.rbrand:hover { filter: none; }
.mark { width: 30px; height: 30px; flex: none; display: grid; place-items: center; border-radius: 9px;
  background: var(--grad-brand); color: #fff;
  box-shadow: 0 4px 12px -3px color-mix(in srgb, var(--accent) 50%, transparent); }
.mark svg { width: 18px; height: 18px; }
.rword { font-weight: 700; font-size: 15.5px; letter-spacing: -0.02em; white-space: nowrap; overflow: hidden; }

.rcreate { width: 100%; justify-content: flex-start; gap: 9px; margin: 2px 0 8px; padding: 9px 11px;
  background: var(--grad-brand); border: none; }

.rnav { display: flex; flex-direction: column; gap: 2px; }
.rlink { width: 100%; justify-content: flex-start; gap: 11px; background: none; border: none; color: var(--muted);
  text-align: left; padding: 9px 11px; border-radius: var(--radius-sm); font-weight: 550; font-size: 14px;
  box-shadow: none; white-space: nowrap; position: relative; }
.rlink:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.rlink.on { background: var(--accent-soft); color: var(--accent); box-shadow: inset 2.5px 0 0 var(--accent); }
.rlink .icon, .rcreate .icon, .rbrand .mark { flex: none; }

.rail.collapsed .rword, .rail.collapsed .rlabel, .rail.collapsed .uinfo { display: none; }
.rail.collapsed .rbrand, .rail.collapsed .rcreate, .rail.collapsed .rlink, .rail.collapsed .uchip {
  justify-content: center; gap: 0; }

.ruser { position: relative; margin-top: 6px; border-top: 1px solid var(--border); padding-top: 8px; }
.uchip { width: 100%; justify-content: flex-start; gap: 9px; background: none; border: none; color: var(--ink);
  padding: 7px 8px; border-radius: var(--radius-sm); box-shadow: none; }
.uchip:hover { background: var(--surface-2); filter: none; }
.uava { width: 28px; height: 28px; flex: none; display: grid; place-items: center; border-radius: 8px;
  font-size: 12.5px; font-weight: 700; background: var(--grad-brand); color: #fff; }
.uinfo { display: flex; flex-direction: column; line-height: 1.2; min-width: 0; text-align: left; }
.uinfo strong { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uinfo small { font-size: 10.5px; color: var(--faint); text-transform: capitalize; }
.umenu { position: absolute; bottom: calc(100% + 4px); left: 6px; right: 6px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius-sm); box-shadow: var(--shadow-lg); padding: 5px; z-index: 30; }
.umitem { width: 100%; justify-content: flex-start; gap: 9px; background: none; border: none; color: var(--ink);
  padding: 8px 10px; box-shadow: none; font-size: 13.5px; }
.umitem:hover { background: var(--surface-2); filter: none; }

.rcollapse { width: 100%; justify-content: center; background: none; border: none; color: var(--faint);
  padding: 6px; margin-top: 4px; box-shadow: none; }
.rcollapse:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.rcollapse .icon { transition: transform 0.16s; }
.rail.collapsed .rcollapse .icon { transform: rotate(180deg); }

/* ── body (topbar + content) ── */
.body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.topbar { display: flex; align-items: center; gap: 6px; padding: 10px 18px; border-bottom: 1px solid var(--border);
  background: var(--bg-glass); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 20; }
.ptitle { margin: 0; font-size: 16px; font-weight: 650; letter-spacing: -0.01em; }
.grow { flex: 1; }
.ib { background: none; border: none; color: var(--muted); padding: 8px; border-radius: var(--radius-sm); box-shadow: none; }
.ib:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.newbtn { gap: 6px; }
.only-mobile { display: none; }
.main { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }

/* ── mobile slide-in nav ── */
.menuwrap { position: fixed; inset: 0; z-index: 60; background: rgba(27,34,55,0.4); backdrop-filter: blur(2px); display: flex; }
.menu { width: min(300px, 86vw); height: 100%; background: var(--bg-soft); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 12px; box-shadow: var(--shadow-lg); }
.mhead { display: flex; align-items: center; gap: 9px; padding: 6px 6px 12px; }
.mhead strong { font-size: 16px; }
.mnav { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.mlink { width: 100%; justify-content: flex-start; gap: 12px; background: none; border: none; color: var(--muted);
  text-align: left; padding: 11px 12px; border-radius: var(--radius-sm); font-weight: 550; font-size: 14.5px; box-shadow: none; }
.mlink:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.mlink.on { background: var(--accent-soft); color: var(--accent); }
.mfoot { color: var(--faint); font-size: 11px; padding: 10px 8px 4px; display: flex; align-items: center; gap: 7px; text-transform: capitalize; }
.mfoot .dot { width: 7px; height: 7px; border-radius: 99px; background: var(--ok); box-shadow: 0 0 0 3px var(--ok-soft); }

.menu-enter-active, .menu-leave-active { transition: opacity 0.18s; }
.menu-enter-active .menu, .menu-leave-active .menu { transition: transform 0.2s ease; }
.menu-enter-from, .menu-leave-to { opacity: 0; }
.menu-enter-from .menu, .menu-leave-to .menu { transform: translateX(-100%); }

.pop-enter-active, .pop-leave-active { transition: opacity 0.14s ease, transform 0.14s ease; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(6px); }

@media (max-width: 860px) {
  .rail { display: none; }
  .only-mobile { display: inline-flex; }
}
@media (max-width: 560px) { .hide-xs { display: none; } }
</style>
