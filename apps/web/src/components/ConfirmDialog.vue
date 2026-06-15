<script setup lang="ts">
import { useAgentStore } from "../stores/agent";
import Icon from "./Icon.vue";

const store = useAgentStore();
</script>

<template>
  <transition name="cd">
    <div v-if="store.confirmState" class="cd-wrap" @click.self="store.resolveConfirm(false)">
      <div class="cd" role="alertdialog" aria-modal="true" :aria-label="store.confirmState.title">
        <div class="cd-icon" :class="{ danger: store.confirmState.danger }">
          <Icon :name="store.confirmState.danger ? 'trash' : 'check'" :size="20" />
        </div>
        <h3>{{ store.confirmState.title }}</h3>
        <p>{{ store.confirmState.message }}</p>
        <div class="cd-actions">
          <button class="ghost" @click="store.resolveConfirm(false)">Cancel</button>
          <button :class="store.confirmState.danger ? 'danger' : ''" @click="store.resolveConfirm(true)">
            {{ store.confirmState.confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.cd-wrap { position: fixed; inset: 0; z-index: 90; background: rgba(0, 0, 0, 0.55);
  display: flex; align-items: center; justify-content: center; padding: 16px; backdrop-filter: blur(2px); }
.cd { width: min(400px, 94vw); background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 22px; text-align: center; box-shadow: var(--shadow-lg);
  animation: veldra-pop 0.16s ease both; }
.cd-icon { width: 46px; height: 46px; margin: 0 auto 14px; display: grid; place-items: center;
  border-radius: 14px; background: var(--accent-soft); color: var(--accent); }
.cd-icon.danger { background: var(--danger-soft); color: var(--danger); }
.cd h3 { margin: 0 0 6px; font-size: 17px; }
.cd p { margin: 0 0 20px; color: var(--muted); font-size: 14px; line-height: 1.55; }
.cd-actions { display: flex; gap: 10px; }
.cd-actions button { flex: 1; padding: 10px; }
.danger { background: var(--danger); color: #fff; border: none; box-shadow: none; }
.cd-enter-active, .cd-leave-active { transition: opacity 0.16s ease; }
.cd-enter-from, .cd-leave-to { opacity: 0; }
</style>
