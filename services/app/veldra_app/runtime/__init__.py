"""veldra_app.runtime — agent run loop + deterministic workflow executor."""

from collections.abc import AsyncIterator

from veldra_spec import AgentSpec

from veldra_app.runtime.agent import build_system_prompt, run_agent
from veldra_app.runtime.workflow import run_workflow


def execute(spec: AgentSpec, message: str, *, tenant_id: str, run_id: str) -> AsyncIterator[dict]:
    """Run an agent: a deterministic workflow if the spec has one, else the agent loop."""
    if spec.workflow_graph and spec.workflow_graph.nodes:
        return run_workflow(spec, message, tenant_id=tenant_id, run_id=run_id)
    return run_agent(spec, message, tenant_id=tenant_id, run_id=run_id)


__all__ = ["execute", "run_agent", "run_workflow", "build_system_prompt"]
