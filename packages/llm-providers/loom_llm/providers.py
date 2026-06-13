"""Provider-pluggable LLM layer.

The runtime and orchestrator speak a small normalized interface so the same agent
loop runs on Anthropic OR a local Ollama model. Two methods cover the platform:

  stream_turn(...) -> async iterator of {"type":"text"|"thinking","text":...}
                      ending with {"type":"final","turn": Turn}
  parse_json(...)  -> dict | None   (constrained/structured output)

Normalized messages (provider-agnostic):
  {"role": "user",      "content": str}
  {"role": "assistant", "content": str, "tool_calls": [ToolCall]?, "raw": <opaque>?}
  {"role": "tool",      "tool_call_id": str, "content": str, "is_error": bool?}

`raw` is an opaque native assistant payload appended verbatim on the next turn —
this is how the Anthropic path preserves thinking blocks (the design's "Python
owns the opaque conversation blob" rule) while staying provider-agnostic.
"""

from __future__ import annotations

import functools
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

# Numeric/length constraints structured-output grammars don't support; we strip
# them before sending and rely on client-side Pydantic validation instead.
_UNSUPPORTED = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "pattern", "minItems", "maxItems",
}


@dataclass
class ToolCall:
    id: str
    name: str  # wire name, e.g. "kb__search"
    arguments: dict


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # end_turn | tool_use | refusal | error
    raw: Any = None  # opaque native assistant content, re-sent verbatim


def _deref(schema: dict) -> dict:
    """Inline $defs/$ref into a self-contained schema (AgentSpec is non-recursive)."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                merged = {k: v for k, v in node.items() if k != "$ref"}
                return {**resolve(defs.get(name, {})), **merged}
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve({k: v for k, v in schema.items() if k != "$defs"})


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k not in _UNSUPPORTED}
    if isinstance(node, list):
        return [_strip(x) for x in node]
    return node


def prepare_json_schema(schema: dict) -> dict:
    """Dereference + strip unsupported keywords so the schema works as a
    constrained-decoding grammar on either provider."""
    return _strip(_deref(schema))


class BaseProvider:
    default_model: str = ""

    def resolve(self, model: str | None) -> str:
        return model or self.default_model

    async def stream_turn(self, **kwargs) -> AsyncIterator[dict]:  # pragma: no cover
        raise NotImplementedError
        yield  # makes this an async generator

    async def parse_json(self, **kwargs) -> dict | None:  # pragma: no cover
        raise NotImplementedError


# ───────────────────────── Anthropic ─────────────────────────
class AnthropicProvider(BaseProvider):
    def __init__(self, default_model: str = "claude-sonnet-4-6") -> None:
        from loom_llm.chat import get_client

        self.client = get_client()
        self.default_model = default_model

    def _to_native(self, messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        pending: list[dict] = []

        def flush() -> None:
            nonlocal pending
            if pending:
                out.append({"role": "user", "content": pending})
                pending = []

        for m in messages:
            role = m["role"]
            if role == "tool":
                pending.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m["content"],
                        "is_error": bool(m.get("is_error")),
                    }
                )
                continue
            flush()
            if role == "user":
                out.append({"role": "user", "content": m["content"]})
            elif role == "assistant":
                out.append({"role": "assistant", "content": m.get("raw") or m.get("content", "")})
        flush()
        return out

    async def stream_turn(
        self, *, model, system, messages, tools, effort, max_tokens
    ) -> AsyncIterator[dict]:
        kwargs: dict = {
            "model": self.resolve(model),
            "max_tokens": max_tokens,
            "system": system,
            "messages": self._to_native(messages),
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": effort},
        }
        if tools:
            kwargs["tools"] = tools
        text = ""
        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    d = event.delta
                    if d.type == "text_delta":
                        text += d.text
                        yield {"type": "text", "text": d.text}
                    elif d.type == "thinking_delta":
                        yield {"type": "thinking", "text": d.thinking}
            final = await stream.get_final_message()

        calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input)
            for b in final.content
            if b.type == "tool_use"
        ]
        sr = final.stop_reason
        stop = "tool_use" if sr == "tool_use" else "refusal" if sr == "refusal" else "end_turn"
        yield {"type": "final", "turn": Turn(text, calls, stop, raw=final.content)}

    async def parse_json(self, *, model, system, messages, schema, max_tokens) -> dict | None:
        resp = await self.client.messages.create(
            model=self.resolve(model),
            max_tokens=max_tokens,
            system=system,
            messages=self._to_native(messages),
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


# ───────────────────────── Ollama (local) ─────────────────────────
class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = model

    def resolve(self, model: str | None) -> str:
        # Single local model serves every role in this deployment.
        return self.default_model

    def _to_native(self, system: str, messages: list[dict]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            if role == "assistant":
                raw = m.get("raw") or {}
                msg = {"role": "assistant", "content": m.get("content", "")}
                if raw.get("tool_calls"):
                    msg["tool_calls"] = raw["tool_calls"]
                out.append(msg)
            elif role == "tool":
                out.append({"role": "tool", "content": m["content"]})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    @staticmethod
    def _to_native_tools(tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    async def stream_turn(
        self, *, model, system, messages, tools, effort, max_tokens
    ) -> AsyncIterator[dict]:
        payload: dict = {
            "model": self.resolve(model),
            "stream": True,
            "messages": self._to_native(system, messages),
            "options": {"num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = self._to_native_tools(tools)

        text = ""
        raw_calls: list[dict] = []
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    msg = chunk.get("message") or {}
                    if msg.get("thinking"):
                        yield {"type": "thinking", "text": msg["thinking"]}
                    if msg.get("content"):
                        text += msg["content"]
                        yield {"type": "text", "text": msg["content"]}
                    if msg.get("tool_calls"):
                        raw_calls.extend(msg["tool_calls"])
                    if chunk.get("done"):
                        break

        calls: list[ToolCall] = []
        for i, tc in enumerate(raw_calls):
            fn = tc.get("function", {})
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=f"call_{i}", name=fn.get("name", ""), arguments=args or {}))

        stop = "tool_use" if calls else "end_turn"
        raw = {"role": "assistant", "content": text}
        if raw_calls:
            raw["tool_calls"] = raw_calls
        yield {"type": "final", "turn": Turn(text, calls, stop, raw=raw)}

    async def parse_json(self, *, model, system, messages, schema, max_tokens) -> dict | None:
        payload = {
            "model": self.resolve(model),
            "stream": False,
            "messages": self._to_native(system, messages),
            "format": schema,  # Ollama constrains output to this JSON schema
            "options": {"num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (data.get("message") or {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


@functools.lru_cache
def get_provider() -> BaseProvider:
    kind = os.getenv("LOOM_LLM_PROVIDER", "anthropic").lower()
    if kind == "ollama":
        return OllamaProvider(
            os.getenv("LOOM_OLLAMA_BASE_URL", "http://localhost:11434"),
            os.getenv("LOOM_OLLAMA_MODEL", "qwen3:0.6b"),
        )
    return AnthropicProvider(os.getenv("LOOM_WORKER_MODEL", "claude-sonnet-4-6"))
