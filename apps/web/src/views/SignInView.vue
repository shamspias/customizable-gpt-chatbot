<script setup lang="ts">
// Sign-in screen, shown when auth is required and there's no valid session.
import { computed, ref } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
const email = ref("");
const password = ref("");
const show = ref(false);
const busy = ref(false);
const error = ref("");

const valid = computed(() => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.value) && password.value.length > 0);

async function submit() {
  if (!valid.value || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await store.login(email.value.trim(), password.value);
  } catch (e: any) {
    error.value = String(e).replace(/^Error:\s*/, "") || "Sign-in failed.";
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
      <h1>Welcome back</h1>
      <p class="sub">Sign in to <b>{{ store.workspace?.name || "Veldra" }}</b>.</p>

      <form @submit.prevent="submit" class="form">
        <label>Email</label>
        <input v-model="email" type="email" placeholder="you@company.com" autocomplete="username" autofocus />
        <label>Password</label>
        <div class="pw">
          <input v-model="password" :type="show ? 'text' : 'password'" placeholder="Your password"
                 autocomplete="current-password" />
          <button type="button" class="reveal" :aria-label="show ? 'Hide password' : 'Show password'"
                  :aria-pressed="show" @click="show = !show">
            <Icon :name="show ? 'eye-off' : 'eye'" :size="16" />
          </button>
        </div>
        <p v-if="error" class="warn">{{ error }}</p>
        <button class="primary" type="submit" :disabled="!valid || busy">
          {{ busy ? "Signing in…" : "Sign in" }}<Icon name="send" :size="16" />
        </button>
      </form>
      <p class="foot">No account? Ask a workspace admin to invite you.</p>
    </div>
  </div>
</template>

<style scoped>
.gate { min-height: 100vh; min-height: 100dvh; display: grid; place-items: center; padding: 24px;
  background:
    radial-gradient(1200px 540px at 80% -10%, var(--accent-soft), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, color-mix(in srgb, var(--ok) 12%, transparent), transparent 60%),
    var(--bg); }
.card { width: min(420px, 100%); background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); padding: 30px; text-align: center;
  animation: veldra-pop 0.32s ease both; }
.mark { width: 50px; height: 50px; margin: 0 auto 16px; display: grid; place-items: center; border-radius: 14px;
  background: linear-gradient(150deg, var(--accent-soft), color-mix(in srgb, var(--accent-strong) 22%, transparent));
  color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent-ring); }
.mark svg { width: 28px; height: 28px; }
h1 { margin: 0; font-size: 23px; letter-spacing: -0.02em; }
.sub { margin: 6px 0 22px; color: var(--muted); font-size: 14px; }
.form { display: flex; flex-direction: column; gap: 8px; text-align: left; }
label { font-size: 12.5px; font-weight: 600; color: var(--muted); }
.pw { position: relative; display: flex; }
.pw input { padding-right: 42px; }
.reveal { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); background: none;
  border: none; box-shadow: none; color: var(--faint); padding: 7px; border-radius: var(--radius-sm); }
.reveal:hover:not(:disabled) { color: var(--ink); background: var(--surface-2); filter: none; }
.warn { color: var(--danger); font-size: 12.5px; margin: 2px 0; }
.primary { margin-top: 10px; padding: 11px 18px; font-size: 14.5px; font-weight: 650; justify-content: center; }
.foot { margin: 18px 0 0; color: var(--faint); font-size: 12px; }
</style>
