<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const newName = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

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
        <div>
          <strong>{{ k.name }}</strong>
          <div class="muted">{{ k.document_count }} document{{ k.document_count === 1 ? "" : "s" }}</div>
        </div>
        <button class="link danger" @click.stop="store.deleteKb(k.id)">delete</button>
      </div>
      <p v-if="!store.kbs.length" class="muted pad">No knowledge bases yet.</p>
    </aside>

    <section class="detail">
      <template v-if="store.selectedKb">
        <div class="dhead">
          <h2>Documents</h2>
          <div class="grow" />
          <button class="ghost sm" :disabled="store.busy" @click="fileInput?.click()">＋ Upload document</button>
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
.detail { background: var(--bg); padding: 18px; overflow: auto; }
.dhead { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.dhead h2 { margin: 0; font-size: 18px; }
.dhead .grow { flex: 1; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--muted); font-weight: 550; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; padding: 6px 10px; border-bottom: 1px solid var(--border); }
td { padding: 10px; border-bottom: 1px solid var(--border); }
.status { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); }
.status.ready { color: var(--ok); }
.status.failed { color: var(--danger); }
.link { background: none; border: none; cursor: pointer; font-size: 13px; color: var(--accent); }
.link.danger { color: var(--danger); }
.muted { color: var(--muted); }
.pad { padding: 8px 2px; }
.empty { margin: 60px auto; text-align: center; }
</style>
