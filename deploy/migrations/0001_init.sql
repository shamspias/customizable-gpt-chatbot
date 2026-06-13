-- Veldra initial schema.
-- {{EMBED_DIM}} is substituted by the migration runner (veldra_app.db) with the
-- configured embedding dimension (default 1536 = text-embedding-3-small).
--
-- Multi-tenancy: every tenant-scoped table carries tenant_id and a row-level
-- security policy is DEFINED below but RLS is NOT ENABLED in the MVP (single
-- tenant). Enabling RLS + setting the `veldra.tenant_id` GUC per request is a v1 task.

CREATE EXTENSION IF NOT EXISTS vector;

-- ───────────────────────── tenancy ─────────────────────────
CREATE TABLE tenants (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text UNIQUE NOT NULL,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Deterministic default tenant for the single-tenant MVP.
INSERT INTO tenants (id, slug, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'default', 'Default')
ON CONFLICT (slug) DO NOTHING;

-- ───────────────────────── agents (versioned spec) ─────────────────────────
-- An agent is DATA: a stable agent row + an append-only stack of immutable spec
-- versions. Rollback = repoint current_version. Self-mod = insert a new version.
CREATE TABLE agents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id),
    name            text NOT NULL,
    current_version int  NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX agents_tenant_name_idx ON agents (tenant_id, name);

CREATE TABLE agent_specs (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version     int  NOT NULL,
    spec        jsonb NOT NULL,
    note        text,                       -- e.g. the self-mod request that produced it
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (agent_id, version)
);

-- ───────────────────────── knowledge bases ─────────────────────────
CREATE TABLE knowledge_bases (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenants(id),
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id         uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    tenant_id     uuid NOT NULL REFERENCES tenants(id),
    filename      text NOT NULL,
    content_type  text,
    s3_key        text NOT NULL,
    num_pages     int,
    status        text NOT NULL DEFAULT 'pending',  -- pending|ingesting|ready|failed
    error         text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Document structure tree (pages/sections). Powers section titles in citations
-- and parent-document expansion later. Self-referential via parent_id.
CREATE TABLE page_index (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id     uuid REFERENCES page_index(id) ON DELETE CASCADE,
    kind          text NOT NULL,            -- 'page' | 'section'
    label         text,                     -- section title / "Page N"
    page_number   int,
    section_path  text,                     -- e.g. "2 › Pricing › Tiers"
    char_start    int,
    char_end      int
);
CREATE INDEX page_index_doc_idx ON page_index (document_id);

-- Retrievable chunks with citation metadata + dual representation (vector + lexical).
CREATE TABLE chunks (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    kb_id         uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    tenant_id     uuid NOT NULL REFERENCES tenants(id),
    ordinal       int  NOT NULL,
    content       text NOT NULL,
    page_number   int,
    section_path  text,
    char_start    int,
    char_end      int,
    token_count   int,
    embedding     vector({{EMBED_DIM}}),
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX chunks_kb_idx  ON chunks (kb_id);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX chunks_vec_idx ON chunks USING hnsw (embedding vector_cosine_ops);

-- ───────────────────────── runs + event log (checkpoints) ─────────────────────────
CREATE TABLE runs (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenants(id),
    agent_id         uuid REFERENCES agents(id),
    agent_version    int,
    kind             text NOT NULL,         -- 'build' | 'ask' | 'selfmod'
    status           text NOT NULL DEFAULT 'running',  -- running|done|error|needs_input
    idempotency_key  text,
    input            jsonb,
    result           jsonb,
    error            text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    finished_at      timestamptz
);
CREATE UNIQUE INDEX runs_idem_idx ON runs (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Every node transition / token / tool call is an append-only step = the
-- checkpoint/resume/replay/audit substrate. Conversation blobs (with thinking +
-- compaction content) are stored here as opaque, Python-owned JSON.
CREATE TABLE run_steps (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    ordinal     int  NOT NULL,
    type        text NOT NULL,             -- node|llm_turn|tool_call|tool_result|message|error
    name        text,
    payload     jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX run_steps_run_idx ON run_steps (run_id, ordinal);

CREATE TABLE audit (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenants(id),
    actor        text NOT NULL,            -- 'user' | 'orchestrator'
    action       text NOT NULL,
    target_type  text,
    target_id    text,
    detail       jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_tenant_idx ON audit (tenant_id, created_at);

-- ───────────────────────── RLS policies (DEFINED, not enabled — v1) ─────────────────────────
-- Each becomes active once `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` is added
-- (v1) and the app does `SET LOCAL veldra.tenant_id = '<uuid>'` per request.
CREATE POLICY tenant_isolation ON agents
    USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON knowledge_bases
    USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON chunks
    USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON runs
    USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON audit
    USING (tenant_id = current_setting('veldra.tenant_id', true)::uuid);
