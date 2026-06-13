"""The agent runtime — a manual streaming agentic loop, provider-agnostic.

Drives the normalized provider interface (Anthropic or local Ollama) so the same
loop runs on either backend. Per-token streaming, permission gates, and tool
dispatch. The assistant turn is appended with its opaque `raw` payload so the
Anthropic path preserves thinking blocks and Ollama preserves its tool_calls.
Yields SSE events and persists run_steps as checkpoints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import loom_thinking as thinking
from loom_llm import get_provider
from loom_mcp import ToolContext, from_wire_name
from loom_spec import AgentSpec

from loom_app import repo
from loom_app.db import get_sessionmaker
from loom_app.events import ev
from loom_app.tools_registry import get_registry
from loom_app.tracing import get_tracer

ANSWER_MAX_TOKENS = 8192


def build_system_prompt(spec: AgentSpec) -> str:
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
    return "\n".join(parts)


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
) -> AsyncIterator[dict]:
    """Drive one agent turn-to-completion, yielding SSE event dicts."""
    provider = get_provider()
    registry = get_registry()
    tracer = get_tracer()

    system = build_system_prompt(spec)
    tool_names = [t.name for t in spec.tools if registry.has(t.name)]
    tool_defs = registry.anthropic_defs(tool_names)  # {name(wire), description, input_schema}
    perm = {t.name: t.permission_mode for t in spec.tools}
    ctx = ToolContext(tenant_id=tenant_id, knowledge_bases=spec.knowledge_bases)

    messages: list[dict] = [{"role": "user", "content": user_message}]
    ordinal = 0
    answer = ""

    with tracer.start_as_current_span("agent.run", attributes={"agent.model": spec.model}):
        for _ in range(spec.guardrails.max_steps):
            turn = None
            async for event in provider.stream_turn(
                model=spec.model,
                system=system,
                messages=messages,
                tools=tool_defs,
                effort=spec.effort,
                max_tokens=ANSWER_MAX_TOKENS,
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

            messages.append(
                {"role": "assistant", "content": turn.text, "tool_calls": turn.tool_calls,
                 "raw": turn.raw}
            )
            ordinal += 1
            await _log_step(run_id, ordinal, "llm_turn", spec.model,
                            {"stop_reason": turn.stop_reason, "text": turn.text})

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
                logical = from_wire_name(call.name)
                mode = perm.get(logical, "ask")
                yield ev("tool_use", name=logical, input=call.arguments)
                ordinal += 1

                if mode == "deny":
                    content, is_error, citations = "This tool is not permitted.", True, []
                else:
                    # MVP: only the read-only kb.search runs. Human-in-the-loop approval
                    # for sensitive tools + a sandbox arrive in v1.
                    result = await registry.call(logical, call.arguments, ctx)
                    content, is_error = result.content, result.is_error
                    citations = result.data.get("citations", [])

                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": content,
                     "is_error": is_error}
                )
                if citations:
                    yield ev("citations", citations=citations)
                yield ev("tool_result", name=logical, ok=not is_error)
                await _log_step(run_id, ordinal, "tool_call", logical,
                                {"input": call.arguments, "is_error": is_error})
        else:
            yield ev("error", message="Agent reached its step limit without finishing.")
            return

    yield ev("done", answer=answer)
