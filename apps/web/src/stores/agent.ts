import { defineStore } from "pinia";
import { reactive, ref } from "vue";
import { apiFetch, clearToken, getJson, getToken, postJson, setToken, streamPost, uploadFile } from "../api";

export interface Citation {
  index: number;
  filename: string;
  page: number | null;
  section_path: string | null;
  snippet: string;
}

export interface Usage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  cost_usd: number;
  cache_hit_rate: number;
}

let _mid = 0;
const nextMsgId = (): string => `m${++_mid}`;

export interface ChatMsg {
  id: string;        // stable key for v-for (streaming mutates messages in place)
  role: "user" | "assistant";
  text: string;
  kind?: "spec" | "error";
  thinking?: string;
  citations?: Citation[];
  usage?: Usage;    // token + cost rollup for this turn
  runId?: string;   // the run this assistant turn belongs to (for feedback)
  rated?: number;   // -1 / 1 once the user has rated it
}

export const useAgentStore = defineStore("agent", () => {
  const docs = ref<any[]>([]);
  const agentId = ref<string | null>(null);
  const spec = ref<any | null>(null);
  const messages = ref<ChatMsg[]>([]);
  const phase = ref("");
  const showBuilder = ref(false);
  const view = ref<
    "home" | "chat" | "knowledge" | "workflows" | "activity" | "skills" | "insights" | "plugins"
  >("home");
  const agents = ref<any[]>([]);
  const kbs = ref<any[]>([]);
  const kbDocs = ref<any[]>([]);
  const selectedKb = ref<string | null>(null);
  const busy = ref(false);
  const diff = ref<any | null>(null);
  const error = ref<string | null>(null);
  // activity log
  const runs = ref<any[]>([]);
  const runSteps = ref<any | null>(null);
  // analytics dashboard
  const analytics = ref<any | null>(null);
  // document editor
  const openDoc = ref<any | null>(null); // { document, text, page_index }
  // learning
  const lessons = ref<any[]>([]);
  // agent tags / filtering
  const agentTags = ref<string[]>([]);
  // skills (markdown playbooks)
  const skills = ref<any[]>([]);
  const openSkill = ref<any | null>(null);
  // settings panel (theme + config + tools catalog)
  const settingsOpen = ref(false);
  const config = ref<any | null>(null);
  const toolCatalog = ref<any[]>([]);
  // confirm dialog (promise-based, replaces native confirm())
  const confirmState = ref<{
    title: string; message: string; confirmLabel: string; danger: boolean;
    resolve: (ok: boolean) => void;
  } | null>(null);
  // create-agent modal (Describe / Team / Manual)
  const createOpen = ref(false);
  // floating Faust admin bot
  const faustOpen = ref(false);
  const faustMsgs = ref<ChatMsg[]>([]);
  const faustBusy = ref(false);
  // auth / workspace
  const authReady = ref(false);
  const authEnabled = ref(true);
  const setupNeeded = ref(false);
  const me = ref<any | null>(null);
  const workspace = ref<{ id: string; name: string } | null>(null);
  const members = ref<any[]>([]);
  const invites = ref<any[]>([]);
  // plugins (MCP connectors)
  const plugins = ref<any[]>([]);
  const pluginTemplates = ref<any[]>([]);

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
    messages.value.push({ id: nextMsgId(), role: "user", text: request });
    try {
      await streamPost("/api/agents/build", { request }, (ev, data) => {
        if (ev === "status") phase.value = data.phase;
        else if (ev === "spec") {
          spec.value = data.spec;
          agentId.value = data.agent_id;
          messages.value.push({
            id: nextMsgId(),
            role: "assistant",
            kind: "spec",
            text: `Built “${data.spec.name}”. Ask it anything below — or refine it on the right.`,
          });
        } else if (ev === "error") {
          error.value = data.message;
          messages.value.push({ id: nextMsgId(), role: "assistant", kind: "error", text: data.message });
        }
      });
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
      phase.value = "";
      if (agentId.value) listAgents().catch(() => {});  // surface the new agent in the roster
    }
  }

  async function ask(message: string) {
    if (!agentId.value) return;
    busy.value = true;
    // Prior turns become conversation history (multi-turn).
    const history = messages.value
      .filter((m) => m.text && (m.kind === undefined))
      .map((m) => ({ role: m.role, text: m.text }));
    messages.value.push({ id: nextMsgId(), role: "user", text: message });
    const assistant = reactive<ChatMsg>({ id: nextMsgId(), role: "assistant", text: "", thinking: "", citations: [] });
    messages.value.push(assistant);
    try {
      await streamPost(`/api/agents/${agentId.value}/ask`, { message, history }, (ev, data) => {
        if (ev === "run") assistant.runId = data.run_id;
        else if (ev === "token") assistant.text += data.text;
        else if (ev === "thinking") assistant.thinking += data.text;
        else if (ev === "citations") assistant.citations = data.citations;
        else if (ev === "usage") assistant.usage = data;
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
        id: nextMsgId(),
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
      const r = await apiFetch(`/api/agents/${agentId.value}/workflow`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph }),
      });
      if (!r.ok) throw new Error(await r.text());
      const detail = await getJson(`/api/agents/${agentId.value}`);
      spec.value = detail.spec;
      showBuilder.value = false;
      messages.value.push({ id: nextMsgId(), role: "assistant", kind: "spec", text: "Workflow saved." });
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }

  // ── agents listing / loading + tags + bulk ──
  async function listAgents(tag?: string | null) {
    agents.value = await getJson(`/api/agents${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`);
  }
  async function loadAgentTags() {
    agentTags.value = await getJson("/api/agent-tags");
  }
  async function setAgentTags(id: string, tags: string[]) {
    await apiFetch(`/api/agents/${id}/tags`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    });
    await Promise.all([listAgents(), loadAgentTags()]);
  }
  async function deleteAgents(ids: string[]) {
    await postJson("/api/agents/delete", { ids });
    await Promise.all([listAgents(), loadAgentTags()]);
  }
  async function deleteRuns(ids: string[]) {
    await postJson("/api/runs/delete", { ids });
    if (runSteps.value && ids.includes(runSteps.value.run?.id)) runSteps.value = null;
    await listRuns();
  }
  async function deleteDocs(kbId: string, ids: string[]) {
    await postJson(`/api/kb/${kbId}/documents/delete`, { ids });
    await Promise.all([selectKb(kbId), listKbs()]);
  }

  // ── settings ──
  async function openSettings() {
    settingsOpen.value = true;
    try {
      if (!config.value) config.value = await getJson("/api/config");
      if (!toolCatalog.value.length) toolCatalog.value = await getJson("/api/tools");
    } catch { /* settings still opens with the theme controls */ }
  }
  async function ensureConfig() {
    if (config.value) return;
    try { config.value = await getJson("/api/config"); } catch { /* offline — chrome still works */ }
  }
  async function ensureCatalog(force = false) {
    try {
      if (force || !toolCatalog.value.length) toolCatalog.value = await getJson("/api/tools");
    } catch { /**/ }
  }

  // ── create agent ──
  function resetChat() {
    agentId.value = null;
    spec.value = null;
    messages.value = [] as any;
  }
  function openCreate() {
    createOpen.value = true;
  }
  async function createAgentManual(specObj: Record<string, any>) {
    const r = await postJson("/api/agents", { spec: specObj });
    await loadAgent(r.agent_id);
    await listAgents();
    return r;
  }
  async function exportAgent(id: string) {
    const d = await getJson(`/api/agents/${id}`);
    const blob = new Blob([JSON.stringify(d.spec, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(d.name || "agent").replace(/\W+/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ── confirm dialog ──
  function confirmAction(opts: {
    title?: string; message: string; confirmLabel?: string; danger?: boolean;
  }): Promise<boolean> {
    return new Promise((resolve) => {
      confirmState.value = {
        title: opts.title ?? "Are you sure?",
        message: opts.message,
        confirmLabel: opts.confirmLabel ?? "Delete",
        danger: opts.danger ?? true,
        resolve,
      };
    });
  }
  function resolveConfirm(ok: boolean) {
    confirmState.value?.resolve(ok);
    confirmState.value = null;
  }

  // ── skills (markdown playbooks) ──
  async function listSkills() {
    skills.value = await getJson("/api/skills");
  }
  async function createSkill(name: string) {
    const s = await postJson("/api/skills", { name, description: "", content: `# ${name}\n\n` });
    await listSkills();
    openSkill.value = s;
  }
  async function saveSkill(id: string, fields: Record<string, any>) {
    const r = await apiFetch(`/api/skills/${id}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!r.ok) throw new Error(await r.text());
    await listSkills();
  }
  async function deleteSkill(id: string) {
    await apiFetch(`/api/skills/${id}`, { method: "DELETE" });
    if (openSkill.value?.id === id) openSkill.value = null;
    await listSkills();
  }

  // ── floating Faust admin bot ──
  async function askFaust(message: string) {
    faustBusy.value = true;
    // Build history BEFORE adding this turn, so the current message isn't duplicated.
    const history = faustMsgs.value
      .filter((m) => m.text && m.kind === undefined)
      .map((m) => ({ role: m.role, text: m.text }));
    faustMsgs.value.push({ id: nextMsgId(), role: "user", text: message });
    const a = reactive<ChatMsg>({ id: nextMsgId(), role: "assistant", text: "", thinking: "", citations: [] });
    faustMsgs.value.push(a);
    try {
      await streamPost("/api/faust/ask", { message, history }, (ev, data) => {
        if (ev === "run") a.runId = data.run_id;
        else if (ev === "token") a.text += data.text;
        else if (ev === "thinking") a.thinking += data.text;
        else if (ev === "usage") a.usage = data;
        else if (ev === "tool_use") phase.value = `· ${data.name}`;
        else if (ev === "tool_result") phase.value = "";
        else if (ev === "error") a.text += `\n\n_[${data.message}]_`;
      });
    } catch (e: any) {
      a.text += `\n\n_[error: ${e}]_`;
    } finally {
      faustBusy.value = false;
      phase.value = "";
      // Faust just acted on the platform — refresh whatever view is open.
      listAgents().catch(() => {});
      if (view.value === "activity") listRuns().catch(() => {});
      if (view.value === "knowledge" && selectedKb.value) selectKb(selectedKb.value).catch(() => {});
    }
  }
  async function loadAgent(id: string) {
    const d = await getJson(`/api/agents/${id}`);
    agentId.value = id;
    spec.value = d.spec;
    messages.value = [];
    view.value = "chat";  // opening an agent → its focused chat screen
    await loadLessons();
  }

  // ── knowledge bases ──
  async function listKbs() {
    kbs.value = await getJson("/api/kb");
  }
  async function createKb(name: string, config: Record<string, any> = {}) {
    await postJson("/api/kb", { name, ...config });
    await listKbs();
  }
  async function updateKb(id: string, fields: Record<string, any>) {
    const r = await apiFetch(`/api/kb/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!r.ok) throw new Error(await r.text());
    await listKbs();
  }
  async function deleteKb(id: string) {
    await apiFetch(`/api/kb/${id}`, { method: "DELETE" });
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
      const r = await apiFetch(`/api/kb/${id}/upload`, { method: "POST", body: fd });
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
    await apiFetch(`/api/kb/${kbId}/documents/${docId}`, { method: "DELETE" });
    if (openDoc.value?.document?.id === docId) openDoc.value = null;
    await selectKb(kbId);
    await listKbs();
  }
  async function viewDoc(kbId: string, docId: string) {
    openDoc.value = await getJson(`/api/kb/${kbId}/documents/${docId}`);
  }
  function closeDoc() {
    openDoc.value = null;
  }
  async function saveDoc(kbId: string, docId: string, text: string) {
    busy.value = true;
    error.value = null;
    try {
      const r = await apiFetch(`/api/kb/${kbId}/documents/${docId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error(await r.text());
      await viewDoc(kbId, docId);
      await selectKb(kbId);
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }
  async function ingestUrl(kbId: string, url: string) {
    busy.value = true;
    error.value = null;
    try {
      const r = await apiFetch(`/api/kb/${kbId}/ingest-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!r.ok) throw new Error(await r.text());
      await selectKb(kbId);
      await listKbs();
    } catch (e: any) {
      error.value = String(e);
    } finally {
      busy.value = false;
    }
  }

  // ── learning (feedback → reflect → lessons) ──
  async function loadLessons() {
    lessons.value = agentId.value ? await getJson(`/api/agents/${agentId.value}/lessons`) : [];
  }
  async function teachLesson(content: string) {
    if (!agentId.value || !content.trim()) return;
    await postJson(`/api/agents/${agentId.value}/lessons`, { content: content.trim() });
    await loadLessons();
  }
  async function forgetLesson(lessonId: string) {
    if (!agentId.value) return;
    await apiFetch(`/api/agents/${agentId.value}/lessons/${lessonId}`, { method: "DELETE" });
    await loadLessons();
  }
  async function rate(msg: ChatMsg, reward: number) {
    if (!msg.runId || msg.rated) return;
    msg.rated = reward;
    try {
      const r = await postJson(`/api/runs/${msg.runId}/feedback`, { reward, note: null });
      if (r?.learned?.lesson) {
        messages.value.push({ id: nextMsgId(), role: "assistant", kind: "spec", text: `✦ Learned: ${r.learned.lesson}` });
        await loadLessons();
      }
    } catch (e: any) {
      error.value = String(e);
    }
  }
  async function setAutoImprove(val: boolean) {
    if (!agentId.value || !spec.value) return;
    const newSpec = { ...spec.value, auto_improve: val };
    await postJson(`/api/agents/${agentId.value}/selfmod/apply`, { spec: newSpec });
    spec.value = newSpec;
  }
  async function reflectRun(runId: string) {
    if (!agentId.value) return null;
    const r = await postJson(`/api/agents/${agentId.value}/reflect`, { run_id: runId });
    await loadLessons();
    return r;
  }

  // ── analytics ──
  async function loadAnalytics() {
    analytics.value = await getJson("/api/analytics");
  }

  // ── activity log ──
  async function listRuns() {
    runs.value = await getJson("/api/runs");
  }
  async function openRun(runId: string) {
    runSteps.value = await getJson(`/api/runs/${runId}/steps`);
  }
  function closeRun() {
    runSteps.value = null;
  }

  // ── auth / workspace / team ──
  async function boot() {
    // Decide the first screen: install wizard → sign-in → app.
    try {
      const status = await getJson("/api/setup/status");
      authEnabled.value = !!status.auth_enabled;
      workspace.value = { id: "", name: status.workspace_name };
      if (status.needs_setup) {
        setupNeeded.value = true;
        authReady.value = true;
        return;
      }
    } catch { /* API unreachable — fall through to a sign-in attempt */ }
    if (getToken() || !authEnabled.value) {
      try {
        await fetchMe();
      } catch {
        clearToken();
        me.value = null;
      }
    }
    authReady.value = true;
  }

  async function fetchMe() {
    const r = await getJson("/api/auth/me");
    me.value = r.user;
    workspace.value = r.workspace;
    authEnabled.value = !!r.auth_enabled;
    return r;
  }

  async function login(email: string, password: string) {
    const r = await postJson("/api/auth/login", { email, password });
    setToken(r.token);
    me.value = r.user;
    await fetchMe().catch(() => {});
    setupNeeded.value = false;
  }

  async function completeSetup(payload: {
    workspace_name: string; name: string; email: string; password: string;
  }) {
    const r = await postJson("/api/setup/complete", payload);
    setToken(r.token);
    me.value = r.user;
    workspace.value = { id: "", name: r.workspace_name };
    setupNeeded.value = false;
    await fetchMe().catch(() => {});
  }

  async function acceptInvite(token: string, name: string, password: string) {
    const r = await postJson("/api/auth/accept", { token, name, password });
    setToken(r.token);
    me.value = r.user;
    await fetchMe().catch(() => {});
    setupNeeded.value = false;
  }

  async function logout() {
    try { await postJson("/api/auth/logout", {}); } catch { /* best-effort */ }
    clearToken();
    me.value = null;
    resetChat();
    view.value = "home";
  }

  function onUnauthorized() {
    // Triggered by api.ts when a token-bearing request 401s (session expired).
    me.value = null;
    view.value = "home";
  }

  // team management (admin)
  async function loadMembers() {
    members.value = await getJson("/api/auth/users");
  }
  async function loadInvites() {
    invites.value = await getJson("/api/auth/invites");
  }
  async function inviteMember(email: string, role: string) {
    const r = await postJson("/api/auth/invites", { email, role });
    await loadInvites();
    return r;  // { accept_url, token, ... }
  }
  async function revokeInvite(id: string) {
    await apiFetch(`/api/auth/invites/${id}`, { method: "DELETE" });
    await loadInvites();
  }
  async function setMemberRole(id: string, role: string) {
    await apiFetch(`/api/auth/users/${id}/role`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    await loadMembers();
  }
  async function removeMember(id: string) {
    await apiFetch(`/api/auth/users/${id}`, { method: "DELETE" });
    await loadMembers();
  }

  // ── plugins (MCP connectors) ──
  async function listPlugins() {
    plugins.value = await getJson("/api/plugins");
  }
  async function loadPluginTemplates() {
    if (!pluginTemplates.value.length) pluginTemplates.value = await getJson("/api/plugins/templates");
  }
  async function installPlugin(body: Record<string, any>) {
    const p = await postJson("/api/plugins", body);
    await Promise.all([listPlugins(), ensureCatalog(true)]);
    return p;
  }
  async function patchPlugin(id: string, body: Record<string, any>) {
    const r = await apiFetch(`/api/plugins/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    await Promise.all([listPlugins(), ensureCatalog(true)]);
    return r.json();
  }
  async function deletePlugin(id: string) {
    await apiFetch(`/api/plugins/${id}`, { method: "DELETE" });
    await Promise.all([listPlugins(), ensureCatalog(true)]);
  }
  async function testPlugin(id: string) {
    return postJson(`/api/plugins/${id}/test`, {});
  }
  async function testPluginConfig(body: Record<string, any>) {
    return postJson("/api/plugins/test", body);
  }

  return {
    docs, agentId, spec, messages, phase, busy, diff, error, showBuilder,
    view, agents, kbs, kbDocs, selectedKb, runs, runSteps, openDoc, lessons,
    agentTags, faustOpen, faustMsgs, faustBusy, skills, openSkill, confirmState,
    settingsOpen, config, toolCatalog, openSettings, ensureConfig, ensureCatalog, exportAgent,
    createOpen, openCreate, createAgentManual, resetChat,
    confirmAction, resolveConfirm,
    upload, build, ask, proposeSelfMod, applySelfMod, dismissDiff, saveWorkflow,
    listAgents, loadAgent, listKbs, createKb, updateKb, deleteKb, selectKb, uploadToKb, deleteDoc,
    viewDoc, closeDoc, saveDoc, ingestUrl, listRuns, openRun, closeRun,
    rate, setAutoImprove, reflectRun, loadLessons, teachLesson, forgetLesson,
    loadAgentTags, setAgentTags, deleteAgents, deleteRuns, deleteDocs, askFaust,
    listSkills, createSkill, saveSkill, deleteSkill,
    analytics, loadAnalytics,
    // auth / workspace / team
    authReady, authEnabled, setupNeeded, me, workspace, members, invites,
    boot, fetchMe, login, completeSetup, acceptInvite, logout, onUnauthorized,
    loadMembers, loadInvites, inviteMember, revokeInvite, setMemberRole, removeMember,
    // plugins
    plugins, pluginTemplates, listPlugins, loadPluginTemplates, installPlugin,
    patchPlugin, deletePlugin, testPlugin, testPluginConfig,
  };
});
