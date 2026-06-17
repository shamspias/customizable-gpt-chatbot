<script setup lang="ts">
// Invite acceptance, reached at #/accept/<token>. Previews the invite, then lets the
// invitee set a name + password to join the workspace.
import { computed, onMounted, ref } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const props = defineProps<{ token: string }>();
const store = useAgentStore();

const loading = ref(true);
const invite = ref<any | null>(null);
const invalid = ref("");
const name = ref("");
const password = ref("");
const confirm = ref("");
const busy = ref(false);
const error = ref("");

onMounted(async () => {
  try {
    const r = await fetch(`/api/auth/invites/${encodeURIComponent(props.token)}/preview`);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Invite not found");
    invite.value = await r.json();
  } catch (e: any) {
    invalid.value = String(e).replace(/^Error:\s*/, "");
  } finally {
    loading.value = false;
  }
});

const valid = computed(
  () => name.value.trim() && password.value.length >= 8 && password.value === confirm.value,
);

async function accept() {
  if (!valid.value || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await store.acceptInvite(props.token, name.value.trim(), password.value);
    window.location.hash = "";
  } catch (e: any) {
    error.value = String(e).replace(/^Error:\s*/, "");
    busy.value = false;
  }
}
</script>

<template>
  <div class="gate">
    <div class="card">
      <span class="mark">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="5" cy="7" r="2.4" fill="currentColor" />
          <circle cx="19" cy="9" r="2.4" fill="currentColor" opacity="0.78" />
          <circle cx="12" cy="18" r="2.4" fill="currentColor" opacity="0.58" />
          <path d="M5 7 19 9 M5 7 12 18 M19 9 12 18" stroke="currentColor" stroke-width="1.4" opacity="0.5" />
        </svg>
      </span>

      <template v-if="loading">
        <p class="sub">Checking your invite…</p>
      </template>

      <template v-else-if="invalid">
        <h1>Invite unavailable</h1>
        <p class="sub">{{ invalid }}</p>
        <button class="primary" @click="$emit('exit')">Go to sign in</button>
      </template>

      <template v-else>
        <h1>Join {{ invite.workspace_name }}</h1>
        <p class="sub">You were invited as <b>{{ invite.role }}</b> ({{ invite.email }}).</p>
        <form @submit.prevent="accept" class="form">
          <label>Your name</label>
          <input v-model="name" placeholder="Ada Lovelace" autocomplete="name" autofocus />
          <div class="two">
            <div>
              <label>Password</label>
              <input v-model="password" type="password" placeholder="8+ characters" autocomplete="new-password" />
            </div>
            <div>
              <label>Confirm</label>
              <input v-model="confirm" type="password" placeholder="Repeat" autocomplete="new-password" />
            </div>
          </div>
          <p v-if="password && password !== confirm" class="warn">Passwords must match.</p>
          <p v-if="error" class="warn">{{ error }}</p>
          <button class="primary" type="submit" :disabled="!valid || busy">
            {{ busy ? "Joining…" : "Join workspace" }}<Icon name="sparkles" :size="16" />
          </button>
        </form>
      </template>
    </div>
  </div>
</template>

<style scoped>
.gate { min-height: 100vh; min-height: 100dvh; display: grid; place-items: center; padding: 24px;
  background:
    radial-gradient(1200px 540px at 80% -10%, var(--accent-soft), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, color-mix(in srgb, var(--ok) 12%, transparent), transparent 60%),
    var(--bg); }
.card { width: min(440px, 100%); background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); padding: 30px; text-align: center;
  animation: veldra-pop 0.32s ease both; }
.mark { width: 50px; height: 50px; margin: 0 auto 16px; display: grid; place-items: center; border-radius: 14px;
  background: linear-gradient(150deg, var(--accent-soft), color-mix(in srgb, var(--accent-strong) 22%, transparent));
  color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent-ring); }
.mark svg { width: 28px; height: 28px; }
h1 { margin: 0; font-size: 22px; letter-spacing: -0.02em; }
.sub { margin: 6px 0 22px; color: var(--muted); font-size: 14px; }
.form { display: flex; flex-direction: column; gap: 8px; text-align: left; }
label { font-size: 12.5px; font-weight: 600; color: var(--muted); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.two > div { display: flex; flex-direction: column; gap: 6px; }
@media (max-width: 400px) { .two { grid-template-columns: 1fr; } }
.warn { color: var(--danger); font-size: 12.5px; margin: 2px 0; }
.primary { margin-top: 10px; padding: 11px 18px; font-size: 14.5px; font-weight: 650; justify-content: center; }
</style>
