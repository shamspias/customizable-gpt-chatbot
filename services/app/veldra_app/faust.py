"""Faust — the floating, platform-aware admin bot.

Faust is a built-in meta-agent that manages the platform by talking: rename/update/
tag/delete agents, inspect + clear the activity log, and delete knowledge-base
documents. It runs through the normal decision/agent loop but with its OWN tool
registry (builtins + admin tools), so its destructive powers can never leak to a
user-built agent. It has a "soul": auto_improve=True, so it reflects on 👎 feedback
and accumulates lessons like any other agent (the same self-improvement architecture).
"""

from __future__ import annotations

import functools
from collections.abc import AsyncIterator

from veldra_mcp import ToolRegistry
from veldra_mcp_servers import builtins
from veldra_spec import AgentSpec

from veldra_app import repo
from veldra_app.config import DEFAULT_TENANT_ID
from veldra_app.db import get_sessionmaker
from veldra_app.runtime import execute

FAUST_NAME = "Faust"

FAUST_PROMPT = """\
You are Faust — Veldra's resident operations assistant with a soul. You manage the \
platform on the user's behalf by USING YOUR TOOLS, never by guessing. You can list, \
rename, re-policy, tag, and delete agents; inspect and clear the activity log; and \
delete knowledge-base documents.

Operating rules:
- Always act through a tool; when asked to change or delete something, call the \
matching admin tool and report exactly what changed.
- Resolve agents by the name the user says. If a name is ambiguous or missing, call \
admin.list_agents first and ask which one.
- Deletion is permanent. For a clearly-scoped request ("delete the TestBot agent", \
"clear the build logs") just do it and confirm. If a request is vague or sweeping \
("delete everything"), confirm the scope in one short question before acting.
- Be concise. After acting, state the result in one line."""

FAUST_TOOLS = [
    "admin.list_agents", "admin.rename_agent", "admin.update_agent", "admin.tag_agent",
    "admin.delete_agent", "admin.list_runs", "admin.clear_runs", "admin.delete_document",
    "time.now",
]


@functools.lru_cache
def get_admin_registry() -> ToolRegistry:
    """Faust-only registry: generic builtins + the platform-admin tools."""
    from veldra_app.admin_tools import build_admin_tools

    registry = ToolRegistry()
    for tool in builtins.build_tools():
        registry.register(tool)
    for tool in build_admin_tools():
        registry.register(tool)
    return registry


def faust_spec() -> AgentSpec:
    from veldra_llm import get_provider
    from veldra_spec import ToolBinding

    # Faust is a meta/admin agent — give it the orchestrator tier (point
    # VELDRA_OLLAMA_ORCHESTRATOR_MODEL at a larger local model for reliable
    # multi-argument tool calls; Anthropic uses the Opus orchestrator).
    return AgentSpec(
        name=FAUST_NAME,
        description="Platform operations assistant.",
        system_prompt=FAUST_PROMPT,
        model=get_provider().orchestrator_model,
        effort="high",
        thinking_method="react",
        tools=[ToolBinding(name=t, permission_mode="auto") for t in FAUST_TOOLS],
        auto_improve=True,  # the "soul": Faust learns from feedback like any agent
    )


async def get_or_create_faust(tenant_id: str = DEFAULT_TENANT_ID) -> str:
    """Ensure the Faust agent row exists; return its id (so runs/lessons attach to it)."""
    sm = get_sessionmaker()
    async with sm() as session:
        existing = await repo.get_agent_by_name(session, tenant_id, FAUST_NAME)
        if existing:
            return str(existing["id"])
        agent_id, _ = await repo.upsert_agent_spec(
            session, tenant_id, FAUST_NAME, faust_spec().model_dump(), note="faust bootstrap"
        )
        await session.commit()
        return agent_id


async def run_faust(
    message: str, tenant_id: str, run_id: str, history: list[dict] | None = None
) -> AsyncIterator[dict]:
    """Run a Faust turn with the admin registry + its learned lessons injected."""
    from veldra_app import learning

    agent_id = await get_or_create_faust(tenant_id)
    spec = faust_spec()
    sm = get_sessionmaker()
    async with sm() as session:
        lessons = await repo.list_lessons(session, agent_id, limit=10)
    if lessons:
        spec = spec.model_copy(
            update={"system_prompt": spec.system_prompt + learning.lessons_block(lessons)}
        )
    async for ev in execute(
        spec, message, tenant_id=tenant_id, run_id=run_id,
        history=history, registry=get_admin_registry(),
    ):
        yield ev
