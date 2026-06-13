"""loom_thinking — pluggable reasoning strategies keyed by AgentSpec.thinking_method."""

from loom_thinking.base import ThinkingMethod, available, get, register

# Importing methods registers the built-ins (react, plan_execute) as a side effect.
from loom_thinking import methods  # noqa: E402,F401

__all__ = ["ThinkingMethod", "get", "register", "available"]
