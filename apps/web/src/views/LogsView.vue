<script setup lang="ts">
import { onMounted } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
onMounted(() => store.listRuns());

function fmt(ts: string | null) {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
const KIND_ICON: Record<string, string> = { build: "sparkles", ask: "send", selfmod: "pencil" };
const STEP_ICON: Record<string, string> = {
  node: "workflow", decision: "brain", tool_call: "wrench", tool_result: "check",
  llm_turn: "spark", final: "check", message: "send", error: "x",
};
function pretty(p: any) {
  if (p == null) return "";
  try { return typeof p === "string" ? p : JSON.stringify(p, null, 2); } catch { return String(p); }
}
</script>

<template>
  <div class="logs" :class="{ 'has-run': store.runSteps }">
    <aside class="runlist">
      <div class="lhead">
        <h2>Activity</h2><div class="grow" />
        <button class="ghost sm" @click="store.listRuns()" aria-label="Refresh"><Icon name="refresh" :size="15" /></button>
      </div>
      <p class="muted sub">Every build, ask, and edit — with the full step trace.</p>
      <div v-if="store.runs.length" class="runs">
        <button v-for="r in store.runs" :key="r.id" class="run"
                :class="{ active: store.runSteps?.run?.id === r.id }" @click="store.openRun(r.id)">
          <span class="st" :class="r.status" />
          <span class="kic"><Icon :name="KIND_ICON[r.kind] || 'activity'" :size="15" /></span>
          <span class="rmeta">
            <span class="rk">{{ r.kind }}<span v-if="r.agent_name" class="ag"> · {{ r.agent_name }}</span></span>
            <span class="rt">{{ fmt(r.created_at) }}</span>
          </span>
          <span class="badge" :class="r.status">{{ r.status }}</span>
        </button>
      </div>
      <div v-else class="empty muted"><div class="halo"><Icon name="activity" :size="24" /></div>No activity yet.</div>
    </aside>

    <section class="trace">
      <template v-if="store.runSteps">
        <div class="thead">
          <span class="kic big"><Icon :name="KIND_ICON[store.runSteps.run.kind] || 'activity'" :size="18" /></span>
          <div>
            <strong>{{ store.runSteps.run.kind }} run</strong>
            <div class="muted small">{{ fmt(store.runSteps.run.created_at) }} · <span class="badge" :class="store.runSteps.run.status">{{ store.runSteps.run.status }}</span></div>
          </div>
          <div class="grow" />
          <button class="ghost sm show-mobile" @click="store.closeRun()" aria-label="Close"><Icon name="x" :size="16" /></button>
        </div>

        <div v-if="store.runSteps.run.input" class="block">
          <div class="blabel">input</div>
          <pre>{{ pretty(store.runSteps.run.input) }}</pre>
        </div>

        <div class="timeline">
          <div v-for="s in store.runSteps.steps" :key="s.ordinal" class="step">
            <span class="sic"><Icon :name="STEP_ICON[s.type] || 'chevron'" :size="14" /></span>
            <div class="sbody">
              <div class="sline"><strong>{{ s.type }}</strong><span v-if="s.name" class="sname">{{ s.name }}</span><span class="grow" /><span class="muted small">{{ fmt(s.created_at) }}</span></div>
              <pre v-if="s.payload" class="spayload">{{ pretty(s.payload) }}</pre>
            </div>
          </div>
          <p v-if="!store.runSteps.steps.length" class="muted">No steps recorded for this run.</p>
        </div>

        <div v-if="store.runSteps.run.error" class="block err">
          <div class="blabel">error</div><pre>{{ store.runSteps.run.error }}</pre>
        </div>
      </template>
      <div v-else class="pick muted">
        <div class="halo"><Icon name="clock" :size="26" /></div>
        Select a run to see every tracked step.
      </div>
    </section>
  </div>
</template>

<style scoped>
.logs { flex: 1; display: grid; grid-template-columns: 360px 1fr; gap: 1px; background: var(--border); overflow: hidden; }
.runlist { background: var(--bg); display: flex; flex-direction: column; min-height: 0; padding: 16px 14px; gap: 4px; }
.lhead { display: flex; align-items: center; }
.lhead h2 { margin: 0; font-size: 19px; }
.grow { flex: 1; }
.sub { margin: 2px 0 12px; font-size: 12.5px; }
.runs { display: flex; flex-direction: column; gap: 6px; overflow: auto; }
.run { display: flex; align-items: center; gap: 10px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 12px; text-align: left; color: var(--ink); cursor: pointer; }
.run:hover { border-color: var(--border-strong); filter: none; }
.run.active { border-color: var(--accent); background: var(--accent-soft); }
.st { width: 8px; height: 8px; border-radius: 99px; background: var(--faint); flex: none; }
.st.done { background: var(--ok); } .st.running { background: var(--accent); animation: veldra-pulse 1.1s infinite; } .st.error { background: var(--danger); }
.kic { color: var(--accent); display: grid; place-items: center; }
.kic.big { width: 38px; height: 38px; border-radius: 11px; background: var(--accent-soft); }
.rmeta { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.rk { font-size: 13.5px; font-weight: 600; text-transform: capitalize; }
.ag { color: var(--muted); font-weight: 500; }
.rt { font-size: 11.5px; color: var(--faint); }
.badge { font-size: 10.5px; font-weight: 600; padding: 1px 7px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); text-transform: capitalize; }
.badge.done { color: var(--ok); } .badge.running { color: var(--accent); } .badge.error { color: var(--danger); }

.trace { background: var(--bg); padding: 18px; overflow: auto; }
.thead { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.thead strong { font-size: 16px; text-transform: capitalize; }
.small { font-size: 12px; }
.block { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 12px; margin-bottom: 12px; }
.block.err { border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
.blabel { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); margin-bottom: 5px; }
pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: var(--ink); }
.timeline { display: flex; flex-direction: column; gap: 2px; position: relative; }
.step { display: flex; gap: 11px; padding: 4px 0; }
.sic { width: 26px; height: 26px; flex: none; display: grid; place-items: center; border-radius: 8px; color: var(--accent); background: var(--accent-soft); margin-top: 1px; }
.sbody { flex: 1; min-width: 0; border-left: 2px solid var(--border); padding: 0 0 12px 12px; margin-left: -1px; }
.sline { display: flex; align-items: center; gap: 8px; }
.sline strong { font-size: 13px; text-transform: capitalize; }
.sname { font-size: 12px; color: var(--accent); background: var(--accent-soft); padding: 1px 7px; border-radius: 999px; }
.spayload { margin-top: 5px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; max-height: 240px; overflow: auto; }
.pick, .empty { margin: 70px auto; text-align: center; color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 12px; }
.halo { width: 56px; height: 56px; display: grid; place-items: center; border-radius: 16px; color: var(--accent); background: var(--accent-soft); }
.muted { color: var(--muted); }
.show-mobile { display: none; }

@media (max-width: 860px) {
  .logs { grid-template-columns: 1fr; }
  .trace { display: none; }
  .logs.has-run .runlist { display: none; }
  .logs.has-run .trace { display: block; }
  .show-mobile { display: inline-flex; }
}
</style>
