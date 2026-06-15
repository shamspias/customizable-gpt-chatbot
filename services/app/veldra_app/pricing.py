"""Token pricing + a per-run usage meter (transparent cost accounting).

Every agent run accumulates the token usage reported by the provider and prices it
against MODEL_PRICING, so the UI can show model · tokens · $cost · cache-hit-rate
per message and analytics can roll spend up over history. Local models price at $0.
"""

from __future__ import annotations

from dataclasses import dataclass

# USD per 1M tokens: (input, output). Cache read = 10% of input, cache write = 125%
# of input (Anthropic ephemeral-cache pricing). Unknown/local models → $0.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5": (10.0, 50.0),
    # common OpenAI-compatible models (best-effort; extend as needed)
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
}
CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25


def price_for(model: str) -> tuple[float, float]:
    return MODEL_PRICING.get(model, (0.0, 0.0))


@dataclass
class UsageMeter:
    """Accumulates per-turn token usage across an agent loop and prices it."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, usage: dict | None) -> None:
        if not usage:
            return
        self.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.output_tokens += int(usage.get("output_tokens", 0) or 0)
        self.cache_read_tokens += int(usage.get("cache_read_tokens", 0) or 0)
        self.cache_write_tokens += int(usage.get("cache_write_tokens", 0) or 0)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens + self.output_tokens
            + self.cache_read_tokens + self.cache_write_tokens
        )

    def cost_usd(self, model: str) -> float:
        p_in, p_out = price_for(model)
        cost = (
            self.input_tokens * p_in
            + self.output_tokens * p_out
            + self.cache_read_tokens * p_in * CACHE_READ_MULT
            + self.cache_write_tokens * p_in * CACHE_WRITE_MULT
        ) / 1_000_000
        return round(cost, 6)

    def cache_hit_rate(self) -> float:
        prompt = self.input_tokens + self.cache_read_tokens + self.cache_write_tokens
        return round(self.cache_read_tokens / prompt, 4) if prompt else 0.0

    def has_data(self) -> bool:
        return self.total_tokens > 0

    def payload(self, model: str) -> dict:
        """The dict shape for an SSE 'usage' event and the persisted run usage."""
        return {
            "model": model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd(model),
            "cache_hit_rate": self.cache_hit_rate(),
        }
