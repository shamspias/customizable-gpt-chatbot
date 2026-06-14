"""NL → AgentSpec compiler — the heart of the platform (provider-agnostic).

The orchestrator compiles the user's request into a validated AgentSpec via the
provider's constrained/structured-output path (Anthropic json_schema or Ollama
`format`), then a static linter checks referential integrity, with a 3-attempt
repair loop that feeds back the full validator output. Terminal behavior: surface
structured errors and never persist an invalid spec.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic import ValidationError
from veldra_llm import get_provider, prepare_json_schema
from veldra_spec import AgentSpec

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.events import ev, status
from veldra_app.orchestrator.catalog import build_catalog, lint_spec, normalize
from veldra_app.tracing import get_tracer

MAX_REPAIR_ATTEMPTS = 3
COMPILE_MAX_TOKENS = 4096

SYSTEM_TEMPLATE = """\
You are Veldra's orchestrator — an expert agent architect. The user describes, in \
plain language, a real business need (e.g. "an agro farm needs a sales agent and an \
info agent", "a B2B SaaS support assistant that triages tickets"). UNDERSTAND THE \
DOMAIN and design what a competent operator in that domain would actually want: a \
sharp policy, the right tools, a knowledge base when answers depend on the user's \
documents, a TEAM when distinct roles are implied, and a deterministic WORKFLOW when \
the task is a routing/decision process. Produce ONE AgentSpec.

Tools you may grant the agent (use these EXACT logical names — do not invent others):
{tool_lines}

Knowledge base available in this workspace:
- id: "{kb_id}" (name: {kb_name}) — the user's uploaded documents.

Existing agents you may delegate to (build a team via `sub_agents`):
{agent_lines}

