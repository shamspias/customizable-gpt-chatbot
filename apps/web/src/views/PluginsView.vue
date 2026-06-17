<script setup lang="ts">
// Plugins & connectors: built-in tools are always on; admins install MCP connectors
// (Shopify, Alibaba, or any Streamable-HTTP / SSE / stdio MCP server) here.
import { computed, onMounted, reactive, ref } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const isAdmin = computed(() => store.me?.role === "admin" || !store.authEnabled);

const mode = ref<"list" | "form">("list");
const editingId = ref<string | null>(null);
const tpl = ref<any | null>(null);
const testing = ref(false);
const saving = ref(false);
const testResult = ref<any | null>(null);
const error = ref("");

const f = reactive({
  key: "", name: "", description: "", transport: "http",
  url: "", command: "", argsStr: "", token: "", headersStr: "", allowStr: "",
});

onMounted(() => { store.listPlugins(); store.loadPluginTemplates(); });

function reset() {
  Object.assign(f, { key: "", name: "", description: "", transport: "http",
    url: "", command: "", argsStr: "", token: "", headersStr: "", allowStr: "" });
  testResult.value = null; error.value = ""; editingId.value = null; tpl.value = null;
}

function openAdd(template: any) {
  reset();
  tpl.value = template;
  f.transport = template.transport;
  f.key = template.key.startsWith("custom") ? "" : template.key;
  f.name = template.name;
  f.description = template.description || "";
  mode.value = "form";
}

function openEdit(p: any) {
  reset();
  editingId.value = p.id;
  Object.assign(f, {
    key: p.key, name: p.name, description: p.description, transport: p.transport,
    url: p.url || "", command: p.command || "", argsStr: (p.args || []).join(" "),
    allowStr: (p.tool_allowlist || []).join(", "),
  });
  mode.value = "form";
}

function buildBody(): Record<string, any> {
  const body: Record<string, any> = {
    name: f.name.trim(), description: f.description.trim(), transport: f.transport,
    url: f.url.trim(), command: f.command.trim(),
    args: f.argsStr.trim() ? f.argsStr.trim().split(/\s+/) : [],
    tool_allowlist: f.allowStr.trim() ? f.allowStr.split(",").map((s) => s.trim()).filter(Boolean) : [],
  };
  if (!editingId.value) body.key = f.key.trim();
  // headers: advanced JSON + a token mapped via the template's auth hint
  let headers: Record<string, string> = {};
  if (f.headersStr.trim()) {
    try { headers = JSON.parse(f.headersStr); } catch { throw new Error("Headers must be valid JSON."); }
  }
  if (f.token.trim()) {
    const auth = tpl.value?.auth;
    const name = auth?.header || "Authorization";
    const prefix = auth?.prefix ?? "Bearer ";
    headers[name] = `${prefix}${f.token.trim()}`;
  }
  if (Object.keys(headers).length || !editingId.value) body.headers = headers;
  return body;
}

async function test() {
  testing.value = true; error.value = ""; testResult.value = null;
  try {
    const b = buildBody();
    testResult.value = await store.testPluginConfig({
      transport: b.transport, url: b.url, command: b.command, args: b.args, headers: b.headers || {},
    });
  } catch (e: any) {
    error.value = String(e).replace(/^Error:\s*/, "");
  } finally {
    testing.value = false;
  }
}

async function save() {
  saving.value = true; error.value = "";
  try {
    const body = buildBody();
    if (editingId.value) await store.patchPlugin(editingId.value, body);
    else await store.installPlugin(body);
    reset(); mode.value = "list";
  } catch (e: any) {
    error.value = String(e).replace(/^Error:\s*/, "");
  } finally {
    saving.value = false;
  }
}

async function toggle(p: any) {
  await store.patchPlugin(p.id, { enabled: !p.enabled });
}
async function remove(p: any) {
  if (!(await store.confirmAction({ message: `Remove the “${p.name}” connector?`, confirmLabel: "Remove" }))) return;
  await store.deletePlugin(p.id);
}
async function testInstalled(p: any) {
  p._testing = true;
  try { p._test = await store.testPlugin(p.id); await store.listPlugins(); }
  finally { p._testing = false; }
}

const canSave = computed(() => f.name.trim() && (editingId.value || f.key.trim()) &&
  (f.transport === "stdio" ? f.command.trim() : f.url.trim()));
const tIcon = (p: any) => store.pluginTemplates.find((t: any) => t.key === p.key)?.icon || "🔌";
</script>

