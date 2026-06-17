# Veldra — Architecture

Veldra is a self-hostable **agent-harness platform**: install it, talk to an
orchestrator AI in natural language, and it designs working agents — writing each
agent's policy, selecting its tools, attaching a RAG knowledge base, and choosing
a reasoning method. You reshape any agent by talking to the same AI, which emits a
reviewable diff you approve.

## Core invariants

1. **An agent is _data_, not code** — a versioned `AgentSpec` row in Postgres
   (`packages/spec-schema`). The runtime is a pure interpreter of that spec.
2. **Python is the brain; Go is the nervous system; Go never calls an LLM.** Go is
   a *target*, introduced only when a measured need appears (see roadmap). The MVP
   is a single Python process.
3. **The declarative-spec safety model covers _configuration_ only.** It protects
   spec edits (prompt, model, retrieval). Executing untrusted tools/code is a
   *separate* problem solved by the v1 sandbox — a hard gate for any non-`kb.search`
   tool. "It's all JSON" does **not** make code execution safe.
4. **RAG is just a tool** (`kb.search`), so retrieval composes with everything.
5. **Forward-compatible, not pre-built.** The schema tolerates additive fields;
   we don't build validators/UI for node/agent types no phase executes yet.
6. **Multi-user, single workspace.** Every request resolves a `Context`
   (tenant + user + role: admin/member/viewer) via one dependency; there is no global
   tenant. Tools come from built-ins + installable **MCP connectors** registered per
   workspace, behind the same `Tool` contract — so the AgentSpec never changes when a
   tool moves out-of-process.

## MVP shape (what's in this repo)

One FastAPI process collapses edge + auth + orchestrator + runtime + rag:

```
apps/web (Vue 3)  ──HTTP/SSE──▶  services/app (FastAPI)
                                   ├─ edge/         REST + SSE; per-request Context (auth)
                                   ├─ auth/         users · roles · sessions · install wizard
                                   ├─ orchestrator/ NL→AgentSpec · route · linter · repair · self-mod
                                   ├─ runtime/      stream + decision loops · tool dispatch · permissions
                                   ├─ plugins/      installable MCP connectors → per-tenant tools
                                   └─ rag/          ingest · page-index · hybrid+RRF · cite
packages/  spec-schema · llm-providers · mcp-client (stdio/HTTP/SSE) · mcp-servers · thinking-methods
cli/       thin Typer client over the same endpoints
deploy/    docker-compose (postgres+pgvector, redis, minio) + Alembic migrations
evals/     NL→spec golden set + decision-loop reliability suite
```

Datastores: **Postgres** (system of record + `pgvector` HNSW + `tsvector`), **Redis**
(wired; pub/sub fan-out inactive until a 2nd process exists), **MinIO/S3** (source docs).

### Key mechanisms

- **Compiler** — `client.messages.parse(output_format=AgentSpec)` → validated
  Pydantic object → static linter (every tool/KB ref resolves) → 3-attempt repair
  feeding back full validator output → terminal = clarify, never persist invalid.
- **Runtime** — manual loop over `messages.stream` (not `tool_runner`) for per-token
  streaming + permission gates. Adaptive thinking (`display:"summarized"`) + effort
  from the spec. Handles `end_turn`/`tool_use`/`pause_turn`/`refusal`; appends the
  full `response.content` each turn (preserves thinking blocks).
- **RAG page-index** — structure-aware chunks carry `page_number/section_path/char_span`
  (the citation metadata is the differentiator). Hybrid pgvector + `tsvector` with RRF.
- **Self-mod** — orchestrator emits a complete revised spec; we diff it to a JSON-Patch
  for human approval. Capability gating blocks adding non-`kb.search` tools (needs the
  v1 sandbox). Every applied change is a new immutable version (rollback = repin).
- **Thinking methods** — pluggable factories keyed by `thinking_method`
  (`packages/thinking-methods`). MVP: `react`, `plan_execute`.

## Models

The LLM layer is **provider-pluggable** via `VELDRA_LLM_PROVIDER`. The runtime and
orchestrator depend only on a normalized provider interface (`stream_turn` +
`parse_json`), so the same agent loop runs on either backend:

- **`ollama`** (default) — fully local, no API key. One model serves every role.
  Structured output uses Ollama's `format` (JSON-schema → grammar); tool use goes
  through Ollama function calls. Schemas are dereferenced + constraint-stripped
  (`prepare_json_schema`) so small models can satisfy the grammar.
- **`openai`** — OpenAI-compatible `/v1/chat/completions` (OpenAI, Groq, OpenRouter,
  vLLM, LM Studio): tools + `response_format` json_schema, streamed tool-call deltas.
- **`anthropic`** — orchestrator `claude-opus-4-8`, workers `claude-sonnet-4-6`,
  cheap `claude-haiku-4-5`, with adaptive thinking + `effort`. The Anthropic path
  preserves thinking blocks via the opaque `raw` payload on each assistant turn.

Each provider exposes `default_model` (agent runs) and `orchestrator_model`
(NL→spec compile); a Claude-named spec default never leaks to a local backend.

## Tools & teams

Tools are registered in an MCP-shaped registry (`packages/mcp-client`): `kb.search`
(RAG), plus bounded builtins — `time.now`, `math.eval`, `http.fetch`, and
workspace-scoped `fs.read`/`fs.write`/`fs.list` (per-tenant dir, path-sandboxed; no
shell/code exec until the v1 sandbox). Agent **teams** are agents-as-tools: a spec's
`sub_agents` (names of other agents) become `team__<name>` delegate tools the
runtime resolves to nested, depth-capped agent runs.

Embeddings are independently pluggable (`VELDRA_EMBED_PROVIDER`): local Ollama
`nomic-embed-text` (768-dim) by default, or OpenAI `text-embedding-3-small`
(1536-dim). Dimension is fixed at first migration.

## Roadmap

- **MVP (this repo)** — one Python process: NL→agent→RAG→cited answer + one
  config-only self-mod, with a golden NL→spec eval bar and OTel tracing.
- **v1** — Go **sandbox** (gVisor) gated on its own breakout/egress/resource-cap
  suite, before any untrusted tool ships; multi-tenancy enforcement (RLS); self-mod
  dry-run replay smoke test; Go gateway *if* measured fan-out/CPU need (then
  Pydantic→Go/TS codegen + CI contract tests become mandatory); Vue Flow canvas;
  RAG rerank + parent-expansion; Reflexion.
- **v2** — Go workflow DAG engine (durable, resumes at node boundaries — Python owns
  the opaque conversation blob) over NATS; multi-agent teams + handoffs; ToT/Debate;
  Firecracker; visual graph editing; Qdrant option.
- **v3 (conditional)** — Temporal durable spine; k8s/Helm.

See the top-level `README.md` for the product tour and the commit history for the
rationale and adversarial critiques that shaped this scope.
