<script setup lang="ts">
import { computed } from "vue";
import DiffModal from "./components/DiffModal.vue";
import WorkflowBuilder from "./components/WorkflowBuilder.vue";
import { useAgentStore } from "./stores/agent";
import KnowledgeView from "./views/KnowledgeView.vue";
import StudioView from "./views/StudioView.vue";
import WorkflowsView from "./views/WorkflowsView.vue";

const store = useAgentStore();
const NAV = [
  { id: "studio", label: "Studio", icon: "✎" },
  { id: "knowledge", label: "Knowledge", icon: "📚" },
  { id: "workflows", label: "Workflows", icon: "⚒" },
] as const;

const current = computed(
  () => (({ studio: StudioView, knowledge: KnowledgeView, workflows: WorkflowsView }) as any)[store.view],
);
</script>

<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <svg class="logo" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="5" cy="7" r="2.4" fill="currentColor" />
          <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.75" />
          <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.55" />
          <path d="M5 7 L19 9 M5 7 L12 18 M19 9 L12 18" stroke="currentColor" stroke-width="1.4" opacity="0.45" />
        </svg>
        <span class="word">Veldra</span>
      </div>
      <nav>
        <button v-for="n in NAV" :key="n.id" class="navbtn" :class="{ active: store.view === n.id }"
                @click="store.view = n.id">
          <span class="ic">{{ n.icon }}</span>{{ n.label }}
        </button>
      </nav>
      <div class="grow" />
      <div class="foot">local-first · talk an<br />agent into existence</div>
    </aside>

    <main class="main">
      <component :is="current" />
    </main>

    <DiffModal />
    <WorkflowBuilder />
  </div>
</template>

<style scoped>
.app { height: 100vh; display: flex; }
.sidebar { width: 210px; flex-shrink: 0; background: var(--bg-soft); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 16px 12px; }
.brand { display: flex; align-items: center; gap: 9px; padding: 4px 8px 16px; }
.logo { width: 22px; height: 22px; color: var(--accent); }
.word { font-weight: 700; font-size: 17px; letter-spacing: -0.02em; }
nav { display: flex; flex-direction: column; gap: 4px; }
.navbtn { display: flex; align-items: center; gap: 10px; background: none; border: none; color: var(--muted);
  text-align: left; padding: 9px 11px; border-radius: var(--radius-sm); font-weight: 500; }
.navbtn:hover { background: var(--surface-2); color: var(--ink); filter: none; }
.navbtn.active { background: var(--accent-soft); color: var(--accent); }
.ic { width: 18px; text-align: center; }
.grow { flex: 1; }
.foot { color: var(--faint); font-size: 11px; line-height: 1.5; padding: 8px; }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
@media (max-width: 760px) { .sidebar { width: 64px; } .word, .foot { display: none; } .navbtn { justify-content: center; } .navbtn span:not(.ic) { display: none; } }
</style>