<template>
  <div class="wrap">
    <div class="inner">
      <header class="phead">
        <div>
          <h1>Plugins &amp; connectors</h1>
          <p>Built-in tools are always available. Connect external MCP servers to give agents new powers.</p>
        </div>
        <button v-if="isAdmin && mode === 'list'" @click="mode = 'form'"><Icon name="plus" :size="16" />Add connector</button>
        <button v-if="mode === 'form'" class="ghost" @click="mode = 'list'; reset()"><Icon name="x" :size="16" />Cancel</button>
      </header>

      <!-- LIST -->
      <template v-if="mode === 'list'">
        <section v-if="store.plugins.length" class="grid">
          <div v-for="p in store.plugins" :key="p.id" class="pcard">
            <div class="ptop">
              <span class="pic">{{ tIcon(p) }}</span>
              <div class="pmeta">
                <strong>{{ p.name }}</strong>
                <small>{{ p.transport }} · {{ p.key }}</small>
              </div>
              <span class="status" :class="p.status">{{ p.status }}</span>
            </div>
            <div class="purl">{{ p.transport === "stdio" ? (p.command + " " + (p.args || []).join(" ")) : p.url }}</div>
            <div class="pfoot">
              <span class="tools">{{ p.n_tools }} tool{{ p.n_tools === 1 ? "" : "s" }}</span>
              <span v-if="p._test && p._test.error" class="err" :title="p._test.error">connect error</span>
              <div class="grow" />
              <template v-if="isAdmin">
                <label class="switch" :title="p.enabled ? 'Enabled' : 'Disabled'">
                  <input type="checkbox" :checked="p.enabled" @change="toggle(p)" /><span /></label>
                <button class="sm ghost" :disabled="p._testing" @click="testInstalled(p)">{{ p._testing ? "…" : "Test" }}</button>
                <button class="sm ghost" @click="openEdit(p)">Edit</button>
                <button class="sm danger" @click="remove(p)"><Icon name="trash" :size="14" /></button>
              </template>
            </div>
          </div>
        </section>
        <div v-else class="empty">
          <span class="pic">🔌</span>
          <p>No connectors yet. {{ isAdmin ? "Pick a template below to add one." : "Ask an admin to add connectors." }}</p>
        </div>

        <!-- templates -->
        <section v-if="isAdmin" class="tpls">
          <h2>Add a connector</h2>
          <div class="grid">
            <button v-for="t in store.pluginTemplates" :key="t.key" class="tcard" @click="openAdd(t)">
              <span class="pic">{{ t.icon }}</span>
              <span class="tbody"><strong>{{ t.name }}</strong><small>{{ t.description }}</small></span>
              <Icon name="plus" :size="15" class="tadd" />
            </button>
          </div>
        </section>
      </template>

      <!-- FORM -->
      <template v-else>
        <section class="form">
          <h2>{{ editingId ? "Edit connector" : (tpl ? `New ${tpl.name} connector` : "New connector") }}</h2>
          <div class="two">
            <div><label>Name</label><input v-model="f.name" placeholder="Shopify store" /></div>
            <div>
              <label>Key (tool namespace)</label>
              <input v-model="f.key" :disabled="!!editingId" placeholder="shopify" />
            </div>
          </div>
          <label>Description</label>
          <input v-model="f.description" placeholder="What this connector is for" />
          <label>Transport</label>
          <select v-model="f.transport">
            <option value="http">Streamable HTTP</option>
            <option value="sse">SSE</option>
            <option value="stdio">Local process (stdio)</option>
          </select>

          <template v-if="f.transport !== 'stdio'">
            <label>Server URL</label>
            <input v-model="f.url" :placeholder="tpl?.url_placeholder || 'https://host/mcp'" />
            <label>Token <small class="opt">— {{ tpl?.auth?.label || 'optional bearer token' }}</small></label>
            <input v-model="f.token" type="password" :placeholder="editingId ? 'leave blank to keep existing' : 'paste token'" />
          </template>
          <template v-else>
            <label>Command</label>
            <input v-model="f.command" :placeholder="tpl?.command_placeholder || 'npx'" />
            <label>Arguments</label>
            <input v-model="f.argsStr" :placeholder="tpl?.args_placeholder || '-y some-mcp-server'" />
          </template>

          <details class="adv">
            <summary>Advanced</summary>
            <label>Tool allow-list <small class="opt">— comma-separated, blank = all</small></label>
            <input v-model="f.allowStr" placeholder="get_products, search_orders" />
            <template v-if="f.transport !== 'stdio'">
              <label>Extra headers (JSON)</label>
              <input v-model="f.headersStr" placeholder='{"X-Api-Version": "2024-10"}' />
            </template>
          </details>

          <div v-if="testResult" class="tres" :class="{ ok: testResult.ok, bad: !testResult.ok }">
            <Icon :name="testResult.ok ? 'check' : 'x'" :size="15" />
            <span v-if="testResult.ok">Connected — {{ testResult.tools.length }} tool(s): {{ testResult.tools.map((t:any)=>t.name).slice(0,8).join(", ") }}</span>
            <span v-else>{{ testResult.error || "Could not connect" }}</span>
          </div>
          <p v-if="error" class="warn">{{ error }}</p>

          <div class="actions">
            <button class="ghost" :disabled="testing" @click="test">{{ testing ? "Testing…" : "Test connection" }}</button>
            <div class="grow" />
            <button :disabled="!canSave || saving" @click="save">{{ saving ? "Saving…" : (editingId ? "Save" : "Install") }}</button>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.wrap { flex: 1; overflow: auto; background: var(--bg); }
