<script setup lang="ts">
import { computed, onMounted } from "vue";
import Icon from "../components/Icon.vue";
import { useAgentStore } from "../stores/agent";

const store = useAgentStore();
onMounted(() => store.loadAnalytics());
const a = computed<any>(() => store.analytics || {});

function money(n: number): string {
  if (!n) return "$0";
  return n < 0.01 ? "<$0.01" : "$" + n.toFixed(n < 1 ? 4 : 2);
}
function tok(n: number): string {
  if (!n) return "0";
  return n >= 1_000_000 ? (n / 1e6).toFixed(2) + "M" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
}
function pct(n: number): string {
  return Math.round((n || 0) * 100) + "%";
}
function ms(n: number): string {
  return n >= 1000 ? (n / 1000).toFixed(1) + "s" : Math.round(n || 0) + "ms";
}
</script>

<template>
  <div class="ins">
    <div class="head">
      <div class="htext">
        <h2>Insights</h2>
        <p>Live rollups over your full run history — usage, cost, reliability, and what to tune.</p>
      </div>
      <div class="grow" />
      <button class="ghost sm" aria-label="Refresh" @click="store.loadAnalytics()">
        <Icon name="refresh" :size="15" />Refresh
      </button>
    </div>

    <div v-if="!store.analytics" class="empty">Loading analytics…</div>

    <template v-else-if="a.total_runs">
      <!-- KPI cards -->
      <div class="kpis">
        <div class="kpi"><span class="kv">{{ a.total_runs }}</span><span class="kl">total runs</span></div>
        <div class="kpi"><span class="kv">{{ pct(a.success_rate) }}</span><span class="kl">success rate</span></div>
        <div class="kpi"><span class="kv accent">{{ money(a.cost_usd_total) }}</span><span class="kl">est. spend</span></div>
        <div class="kpi"><span class="kv">{{ tok(a.tokens_total) }}</span><span class="kl">tokens</span></div>
        <div class="kpi"><span class="kv">{{ ms(a.latency_ms?.p95) }}</span><span class="kl">p95 latency</span></div>
        <div class="kpi">
          <span class="kv">
            <span class="up">▲{{ a.reward?.thumbs_up || 0 }}</span>
            <span class="down">▼{{ a.reward?.thumbs_down || 0 }}</span>
          </span>
          <span class="kl">feedback</span>
        </div>
      </div>

      <div class="grid2">
        <!-- tuning suggestions -->
        <section v-if="a.suggestions?.length" class="card span2">
          <h3><Icon name="spark" :size="14" /> Suggestions</h3>
          <div v-for="(s, i) in a.suggestions" :key="i" class="sug" :class="s.severity">
            <span class="sev">{{ s.severity }}</span><span>{{ s.text }}</span>
          </div>
        </section>

        <!-- per-agent table -->
        <section class="card span2">
          <h3>Per-agent</h3>
          <div class="tbl">
            <div class="tr th">
              <span>Agent</span><span>Runs</span><span>Success</span><span>Tokens</span><span>Cost</span><span>Rating</span>
            </div>
            <div v-for="ag in a.agents" :key="ag.agent_id" class="tr">
              <span class="nm">{{ ag.name }}</span>
              <span>{{ ag.runs }}</span>
              <span>{{ pct(ag.success_rate) }}</span>
              <span>{{ tok(ag.tokens) }}</span>
              <span>{{ money(ag.cost_usd) }}</span>
              <span class="rt">
                <template v-if="ag.thumbs_up || ag.thumbs_down">
                  <span class="up">▲{{ ag.thumbs_up }}</span> <span class="down">▼{{ ag.thumbs_down }}</span>
                </template>
                <span v-else class="muted">—</span>
              </span>
            </div>
          </div>
        </section>

        <!-- cost by model -->
        <section class="card">
          <h3>Spend by model</h3>
          <div v-if="a.by_model?.length">
            <div v-for="m in a.by_model" :key="m.model" class="mrow">
              <span class="mname">{{ m.model }}</span>
              <span class="mmeta">{{ tok(m.tokens) }} tok · {{ m.runs }} runs</span>
              <span class="mcost">{{ money(m.cost_usd) }}</span>
            </div>
          </div>
          <p v-else class="muted">No priced usage yet.</p>
        </section>

        <!-- recent errors -->
        <section class="card">
          <h3>Recent errors <span v-if="a.errors?.length" class="badge">{{ a.errors.length }}</span></h3>
          <div v-if="a.errors?.length" class="errs">
            <div v-for="e in a.errors" :key="e.id" class="erow">
              <strong>{{ e.agent }}</strong><span>{{ e.error }}</span>
            </div>
          </div>
          <p v-else class="muted">No errors — clean runs. 🎉</p>
        </section>
      </div>
    </template>

    <div v-else class="empty">
      <div class="halo"><Icon name="activity" :size="26" /></div>
      <p>No runs yet. Chat with an agent and analytics will appear here.</p>
    </div>
  </div>
