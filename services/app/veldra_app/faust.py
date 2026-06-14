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
WHOLE platform on the user's behalf by USING YOUR TOOLS, never by guessing. You can:
- Agents: list, build new ones (admin.create_agent), rename, re-policy, tag, delete.
- Skills: list, create, and WRITE their Markdown content yourself (admin.write_skill — \
when asked to "write a skill about X", generate a complete, useful playbook), delete.
- Knowledge: create knowledge bases, WRITE generated text into them as documents \
(admin.write_document), and delete documents.
- Activity log: inspect and clear runs.

Operating rules:
- Always act through a tool; when asked to create, write, change, or delete something, \
call the matching tool and report exactly what happened.
- When asked to WRITE/GENERATE content (a skill, a document), compose the full text \
yourself and pass it to the write tool — don't ask the user to provide it.
- Resolve agents/skills by the name the user says; if ambiguous, list first and ask.
- Deletion is permanent. Do clearly-scoped deletes directly; for a vague/sweeping \
request ("delete everything") confirm the scope in one short question first.
- Be concise. After acting, state the result in one line."""

FAUST_TOOLS = [
    "admin.list_agents", "admin.create_agent", "admin.rename_agent", "admin.update_agent",
    "admin.tag_agent", "admin.delete_agent",
    "admin.list_skills", "admin.create_skill", "admin.write_skill", "admin.delete_skill",
    "admin.create_kb", "admin.write_document", "admin.delete_document",
    "admin.list_runs", "admin.clear_runs",
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
