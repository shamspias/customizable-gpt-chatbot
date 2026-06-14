<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const newName = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

const MODES = [
  { id: "hybrid", label: "Hybrid", hint: "Vector + keyword (RRF) — best default" },
  { id: "semantic", label: "Semantic", hint: "Vector similarity only" },
  { id: "keyword", label: "Keyword", hint: "Lexical / BM25 only" },
];

const selected = computed(() => store.kbs.find((k) => k.id === store.selectedKb));

// Editable config form, synced whenever the selected KB changes.
const form = ref<any>({});
const dirty = ref(false);
const saved = ref(false);
watch(selected, (k) => {
  form.value = k
    ? {
        name: k.name,
        description: k.description || "",
        retrieval_mode: k.retrieval_mode || "hybrid",
        embedding_model: k.embedding_model || "",
        rerank_model: k.rerank_model || "",
        page_index_enabled: k.page_index_enabled ?? true,
      }
    : {};
  dirty.value = false;
  saved.value = false;
}, { immediate: true });

function touch() { dirty.value = true; saved.value = false; }

onMounted(() => store.listKbs());

function create() {
  const n = newName.value.trim();
  if (!n) return;
  store.createKb(n);
  newName.value = "";
}
function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f && store.selectedKb) store.uploadToKb(store.selectedKb, f);
  (e.target as HTMLInputElement).value = "";
}
async function saveConfig() {
  if (!store.selectedKb) return;
  await store.updateKb(store.selectedKb, {
    ...form.value,
    embedding_model: form.value.embedding_model || null,
    rerank_model: form.value.rerank_model || null,
  });
  dirty.value = false;
  saved.value = true;
}
</script>

<template>
  <div class="kb">
    <aside class="list">
      <div class="newrow">
        <input v-model="newName" placeholder="New knowledge base…" @keyup.enter="create" />
        <button class="sm" @click="create">Create</button>
      </div>
      <div v-for="k in store.kbs" :key="k.id" class="kbitem"
           :class="{ active: store.selectedKb === k.id }" @click="store.selectKb(k.id)">
        <div class="kbinfo">
          <strong>{{ k.name }}</strong>
          <div class="muted">
            <span class="pill">{{ k.retrieval_mode || "hybrid" }}</span>
            {{ k.document_count }} doc{{ k.document_count === 1 ? "" : "s" }}
          </div>
        </div>
        <button class="link danger" @click.stop="store.deleteKb(k.id)">delete</button>
      </div>
      <p v-if="!store.kbs.length" class="muted pad">No knowledge bases yet.</p>
    </aside>

    <section class="detail">
      <template v-if="selected">
        <!-- ── retrieval settings ── -->
        <div class="card">
          <div class="chead">
            <h2>{{ form.name }}</h2>
            <span v-if="saved" class="saved">✓ saved</span>
            <div class="grow" />
            <button class="primary sm" :disabled="!dirty || store.busy" @click="saveConfig">Save settings</button>
          </div>

          <div class="grid2">
            <label class="field">
              <span>Name</span>
              <input v-model="form.name" @input="touch" />
            </label>
            <label class="field">
              <span>Description</span>
              <input v-model="form.description" placeholder="What's in this KB?" @input="touch" />
            </label>
          </div>

          <div class="field">
            <span>Retrieval mode</span>
            <div class="seg">
              <button v-for="m in MODES" :key="m.id" :class="{ on: form.retrieval_mode === m.id }"
                      :title="m.hint" @click="form.retrieval_mode = m.id; touch()">{{ m.label }}</button>
            </div>
            <small class="muted">{{ MODES.find((m) => m.id === form.retrieval_mode)?.hint }}</small>
          </div>

          <div class="grid2">
            <label class="field">
              <span>Embedding model</span>
              <input v-model="form.embedding_model" placeholder="ollama:nomic-embed-text (blank = default)" @input="touch" />
              <small class="muted">provider:model — must match the index dimension.</small>
            </label>
            <label class="field">
              <span>Rerank model</span>
              <input v-model="form.rerank_model" placeholder="cohere:rerank-3.5 / local:BAAI/bge-reranker-base (blank = off)" @input="touch" />
              <small class="muted">Optional second-stage precision. Off by default.</small>
            </label>
          </div>

          <label class="toggle" @click="form.page_index_enabled = !form.page_index_enabled; touch()">
            <span class="switch" :class="{ on: form.page_index_enabled }"><span class="knob" /></span>
            <span>Build page index <small class="muted">(structural page/section map for richer citations)</small></span>
          </label>
        </div>

        <!-- ── documents ── -->
        <div class="card">
          <div class="dhead">
            <h2>Documents</h2>
            <div class="grow" />
            <button class="ghost sm" :disabled="store.busy" @click="fileInput?.click()">＋ Upload</button>
            <input ref="fileInput" type="file" hidden accept=".pdf,.txt,.md" @change="onFile" />
          </div>
          <table v-if="store.kbDocs.length">
            <thead><tr><th>File</th><th>Pages</th><th>Chunks</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="d in store.kbDocs" :key="d.id">
                <td>📄 {{ d.filename }}</td>
                <td>{{ d.num_pages || "—" }}</td>
                <td>{{ d.chunk_count }}</td>
                <td><span class="status" :class="d.status">{{ d.status }}</span></td>
                <td><button class="link danger" @click="store.deleteDoc(store.selectedKb!, d.id)">delete</button></td>
              </tr>
            </tbody>
          </table>
          <p v-else class="muted pad">No documents yet — upload a PDF, Markdown, or text file.</p>
        </div>
      </template>
      <div v-else class="empty muted">Select or create a knowledge base.</div>
    </section>
  </div>
