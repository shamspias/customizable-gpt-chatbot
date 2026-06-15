<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const filterTag = ref<string | null>(null);
const selected = ref<Set<string>>(new Set());
const editingTags = ref<string | null>(null);
const tagDraft = ref("");

onMounted(() => Promise.all([store.listAgents(), store.loadAgentTags()]));

const allSelected = computed(
  () => store.agents.length > 0 && store.agents.every((a: any) => selected.value.has(a.id)),
);
function toggle(id: string) {
  const s = new Set(selected.value);
  s.has(id) ? s.delete(id) : s.add(id);
  selected.value = s;
}
function toggleAll() {
  selected.value = allSelected.value ? new Set() : new Set(store.agents.map((a: any) => a.id));
}
function setFilter(t: string | null) {
  filterTag.value = t;
  store.listAgents(t);
  selected.value = new Set();
}
async function bulkDelete() {
  const ids = [...selected.value];
  if (!ids.length) return;
  const ok = await store.confirmAction({
    title: `Delete ${ids.length} agent${ids.length === 1 ? "" : "s"}?`,
    message: "This permanently removes the agent(s), their versions, runs, and lessons.",
    confirmLabel: "Delete",
  });
  if (!ok) return;
  await store.deleteAgents(ids);
  selected.value = new Set();
}
function openTagEditor(a: any) {
  editingTags.value = a.id;
  tagDraft.value = (a.tags || []).join(", ");
}
async function saveTags(id: string) {
  const tags = tagDraft.value.split(",").map((t) => t.trim()).filter(Boolean);
  await store.setAgentTags(id, tags);
  editingTags.value = null;
}
async function openBuilder(id: string) {
  await store.loadAgent(id);
  store.showBuilder = true;
}
// Open the agent on its own shareable test page (#/agent/<id>).
function openChat(id: string) {
  window.location.hash = `#/agent/${id}`;
}
function newAgent() {
  store.openCreate();
}
</script>

<template>
  <div class="wf">
    <div class="head">
      <div class="htext">
        <h2>Agents
          <span v-if="store.agents.length" class="count">{{ store.agents.length }}</span>
        </h2>
        <p>Every agent you've built — chat with one, reshape it in the builder, or export its spec.</p>
      </div>
      <div class="grow" />
      <button class="ghost sm" @click="store.listAgents(filterTag); store.loadAgentTags()">
        <Icon name="refresh" :size="15" />Refresh
      </button>
      <button class="sm" @click="newAgent">
        <Icon name="plus" :size="15" />New agent
      </button>
    </div>

    <div v-if="store.agentTags.length" class="filters">
      <button class="chip" :class="{ on: !filterTag }" @click="setFilter(null)">All</button>
      <button v-for="t in store.agentTags" :key="t" class="chip" :class="{ on: filterTag === t }"
              @click="setFilter(t)">{{ t }}</button>
    </div>

    <div v-if="selected.size" class="bulkbar">
      <label class="selall"><input type="checkbox" :checked="allSelected" @change="toggleAll" /> {{ selected.size }} selected</label>
      <div class="grow" />
      <button class="danger sm" @click="bulkDelete"><Icon name="trash" :size="14" />Delete selected</button>
    </div>

    <div v-if="store.agents.length" class="grid">
      <div v-for="a in store.agents" :key="a.id" class="card" :class="{ sel: selected.has(a.id) }">
        <div class="top">
          <input class="cb" type="checkbox" :checked="selected.has(a.id)" @change="toggle(a.id)" />
          <span class="avatar"><Icon name="bot" :size="20" /></span>
          <div class="meta">
            <strong>{{ a.name }}</strong>
            <span class="ver">v{{ a.current_version }}</span>
          </div>
        </div>
        <div class="tags">
          <template v-if="editingTags === a.id">
            <input v-model="tagDraft" class="taginput" placeholder="tag1, tag2"
                   @keyup.enter="saveTags(a.id)" @keyup.esc="editingTags = null" />
            <button class="iconbtn" aria-label="Save tags" title="Save tags" @click="saveTags(a.id)"><Icon name="check" :size="14" /></button>
          </template>
          <template v-else>
            <span v-for="t in (a.tags || [])" :key="t" class="tag">{{ t }}</span>
            <button class="addtag" @click="openTagEditor(a)">
              <Icon name="plus" :size="12" />{{ (a.tags || []).length ? "" : "tag" }}
            </button>
          </template>
        </div>
        <div class="actions">
          <button class="ghost sm" title="Open this agent on its own test page" @click="openChat(a.id)"><Icon name="sparkles" :size="14" />Chat</button>
          <button class="ghost sm" @click="openBuilder(a.id)"><Icon name="workflow" :size="14" />Builder</button>
          <button class="ghost sm icononly" aria-label="Export spec JSON" title="Export spec JSON" @click="store.exportAgent(a.id)"><Icon name="save" :size="14" /></button>
        </div>
      </div>
    </div>

    <div v-else class="empty">
      <div class="halo"><Icon name="bot" :size="26" /></div>
      <p v-if="filterTag">No agents tagged “{{ filterTag }}”.</p>
      <p v-else>No agents yet — create your first one.</p>
      <button class="sm" @click="store.openCreate()"><Icon name="plus" :size="15" />Create agent</button>
    </div>
  </div>
