<script setup lang="ts">
// First-run install wizard: name the workspace → check the providers → create the
// first admin. Shown only when no users exist yet (store.setupNeeded).
import { computed, onMounted, ref } from "vue";
import Icon from "../components/Icon.vue";
import { postJson } from "../api";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();

const step = ref(0); // 0 workspace · 1 providers · 2 admin
const steps = ["Workspace", "Connection", "Admin"];

const workspaceName = ref("");
const name = ref("");
const email = ref("");
const password = ref("");
const confirm = ref("");

const testing = ref(false);
const test = ref<any | null>(null);
const submitting = ref(false);
const error = ref("");

const cfg = ref<any | null>(null);
onMounted(async () => {
  try {
    const r = await fetch("/api/setup/status");
    if (r.ok) cfg.value = await r.json();
  } catch { /* provider info is informational only */ }
  workspaceName.value = cfg.value?.workspace_name && cfg.value.workspace_name !== "Veldra"
    ? cfg.value.workspace_name : "";
});

const canWorkspace = computed(() => workspaceName.value.trim().length >= 2);
const passwordsMatch = computed(() => password.value.length >= 8 && password.value === confirm.value);
const canFinish = computed(
  () => name.value.trim() && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.value) && passwordsMatch.value,
);

async function runTest() {
  testing.value = true;
  test.value = null;
  try {
    test.value = await postJson("/api/setup/test", {});
  } catch (e: any) {
    test.value = { llm_ok: false, llm_detail: String(e), embed_ok: false, embed_detail: "" };
  } finally {
    testing.value = false;
  }
}

async function finish() {
  if (!canFinish.value) return;
  submitting.value = true;
  error.value = "";
  try {
    await store.completeSetup({
      workspace_name: workspaceName.value.trim(),
      name: name.value.trim(),
      email: email.value.trim(),
      password: password.value,
    });
  } catch (e: any) {
    error.value = String(e).replace(/^Error:\s*/, "");
    submitting.value = false;
  }
}
</script>

<template>
  <div class="gate">
    <div class="card" :class="`s${step}`">
      <div class="brand">
        <span class="mark">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="5" cy="7" r="2.4" fill="currentColor" />
            <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
            <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
            <path d="M5 7 19 9 M5 7 12 18 M19 9 12 18" stroke="currentColor" stroke-width="1.4" opacity="0.5" />
          </svg>
        </span>
        <div>
          <h1>Welcome to Veldra</h1>
          <p>Let's set up your workspace — it takes a minute.</p>
        </div>
      </div>

      <div class="rail">
        <div v-for="(s, i) in steps" :key="s" class="rstep" :class="{ on: i === step, done: i < step }">
          <span class="rdot"><Icon v-if="i < step" name="check" :size="13" /><template v-else>{{ i + 1 }}</template></span>
          <span>{{ s }}</span>
        </div>
      </div>

      <!-- Step 0: workspace -->
      <section v-if="step === 0" class="body">
        <label>Workspace name</label>
        <input v-model="workspaceName" placeholder="Acme AI, Support Desk, …" @keyup.enter="canWorkspace && (step = 1)" autofocus />
        <p class="hint">This is the home for your agents, knowledge, and team.</p>
        <button class="primary" :disabled="!canWorkspace" @click="step = 1">
          Continue<Icon name="send" :size="16" />
        </button>
      </section>

      <!-- Step 1: connection -->
      <section v-else-if="step === 1" class="body">
        <p class="lead">
          Veldra talks to <b>{{ cfg?.llm_provider || "your LLM" }}</b> for reasoning and
          <b>{{ cfg?.embed_provider || "embeddings" }}</b> ({{ cfg?.embed_dim || "—" }}-dim) for search.
          Run a quick check.
        </p>
        <button class="ghost" :disabled="testing" @click="runTest">
          <Icon name="refresh" :size="16" />{{ testing ? "Testing…" : "Test connection" }}
        </button>
        <div v-if="test" class="checks">
          <div class="chk" :class="{ ok: test.llm_ok, bad: !test.llm_ok }">
            <Icon :name="test.llm_ok ? 'check' : 'x'" :size="15" />
            <span><b>LLM</b> — {{ test.llm_detail || (test.llm_ok ? 'OK' : 'unreachable') }}</span>
          </div>
          <div class="chk" :class="{ ok: test.embed_ok, bad: !test.embed_ok }">
            <Icon :name="test.embed_ok ? 'check' : 'x'" :size="15" />
            <span><b>Embeddings</b> — {{ test.embed_detail || (test.embed_ok ? 'OK' : 'unreachable') }}</span>
          </div>
        </div>
        <p class="hint">Providers are configured via environment (see <code>example.env</code>). You can finish setup either way and adjust later.</p>
        <div class="row">
          <button class="ghost" @click="step = 0">Back</button>
          <button class="primary" @click="step = 2">Continue<Icon name="send" :size="16" /></button>
        </div>
      </section>

      <!-- Step 2: admin -->
      <section v-else class="body">
        <label>Your name</label>
        <input v-model="name" placeholder="Ada Lovelace" autofocus />
        <label>Email</label>
        <input v-model="email" type="email" placeholder="you@company.com" />
        <div class="two">
          <div>
            <label>Password</label>
            <input v-model="password" type="password" placeholder="8+ characters" />
          </div>
          <div>
            <label>Confirm</label>
            <input v-model="confirm" type="password" placeholder="Repeat" @keyup.enter="finish" />
          </div>
        </div>
        <p v-if="password && !passwordsMatch" class="warn">Passwords must match and be at least 8 characters.</p>
        <p v-if="error" class="warn">{{ error }}</p>
        <div class="row">
          <button class="ghost" @click="step = 1">Back</button>
          <button class="primary" :disabled="!canFinish || submitting" @click="finish">
            {{ submitting ? "Creating…" : "Create workspace" }}<Icon name="sparkles" :size="16" />
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.gate { min-height: 100vh; min-height: 100dvh; display: grid; place-items: center; padding: 24px;
  background:
    radial-gradient(1200px 540px at 80% -10%, var(--accent-soft), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, color-mix(in srgb, var(--ok) 12%, transparent), transparent 60%),
    var(--bg); }
