"""NL → AgentSpec compiler — the heart of the platform (provider-agnostic).

The orchestrator compiles the user's request into a validated AgentSpec via the
provider's constrained/structured-output path (Anthropic json_schema or Ollama
`format`), then a static linter checks referential integrity, with a 3-attempt
repair loop that feeds back the full validator output. Terminal behavior: surface
structured errors and never persist an invalid spec.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from veldra_llm import get_provider, prepare_json_schema
from veldra_spec import AgentSpec
from pydantic import ValidationError

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.events import ev, status
from veldra_app.orchestrator.catalog import build_catalog, lint_spec, normalize
from veldra_app.tracing import get_tracer

MAX_REPAIR_ATTEMPTS = 3
COMPILE_MAX_TOKENS = 4096

SYSTEM_TEMPLATE = """\
You are Veldra's orchestrator — an expert agent architect. Given a user's request \
in natural language, design ONE working agent by producing an AgentSpec.

Tools you may grant the agent (use these EXACT logical names — do not invent others):
{tool_lines}

Knowledge base available in this workspace:
- id: "{kb_id}" (name: {kb_name}) — the user's uploaded documents.

Existing agents you may delegate to (build a team via `sub_agents`):
{agent_lines}

Design rules:
- Write a clear, production-quality `system_prompt` (the agent's policy/persona/\
instructions): what it does, its tone, how it uses tools, and how it cites sources.
- Grant a tool by adding {{"name": "<exact catalog name>", "permission_mode": "auto"}} to \
`tools` — copy the name VERBATIM from the list above (e.g. "kb.search", "math.eval"). If \
answering depends on the user's uploaded documents, grant "kb.search" and put "{kb_id}" \
in `knowledge_bases`. If the task needs no tools/documents, leave `tools` empty.
- Never invent a tool name that is not in the catalog above.
- Set `model` to "{default_model}". Set `effort` to "high" unless the task is simple.
- `thinking_method`: "react" for tool-using agents, "plan_execute" for multi-step \
planning agents.
- To build a coordinator that delegates to a TEAM, list existing agent names (only \
from the list above) in `sub_agents`; the coordinator can then call each as a tool. \
Leave `sub_agents` empty for a standalone agent.
- For a deterministic multi-step PIPELINE/WORKFLOW (e.g. "search the docs, then \
summarize, then ..."), set `workflow_graph`: `nodes` with types start / kb_search / \
llm / condition / end, and `edges` connecting them start→…→end (each edge {{source, \
target}}; condition edges add when:"true"/"false"). In templates use {{input}} for the \
user's message and {{context}} for kb_search output. Otherwise leave `workflow_graph` \
null and rely on tools.
- Set sensible `guardrails` (max_steps between 1 and 64). Keep `name` short and descriptive.

Return only the AgentSpec."""


def _system_prompt(catalog: dict) -> str:
    tool_lines = "\n".join(f'- {t["name"]}: {t["description"]}' for t in catalog["tools"])
    agents = catalog.get("agents", [])
    agent_lines = "\n".join(f"- {a}" for a in agents) if agents else "- (none yet)"
    return SYSTEM_TEMPLATE.format(
        tool_lines=tool_lines,
        kb_id=catalog["kb_id"],
        kb_name=catalog["kb_name"],
        agent_lines=agent_lines,
        default_model=get_provider().default_model,
    )


WORKFLOW_KEYWORDS = ("workflow", "pipeline", "multi-step", "multistep", "step by step",
                     "step-by-step", "first ", "then ", "stage")


def wants_workflow(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in WORKFLOW_KEYWORDS)


async def parse_spec(
    system: str, messages: list[dict], include_workflow: bool = False, include_team: bool = False
) -> tuple[AgentSpec | None, bool]:
    """Constrained-decode an AgentSpec via the active provider. Returns (spec, refused).

    workflow_graph and sub_agents are dropped from the generation schema unless they
    apply — they enlarge the schema and small local models then mis-fill them (inventing
    sub-agents / broken graphs) even for trivial agents. Storage uses the full AgentSpec.
    """
    provider = get_provider()
    raw = AgentSpec.model_json_schema()
    props = raw.get("properties", {})
    if not include_workflow:
        props.pop("workflow_graph", None)
    if not include_team:
        props.pop("sub_agents", None)
    schema = prepare_json_schema(raw)
    data = await provider.parse_json(
        model=provider.orchestrator_model, system=system, messages=messages,
        schema=schema, max_tokens=COMPILE_MAX_TOKENS,
    )
    if data is None:
        return None, False
    try:
        return AgentSpec.model_validate(data), False
    except ValidationError:
        return None, False


async def compile_with_repair(
    system: str, seed_messages: list[dict], catalog: dict,
    include_workflow: bool = False, include_team: bool = False
) -> tuple[AgentSpec | None, list[str]]:
    messages = list(seed_messages)
    last_errors: list[str] = ["the model did not return a usable spec"]
    for _ in range(MAX_REPAIR_ATTEMPTS):
        spec, refused = await parse_spec(system, messages, include_workflow, include_team)
        if refused:
            return None, ["the request was declined by the model's safety system"]
        if spec is None:
            messages.append(
                {"role": "user", "content": "Return a valid AgentSpec for the request."}
            )
            continue
        errors = lint_spec(spec, catalog)
        if not errors:
            final = normalize(spec, catalog)
            # Reflect the model that will actually serve this agent (Ollama forces
            # its single local model; Anthropic keeps the orchestrator's choice).
            final = final.model_copy(update={"model": get_provider().resolve(final.model)})
            return final, []
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
            system, [{"role": "user", "content": nl_request}], catalog,
            include_workflow=wants_workflow(nl_request),
            include_team=bool(catalog.get("agents")),
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
