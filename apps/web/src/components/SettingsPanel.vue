<script setup lang="ts">
import { ref } from "vue";
import { useAgentStore } from "../stores/agent";
import { ACCENT_SWATCH, ACCENTS, type Accent, getAccent, getMode, type Mode, setAccent, setMode } from "../theme";
import Icon from "./Icon.vue";

const store = useAgentStore();
const mode = ref<Mode>(getMode());
const accent = ref<Accent>(getAccent());
const MODES: { id: Mode; label: string; icon: string }[] = [
  { id: "system", label: "System", icon: "settings" },
  { id: "light", label: "Light", icon: "sparkles" },
  { id: "dark", label: "Dark", icon: "bot" },
];
function pickMode(m: Mode) { mode.value = m; setMode(m); }
function pickAccent(a: Accent) { accent.value = a; setAccent(a); }
</script>

<template>
  <transition name="cd">
    <div v-if="store.settingsOpen"
         class="fixed inset-0 z-[85] flex items-center justify-center p-4"
         style="background: rgba(0,0,0,.55); backdrop-filter: blur(2px)"
         @click.self="store.settingsOpen = false">
      <div class="w-[min(560px,95vw)] max-h-[86vh] overflow-auto rounded-veldra-lg border border-border bg-bg shadow-[var(--shadow-lg)]"
           style="animation: veldra-pop .16s ease both" role="dialog" aria-modal="true" aria-label="Settings">
        <header class="flex items-center gap-2.5 px-5 py-4 border-b border-border sticky top-0 bg-bg z-10">
          <span class="grid place-items-center w-8 h-8 rounded-[9px] bg-accent/15 text-accent"><Icon name="settings" :size="17" /></span>
          <strong class="text-[16px]">Settings</strong>
          <div class="flex-1" />
          <button class="ghost sm" aria-label="Close" @click="store.settingsOpen = false"><Icon name="x" :size="15" /></button>
        </header>

        <div class="p-5 flex flex-col gap-6">
          <!-- Appearance -->
          <section>
            <h3 class="text-[12px] font-semibold uppercase tracking-wide text-muted mb-2.5">Appearance</h3>
            <div class="inline-flex rounded-veldra-sm border border-border overflow-hidden">
              <button v-for="m in MODES" :key="m.id"
                      class="flex items-center gap-2 px-4 py-2 text-[13px] font-medium border-r border-border last:border-r-0"
                      :class="mode === m.id ? 'bg-accent/15 text-accent' : 'bg-surface text-muted hover:text-ink'"
                      style="box-shadow:none" @click="pickMode(m.id)">
                <Icon :name="m.icon" :size="15" />{{ m.label }}
              </button>
            </div>
          </section>

          <!-- Accent -->
          <section>
            <h3 class="text-[12px] font-semibold uppercase tracking-wide text-muted mb-2.5">Accent color</h3>
            <div class="flex flex-wrap gap-2.5">
              <button v-for="a in ACCENTS" :key="a" :title="a"
                      class="w-9 h-9 rounded-full border-2 transition"
                      :class="accent === a ? 'border-ink scale-110' : 'border-transparent'"
                      :style="{ background: ACCENT_SWATCH[a], boxShadow: 'none' }"
                      @click="pickAccent(a)">
                <Icon v-if="accent === a" name="check" :size="16" class="text-white m-auto" />
              </button>
            </div>
            <p class="text-[12px] text-faint mt-2 capitalize">{{ accent }}</p>
          </section>

          <!-- Environment -->
          <section v-if="store.config">
            <h3 class="text-[12px] font-semibold uppercase tracking-wide text-muted mb-2.5">Environment</h3>
            <div class="grid grid-cols-2 gap-px bg-border rounded-veldra-sm overflow-hidden border border-border">
              <div v-for="[k, v] in Object.entries(store.config)" :key="k" class="bg-surface px-3 py-2">
                <div class="text-[11px] text-faint">{{ k.replace(/_/g, ' ') }}</div>
                <div class="text-[13px] font-mono truncate">{{ v }}</div>
              </div>
            </div>
            <p class="text-[11.5px] text-faint mt-2">Read-only — set via environment / .env.</p>
          </section>

          <!-- Tools catalog -->
          <section v-if="store.toolCatalog.length">
            <h3 class="text-[12px] font-semibold uppercase tracking-wide text-muted mb-2.5">
              Built-in tools <span class="text-faint font-normal normal-case">({{ store.toolCatalog.length }})</span>
            </h3>
            <ul class="flex flex-col gap-1.5">
              <li v-for="t in store.toolCatalog" :key="t.name"
                  class="flex gap-2.5 items-baseline rounded-veldra-sm border border-border bg-surface px-3 py-2">
                <code class="text-[12.5px] text-accent shrink-0">{{ t.name }}</code>
                <span class="text-[12.5px] text-muted leading-snug">{{ t.description }}</span>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  </transition>
</template>
