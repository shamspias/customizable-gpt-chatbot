# Loom — talk an agent into existence

**Loom is a self-hostable, local-first agent-harness platform.** Install it, open
the web app, and describe what you want in plain language. An orchestrator AI
compiles your request into a *working agent* — writing its policy, selecting its
tools, attaching a RAG knowledge base, choosing a reasoning method, and even wiring
a **team** of agents. Reshape anything later just by talking to it; the orchestrator
proposes a reviewable diff you approve.

> **The one load-bearing idea:** an agent is *data*, not code — a versioned
> `AgentSpec` row in Postgres. "Build me an agent" = compile natural language →
> validated `AgentSpec`. "Change it" = a JSON-Patch you approve. The runtime is a
> pure interpreter of that spec.

## ✅ Status — verified running locally

This MVP has been run end-to-end against a **local Ollama** (`qwen3.5:0.8b`), no
cloud key required. Verified working: upload → embed → retrieve with citations;
NL → `AgentSpec`; the streaming agent loop with tool-calling; the tool suite
(`math.eval`, `fs.write`, …); config-only self-modification with versioning; and
**agent teams** (a coordinator delegating to a sub-agent). Small local models
produce valid structure but rambly prose — see [Models](#models) for picking a
better one.

## 🖥️ Where's the front-end?

It's the Vue 3 app in **`apps/web/`**. Run it and open **http://localhost:5173**:

```bash
cd apps/web && npm install && npm run dev
```

It's a chat-to-build UI: upload documents, describe the agent you want (left), watch
the orchestrator stream its plan and render the generated **spec** — policy, tools,
knowledge bases, team, and the workflow — on the right; then chat with the agent
(streamed answers + clickable citations), and refine it with a diff-approval modal.
The dev server proxies `/api` to the backend on `:8000`, so it's same-origin (no CORS).

## Quick start

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 20+, and a running
[Ollama](https://ollama.com). **No cloud API key needed.**

```bash
# 1. models (set LOOM_OLLAMA_MODEL to a tag you actually have — see `ollama list`)
ollama pull qwen3.5:0.8b          # chat/agent model (tools + thinking)
ollama pull nomic-embed-text      # embeddings (768-dim)

# 2. backend
cp example.env .env               # defaults: provider=ollama, db on :5433
uv sync                           # installs the Python workspace
docker compose -f deploy/docker-compose.yml up -d   # postgres+pgvector, redis, minio
uv run python -m loom_app.db migrate
uv run uvicorn loom_app.main:app --port 8000

# 3. front-end (separate terminal)
cd apps/web && npm install && npm run dev   # http://localhost:5173
```

> The Postgres container maps host port **5433** (to avoid clashing with a local
> Postgres on 5432). `DATABASE_URL` in `example.env` already points there.

Then, in the web app: upload a doc or two → *"Answer questions from these docs and
always cite the page"* → ask away. Or via the CLI:

```bash
uv run loom kb add ./whitepaper.pdf
uv run loom build "answer from my docs with citations"
uv run loom ask "what does section 3 say about pricing?"
```

## What you can build

- **Single agents** — a policy + model + thinking method, optionally with tools and a KB.
- **Tool-using agents** — first-party tools the orchestrator can grant:
  `kb.search` (RAG over your docs), `time.now`, `math.eval`, `http.fetch`, and
  workspace files `fs.read` / `fs.write` / `fs.list` (so agents can *create* artifacts).
  All bounded and local-first; untrusted code execution is gated behind the v1 sandbox.
- **Agent teams** — give an agent `sub_agents` (names of other agents) and it gets a
  `team__<name>` tool for each; the coordinator delegates subtasks and they run as
  nested agents (depth-capped).
- **Knowledge bases** — upload PDF/markdown/text; structure-aware page-indexed chunks
  with `page`/`section`/`char-span` citations; hybrid pgvector + `tsvector` retrieval (RRF).
- **Self-modification** — "make answers more concise", "give it the http.fetch tool":
  the orchestrator emits a JSON-Patch you approve; every change is a new immutable
  version (rollback = repin). Granting new tools is gated as "sensitive".

## Models / providers

The LLM layer is **provider-pluggable** via `LOOM_LLM_PROVIDER`:

| Provider | `LOOM_LLM_PROVIDER` | Notes |
|---|---|---|
| **Ollama** (default) | `ollama` | Fully local, no key. `LOOM_OLLAMA_MODEL` (+ optional `LOOM_OLLAMA_ORCHESTRATOR_MODEL` for a stronger compile model). Uses Ollama `format` for structured output + function-calling. |
| **OpenAI-compatible** | `openai` | OpenAI, Groq, OpenRouter, vLLM, LM Studio — set `LOOM_OPENAI_BASE_URL`, `OPENAI_API_KEY`, `LOOM_OPENAI_MODEL`. |
| **Anthropic** | `anthropic` | Claude with adaptive thinking + `effort`: orchestrator `claude-opus-4-8`, agents `claude-sonnet-4-6`. Needs `ANTHROPIC_API_KEY`. |

Embeddings are independently pluggable (`LOOM_EMBED_PROVIDER`): local Ollama
`nomic-embed-text` (768-dim) by default, or OpenAI `text-embedding-3-small` (1536).
The dimension is fixed at first migration.

> **Tiny-model caveat:** a sub-1B model (like `qwen3.5:0.8b`) emits schema-valid
> output via constrained decoding and *can* call tools, but it designs weak specs
> (often grants no tools from a vague request) and writes rambly answers. For a
> genuinely capable orchestrator, point `LOOM_OLLAMA_ORCHESTRATOR_MODEL` at a bigger
> local model (`qwen3:1.7b`, `gemma3`, `gpt-oss:120b-cloud`) or use the `openai` /
> `anthropic` providers.

## Repository layout

```
apps/web/        Vue 3 + Vite + Pinia + TS — the chat-to-build front-end
services/app/    one FastAPI process: edge (REST+SSE) · orchestrator · runtime · rag
packages/        spec-schema · llm-providers · mcp-client · mcp-servers · thinking-methods
cli/             thin Typer client (loom kb add | build | ask | agents | selfmod)
deploy/          docker-compose (postgres+pgvector, redis, minio) + SQL migrations
evals/           NL→spec golden accuracy suite
docs/            ARCHITECTURE.md — full design + phased roadmap
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design, the provider
interface, the Python/Go boundary, and the roadmap (v1 execution sandbox + Go
gateway, v2 visual workflow DAG engine + richer multi-agent, v3 durable spine).

## Status & history

MVP. The previous Django GPT-3.5 chatbot is preserved on `origin/main` and the
`archive/v1-django` tag.