</template>

<style scoped>
.ins { flex: 1; background: var(--bg); padding: 22px; overflow: auto; }
.head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
.htext h2 { margin: 0; font-size: 20px; letter-spacing: -0.015em; }
.htext p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
.head .grow { flex: 1; }
.empty { color: var(--muted); text-align: center; margin: 70px auto; display: flex; flex-direction: column; align-items: center; gap: 14px; }
.halo { width: 60px; height: 60px; display: grid; place-items: center; border-radius: 18px; color: var(--accent); background: var(--accent-soft); }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 11px; margin-bottom: 14px; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; display: flex; flex-direction: column; gap: 3px; }
.kv { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }
.kv.accent { color: var(--accent); }
.kl { font-size: 12px; color: var(--muted); }
.up { color: var(--ok); } .down { color: var(--danger); margin-left: 6px; }

.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 15px; }
.card.span2 { grid-column: 1 / -1; }
.card h3 { margin: 0 0 10px; font-size: 13px; display: flex; align-items: center; gap: 7px; }
.badge { font-size: 11px; color: var(--danger); background: var(--danger-soft); border-radius: 999px; padding: 1px 7px; }

.sug { display: flex; gap: 10px; align-items: baseline; padding: 8px 0; border-top: 1px solid var(--border); font-size: 13px; }
.sug:first-of-type { border-top: none; }
.sev { font-size: 10px; text-transform: uppercase; font-weight: 700; letter-spacing: .05em; border-radius: 999px; padding: 1px 8px; flex: none;
  color: var(--muted); background: var(--surface-2); }
.sug.high .sev { color: var(--danger); background: var(--danger-soft); }
.sug.medium .sev { color: var(--warn); background: color-mix(in srgb, var(--warn) 16%, transparent); }
.sug.low .sev { color: var(--ok); background: var(--ok-soft); }

.tbl { display: flex; flex-direction: column; }
.tr { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1.2fr; gap: 8px; padding: 8px 4px; border-top: 1px solid var(--border); font-size: 13px; align-items: center; }
.tr.th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; border-top: none; }
.tr .nm { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rt { font-size: 12px; }

.mrow { display: flex; align-items: baseline; gap: 8px; padding: 7px 0; border-top: 1px solid var(--border); font-size: 13px; }
.mrow:first-child { border-top: none; }
.mname { font-weight: 600; }
.mmeta { color: var(--faint); font-size: 12px; }
.mcost { margin-left: auto; color: var(--accent); font-weight: 600; }

.errs { display: flex; flex-direction: column; gap: 6px; }
.erow { display: flex; flex-direction: column; gap: 1px; font-size: 12.5px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; }
.erow span { color: var(--muted); word-break: break-word; }
.muted { color: var(--muted); }

@media (max-width: 760px) {
  .grid2 { grid-template-columns: 1fr; }
  .ins { padding: 16px; }
  /* keep the per-agent columns legible — scroll horizontally instead of crushing */
  .tbl { overflow-x: auto; }
  .tr { grid-template-columns: minmax(120px, 2fr) repeat(4, minmax(52px, 1fr)) minmax(64px, 1.2fr); min-width: 460px; }
}
</style>
