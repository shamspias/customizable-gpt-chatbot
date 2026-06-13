"""Anthropic client access + model defaults.

Kept dependency-free of veldra_app: the Anthropic SDK resolves ANTHROPIC_API_KEY
from the environment, so `get_client()` needs no config injection. The runtime
drives streaming/tool-loop logic itself (it needs event-level control), so this
module only hands back a configured AsyncAnthropic.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

# Defaults (overridable per-agent via AgentSpec.model / .effort).
ORCHESTRATOR_MODEL = "claude-opus-4-8"
WORKER_MODEL = "claude-sonnet-4-6"
CHEAP_MODEL = "claude-haiku-4-5"

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Process-wide async Anthropic client (reads ANTHROPIC_API_KEY from env)."""
    global _client
    if _client is None:
        _client = AsyncAnthropic()
    return _client
