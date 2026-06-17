"""The agent runtime — a manual streaming agentic loop, provider-agnostic.

Drives the normalized provider interface (Anthropic / Ollama / OpenAI-compatible)
so the same loop runs on any backend. Per-token streaming, permission gates, tool
dispatch, and **agent teams**: an agent's `sub_agents` are exposed as delegate
tools (`team__<name>`) that run a nested agent and return its answer — depth-capped
to prevent runaway recursion. Yields SSE events and persists run_steps.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

import veldra_thinking as thinking
from veldra_llm import get_provider
from veldra_mcp import ToolContext, from_wire_name
from veldra_spec import AgentSpec

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.events import ev
from veldra_app.pricing import UsageMeter
from veldra_app.runtime.permissions import (
    approval_block_message,
    exposed_tool_names,
    is_allowed,
)
from veldra_app.tools_registry import build_registry
from veldra_app.tracing import get_tracer

ANSWER_MAX_TOKENS = 8192
MAX_TEAM_DEPTH = 2


def build_system_prompt(spec: AgentSpec, delegates: dict[str, AgentSpec]) -> str:
    tm = thinking.get(spec.thinking_method)
    parts = [spec.system_prompt.strip(), "", f"## Reasoning approach\n{tm.preamble}"]
    if spec.guardrails.system_reminders:
        parts += ["", "## Operating rules", *(f"- {r}" for r in spec.guardrails.system_reminders)]
    if spec.knowledge_bases:
        parts += [
            "",
            "When you cite a passage from the search tool, reference its bracketed "
            "number so the user can trace the source.",
        ]
    if delegates:
        roster = ", ".join(f"'{n}'" for n in delegates)
        parts += [
            "",
            f"## Team\nYou coordinate a team of sub-agents ({roster}). Delegate a "
            "subtask by calling its team__ tool with a clear `task`; use their results "
            "to complete the user's request.",
        ]
    return "\n".join(parts)


def _wire(name: str) -> str:
    return "team__" + re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


async def _resolve_delegates(spec: AgentSpec, tenant_id: str) -> dict[str, AgentSpec]:
    """name -> sub-agent spec, for each existing agent referenced in sub_agents."""
    if not spec.sub_agents:
        return {}
    out: dict[str, AgentSpec] = {}
    sm = get_sessionmaker()
    async with sm() as session:
        for name in spec.sub_agents:
            agent = await repo.get_agent_by_name(session, tenant_id, name)
            if not agent:
                continue
            sub = await repo.get_spec(session, str(agent["id"]))
            if sub:
                out[name] = AgentSpec.model_validate(sub)
    return out


async def _log_step(run_id: str, ordinal: int, type_: str, name: str | None, payload: dict) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        await repo.insert_run_step(session, run_id, ordinal, type_, name, payload)
        await session.commit()


async def run_agent(
    spec: AgentSpec,
    user_message: str,
    *,
    tenant_id: str,
    run_id: str,
    depth: int = 0,
    history: list[dict] | None = None,
    registry=None,
    approved_tools: list[str] | None = None,
) -> AsyncIterator[dict]:
    """Drive one agent turn-to-completion, yielding SSE event dicts."""
    provider = get_provider()
    registry = registry or await build_registry(tenant_id)
    approved = set(approved_tools or [])
    tracer = get_tracer()

    delegates = await _resolve_delegates(spec, tenant_id) if depth < MAX_TEAM_DEPTH else {}
    delegate_tools = {
        _wire(name): sub for name, sub in delegates.items()
    }  # wire -> sub spec

    system = build_system_prompt(spec, delegates)
    perm = {t.name: t.permission_mode for t in spec.tools}
    tool_names = [name for name in exposed_tool_names(spec, approved) if registry.has(name)]
    tool_defs = registry.anthropic_defs(tool_names)
    for wire, sub in delegate_tools.items():
        tool_defs.append(
            {
                "name": wire,
                "description": f"Delegate a subtask to the '{sub.name}' agent: "
                f"{sub.description or sub.system_prompt[:80]}",
                "input_schema": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"task": {"type": "string"}}, "required": ["task"],
                },
            }
        )
    ctx = ToolContext(tenant_id=tenant_id, knowledge_bases=spec.knowledge_bases)

    messages: list[dict] = []
    for h in history or []:  # prior turns for multi-turn chat
        role = h.get("role")
        text = h.get("text") or h.get("content") or ""
        if role in ("user", "assistant") and text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user_message})
    ordinal = 0
    answer = ""
    meter = UsageMeter()

    with tracer.start_as_current_span("agent.run", attributes={"agent.depth": depth}):
        for _ in range(spec.guardrails.max_steps):
            turn = None
            async for event in provider.stream_turn(
                model=spec.model, system=system, messages=messages,
                tools=tool_defs, effort=spec.effort, max_tokens=ANSWER_MAX_TOKENS,
            ):
                if event["type"] == "text":
                    yield ev("token", text=event["text"])
                elif event["type"] == "thinking":
                    yield ev("thinking", text=event["text"])
                elif event["type"] == "final":
                    turn = event["turn"]

            if turn is None:
                yield ev("error", message="The model returned no response.")
                return

            meter.add(turn.usage)
            messages.append({"role": "assistant", "content": turn.text,
                             "tool_calls": turn.tool_calls, "raw": turn.raw})
            ordinal += 1
            await _log_step(run_id, ordinal, "llm_turn", spec.model,
                            {"stop_reason": turn.stop_reason, "depth": depth, "tokens": turn.usage})

            if turn.stop_reason == "end_turn":
                answer = turn.text
                break
            if turn.stop_reason == "refusal":
                yield ev("error", message="The model declined to complete this request.")
                return
            if turn.stop_reason != "tool_use":
                yield ev("error", message=f"Unexpected stop reason: {turn.stop_reason}")
                return

            for call in turn.tool_calls:
                ordinal += 1
                # ── delegate to a sub-agent (team) ──
                if call.name in delegate_tools:
                    sub = delegate_tools[call.name]
                    task = str(call.arguments.get("task") or user_message)
                    yield ev("tool_use", name=f"team:{sub.name}", input={"task": task})
                    sub_answer = ""
                    async for sub_ev in run_agent(
                        sub, task, tenant_id=tenant_id, run_id=run_id, depth=depth + 1
                    ):
                        if sub_ev["event"] == "done":
                            sub_answer = json.loads(sub_ev["data"]).get("answer", "")
                        elif sub_ev["event"] == "usage":  # fold delegate tokens into the total
                            meter.add(json.loads(sub_ev["data"]))
                    messages.append({"role": "tool", "tool_call_id": call.id,
                                     "content": sub_answer or "(no answer)", "is_error": False})
                    yield ev("tool_result", name=f"team:{sub.name}", ok=True)
                    await _log_step(run_id, ordinal, "delegate", sub.name, {"task": task})
                    continue

                # ── first-party tool ──
                logical = from_wire_name(call.name)
                yield ev("tool_use", name=logical, input=call.arguments)
                if perm.get(logical, "ask") == "deny":
                    content, is_error, citations = "This tool is not permitted.", True, []
                elif not is_allowed(logical, perm, approved):
                    content, is_error, citations = approval_block_message(logical), True, []
                else:
                    result = await registry.call(logical, call.arguments, ctx)
                    content, is_error = result.content, result.is_error
                    citations = result.data.get("citations", [])
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": content, "is_error": is_error})
                if citations:
                    yield ev("citations", citations=citations)
                yield ev("tool_result", name=logical, ok=not is_error)
                await _log_step(run_id, ordinal, "tool_call", logical, {"is_error": is_error})
        else:
            yield ev("error", message="Agent reached its step limit without finishing.")
            return

    # Emit at every depth: a delegate's usage event is folded into its parent's meter
    # (the parent swallows sub-agent events); only the depth-0 event reaches the client.
    if meter.has_data():
        yield ev("usage", **meter.payload(spec.model))
    yield ev("done", answer=answer)
