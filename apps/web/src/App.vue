<script setup lang="ts">
import { computed } from "vue";
import DiffModal from "./components/DiffModal.vue";
import Icon from "./components/Icon.vue";
import WorkflowBuilder from "./components/WorkflowBuilder.vue";
import { useAgentStore } from "./stores/agent";
import KnowledgeView from "./views/KnowledgeView.vue";
import StudioView from "./views/StudioView.vue";
import WorkflowsView from "./views/WorkflowsView.vue";

const store = useAgentStore();
const NAV = [
  { id: "studio", label: "Studio", icon: "sparkles" },
  { id: "knowledge", label: "Knowledge", icon: "book" },
  { id: "workflows", label: "Agents", icon: "workflow" },
] as const;

const current = computed(
  () => (({ studio: StudioView, knowledge: KnowledgeView, workflows: WorkflowsView }) as any)[store.view],
);
const title = computed(() => NAV.find((n) => n.id === store.view)?.label ?? "Veldra");
</script>

<template>
  <div class="app">
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
        <span class="word">Veldra</span>
      </div>
      <nav class="nav">
        <button v-for="n in NAV" :key="n.id" class="navbtn" :class="{ active: store.view === n.id }"
                @click="store.view = n.id">
          <Icon :name="n.icon" :size="19" /><span class="lbl">{{ n.label }}</span>
        </button>
      </nav>
      <div class="grow" />
      <div class="foot"><span class="dotlive" />local-first · talk an agent into existence</div>
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
      </header>
      <component :is="current" />
    </main>

    <nav class="tabbar">
      <button v-for="n in NAV" :key="n.id" class="tab" :class="{ active: store.view === n.id }"
              @click="store.view = n.id">
        <Icon :name="n.icon" :size="21" /><span>{{ n.label }}</span>
      </button>
    </nav>

    <DiffModal />
    <WorkflowBuilder />
  </div>
</template>

<style scoped>
.app { height: 100vh; height: 100dvh; display: flex; }

.sidebar {
  width: 216px; flex-shrink: 0; background: var(--bg-soft); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 16px 12px;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 6px 8px 18px; }
.mark { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 9px;
  background: var(--accent-soft); color: var(--accent); }
.mark svg { width: 19px; height: 19px; }
.word { font-weight: 750; font-size: 18px; letter-spacing: -0.02em;
  background: var(--accent-grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.nav { display: flex; flex-direction: column; gap: 3px; }
.navbtn {
  display: flex; align-items: center; gap: 11px; background: none; border: none; color: var(--muted);
  text-align: left; padding: 10px 11px; border-radius: var(--radius-sm); font-weight: 550; font-size: 14px;
}
.navbtn:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.navbtn.active { background: var(--accent-soft); color: var(--accent); }
.grow { flex: 1; }
.foot { color: var(--faint); font-size: 11px; line-height: 1.5; padding: 8px; display: flex; align-items: center; gap: 7px; }
.dotlive { width: 7px; height: 7px; border-radius: 99px; background: var(--ok); box-shadow: 0 0 0 3px var(--ok-soft); flex: none; }

.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.topbar { display: none; align-items: center; gap: 10px; padding: 12px 16px;
  border-bottom: 1px solid var(--border); background: var(--bg-glass); backdrop-filter: blur(10px); }
.topbar .mark.sm { width: 26px; height: 26px; }
.topbar strong { font-size: 16px; }

.tabbar { display: none; }

/* ── mobile ── */
@media (max-width: 760px) {
  .app { flex-direction: column; }
  .sidebar { display: none; }
  .topbar { display: flex; position: sticky; top: 0; z-index: 20; }
  .main { padding-bottom: 64px; }
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