.inner { max-width: 940px; margin: 0 auto; padding: 28px 22px 60px; }
.phead { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 22px; }
.phead h1 { margin: 0; font-size: 22px; letter-spacing: -0.02em; }
.phead p { margin: 4px 0 0; color: var(--muted); font-size: 13.5px; max-width: 60ch; }
.phead button { margin-left: auto; }
.phead .ghost { margin-left: auto; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.pcard { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px;
  display: flex; flex-direction: column; gap: 10px; }
.ptop { display: flex; align-items: center; gap: 11px; }
.pic { width: 38px; height: 38px; flex: none; display: grid; place-items: center; border-radius: 11px;
  background: var(--surface-2); font-size: 20px; }
.pmeta { display: flex; flex-direction: column; min-width: 0; }
.pmeta strong { font-size: 14.5px; }
.pmeta small { color: var(--faint); font-size: 11.5px; text-transform: capitalize; }
.status { margin-left: auto; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  padding: 2px 8px; border-radius: 999px; background: var(--surface-2); color: var(--muted); }
.status.ok { background: var(--ok-soft); color: var(--ok); }
.status.error { background: var(--danger-soft); color: var(--danger); }
.purl { font-family: ui-monospace, monospace; font-size: 11.5px; color: var(--muted); background: var(--surface-2);
  padding: 7px 9px; border-radius: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pfoot { display: flex; align-items: center; gap: 8px; }
.tools { font-size: 12px; color: var(--faint); }
.err { color: var(--danger); font-size: 11.5px; }
.grow { flex: 1; }
.pfoot .sm { padding: 5px 9px; font-size: 12px; }

.switch { position: relative; width: 34px; height: 19px; display: inline-block; }
.switch input { opacity: 0; width: 0; height: 0; }
.switch span { position: absolute; inset: 0; background: var(--border-strong); border-radius: 999px; transition: 0.16s; cursor: pointer; }
.switch span::before { content: ""; position: absolute; width: 15px; height: 15px; left: 2px; top: 2px; background: #fff; border-radius: 50%; transition: 0.16s; }
.switch input:checked + span { background: var(--accent); }
.switch input:checked + span::before { transform: translateX(15px); }

.empty { text-align: center; padding: 40px 0; color: var(--muted); }
.empty .pic { margin: 0 auto 10px; }

.tpls { margin-top: 28px; }
.tpls h2, .form h2 { font-size: 15px; margin: 0 0 12px; }
.tcard { display: flex; align-items: center; gap: 11px; text-align: left; color: var(--ink); background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius); padding: 13px; box-shadow: none; }
.tcard:hover { border-color: var(--accent); filter: none; }
.tbody { display: flex; flex-direction: column; min-width: 0; }
.tbody strong { font-size: 14px; }
.tbody small { font-size: 11.5px; color: var(--faint); line-height: 1.4; }
.tadd { margin-left: auto; color: var(--faint); flex: none; }

.form { max-width: 560px; display: flex; flex-direction: column; gap: 8px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 22px; }
.form label { font-size: 12.5px; font-weight: 600; color: var(--muted); }
.form .opt { font-weight: 400; color: var(--faint); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.two > div { display: flex; flex-direction: column; gap: 6px; }
.adv { margin: 6px 0; }
.adv summary { cursor: pointer; font-size: 13px; color: var(--accent); font-weight: 600; }
.adv > label { margin-top: 8px; display: block; }
.tres { display: flex; align-items: center; gap: 8px; font-size: 12.5px; padding: 9px 11px; border-radius: var(--radius-sm); }
.tres.ok { background: var(--ok-soft); color: var(--ok); }
.tres.bad { background: var(--danger-soft); color: var(--danger); }
.warn { color: var(--danger); font-size: 12.5px; }
.actions { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
</style>
