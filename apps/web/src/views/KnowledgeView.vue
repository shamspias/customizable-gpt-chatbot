<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import Icon from "../components/Icon.vue";
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
        vector_store: k.vector_store || "pgvector",
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

// ── doc multi-select ──
const selDocs = ref<Set<string>>(new Set());
watch(() => store.selectedKb, () => { selDocs.value = new Set(); });
function toggleDoc(id: string) {
  const s = new Set(selDocs.value);
  s.has(id) ? s.delete(id) : s.add(id);
  selDocs.value = s;
}
async function bulkDeleteDocs() {
  const ids = [...selDocs.value];
  if (!ids.length || !store.selectedKb) return;
  const ok = await store.confirmAction({
    title: `Delete ${ids.length} document${ids.length === 1 ? "" : "s"}?`,
    message: "Their chunks and page index are removed from this knowledge base.",
  });
  if (!ok) return;
  await store.deleteDocs(store.selectedKb, ids);
  selDocs.value = new Set();
}
async function delDoc(id: string) {
  if (!store.selectedKb) return;
  const ok = await store.confirmAction({ title: "Delete this document?", message: "It will be removed from the knowledge base." });
  if (ok) await store.deleteDoc(store.selectedKb, id);
}
async function delKb(id: string, name: string) {
  const ok = await store.confirmAction({
    title: `Delete “${name}”?`, message: "The knowledge base and all its documents are removed.",
  });
  if (ok) await store.deleteKb(id);
}

