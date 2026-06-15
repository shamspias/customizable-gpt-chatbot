<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import Icon from "./Icon.vue";
import { useAgentStore } from "../stores/agent";

// A proper, guided "create an agent" experience (modeled on aura-proto's builder):
//  • Describe — say what you want, Veldra designs the whole agent.
//  • Team     — describe a company, get a coordinator + specialist agents.
//  • Manual   — full control: name, policy, model, tools, knowledge, skills.
const store = useAgentStore();
const tab = ref<"describe" | "team" | "manual">("describe");
const desc = ref("");
const descEl = ref<HTMLTextAreaElement | null>(null);

const DESCRIBE_EX = [
  "Answer questions from my docs and always cite the page.",
  "Triage support emails and draft replies grounded in our docs.",
  "A research assistant that searches my docs, then summarizes with citations.",
];
const TEAM_EX = [
  "A digital marketing agency: strategy, content, and client-support agents.",
  "An online store: a sales agent, an order-support agent, and a returns agent.",
  "A clinic: reception/booking, billing, and a patient-FAQ agent from our docs.",
];
const examples = computed(() => (tab.value === "team" ? TEAM_EX : DESCRIBE_EX));

// ── manual form ──
const m = ref({
  name: "", system_prompt: "", model: "", effort: "high",
  tools: [] as string[], knowledge_bases: [] as string[], skills: [] as string[],
});
const manualErr = ref("");

watch(() => store.createOpen, (open) => {
  if (!open) return;
  tab.value = "describe";
  desc.value = "";
  manualErr.value = "";
  m.value = { name: "", system_prompt: "", model: "", effort: "high", tools: [], knowledge_bases: [], skills: [] };
  store.ensureConfig();
  nextTick(() => descEl.value?.focus());
});
watch(tab, (t) => {
  if (t === "manual") {
    store.ensureCatalog();
    if (!store.kbs.length) store.listKbs();
    if (!store.skills.length) store.listSkills();
    if (!m.value.model) m.value.model = store.config?.worker_model || store.config?.ollama_model || "";
  }
});

function close() { store.createOpen = false; }

async function runBuild(prompt: string) {
  store.resetChat();
  store.view = "studio";
  await store.build(prompt);
  if (store.agentId && !store.error) close();  // success → land in Studio with the new agent
}
function submitDescribe() {
  const t = desc.value.trim();
  if (!t || store.busy) return;
  runBuild(tab.value === "team" ? `Set up a team of agents for this company: ${t}` : t);
}
function toggle(list: string[], v: string) {
  const i = list.indexOf(v);
  i >= 0 ? list.splice(i, 1) : list.push(v);
}
async function submitManual() {
  manualErr.value = "";
  if (!m.value.name.trim() || !m.value.system_prompt.trim()) {
    manualErr.value = "Name and instructions are required.";
    return;
  }
  const spec: Record<string, any> = {
    name: m.value.name.trim(),
    description: "",
    system_prompt: m.value.system_prompt.trim(),
    model: m.value.model.trim() || (store.config?.worker_model ?? "claude-sonnet-4-6"),
    effort: m.value.effort,
    thinking_method: "react",
    tools: m.value.tools.map((name) => ({ name, permission_mode: "auto" })),
    knowledge_bases: m.value.knowledge_bases,
    skills: m.value.skills,
    auto_improve: false,
  };
  try {
    await store.createAgentManual(spec);
    store.view = "studio";
    close();
  } catch (e: any) {
    manualErr.value = String(e?.message || e).replace(/^Error:\s*/, "");
  }
}
</script>