.card { width: min(520px, 100%); background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); padding: 28px; animation: veldra-pop 0.32s ease both; }
.brand { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.mark { width: 46px; height: 46px; flex: none; display: grid; place-items: center; border-radius: 13px;
  background: linear-gradient(150deg, var(--accent-soft), color-mix(in srgb, var(--accent-strong) 22%, transparent));
  color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent-ring); }
.mark svg { width: 26px; height: 26px; }
.brand h1 { margin: 0; font-size: 21px; letter-spacing: -0.02em; }
.brand p { margin: 2px 0 0; color: var(--muted); font-size: 13.5px; }

.rail { display: flex; gap: 6px; margin-bottom: 22px; }
.rstep { flex: 1; display: flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--faint);
  padding: 7px 9px; border-radius: var(--radius-sm); background: var(--surface-2); font-weight: 600; }
.rstep.on { color: var(--accent); background: var(--accent-soft); }
.rstep.done { color: var(--ok); }
.rdot { width: 19px; height: 19px; flex: none; display: grid; place-items: center; border-radius: 999px;
  background: var(--surface); font-size: 11px; box-shadow: inset 0 0 0 1.5px currentColor; }

.body { display: flex; flex-direction: column; gap: 9px; }
label { font-size: 12.5px; font-weight: 600; color: var(--muted); }
.lead { color: var(--ink); font-size: 14px; line-height: 1.55; margin: 0 0 4px; }
.hint { color: var(--faint); font-size: 12px; line-height: 1.5; margin: 2px 0 0; }
.hint code, .lead code { background: var(--surface-2); padding: 1px 5px; border-radius: 5px; font-size: 11.5px; }
.warn { color: var(--danger); font-size: 12.5px; margin: 2px 0 0; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.two > div { display: flex; flex-direction: column; gap: 6px; }
.row { display: flex; gap: 10px; margin-top: 10px; }
.row .ghost { flex: none; }
.primary { flex: 1; padding: 11px 18px; font-size: 14.5px; font-weight: 650; }
.primary, .row .primary { margin-left: auto; }
button.ghost { background: var(--surface-2); }

.checks { display: flex; flex-direction: column; gap: 8px; margin: 4px 0; }
.chk { display: flex; align-items: center; gap: 9px; padding: 10px 12px; border-radius: var(--radius-sm);
  font-size: 13px; border: 1px solid var(--border); }
.chk.ok { color: var(--ok); border-color: var(--ok-border); background: var(--ok-soft); }
.chk.bad { color: var(--danger); border-color: color-mix(in srgb, var(--danger) 40%, transparent); background: var(--danger-soft); }
.chk b { color: var(--ink); }
.chk.ok b, .chk.bad b { color: inherit; }
</style>
