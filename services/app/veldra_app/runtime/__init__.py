"""veldra_app.runtime — agent runtime.

Dispatch order: a deterministic workflow if the spec has one; else the structured
*decision loop* for small/local models (reliable constrained decisions); else the
native tool-calling loop (Claude / large models). Override with VELDRA_AGENT_MODE
(auto | decision | native).
"""

import os
from collections.abc import AsyncIterator

from veldra_llm import get_provider
from veldra_spec import AgentSpec

from veldra_app.runtime.agent import build_system_prompt, run_agent
from veldra_app.runtime.decisions import run_decision_agent
from veldra_app.runtime.workflow import run_workflow


def _use_decision_mode() -> bool:
    mode = os.getenv("VELDRA_AGENT_MODE", "auto").lower()
    if mode == "decision":
        return True
    if mode == "native":
        return False
    return get_provider().prefers_structured  # auto: small/local → decision loop


def execute(
    spec: AgentSpec, message: str, *, tenant_id: str, run_id: str,
    history: list[dict] | None = None, registry=None, approved_tools: list[str] | None = None,
) -> AsyncIterator[dict]:
    if spec.workflow_graph and spec.workflow_graph.nodes:
        return run_workflow(spec, message, tenant_id=tenant_id, run_id=run_id)
    if _use_decision_mode():
        return run_decision_agent(
            spec, message, tenant_id=tenant_id, run_id=run_id, history=history,
            registry=registry, approved_tools=approved_tools,
        )
    return run_agent(
        spec, message, tenant_id=tenant_id, run_id=run_id, history=history,
        registry=registry, approved_tools=approved_tools,
    )


__all__ = ["execute", "run_agent", "run_decision_agent", "run_workflow", "build_system_prompt"]
