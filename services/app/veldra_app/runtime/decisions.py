"""Structured-decision agent loop — reliable on small/local models (sub-1B).

Research-backed design (constrained-decision loops, ReAct, validator-first, repair):
instead of fragile native tool-calling, the harness drives the model with a two-phase
CONSTRAINED step each turn —
  Phase 1 (route): emit {thought, action} where `action` is pinned to an enum of the
    granted tools + "final" (hallucinated tool names become impossible by construction).
  Phase 2 (args): fill exactly the chosen tool's input schema (never a big union).
Termination is the structural `final` action; the user-facing answer is a SEPARATE,
streamed, grounded composition ("answer only from observations; if absent, say so").
Plus: bounded parse-repair, a no-progress circuit breaker, and graceful step-limit
fallback — so the loop degrades to a present answer, never a dead-end error.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator

import veldra_thinking as thinking
from veldra_llm import get_provider
from veldra_mcp import ToolContext, from_wire_name, to_wire_name
from veldra_spec import AgentSpec

from veldra_app.events import ev
from veldra_app.pricing import UsageMeter
from veldra_app.runtime.agent import MAX_TEAM_DEPTH, _log_step, _resolve_delegates, _wire
from veldra_app.tools_registry import get_registry

DECISION_MAX_TOKENS = 1024
FINAL_MAX_TOKENS = 8192
SMALL_TIER_MAX_STEPS = 6
REPAIR_ATTEMPTS = 3


def _route_schema(actions: list[str]) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["thought", "action"],
        "properties": {
            "thought": {"type": "string", "description": "One short sentence: what to do next and why."},
            "action": {"type": "string", "enum": actions},
        },
    }


_FINAL_ONLY = {
    "type": "object", "additionalProperties": False, "required": ["action"],
    "properties": {"action": {"type": "string", "enum": ["final"]}},
}


def _system_prompt(spec: AgentSpec, tool_descs: dict[str, str]) -> str:
    tm = thinking.get(spec.thinking_method)
    parts = [
        spec.system_prompt.strip(), "",
        f"## Reasoning\n{tm.preamble}", "",
        "## How to act",
        "Work in small steps. At EACH step return a JSON object: "
        '{"thought": "<one short sentence>", "action": "<one allowed action>"}. '
        'Use a tool action to gather what you need; choose "final" as soon as you can answer.',
        "", "## Allowed actions",
    ]
    for wire, desc in tool_descs.items():
        parts.append(f"- {wire} — {desc}")
    parts.append('- final — you have enough information; answer the user.')
    if tool_descs:  # few-shot: teach the use-a-tool-then-finalize shape (helps small models)
        example_tool = next(iter(tool_descs))
        parts += [
            "", "## Example",
            f'Step 1: {{"thought": "I need information first.", "action": "{example_tool}"}}',
            "(an observation from the tool is added to the conversation)",
            'Step 2: {"thought": "The observation has what I need.", "action": "final"}',
        ]
    return "\n".join(parts)


async def _decode(provider, model: str, system: str, conv: list[dict], schema: dict) -> dict | None:
    """parse_json with a small repair budget (re-ask for valid JSON)."""
    msgs = list(conv)
    for _ in range(REPAIR_ATTEMPTS):
        data = await provider.parse_json(
            model=model, system=system, messages=msgs, schema=schema, max_tokens=DECISION_MAX_TOKENS
        )
        if data is not None:
            return data
        msgs = msgs + [{"role": "user", "content": "Reply with ONLY a JSON object in the required format."}]
    return None


# Free-text fields where the user's raw request is a sensible last-resort value
# (e.g. a kb.search `query`). Typed fields like `expression`/`url`/`path` are NOT here —
# poisoning them with the raw question is worse than leaving them empty.
_FREETEXT = {"query", "question", "text", "task", "prompt", "input", "content", "message", "topic"}


def _example_value(prop: dict) -> str:
    return {
        "string": '"..."', "integer": "0", "number": "0",
        "boolean": "true", "array": "[]", "object": "{}",
    }.get(prop.get("type"), '"..."')


async def _fill_args(
    provider, model: str, system: str,
    action: str, desc: str, schema: dict, user_message: str, last_obs: str | None = None,
) -> dict:
    """Phase 2: fill the chosen tool's args — tiny-model hardened.

    Probed reality: Ollama's `format` does NOT enforce required/additionalProperties, and
    feeding the route-phase JSON back makes a sub-1B model echo `thought` or invent keys
    (`{"result": ...}`) and omit the real field. So we (a) drive args from a CLEAN,
    example-driven instruction naming the exact fields (the single biggest reliability
    lever — verified turns `144*12` into `{"expression":"144*12"}`), (b) drop any key not
    in the schema, and (c) re-ask, then fall back on a blank required field — but only for
    free-text fields, never poisoning a typed one (the empty-query failure mode)."""
    props = schema.get("properties", {})
    required = schema.get("required", [])
    if not props:  # no-arg tool (time.now, fs.list) — nothing to fill
        return {}

    fields = ", ".join(f'"{f}"' for f in props)
    pairs = ", ".join(f'"{f}": {_example_value(props[f])}' for f in (required or props))
    example = "{" + pairs + "}"
    hints = "; ".join(f"{f}: {p['description']}" for f, p in props.items() if p.get("description"))
    instruction = (
        f"Call {action} ({desc}). Reply with ONLY a JSON object using these fields: {fields}. "
        + (f"Field notes — {hints}. " if hints else "")
        + f"Example shape: {example}. The values must accomplish the request."
    )
    base = [{"role": "user", "content": f'Request: "{user_message}"'}]
    if last_obs:
        base.append({"role": "user", "content": f"Most recent observation:\n{last_obs[:2000]}"})
    base.append({"role": "user", "content": instruction})

    args: dict = {}
    for _ in range(REPAIR_ATTEMPTS):
        raw = await _decode(provider, model, system, base, schema) or {}
        args = {k: v for k, v in raw.items() if k in props}  # drop leaked keys (thought/result/…)
        missing = [f for f in required if not str(args.get(f, "")).strip()]
        if not missing:
            return args
        base = base + [{"role": "user", "content":
            f"These required fields were missing or empty: {missing}. "
            "Give a concrete, non-empty value for each, as JSON."}]
    for f in required:  # last-resort: only free-text fields default to the user's request
        blank = not str(args.get(f, "")).strip()
        if blank and f in _FREETEXT and props.get(f, {}).get("type") == "string":
            args[f] = user_message
    return args


async def run_decision_agent(
    spec: AgentSpec,
    user_message: str,
    *,
    tenant_id: str,
    run_id: str,
    depth: int = 0,
    history: list[dict] | None = None,
    registry=None,
) -> AsyncIterator[dict]:
    provider = get_provider()
    registry = registry or get_registry()

    delegates = await _resolve_delegates(spec, tenant_id) if depth < MAX_TEAM_DEPTH else {}
    delegate_tools = {_wire(n): sub for n, sub in delegates.items()}
    perm = {t.name: t.permission_mode for t in spec.tools}

    tool_descs: dict[str, str] = {}
    arg_schemas: dict[str, dict] = {}
    for name in (n for n in perm if registry.has(n)):
        wire = to_wire_name(name)
        tool = registry.get(name)
        tool_descs[wire] = tool.description
        arg_schemas[wire] = tool.input_schema
    for wire, sub in delegate_tools.items():
        tool_descs[wire] = f"Delegate a subtask to the '{sub.name}' agent."
        arg_schemas[wire] = {
            "type": "object", "additionalProperties": False, "required": ["task"],
            "properties": {"task": {"type": "string"}},
        }

    actions = [*tool_descs.keys(), "final"]
    ctx = ToolContext(tenant_id=tenant_id, knowledge_bases=spec.knowledge_bases)
    system = _system_prompt(spec, tool_descs)
    model = spec.model

    conv: list[dict] = []
    for h in history or []:
        role, txt = h.get("role"), (h.get("text") or h.get("content") or "")
        if role in ("user", "assistant") and txt:
            conv.append({"role": role, "content": txt})
    conv.append({"role": "user", "content": user_message})

    observations: list[dict] = []
    seen: dict[tuple, int] = {}
    no_progress = 0
    ordinal = 0
    max_steps = min(spec.guardrails.max_steps, SMALL_TIER_MAX_STEPS)
    # Grounding guard: a RAG agent must consult its KB before answering.
    kb_wire = to_wire_name("kb.search")
    grounded = bool(spec.knowledge_bases) and kb_wire in arg_schemas

    if len(actions) > 1:  # has tools → run the decision loop
        for step in range(max_steps):
            schema = _FINAL_ONLY if step == max_steps - 1 else _route_schema(actions)
            decision = await _decode(provider, model, system, conv, schema)
            if decision is None:
                break
            thought = str(decision.get("thought", ""))
            action = decision.get("action", "final")
            if thought:
                yield ev("thinking", text=thought)
            conv.append({"role": "assistant", "content": json.dumps(decision)})
            ordinal += 1
            await _log_step(run_id, ordinal, "decision", action, {"thought": thought})
            if action == "final" or action not in arg_schemas:
                if grounded and not observations:  # a RAG agent must ground before answering
                    action = kb_wire  # force the KB search deterministically
                    yield ev("thinking", text="Searching the knowledge base to ground the answer.")
                else:
                    break

            args = await _fill_args(
                provider, model, system, action, tool_descs[action],
                arg_schemas[action], user_message,
                last_obs=observations[-1]["content"] if observations else None,
            )

            key = (action, hashlib.sha1(json.dumps(args, sort_keys=True).encode()).hexdigest())
            if seen.get(key, 0) >= 1:  # already did this exact call
                no_progress += 1
                conv.append({"role": "user", "content":
                    f"You already ran {action} with those arguments. Try something else or answer (final)."})
                if no_progress >= 2:
                    break
                continue
            seen[key] = seen.get(key, 0) + 1

            logical = from_wire_name(action)
            yield ev("tool_use", name=logical, input=args)
            ordinal += 1
            if action in delegate_tools:
                sub = delegate_tools[action]
                sub_answer = ""
                async for sev in run_decision_agent(
                    sub, str(args.get("task") or user_message),
                    tenant_id=tenant_id, run_id=run_id, depth=depth + 1,
                ):
                    if sev["event"] == "done":
                        sub_answer = json.loads(sev["data"]).get("answer", "")
                content, is_error = sub_answer or "(no answer)", False
                yield ev("tool_result", name=logical, ok=True)
            elif perm.get(logical) == "deny":
                content, is_error = "This tool is not permitted.", True
                yield ev("tool_result", name=logical, ok=False)
            else:
                result = await registry.call(logical, args, ctx)
                content, is_error = result.content, result.is_error
                if result.data.get("citations"):
                    yield ev("citations", citations=result.data["citations"])
                yield ev("tool_result", name=logical, ok=not is_error)

            observations.append({"tool": logical, "content": content})
            conv.append({"role": "user", "content": f"Observation from {logical}:\n{content}"})
            await _log_step(run_id, ordinal, "tool_call", logical, {"is_error": is_error})

    # ── compose the final answer: separate, streamed, grounded ──
    if observations:
        grounding = (
            "Answer the user's question now using ONLY the observations above. Cite the "
            "bracketed [n] source numbers you use. If the observations do not contain the "
            "answer, say you don't know — do not guess."
        )
    else:
        grounding = "Answer the user's question directly and helpfully."
    final_system = f"{spec.system_prompt.strip()}\n\n{grounding}"
    compose = conv + [{"role": "user", "content": f"Now answer my question: {user_message}"}]

    answer = ""
    meter = UsageMeter()
    async for e in provider.stream_turn(
        model=model, system=final_system, messages=compose,
        tools=[], effort=spec.effort, max_tokens=FINAL_MAX_TOKENS,
    ):
        if e["type"] == "text":
            answer += e["text"]
            yield ev("token", text=e["text"])
        elif e["type"] == "thinking":
            yield ev("thinking", text=e["text"])
        elif e["type"] == "final":
            answer = e["turn"].text or answer
            meter.add(e["turn"].usage)

    ordinal += 1
    await _log_step(run_id, ordinal, "final", model, {"chars": len(answer), "tokens": meter.payload(model)})
    if meter.has_data():
        yield ev("usage", **meter.payload(model))
    yield ev("done", answer=answer)