</template>

<style scoped>
.kb { flex: 1; display: grid; grid-template-columns: 300px 1fr; gap: 1px; background: var(--border); overflow: hidden; }
.list { background: var(--bg); padding: 14px; display: flex; flex-direction: column; gap: 8px; overflow: auto; }
.newrow { display: flex; gap: 8px; }
.newrow input { flex: 1; }
button.sm { padding: 8px 12px; font-size: 13px; }
.kbitem { display: flex; justify-content: space-between; align-items: center; padding: 11px 13px; border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; }
.kbitem:hover { border-color: var(--border-strong); }
.kbitem.active { border-color: var(--accent); background: var(--accent-soft); }
.kbinfo strong { display: block; }
.pill { font-size: 11px; padding: 1px 7px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); margin-right: 6px; text-transform: capitalize; }
.detail { background: var(--bg); padding: 18px; overflow: auto; display: flex; flex-direction: column; gap: 16px; }
.card { border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; background: var(--surface); }
.chead, .dhead { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.chead h2, .dhead h2 { margin: 0; font-size: 17px; }
.grow { flex: 1; }
.saved { color: var(--ok); font-size: 13px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
.field > span { font-size: 12px; color: var(--muted); font-weight: 550; text-transform: uppercase; letter-spacing: .04em; }
.field input { width: 100%; }
.field small { font-size: 11.5px; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; width: fit-content; }
.seg button { padding: 8px 16px; font-size: 13px; background: var(--bg); border: none; border-right: 1px solid var(--border); cursor: pointer; color: var(--ink); }
.seg button:last-child { border-right: none; }
.seg button.on { background: var(--accent); color: #fff; }
.toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 14px; }
.switch { width: 38px; height: 22px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); position: relative; transition: background .15s; flex: none; }
.switch.on { background: var(--accent); border-color: var(--accent); }
.switch .knob { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: left .15s; }
.switch.on .knob { left: 18px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--muted); font-weight: 550; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; padding: 6px 10px; border-bottom: 1px solid var(--border); }
td { padding: 10px; border-bottom: 1px solid var(--border); }
.status { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); }
.status.ready { color: var(--ok); }
.status.failed { color: var(--danger); }
.link { background: none; border: none; cursor: pointer; font-size: 13px; color: var(--accent); }
.link.danger { color: var(--danger); }
.primary { background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer; }
.primary:disabled { opacity: .5; cursor: default; }
.muted { color: var(--muted); }
.pad { padding: 8px 2px; }
.empty { margin: 60px auto; text-align: center; }
</style>
