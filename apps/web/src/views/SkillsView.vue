<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const newName = ref("");
const form = ref<any>({});
const dirty = ref(false);
const saved = ref(false);

onMounted(() => store.listSkills());

watch(() => store.openSkill, (s) => {
  form.value = s ? { name: s.name, description: s.description || "", content: s.content || "" } : {};
  dirty.value = false;
  saved.value = false;
}, { immediate: true });

function touch() { dirty.value = true; saved.value = false; }
function create() {
  const n = newName.value.trim();
  if (!n) return;
  store.createSkill(n);
  newName.value = "";
}
async function save() {
  if (!store.openSkill) return;
  await store.saveSkill(store.openSkill.id, form.value);
  store.openSkill = { ...store.openSkill, ...form.value };
  dirty.value = false;
  saved.value = true;
}
async function delSkill() {
  if (!store.openSkill) return;
  const ok = await store.confirmAction({
    title: `Delete “${store.openSkill.name}”?`, message: "This skill will be removed.",
  });
  if (ok) await store.deleteSkill(store.openSkill.id);
}
</script>

<template>
  <div class="sk">
    <aside class="list">
      <div class="newrow">
        <input v-model="newName" placeholder="New skill…" @keyup.enter="create" />
        <button class="sm" @click="create"><Icon name="plus" :size="15" /></button>
      </div>
      <button v-for="s in store.skills" :key="s.id" class="item"
              :class="{ active: store.openSkill?.id === s.id }" @click="store.openSkill = s">
        <span class="ic"><Icon name="scroll" :size="15" /></span>
        <span class="meta">
          <strong>{{ s.name }}</strong>
          <span class="desc">{{ s.description || 'no description' }}</span>
        </span>
      </button>
      <p v-if="!store.skills.length" class="muted pad">
        No skills yet. Skills are reusable Markdown playbooks an agent follows —
        the orchestrator can attach them when building an agent.
      </p>
    </aside>

    <section class="detail">
      <template v-if="store.openSkill">
        <div class="dhead">
          <Icon name="scroll" :size="18" />
          <strong>{{ form.name }}</strong>
          <span v-if="saved" class="savedtag"><Icon name="check" :size="13" /> saved</span>
          <div class="grow" />
          <button class="primary sm" :disabled="!dirty" @click="save"><Icon name="save" :size="14" />Save</button>
          <button class="ghost sm" title="Delete skill" @click="delSkill"><Icon name="trash" :size="14" /></button>
        </div>
        <div class="grid2">
          <label class="field"><span>Name</span><input v-model="form.name" @input="touch" /></label>
          <label class="field"><span>Description</span><input v-model="form.description" placeholder="When should an agent use this?" @input="touch" /></label>
        </div>
        <label class="field grow1">
          <span>Playbook (Markdown) — injected into the agent's instructions</span>
          <textarea v-model="form.content" class="md" spellcheck="false" @input="touch"
                    placeholder="# How to handle X&#10;- step one&#10;- step two" />
        </label>
      </template>
      <div v-else class="empty">
        <div class="halo"><Icon name="scroll" :size="26" /></div>
        <p>Select or create a skill.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sk { flex: 1; display: grid; grid-template-columns: 300px 1fr; gap: 1px; background: var(--border); overflow: hidden; }
.list { background: var(--bg); padding: 14px; display: flex; flex-direction: column; gap: 8px; overflow: auto; }
.newrow { display: flex; gap: 8px; }
.newrow input { flex: 1; }
.item { display: flex; align-items: center; gap: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 12px; text-align: left; color: var(--ink); box-shadow: none; }
.item:hover { border-color: var(--border-strong); filter: none; }
.item.active { border-color: var(--accent); background: var(--accent-soft); }
.item .ic { color: var(--accent); }
.meta { display: flex; flex-direction: column; min-width: 0; }
.meta strong { font-size: 13.5px; }
.desc { font-size: 11.5px; color: var(--faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail { background: var(--bg); padding: 18px; overflow: auto; display: flex; flex-direction: column; min-height: 0; }
.dhead { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; }
.dhead strong { font-size: 16px; }
.savedtag { color: var(--ok); font-size: 12.5px; display: inline-flex; align-items: center; gap: 4px; }
.grow { flex: 1; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.field > span { font-size: 12px; color: var(--muted); font-weight: 550; }
.field input { width: 100%; }
.grow1 { flex: 1; min-height: 0; }
.md { flex: 1; min-height: 320px; resize: vertical; font-family: ui-monospace, Menlo, monospace; font-size: 13px; line-height: 1.55; }
.muted { color: var(--muted); }
.pad { padding: 8px 2px; font-size: 12.5px; line-height: 1.5; }
.empty { margin: auto; text-align: center; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 12px; }
.halo { width: 56px; height: 56px; display: grid; place-items: center; border-radius: 16px; color: var(--accent); background: var(--accent-soft); }
.primary { background: var(--accent-strong); color: #fff; border: none; }
@media (max-width: 760px) {
  .sk { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
  .list { max-height: 36vh; }
  .grid2 { grid-template-columns: 1fr; }
}
</style>
