import { defineStore } from "pinia";
import { reactive, ref } from "vue";
import { getJson, postJson, streamPost, uploadFile } from "../api";

export interface Citation {
  index: number;
  filename: string;
  page: number | null;
  section_path: string | null;
  snippet: string;
}

export interface ChatMsg {
  role: "user" | "assistant";
  text: string;
  kind?: "spec" | "error";
  thinking?: string;
  citations?: Citation[];
}

export const useAgentStore = defineStore("agent", () => {
  const docs = ref<any[]>([]);
  const agentId = ref<string | null>(null);
  const spec = ref<any | null>(null);
  const messages = ref<ChatMsg[]>([]);
  const phase = ref("");
  const showBuilder = ref(false);
  const view = ref<"studio" | "knowledge" | "workflows">("studio");
  const agents = ref<any[]>([]);
  const kbs = ref<any[]>([]);
  const kbDocs = ref<any[]>([]);
  const selectedKb = ref<string | null>(null);
  const busy = ref(false);
  const diff = ref<any | null>(null);
  const error = ref<string | null>(null);

  async function upload(file: File) {
    busy.value = true;
    error.value = null;
    try {
      docs.value.push(await uploadFile(file));
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }

  async function build(request: string) {
    busy.value = true;
    error.value = null;
    phase.value = "starting";
    messages.value.push({ role: "user", text: request });
    try {
      await streamPost("/api/agents/build", { request }, (ev, data) => {
        if (ev === "status") phase.value = data.phase;
        else if (ev === "spec") {
          spec.value = data.spec;
          agentId.value = data.agent_id;
          messages.value.push({
            role: "assistant",
            kind: "spec",
            text: `Built “${data.spec.name}”. Ask it anything below — or refine it on the right.`,
          });
        } else if (ev === "error") {
          error.value = data.message;
          messages.value.push({ role: "assistant", kind: "error", text: data.message });
        }
      });
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
      phase.value = "";
    }
  }

  async function ask(message: string) {
    if (!agentId.value) return;
    busy.value = true;
    // Prior turns become conversation history (multi-turn).
    const history = messages.value
      .filter((m) => m.text && (m.kind === undefined))
      .map((m) => ({ role: m.role, text: m.text }));
    messages.value.push({ role: "user", text: message });
    const assistant = reactive<ChatMsg>({ role: "assistant", text: "", thinking: "", citations: [] });
    messages.value.push(assistant);
    try {
      await streamPost(`/api/agents/${agentId.value}/ask`, { message, history }, (ev, data) => {
        if (ev === "token") assistant.text += data.text;
        else if (ev === "thinking") assistant.thinking += data.text;
        else if (ev === "citations") assistant.citations = data.citations;
        else if (ev === "node") phase.value = `${data.type}`;
        else if (ev === "tool_use") phase.value = `tool · ${data.name}`;
        else if (ev === "tool_result") phase.value = "";
        else if (ev === "error") assistant.text += `\n\n_[${data.message}]_`;
      });
    } catch (e: any) {
      assistant.text += `\n\n_[error: ${e}]_`;
    } finally {
      busy.value = false;
      phase.value = "";
    }
  }

  async function proposeSelfMod(instruction: string) {
    if (!agentId.value) return;
    busy.value = true;
    phase.value = "proposing";
    try {
      await streamPost(
        `/api/agents/${agentId.value}/selfmod/propose`,
        { instruction },
        (ev, data) => {
          if (ev === "status") phase.value = data.phase;
          else if (ev === "diff") diff.value = data;
          else if (ev === "error") error.value = data.message;
        },
      );
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
      phase.value = "";
    }
  }

  async function applySelfMod() {
    if (!agentId.value || !diff.value) return;
    busy.value = true;
    try {
      await postJson(`/api/agents/${agentId.value}/selfmod/apply`, { spec: diff.value.new_spec });
      spec.value = diff.value.new_spec;
      messages.value.push({
        role: "assistant",
        kind: "spec",
        text: `Applied: ${diff.value.summary}`,
      });
      diff.value = null;
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }

  const dismissDiff = () => (diff.value = null);

  async function saveWorkflow(graph: any) {
    if (!agentId.value) return;
    busy.value = true;
    error.value = null;
    try {
      const r = await fetch(`/api/agents/${agentId.value}/workflow`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph }),
      });
      if (!r.ok) throw new Error(await r.text());
      const detail = await getJson(`/api/agents/${agentId.value}`);
      spec.value = detail.spec;
      showBuilder.value = false;
      messages.value.push({ role: "assistant", kind: "spec", text: "Workflow saved." });
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }

  // ── agents listing / loading ──
  async function listAgents() {
    agents.value = await getJson("/api/agents");
  }
  async function loadAgent(id: string) {
    const d = await getJson(`/api/agents/${id}`);
    agentId.value = id;
    spec.value = d.spec;
    messages.value = [];
    view.value = "studio";
  }

  // ── knowledge bases ──
  async function listKbs() {
    kbs.value = await getJson("/api/kb");
  }
  async function createKb(name: string) {
    await postJson("/api/kb", { name });
    await listKbs();
  }
  async function deleteKb(id: string) {
    await fetch(`/api/kb/${id}`, { method: "DELETE" });
    if (selectedKb.value === id) {
      selectedKb.value = null;
      kbDocs.value = [];
    }
    await listKbs();
  }
  async function selectKb(id: string) {
    selectedKb.value = id;
    kbDocs.value = await getJson(`/api/kb/${id}/documents`);
  }
  async function uploadToKb(id: string, file: File) {
    busy.value = true;
    error.value = null;
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`/api/kb/${id}/upload`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      await selectKb(id);
      await listKbs();
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }
  async function deleteDoc(kbId: string, docId: string) {
    await fetch(`/api/kb/${kbId}/documents/${docId}`, { method: "DELETE" });
    await selectKb(kbId);
    await listKbs();
  }

  return {
    docs, agentId, spec, messages, phase, busy, diff, error, showBuilder,
    view, agents, kbs, kbDocs, selectedKb,
    upload, build, ask, proposeSelfMod, applySelfMod, dismissDiff, saveWorkflow,
    listAgents, loadAgent, listKbs, createKb, deleteKb, selectKb, uploadToKb, deleteDoc,
  };
});