<template>
  <transition name="cam">
    <div v-if="store.createOpen" class="wrap" @click.self="close">
      <div class="modal" role="dialog" aria-modal="true" aria-label="Create an agent">
        <header>
          <div class="ttl"><span class="mk"><Icon name="sparkles" :size="16" /></span> Create an agent</div>
          <button class="x" aria-label="Close" @click="close"><Icon name="x" :size="16" /></button>
        </header>

        <div class="tabs" role="tablist">
          <button role="tab" :class="{ on: tab === 'describe' }" @click="tab = 'describe'"><Icon name="sparkles" :size="14" />Describe</button>
          <button role="tab" :class="{ on: tab === 'team' }" @click="tab = 'team'"><Icon name="layers" :size="14" />Team</button>
          <button role="tab" :class="{ on: tab === 'manual' }" @click="tab = 'manual'"><Icon name="settings" :size="14" />Manual</button>
        </div>

        <!-- Describe / Team -->
        <div v-if="tab !== 'manual'" class="body">
          <p class="lead">
            <template v-if="tab === 'team'">Describe your company. Veldra designs a <strong>team</strong> —
              a coordinator plus a specialist agent per role — and wires them together.</template>
            <template v-else>Say what you want in plain words. Veldra designs the policy, tools,
              knowledge, and even a workflow — then you chat with it.</template>
          </p>
          <textarea ref="descEl" v-model="desc" rows="4" :disabled="store.busy"
            :placeholder="tab === 'team' ? 'e.g. An online store with sales, order-support, and returns agents…' : 'e.g. A support agent that answers from our help docs and always cites the page…'"
            @keydown.enter.exact.prevent="submitDescribe" />
          <div class="ex">
            <span class="exlabel">Try:</span>
            <button v-for="e in examples" :key="e" class="exchip" :disabled="store.busy" @click="desc = e">{{ e }}</button>
          </div>
          <div class="foot">
            <span v-if="store.busy" class="busy"><span class="dot" />{{ store.phase || "designing…" }}</span>
            <span v-else-if="store.error" class="err">{{ store.error }}</span>
            <div class="grow" />
            <button class="ghost" :disabled="store.busy" @click="close">Cancel</button>
            <button :disabled="store.busy || !desc.trim()" @click="submitDescribe">
              <Icon name="sparkles" :size="15" />{{ tab === 'team' ? 'Build team' : 'Create agent' }}
            </button>
          </div>
        </div>

        <!-- Manual -->
        <div v-else class="body manual">
          <div class="row2">
            <label>Name<input v-model="m.name" placeholder="Support Assistant" /></label>
            <label>Effort
              <select v-model="m.effort"><option>low</option><option>medium</option><option>high</option><option>xhigh</option></select>
            </label>
          </div>
          <label>Instructions (policy)
            <textarea v-model="m.system_prompt" rows="4" placeholder="You are a helpful support agent. Answer concisely and cite sources…" />
          </label>
          <label>Model<input v-model="m.model" :placeholder="store.config?.worker_model || 'model id'" /></label>

          <div v-if="store.toolCatalog.length" class="pick">
            <div class="picklabel">Tools</div>
            <div class="chips">
              <button v-for="t in store.toolCatalog" :key="t.name" class="pchip" :class="{ on: m.tools.includes(t.name) }"
                      :title="t.description" @click="toggle(m.tools, t.name)">{{ t.name }}</button>
            </div>
          </div>
          <div v-if="store.kbs.length" class="pick">
            <div class="picklabel">Knowledge bases</div>
            <div class="chips">
              <button v-for="k in store.kbs" :key="k.id" class="pchip" :class="{ on: m.knowledge_bases.includes(k.id) }"
                      @click="toggle(m.knowledge_bases, k.id)">{{ k.name }}</button>
            </div>
          </div>
          <div v-if="store.skills.length" class="pick">
            <div class="picklabel">Skills</div>
            <div class="chips">
              <button v-for="s in store.skills" :key="s.id" class="pchip" :class="{ on: m.skills.includes(s.name) }"
                      @click="toggle(m.skills, s.name)">{{ s.name }}</button>
            </div>
          </div>

          <div class="foot">
            <span v-if="manualErr" class="err">{{ manualErr }}</span>
            <div class="grow" />
            <button class="ghost" @click="close">Cancel</button>
            <button :disabled="!m.name.trim() || !m.system_prompt.trim()" @click="submitManual">
              <Icon name="check" :size="15" />Create agent
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.wrap { position: fixed; inset: 0; z-index: 70; background: rgba(27, 34, 55, 0.4); backdrop-filter: blur(3px); display: flex; align-items: flex-start; justify-content: center; padding: 8vh 16px 16px; }
.modal { width: min(620px, 100%); background: var(--bg); border: 1px solid var(--border-strong); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow: hidden; animation: veldra-pop 0.16s ease both; max-height: 84vh; display: flex; flex-direction: column; }
header { display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--border); }
.ttl { display: flex; align-items: center; gap: 9px; font-size: 15px; font-weight: 700; }
.mk { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 9px; background: var(--accent-soft); color: var(--accent); }
header .x { margin-left: auto; background: none; border: none; color: var(--muted); padding: 6px; border-radius: 8px; box-shadow: none; }
header .x:hover { background: var(--surface-2); color: var(--ink); filter: none; }

.tabs { display: flex; gap: 4px; padding: 8px 12px 0; border-bottom: 1px solid var(--border); }
.tabs [role="tab"] { background: none; border: none; box-shadow: none; color: var(--muted); font-weight: 600; font-size: 13px; padding: 8px 12px; border-radius: var(--radius-sm) var(--radius-sm) 0 0; display: inline-flex; align-items: center; gap: 6px; position: relative; }
.tabs [role="tab"]:hover { color: var(--ink); background: var(--surface-2); filter: none; }
.tabs [role="tab"].on { color: var(--accent); }
.tabs [role="tab"].on::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: -1px; height: 2px; border-radius: 2px; background: var(--accent); }

.body { padding: 16px; overflow: auto; display: flex; flex-direction: column; gap: 12px; }
.lead { margin: 0; font-size: 13.5px; line-height: 1.6; color: var(--muted); }
.body textarea, .body input, .body select { width: 100%; }
.ex { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; }
.exlabel { font-size: 11px; color: var(--faint); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; }
.exchip { background: var(--surface); border: 1px solid var(--border); color: var(--ink); border-radius: 999px; padding: 6px 12px; font-size: 12.5px; font-weight: 500; box-shadow: none; text-align: left; }
.exchip:hover { border-color: var(--accent); color: var(--accent); filter: none; }

.foot { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.foot .grow { flex: 1; }
.busy { display: inline-flex; align-items: center; gap: 7px; color: var(--accent); font-size: 13px; text-transform: capitalize; }
.busy .dot { width: 7px; height: 7px; border-radius: 99px; background: var(--accent); animation: veldra-pulse 1s ease-in-out infinite; }
.err { color: var(--danger); font-size: 12.5px; }

.manual label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; font-weight: 600; color: var(--muted); }
.row2 { display: grid; grid-template-columns: 1fr 140px; gap: 12px; }
.pick { display: flex; flex-direction: column; gap: 7px; }
.picklabel { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.pchip { background: var(--surface-2); border: 1px solid var(--border); color: var(--muted); border-radius: 999px; padding: 4px 11px; font-size: 12px; box-shadow: none; }
.pchip:hover { border-color: var(--border-strong); color: var(--ink); filter: none; }
.pchip.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }

.cam-enter-active, .cam-leave-active { transition: opacity 0.16s ease; }
.cam-enter-from, .cam-leave-to { opacity: 0; }
@media (max-width: 560px) { .row2 { grid-template-columns: 1fr; } .wrap { padding: 4vh 10px 10px; } }
</style>