// ── add from URL + document editor ──
const urlInput = ref("");
function addUrl() {
  const u = urlInput.value.trim();
  if (!u || !store.selectedKb) return;
  store.ingestUrl(store.selectedKb, u);
  urlInput.value = "";
}
const editText = ref("");
watch(() => store.openDoc, (d) => { editText.value = d?.text || ""; });
function openEditor(docId: string) {
  if (store.selectedKb) store.viewDoc(store.selectedKb, docId);
}
async function saveDocText() {
  if (store.selectedKb && store.openDoc) await store.saveDoc(store.selectedKb, store.openDoc.document.id, editText.value);
}
const docDirty = computed(() => !!store.openDoc && editText.value !== (store.openDoc.text || ""));
async function closeDocSafe() {
  if (docDirty.value) {
    const ok = await store.confirmAction({
      title: "Discard unsaved changes?",
      message: "Your edits to this document haven't been saved and will be lost.",
      confirmLabel: "Discard", danger: true,
    });
    if (!ok) return;
  }
  store.closeDoc();
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
        <button class="iconbtn danger kbdel" title="Delete knowledge base"
                aria-label="Delete knowledge base" @click.stop="delKb(k.id, k.name)">
          <Icon name="trash" :size="15" />
        </button>
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

          <div class="field">
            <span>Vector storage</span>
            <div class="seg">
              <button :class="{ on: form.vector_store === 'pgvector' }"
                      title="Postgres + pgvector (built-in)" @click="form.vector_store = 'pgvector'; touch()">pgvector</button>
              <button :class="{ on: form.vector_store === 'qdrant' }"
                      title="Qdrant (needs the qdrant service)" @click="form.vector_store = 'qdrant'; touch()">Qdrant</button>
            </div>
            <small class="muted">Where this KB's vectors live. Qdrant needs the qdrant service running.</small>
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
            <button v-if="selDocs.size" class="danger sm" @click="bulkDeleteDocs">
              <Icon name="trash" :size="14" />Delete {{ selDocs.size }}
            </button>
            <button class="ghost sm" :disabled="store.busy" @click="fileInput?.click()"><Icon name="upload" :size="15" />Upload</button>
            <input ref="fileInput" type="file" hidden accept=".pdf,.txt,.md" @change="onFile" />
          </div>
          <div class="urlrow">
            <Icon name="globe" :size="15" class="urlic" />
            <input v-model="urlInput" placeholder="Index a web page — https://…" @keyup.enter="addUrl" />
            <button class="ghost sm" :disabled="store.busy || !urlInput.trim()" @click="addUrl">Fetch &amp; index</button>
          </div>
          <table v-if="store.kbDocs.length">
            <thead><tr><th></th><th>File</th><th>Pages</th><th>Chunks</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="d in store.kbDocs" :key="d.id" class="docrow" :class="{ sel: selDocs.has(d.id) }" @click="openEditor(d.id)">
                <td class="cbcell"><input class="cb" type="checkbox" :checked="selDocs.has(d.id)" @click.stop="toggleDoc(d.id)" /></td>
                <td class="fname"><Icon name="file" :size="14" /> {{ d.filename }}</td>
                <td>{{ d.num_pages || "—" }}</td>
                <td>{{ d.chunk_count }}</td>
                <td><span class="status" :class="d.status">{{ d.status }}</span></td>
                <td class="rowact">
                  <button class="iconbtn" title="Edit" @click.stop="openEditor(d.id)"><Icon name="pencil" :size="14" /></button>
                  <button class="iconbtn danger" title="Delete" @click.stop="delDoc(d.id)"><Icon name="trash" :size="14" /></button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="muted pad">No documents yet — upload a file or index a web page.</p>
        </div>
      </template>
      <div v-else class="empty muted">Select or create a knowledge base.</div>
    </section>

    <!-- ── document editor + page-index tree (drawer) ── -->
    <transition name="drawer">
      <div v-if="store.openDoc" class="drawer-wrap" @click.self="closeDocSafe()">
        <div class="drawer">
          <div class="drawer-h">
            <Icon name="file" :size="16" /><strong class="dt">{{ store.openDoc.document.filename }}</strong>
            <div class="grow" />
            <button class="primary sm" :disabled="store.busy" @click="saveDocText"><Icon name="save" :size="14" />Save &amp; re-embed</button>
            <button class="ghost sm" aria-label="Close" title="Close" @click="closeDocSafe()"><Icon name="x" :size="16" /></button>
          </div>
          <div class="drawer-body">
            <label class="field">
              <span>Content <small class="muted">— edits are re-chunked &amp; re-embedded on save</small></span>
              <textarea v-model="editText" class="doctext" spellcheck="false" />
            </label>
            <div class="field">
              <span><Icon name="tree" :size="13" /> Page index <small class="muted">({{ store.openDoc.page_index.length }} nodes)</small></span>
              <div v-if="store.openDoc.page_index.length" class="ptree">
                <div v-for="(p, i) in store.openDoc.page_index" :key="i" class="pnode" :class="p.kind">
                  <span class="pk">{{ p.kind }}</span>
                  <span class="pl">{{ p.label || p.section_path || ('Page ' + (p.page_number ?? '?')) }}</span>
                  <span class="pc muted">{{ p.char_start }}–{{ p.char_end }}</span>
                </div>
              </div>
              <p v-else class="muted small">No page index (disabled for this KB, or not built yet).</p>
            </div>
          </div>
        </div>
      </div>
    </transition>
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
.kbinfo { min-width: 0; }
.kbinfo strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kbdel { flex: none; opacity: 0; transition: opacity .14s ease; }
.kbitem:hover .kbdel, .kbitem.active .kbdel, .kbitem:focus-within .kbdel { opacity: 1; }
@media (hover: none) { .kbdel { opacity: 1; } }
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
.primary { background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer; }
.primary:disabled { opacity: .5; cursor: default; }
.muted { color: var(--muted); }
.pad { padding: 8px 2px; }
.empty { margin: 60px auto; text-align: center; }
.fname { display: flex; align-items: center; gap: 7px; }
.small { font-size: 12px; }

/* url ingest row */
.urlrow { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.urlrow input { flex: 1; }
.urlic { color: var(--muted); flex: none; }

/* document rows */
.docrow { cursor: pointer; }
.docrow:hover { background: var(--surface-2); }
.docrow.sel { background: var(--accent-soft); }
.cbcell { width: 30px; }
.cb { width: 15px; height: 15px; accent-color: var(--accent); }
.danger { background: var(--danger); color: #fff; border: none; box-shadow: none; }
.rowact { display: flex; gap: 4px; justify-content: flex-end; }
.iconbtn { background: none; border: 1px solid transparent; color: var(--muted); padding: 5px; border-radius: 8px; }
.iconbtn:hover { background: var(--surface-2); border-color: var(--border); color: var(--ink); filter: none; }
.iconbtn.danger:hover { color: var(--danger); }

/* editor drawer */
.drawer-wrap { position: fixed; inset: 0; z-index: 50; background: rgba(0, 0, 0, 0.5); display: flex; justify-content: flex-end; }
.drawer { width: min(640px, 96vw); background: var(--bg); height: 100%; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.drawer-h { display: flex; align-items: center; gap: 9px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.drawer-h .dt { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.drawer-body { padding: 16px; overflow: auto; display: flex; flex-direction: column; gap: 16px; }
.doctext { width: 100%; min-height: 320px; resize: vertical; font-family: ui-monospace, Menlo, monospace; font-size: 13px; line-height: 1.55; }
.ptree { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
.pnode { display: flex; align-items: center; gap: 10px; padding: 8px 11px; border-bottom: 1px solid var(--border); font-size: 13px; }
.pnode:last-child { border-bottom: none; }
.pnode.section { padding-left: 26px; }
.pk { font-size: 10.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--accent); background: var(--accent-soft); padding: 1px 7px; border-radius: 999px; }
.pl { flex: 1; }
.pc { font-size: 11.5px; font-family: ui-monospace, Menlo, monospace; }
.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s; }
.drawer-enter-active .drawer, .drawer-leave-active .drawer { transition: transform 0.22s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer, .drawer-leave-to .drawer { transform: translateX(100%); }

@media (max-width: 760px) {
  .kb { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
  .list { max-height: 38vh; }
  .grid2 { grid-template-columns: 1fr; }
  .detail { padding: 14px; }
}
</style>
