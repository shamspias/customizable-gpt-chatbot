"""Pluggable reasoning strategies, keyed by AgentSpec.thinking_method.

A thinking method shapes how the agent reasons. In the MVP it contributes a
system-prompt preamble (and could tune effort). New methods register a factory —
no core change. This is the seam for Reflexion / Tree-of-Thought / Debate later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ThinkingMethod:
    name: str
    preamble: str
    description: str = ""


_REGISTRY: dict[str, Callable[[], ThinkingMethod]] = {}


def register(name: str, factory: Callable[[], ThinkingMethod]) -> None:
    _REGISTRY[name] = factory


def get(name: str) -> ThinkingMethod:
    factory = _REGISTRY.get(name)
    if factory is None:  # forward-compat: unknown method falls back to react
        factory = _REGISTRY["react"]
    return factory()


def available() -> list[str]:
    return sorted(_REGISTRY)