Agent design:
- `system_prompt`: a production-quality policy/persona — what the agent does, its \
tone, domain-specific rules, how it uses its tools, and how it cites sources.
- Grant a tool with {{"name": "<exact catalog name>", "permission_mode": "auto"}} — copy \
the name VERBATIM (e.g. "kb.search", "math.eval"). If answering depends on the user's \
uploaded documents, grant "kb.search" and put "{kb_id}" in `knowledge_bases`. Never \
invent a tool name. Leave `tools` empty if none are needed.
- `model` = "{default_model}"; `effort` = "high" unless trivial; `thinking_method` = \
"react" for tool-using agents, "plan_execute" for multi-step planners.
- TEAM: to coordinate DISTINCT ROLES, list existing agent names (only from the list \
above) in `sub_agents`; the coordinator calls each as a tool. Empty for a standalone agent.
- `guardrails.max_steps` 1..64. Keep `name` short and descriptive.
{workflow_guide}
Return only the AgentSpec."""

# Appended only when a workflow is wanted — keeps simple builds lean and avoids
# small models over-filling a graph they don't need.
WORKFLOW_GUIDE = """
WORKFLOW — set `workflow_graph` when the task is a deterministic routing/decision \
process. Each node has a unique `id`, a `type`, and `config`; `edges` connect \
{source,target} and branch edges add `when`. Variables flow via {var} templates \
({input} = the user's message; each node writes its `config.output_var`). Node types:
- start / end — entry / exit (end returns config.output_var, default "output").
- llm — config.prompt (template); writes config.output_var.
- kb_search — config.query (default "{input}"), config.k; writes "context".
- if_else — branch on config.var with config.op (eq/ne/gt/lt/gte/lte/contains/
  not_contains/regex/empty) vs config.value; edges use when:"true"/"false".
- classifier — config.classes (list) + config.prompt; routes to the edge whose
  `when` equals the chosen class.
- tool — config.tool (catalog name) + config.inputs [{name,value}]; writes output_var.
- code — config.code: a SAFE expression over variables (e.g. "len(input)",
  "price*qty", "input.lower()"); writes output_var.
- template — config.template text over {vars}. aggregator — merges config.inputs.
"""

WORKFLOW_EXAMPLE = """
Example — "agro farm: route buyers to sales, questions to an info desk":
{
 "nodes": [
  {"id":"start","type":"start"},
  {"id":"route","type":"classifier","config":{"var":"input","prompt":"Is this a buying inquiry or a general question?","classes":["sales","info"]}},
  {"id":"sales","type":"llm","config":{"prompt":"You are a sales rep for an agro farm. Respond to: {input}","output_var":"output"}},
  {"id":"lookup","type":"kb_search","config":{"query":"{input}","output_var":"context"}},
  {"id":"answer","type":"llm","config":{"prompt":"Answer using these notes:\\n{context}\\n\\nQuestion: {input}","output_var":"output"}},
  {"id":"end","type":"end","config":{"output_var":"output"}}
 ],
 "edges": [
  {"source":"start","target":"route"},
  {"source":"route","target":"sales","when":"sales"},
  {"source":"route","target":"lookup","when":"info"},
  {"source":"sales","target":"end"},
  {"source":"lookup","target":"answer"},
  {"source":"answer","target":"end"}
 ],
 "entrypoint": "start"
}
"""


def _system_prompt(catalog: dict, include_workflow: bool = False) -> str:
    tool_lines = "\n".join(f'- {t["name"]}: {t["description"]}' for t in catalog["tools"])
    agents = catalog.get("agents", [])
    agent_lines = "\n".join(f"- {a}" for a in agents) if agents else "- (none yet)"
    guide = (WORKFLOW_GUIDE + WORKFLOW_EXAMPLE) if include_workflow else ""
    return SYSTEM_TEMPLATE.format(
        tool_lines=tool_lines,
        kb_id=catalog["kb_id"],
        kb_name=catalog["kb_name"],
        agent_lines=agent_lines,
        default_model=get_provider().default_model,
        workflow_guide=guide,
    )


# Intent signals that a deterministic routing/decision workflow is wanted — not just
# the literal word "workflow" but the shape of a business process.
WORKFLOW_KEYWORDS = (
    "workflow", "pipeline", "multi-step", "multistep", "step by step", "step-by-step",
    "first ", "then ", "stage", "route", "routing", "triage", "classify", "categorize",
    "if ", "when ", "based on", "depending on", "escalate", "branch", "decision",
    "qualify", "otherwise", "flow",
)


def wants_workflow(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in WORKFLOW_KEYWORDS)


def wants_team(text: str) -> bool:
    """A team is implied by the word 'team', a plural 'agents', or ≥2 distinct roles."""
    t = text.lower()
    return "team" in t or "agents" in t or t.count(" agent") >= 2


# Plan for a team: a coordinator + role members (each becomes its own agent).
TEAM_PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["coordinator", "members"],
    "properties": {
        "coordinator": {
            "type": "object", "additionalProperties": False, "required": ["name", "purpose"],
            "properties": {"name": {"type": "string"}, "purpose": {"type": "string"}},
        },
        "members": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["name", "purpose"],
                "properties": {"name": {"type": "string"}, "purpose": {"type": "string"}},
            },
        },
    },
}

TEAM_PLAN_SYSTEM = """\
You are a team architect. Given a business need, design a SMALL team: one coordinator \
plus 2-4 specialist member agents, each with a short distinct role. Return a plan with \
the coordinator (name + purpose) and the members (name + one-line purpose each). Use \
short PascalCase names (e.g. SalesAgent, InfoDeskAgent)."""

MAX_TEAM_MEMBERS = 4


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


async def _compile_and_save(
    seed: str, catalog: dict, tenant_id: str, note: str,
    *, name: str | None = None, include_workflow: bool = False, include_team: bool = False,
    sub_agents: list[str] | None = None,
) -> tuple[str, int, AgentSpec] | None:
    """Compile one agent from a seed request and persist it; returns (id, version, spec)."""
    system = _system_prompt(catalog, include_workflow=include_workflow)
    spec, _errors = await compile_with_repair(
        system, [{"role": "user", "content": seed}], catalog,
        include_workflow=include_workflow, include_team=include_team,
    )
    if spec is None:
        return None
    updates: dict = {}
    if name:
        updates["name"] = name
    if sub_agents is not None:
        updates["sub_agents"] = sub_agents
    if updates:
        spec = spec.model_copy(update=updates)
    sm = get_sessionmaker()
    async with sm() as session:
        agent_id, version = await repo.upsert_agent_spec(
            session, tenant_id, spec.name, spec.model_dump(), note=note
        )
        await session.commit()
    return agent_id, version, spec


async def build_team(nl_request: str, tenant_id: str, run_id: str) -> AsyncIterator[dict]:
    """Design a whole TEAM: plan roles → build + persist each member → a coordinator
    that delegates to them. Streams progress; the final spec is the coordinator."""
    yield status("planning team")
    provider = get_provider()
    plan = await provider.parse_json(
        model=provider.orchestrator_model, system=TEAM_PLAN_SYSTEM,
        messages=[{"role": "user", "content": nl_request}],
        schema=TEAM_PLAN_SCHEMA, max_tokens=800,
    )
    members = (plan or {}).get("members") or []
    if not members:  # plan failed → fall back to a single agent
        async for e in build_agent(nl_request, tenant_id, run_id, _allow_team=False):
            yield e
        return
    members = members[:MAX_TEAM_MEMBERS]

    # Never overwrite an existing/unrelated agent: names are made unique against the
    # tenant's current agents AND each other (dedupes duplicate plan names too).
    taken = {a.lower() for a in (await build_catalog(tenant_id)).get("agents", [])}

    def _unique(name: str) -> str:
        base = name or "Agent"
        candidate, i = base, 2
        while candidate.lower() in taken:
            candidate, i = f"{base}{i}", i + 1
        taken.add(candidate.lower())
        return candidate

    built: list[str] = []
    for m in members:
        raw = (m.get("name") or "").strip()
        purpose = (m.get("purpose") or "").strip()
        if not raw:
            continue
        name = _unique(raw)
        yield status(f"building {name}")
        catalog = await build_catalog(tenant_id)
        seed = (f"Design the '{name}' agent. Role: {purpose}. It is one specialist member of "
                f"a team built for this goal: {nl_request}")
        res = await _compile_and_save(
            seed, catalog, tenant_id, note=f"team member of: {nl_request[:120]}",
            name=name, include_workflow=wants_workflow(purpose),
        )
        if res:
            built.append(res[2].name)
            yield ev("member", name=res[2].name, agent_id=res[0])

    if not built:
        async for e in build_agent(nl_request, tenant_id, run_id, _allow_team=False):
            yield e
        return

    yield status("wiring coordinator")
    coord = (plan.get("coordinator") or {})
    # Coordinator must be distinct from members (else it would overwrite one and end up
    # delegating to itself) and from existing agents.
    coord_name = _unique((coord.get("name") or "Coordinator").strip())
    roster = "; ".join(built)
    catalog = await build_catalog(tenant_id)  # now includes the new members
    seed = (f"Design the coordinator agent named '{coord_name}'. {coord.get('purpose', '')} "
            f"It leads a team and delegates subtasks to these members: {roster}. "
            f"Overall goal: {nl_request}")
    res = await _compile_and_save(
        seed, catalog, tenant_id, note=f"team coordinator: {nl_request[:120]}",
        name=coord_name, include_team=True, sub_agents=built,
    )
    if res is None:  # coordinator failed → surface the members anyway via the first one
        yield ev("error", message="Built the team members but couldn't wire a coordinator. "
                 "They're available in Agents.")
        return
    agent_id, version, spec = res
    async with get_sessionmaker()() as session:
        await repo.insert_audit(
            session, tenant_id, "orchestrator", "build_team", "agent", agent_id,
            {"request": nl_request, "members": built},
        )
        await session.commit()
    yield ev("spec", agent_id=agent_id, version=version, spec=spec.model_dump())
    yield ev("done", agent_id=agent_id, version=version)


async def build_agent(
    nl_request: str, tenant_id: str, run_id: str, _allow_team: bool = True
) -> AsyncIterator[dict]:
    """Compile NL → AgentSpec, persist it as an immutable version, stream events.

    When the request implies multiple roles, build a whole TEAM instead."""
    if _allow_team and wants_team(nl_request):
        async for e in build_team(nl_request, tenant_id, run_id):
            yield e
        return
    tracer = get_tracer()
    with tracer.start_as_current_span("orchestrator.build"):
        yield status("planning")
        catalog = await build_catalog(tenant_id)
        want_wf = wants_workflow(nl_request)
        system = _system_prompt(catalog, include_workflow=want_wf)

        yield status("designing")
        spec, errors = await compile_with_repair(
            system, [{"role": "user", "content": nl_request}], catalog,
            include_workflow=want_wf,
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
