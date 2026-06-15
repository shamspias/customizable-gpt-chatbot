"""SSE event helpers.

The MVP streams events directly from the request handler's async generator (no
Redis fan-out yet — that activates when a second process exists). Each event is a
dict shaped for sse_starlette.EventSourceResponse: {"event": <type>, "data": <json>}.

Event types (the client/CLI switch on these):
  status   — coarse phase updates ("planning", "answering", ...)
  thinking — summarized reasoning delta
  token    — assistant answer text delta
  tool_use — agent invoked a tool   {name, input}
  tool_result — tool returned       {name, ok}
  citations — retrieved sources     {citations: [...]}
  usage    — token + cost rollup     {model, input_tokens, output_tokens, cache_read_tokens,
             cache_write_tokens, total_tokens, cost_usd, cache_hit_rate}
  spec     — orchestrator produced/updated an AgentSpec {agent_id, version, spec}
  diff     — self-mod JSON-Patch awaiting approval {patch, ...}
  error    — {message}
  done     — terminal {answer?, ...}
"""

from __future__ import annotations

import json
from typing import Any


def ev(event_type: str, **data: Any) -> dict[str, str]:
    return {"event": event_type, "data": json.dumps(data, default=str)}


def status(phase: str, **extra: Any) -> dict[str, str]:
    return ev("status", phase=phase, **extra)


def error(message: str) -> dict[str, str]:
    return ev("error", message=message)
