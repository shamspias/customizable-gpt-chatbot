"""The AgentSpec — Veldra's load-bearing data model.

An agent is *data*, not code: a versioned AgentSpec the runtime interprets. The
orchestrator compiles natural language into one of these (via constrained decoding)
and edits it via JSON-Patch. Keep this package dependency-free (pydantic only).

Forward-compatibility rule: evolve additively. New capabilities are added as
*optional* fields with defaults so old persisted specs still validate, and
`schema_version` is bumped when a breaking change is unavoidable. Fields marked
`[fwd]` are part of the model for forward-compat but are not exercised in the MVP.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Defaults live here (not in app config) so the schema package stays standalone.
DEFAULT_ORCHESTRATOR_MODEL = "claude-opus-4-8"
DEFAULT_WORKER_MODEL = "claude-sonnet-4-6"
DEFAULT_CHEAP_MODEL = "claude-haiku-4-5"

PermissionMode = Literal["auto", "ask", "deny"]
Effort = Literal["low", "medium", "high", "xhigh"]
ThinkingMethod = Literal["react", "plan_execute"]  # MVP set; reflexion/tot/debate later


class ToolBinding(BaseModel):
    """A tool the agent may call, addressed as `<mcp_server>.<tool_name>`."""

    model_config = ConfigDict(extra="forbid")

    mcp_server: str = Field(description="Logical MCP server name, e.g. 'kb'.")
    tool_name: str = Field(description="Tool exposed by that server, e.g. 'search'.")
    permission_mode: PermissionMode = Field(
        default="ask",
        description="auto = run silently; ask = require human approval; deny = never.",
    )
    reason: str = Field(default="", description="Why the orchestrator gave the agent this tool.")


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    scope: Literal["session", "cross_session"] = "session"  # cross_session is [fwd] v1+


class Guardrails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(default=12, ge=1, le=64, description="Max agent loop iterations.")
    blocked_topics: list[str] = Field(default_factory=list)
    system_reminders: list[str] = Field(
        default_factory=list, description="Extra always-on instructions appended to the policy."
    )


class AgentSpec(BaseModel):
    """A complete, runnable agent definition. This is what the orchestrator emits."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1

    name: str = Field(description="Short, human-friendly agent name.")
    description: str = Field(default="", description="One-line summary of what the agent does.")

    system_prompt: str = Field(
        description="The agent's policy / persona / instructions (its system prompt)."
    )

    model: str = Field(default=DEFAULT_WORKER_MODEL, description="LLM model id for this agent.")
    effort: Effort = Field(default="high", description="Reasoning effort (output_config.effort).")
    thinking_method: ThinkingMethod = Field(
        default="react", description="Reasoning strategy the runtime applies."
    )

    tools: list[ToolBinding] = Field(default_factory=list)
    knowledge_bases: list[str] = Field(
        default_factory=list, description="KB ids/names the agent can search via kb.search."
    )

    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    guardrails: Guardrails = Field(default_factory=Guardrails)

    # ── forward-compat (not exercised in MVP) ──
    sub_agents: list[str] = Field(
        default_factory=list, description="[fwd v1+] names of delegate agents for teams."
    )
    workflow_graph_ref: str | None = Field(
        default=None, description="[fwd v2] reference to a workflow graph that drives this agent."
    )

    @field_validator("name", "system_prompt")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v

    def tool_keys(self) -> set[str]:
        return {f"{t.mcp_server}.{t.tool_name}" for t in self.tools}
