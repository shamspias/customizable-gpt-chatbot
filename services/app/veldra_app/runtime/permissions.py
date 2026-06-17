"""Tool permission gating for an agent run.

`permission_mode` per tool: ``auto`` (run silently), ``ask`` (needs approval), ``deny``
(never). Built-in tools are bounded/local-first, so ``ask`` on a built-in keeps running
(no behaviour change). For *connector* (plugin) tools — the side-effecting surface —
``ask`` means the call is gated: the tool is only exposed/run when the user has approved
it for the turn (or set it to ``auto``). This adds real safety for Shopify/Alibaba-style
connectors without regressing existing agents.
"""

from __future__ import annotations

from veldra_spec import AgentSpec

BUILTIN_NAMESPACES = {"kb", "time", "math", "calc", "http", "web", "fs", "json", "regex", "agent"}


def is_builtin(name: str) -> bool:
    return name.split(".", 1)[0] in BUILTIN_NAMESPACES


def _needs_approval(name: str, mode: str, approved: set[str]) -> bool:
    """A connector tool in 'ask' mode needs explicit approval before it can run."""
    return mode == "ask" and not is_builtin(name) and name not in approved


def is_allowed(name: str, perm: dict[str, str], approved: set[str] | None = None) -> bool:
    approved = approved or set()
    mode = perm.get(name, "ask")
    if mode == "deny":
        return False
    return not _needs_approval(name, mode, approved)


def exposed_tool_names(spec: AgentSpec, approved: set[str] | None = None) -> list[str]:
    """The tools advertised to the model this turn (deny + unapproved connectors hidden)."""
    approved = approved or set()
    return [
        t.name for t in spec.tools
        if t.permission_mode != "deny" and not _needs_approval(t.name, t.permission_mode, approved)
    ]


def approval_block_message(name: str) -> str:
    return (
        f"The tool '{name}' needs your approval before it can run. "
        "Approve it for this chat, or set its permission to 'auto'."
    )