</template>

<style scoped>
.wf { flex: 1; background: var(--bg); padding: 22px; overflow: auto; }
.head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
.htext h2 { margin: 0; font-size: 20px; letter-spacing: -0.015em; display: flex; align-items: center; gap: 9px; }
.htext .count { font-size: 12px; font-weight: 650; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 1px 9px; }
.htext p { margin: 4px 0 0; color: var(--muted); font-size: 13px; max-width: 60ch; }
.head .grow { flex: 1; }
.filters { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 14px; }
.chip { background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); border-radius: 999px; padding: 5px 13px; font-size: 12.5px; box-shadow: none; }
.chip:hover { border-color: var(--border-strong); color: var(--ink); filter: none; }
.chip.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
.bulkbar { display: flex; align-items: center; gap: 10px; background: var(--accent-soft); border: 1px solid var(--accent); border-radius: var(--radius-sm); padding: 8px 13px; margin-bottom: 14px; animation: veldra-rise .15s ease; }
.selall { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; }
.bulkbar .grow { flex: 1; }
.danger { background: var(--danger); color: #fff; border: none; box-shadow: none; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 13px; }
.card { position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 15px; display: flex; flex-direction: column; gap: 11px; transition: transform 0.12s, border-color 0.15s, box-shadow 0.15s; overflow: hidden; }
.card::before { content: ""; position: absolute; inset: 0 0 auto; height: 2px; background: linear-gradient(90deg, var(--accent), transparent); opacity: 0; transition: opacity 0.15s; }
.card:hover { border-color: var(--border-strong); box-shadow: var(--shadow); transform: translateY(-2px); }
.card:hover::before { opacity: 1; }
.card.sel { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-ring); }
.card.sel::before { opacity: 1; }
.top { display: flex; align-items: center; gap: 11px; }
.cb { width: 16px; height: 16px; flex: none; accent-color: var(--accent); }
.avatar { width: 38px; height: 38px; flex: none; display: grid; place-items: center; border-radius: 11px; color: var(--accent); background: var(--accent-soft); }
.meta { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.meta strong { font-size: 14.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ver { font-size: 10.5px; font-weight: 600; color: var(--muted); background: var(--surface-2); border: 1px solid var(--border); border-radius: 999px; padding: 1px 7px; align-self: flex-start; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; min-height: 22px; }
.tag { font-size: 11px; background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); border-radius: 999px; padding: 1px 9px; }
.addtag { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: none; border: 1px dashed var(--border-strong); color: var(--faint); box-shadow: none; display: inline-flex; align-items: center; gap: 3px; }
.addtag:hover { border-color: var(--accent); color: var(--accent); filter: none; }
.taginput { flex: 1; padding: 5px 9px; font-size: 12.5px; }
.iconbtn { background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); padding: 5px; border-radius: 8px; box-shadow: none; }
.actions { display: flex; gap: 8px; }
.actions button { flex: 1; }
.actions .icononly { flex: 0 0 auto; padding: 6px 9px; }
.empty { margin: 70px auto; text-align: center; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 14px; }
.empty .halo { width: 60px; height: 60px; display: grid; place-items: center; border-radius: 18px; color: var(--accent); background: var(--accent-soft); }
.empty p { margin: 0; }
@media (max-width: 640px) {
  .wf { padding: 16px; }
  .grid { grid-template-columns: 1fr; }
  .head { flex-wrap: wrap; }
  .htext { flex: 1 1 100%; }
  .head .grow { display: none; }  /* let the action buttons sit right under the wrapped header */
}
</style>
