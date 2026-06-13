# Loom — talk an agent into existence

**Loom is a self-hostable agent-harness platform.** You install it, open a chat, and
describe what you want in plain language. An orchestrator AI (Claude) compiles your
request into a *working agent* — writing its policy, selecting its tools, attaching a
RAG knowledge base, and choosing a reasoning ("thinking") method. You reshape any
agent later just by talking to the same AI; it proposes a reviewable diff you approve.

> The one load-bearing idea: **an agent is _data_, not code** — a versioned `AgentSpec`
> row in Postgres. The runtime is a pure interpreter of that spec. "Build me an agent"
> means *compile natural language → validated `AgentSpec`*. "Change everything" means
> *emit a JSON-Patch against the spec that you approve*.

This repository is the **MVP vertical slice**: a single Python process proving the full
loop — `your words → agent spec → runtime → RAG → cited, streamed answer` — plus a Vue 3
web client and a `loom` CLI. Go services, the execution sandbox, multi-agent teams, and
the visual workflow canvas are part of the architecture but deliberately deferred to
later phases (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

## Architecture at a glance

```
apps/web        Vue 3 + Vite + Pinia + TS  (chat, upload, spec viewer, citations, diff modal)
services/app    ONE FastAPI process: edge (REST+SSE) · orchestrator · runtime · rag
packages/       spec-schema · llm-providers · mcp-client · mcp-servers/kb_search · thinking-methods
cli/            thin Python (Typer) client: loom kb add | build | ask
deploy/         docker-compose (postgres+pgvector, redis, minio) + SQL migrations
evals/          NL→spec golden set + accuracy runner
```

Everything talks to Postgres (system of record + `pgvector` + `tsvector`), Redis, and
an S3-compatible object store (MinIO). RAG is exposed to agents as an MCP tool
(`kb.search`), so retrieval composes with everything else.

## Quick start

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 20+,
[go-task](https://taskfile.dev) (`task`), and a running [Ollama](https://ollama.com).
**No cloud API key is required** — Loom defaults to your local Ollama.

```bash
ollama pull qwen3:0.6b         # your chat model (set LOOM_OLLAMA_MODEL to match)
ollama pull nomic-embed-text   # embeddings (768-dim)
cp example.env .env            # already set to LOOM_LLM_PROVIDER=ollama
task up                        # start postgres+pgvector, redis, minio
task migrate                   # apply SQL migrations
task dev                       # FastAPI on :8000, Vue on :5173
```

> **Tiny-model caveat:** a 0.6–0.8B model emits schema-valid output via
> constrained decoding, but the *quality* of generated agents and tool calls will
> be weak. For a genuinely capable orchestrator, point `LOOM_OLLAMA_MODEL` at a
> larger local model (`qwen2.5:7b`, `llama3.1:8b`) — or set
> `LOOM_LLM_PROVIDER=anthropic` with an `ANTHROPIC_API_KEY`.

Open http://localhost:5173, upload a couple of PDFs, and type:
*"Build an agent that answers questions from these docs and always cites the page."*
Watch the orchestrator stream its plan, render the generated `AgentSpec`, then ask a
question and get a streamed answer with clickable page/section citations.

CLI parity:

```bash
loom kb add ./whitepaper.pdf
loom build "answer from my docs with citations"
loom ask "what does section 3 say about pricing?"
```

## Models

The LLM layer is **provider-pluggable** via `LOOM_LLM_PROVIDER`:

- **`ollama`** (default) — fully local; one model serves every role. Set
  `LOOM_OLLAMA_MODEL` to your tag. Structured output uses Ollama's `format`
  (JSON-schema) and tool use goes through Ollama function calls.
- **`anthropic`** — Claude with adaptive thinking + `effort`: orchestrator
  `claude-opus-4-8`, worker agents `claude-sonnet-4-6`, cheap `claude-haiku-4-5`.

Embeddings are independently pluggable (`LOOM_EMBED_PROVIDER`): local Ollama
`nomic-embed-text` (768-dim) by default, or OpenAI `text-embedding-3-small`
(1536-dim) with a key. The dimension is fixed at first migration.

## Status

MVP. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design, the
Python/Go boundary, the security model, and the phased roadmap (v1 sandbox + Go gateway,
v2 workflow DAG engine + teams, v3 durable spine).

## License

TBD.
