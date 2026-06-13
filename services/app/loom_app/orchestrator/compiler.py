"""NL → AgentSpec compiler — the heart of the platform (provider-agnostic).

The orchestrator compiles the user's request into a validated AgentSpec via the
provider's constrained/structured-output path (Anthropic json_schema or Ollama
`format`), then a static linter checks referential integrity, with a 3-attempt
repair loop that feeds back the full validator output. Terminal behavior: surface
structured errors and never persist an invalid spec.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from loom_llm import ORCHESTRATOR_MODEL, get_provider, prepare_json_schema
from loom_spec import AgentSpec
from pydantic import ValidationError

from loom_app import repo
from loom_app.db import get_sessionmaker
from loom_app.events import ev, status
from loom_app.orchestrator.catalog import build_catalog, lint_spec, normalize
from loom_app.tracing import get_tracer

MAX_REPAIR_ATTEMPTS = 3
COMPILE_MAX_TOKENS = 4096

SYSTEM_TEMPLATE = """\
You are Loom's orchestrator — an expert agent architect. Given a user's request \
in natural language, design ONE working agent by producing an AgentSpec.

Tools you may grant the agent (use these EXACT logical names — do not invent others):
{tool_lines}

Knowledge base available in this workspace:
- id: "{kb_id}" (name: {kb_name}) — the user's uploaded documents.

Design rules:
- Write a clear, production-quality `system_prompt` (the agent's policy/persona/\
instructions): what it does, its tone, how it uses tools, and how it cites sources.
- If answering the request depends on the user's uploaded documents, grant the \
`kb.search` tool (mcp_server="kb", tool_name="search", permission_mode="auto") and \
put "{kb_id}" in `knowledge_bases`. If the task needs no documents, grant no tools.
- Never reference a tool or knowledge base that is not listed above.
- Set `model` to "{default_model}". Set `effort` to "high" unless the task is simple.
- `thinking_method`: "react" for tool-using agents, "plan_execute" for multi-step \
planning agents.
- Set sensible `guardrails` (max_steps between 1 and 64). Keep `name` short and \
descriptive. Leave `sub_agents` empty and `workflow_graph_ref` null (not supported yet).

Return only the AgentSpec."""


def _system_prompt(catalog: dict) -> str:
    tool_lines = "\n".join(f'- {t["name"]}: {t["description"]}' for t in catalog["tools"])
    return SYSTEM_TEMPLATE.format(
        tool_lines=tool_lines,
        kb_id=catalog["kb_id"],
        kb_name=catalog["kb_name"],
        default_model=get_provider().default_model,
    )


async def parse_spec(system: str, messages: list[dict]) -> tuple[AgentSpec | None, bool]:
    """Constrained-decode an AgentSpec via the active provider. Returns (spec, refused)."""
    provider = get_provider()
    schema = prepare_json_schema(AgentSpec.model_json_schema())
    data = await provider.parse_json(
        model=ORCHESTRATOR_MODEL, system=system, messages=messages,
        schema=schema, max_tokens=COMPILE_MAX_TOKENS,
    )
    if data is None:
        return None, False
    try:
        return AgentSpec.model_validate(data), False
    except ValidationError:
        return None, False


async def compile_with_repair(
    system: str, seed_messages: list[dict], catalog: dict
) -> tuple[AgentSpec | None, list[str]]:
    messages = list(seed_messages)
    last_errors: list[str] = ["the model did not return a usable spec"]
    for _ in range(MAX_REPAIR_ATTEMPTS):
        spec, refused = await parse_spec(system, messages)
        if refused:
            return None, ["the request was declined by the model's safety system"]
        if spec is None:
            messages.append(
                {"role": "user", "content": "Return a valid AgentSpec for the request."}
            )
            continue
        errors = lint_spec(spec, catalog)
        if not errors:
            return normalize(spec, catalog), []
        last_errors = errors
        messages.append(
            {
                "role": "user",
                "content": "Your previous AgentSpec had these problems:\n"
                + "\n".join(f"- {e}" for e in errors)
                + "\nReturn a corrected AgentSpec.",
            }
        )
    return None, last_errors


async def build_agent(nl_request: str, tenant_id: str, run_id: str) -> AsyncIterator[dict]:
    """Compile NL → AgentSpec, persist it as an immutable version, stream events."""
    tracer = get_tracer()
    with tracer.start_as_current_span("orchestrator.build"):
        yield status("planning")
        catalog = await build_catalog(tenant_id)
        system = _system_prompt(catalog)

        yield status("designing")
        spec, errors = await compile_with_repair(
            system, [{"role": "user", "content": nl_request}], catalog
        )
        if spec is None:
            yield ev(
                "error",
                message="I couldn't design a valid agent for that. "
                + "; ".join(errors)
                + ". Could you clarify what the agent should do?",
            )
            return

        sm = get_sessionmaker()
        async with sm() as session:
            agent_id, version = await repo.upsert_agent_spec(
                session, tenant_id, spec.name, spec.model_dump(), note=f"build: {nl_request[:200]}"
            )
            await repo.insert_audit(
                session, tenant_id, "orchestrator", "build_agent", "agent", agent_id,
                {"request": nl_request},
            )
            await session.commit()

        yield ev("spec", agent_id=agent_id, version=version, spec=spec.model_dump())
        yield ev("done", agent_id=agent_id, version=version)
