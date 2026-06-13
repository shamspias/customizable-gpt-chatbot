"""loom_app.orchestrator — NL→AgentSpec compiler + config-only self-modification."""

from loom_app.orchestrator import selfmod
from loom_app.orchestrator.compiler import build_agent, compile_with_repair, parse_spec

__all__ = ["build_agent", "compile_with_repair", "parse_spec", "selfmod"]
