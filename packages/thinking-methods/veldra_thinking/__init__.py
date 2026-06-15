"""veldra_thinking — pluggable reasoning strategies keyed by AgentSpec.thinking_method."""

# Importing methods registers the built-ins (react, plan_execute) as a side effect.
from veldra_thinking import methods  # noqa: E402,F401
from veldra_thinking.base import ThinkingMethod, available, get, register

__all__ = ["ThinkingMethod", "get", "register", "available"]
