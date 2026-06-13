"""veldra_thinking — pluggable reasoning strategies keyed by AgentSpec.thinking_method."""

from veldra_thinking.base import ThinkingMethod, available, get, register

# Importing methods registers the built-ins (react, plan_execute) as a side effect.
from veldra_thinking import methods  # noqa: E402,F401

__all__ = ["ThinkingMethod", "get", "register", "available"]
