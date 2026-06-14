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
    """A tool the agent may call, named exactly as it appears in the catalog (e.g. 'kb.search')."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Tool name, copied verbatim from the catalog, e.g. 'kb.search'.")
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


# Rich, Dify-class node set. `condition` is kept for back-compat (substring routing);
# `if_else` is the operator-based branch. All routing nodes branch via edge `when`.
WorkflowNodeType = Literal[
    "start",
    "end",
    "llm",          # prompt an LLM (streams tokens)
    "kb_search",    # retrieve from knowledge bases (with citations)
    "condition",    # legacy substring branch (true/false)
    "if_else",      # operator branch (==, !=, >, <, contains, regex, …) → true/false
    "code",         # sandboxed safe-expression transform over variables
    "tool",         # invoke a built-in tool (math.eval, time.now, http.fetch, …)
    "http",         # HTTP request node
    "template",     # render a text template over variables
    "aggregator",   # merge several variables/branch outputs into one
    "classifier",   # LLM intent routing → branches via the matched class name
]

CompareOp = Literal[
    "contains", "not_contains", "eq", "ne", "gt", "lt", "gte", "lte",
    "regex", "empty", "not_empty",
]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


class NodeInput(BaseModel):
    """A named input binding: `name` = `value`, where value may template {vars}.

    Used for tool arguments, http headers, template/code variable bindings, and the
    sources an aggregator merges (a closed shape keeps constrained decoding happy)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Argument / variable / header name.")
    value: str = Field(default="", description="Value or template, e.g. '{input}' or 'Bearer {token}'.")


class NodeConfig(BaseModel):
    """Flat, closed node config covering every node type (constrained-decoding friendly).

    Templating: any string may reference pool variables with {var} — e.g. an `llm`
    prompt of "Summarize: {context}" inserts the `context` written by an upstream node.
    Each field is used only by the node types noted; others are ignored.
    """

    model_config = ConfigDict(extra="forbid")

    # llm / classifier
    prompt: str = Field(default="", description="llm node: prompt template, with {var} substitution.")
    model: str = Field(default="", description="llm/classifier: optional per-node model override.")
    # kb_search
    query: str = Field(default="", description="kb_search node: query template (default '{input}').")
    k: int = Field(default=6, ge=1, le=20, description="kb_search node: passages to retrieve.")
    mode: str = Field(default="", description="kb_search: retrieval mode override (semantic|keyword|hybrid).")
    # condition / if_else
    var: str = Field(default="", description="condition/if_else: pool variable to test.")
    op: CompareOp = Field(default="contains", description="if_else: comparison operator.")
    value: str = Field(default="", description="if_else: right-hand value to compare against (templated).")
    contains: str = Field(default="", description="condition: routes to 'true' if var contains this.")
    # code
    code: str = Field(default="", description="code node: a sandboxed expression over input variables.")
    # tool
    tool: str = Field(default="", description="tool node: tool name, e.g. 'math.eval'.")
    # http
    method: HttpMethod = Field(default="GET", description="http node: request method.")
    url: str = Field(default="", description="http node: URL template.")
    body: str = Field(default="", description="http node: request body template.")
    headers: list[NodeInput] = Field(default_factory=list, description="http node: request headers.")
    # template
    template: str = Field(default="", description="template node: text template over {vars}.")
    # classifier
    classes: list[str] = Field(
        default_factory=list, description="classifier: candidate classes; edge.when matches the chosen one."
    )
    # generic bindings (tool args, code/template vars, aggregator sources)
    inputs: list[NodeInput] = Field(
        default_factory=list, description="Named inputs: tool args, variable bindings, aggregator sources."
    )
    # output
    output_var: str = Field(default="output", description="Pool variable this node writes its result to.")


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: WorkflowNodeType
    label: str = ""
    config: NodeConfig = Field(default_factory=NodeConfig)


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    when: str | None = Field(
        default=None,
        description="Branch label: 'true'/'false' for condition/if_else, a class name for "
        "classifier; null = unconditional.",
    )


class WorkflowGraph(BaseModel):
    """A deterministic flow: start → (llm/kb_search/tool/code/if_else/…)* → end."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entrypoint: str = "start"

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}


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

    sub_agents: list[str] = Field(
        default_factory=list,
        description="Names of delegate agents (a team); each becomes a delegate tool.",
    )
    workflow_graph: WorkflowGraph | None = Field(
        default=None,
        description="Optional deterministic workflow; when set, the runtime executes the "
        "graph (start→…→end) instead of the free-form agent loop.",
    )

    @field_validator("name", "system_prompt")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v

    def tool_keys(self) -> set[str]:
        return {t.name for t in self.tools}
