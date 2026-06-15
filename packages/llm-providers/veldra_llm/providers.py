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
    # Token usage for this turn (normalized across providers). Keys:
    #   input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
    usage: dict = field(default_factory=dict)


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


_RETRY_STATUS = {429, 500, 502, 503, 504}


async def _with_retries(call, attempts: int = 3, base: float = 0.5):
    """Retry a coroutine factory on transient transport errors (timeouts, 5xx/429)."""
    import asyncio

    last: Exception | None = None
    for i in range(attempts):
        try:
            return await call()
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRY_STATUS or i == attempts - 1:
                raise
            last = e
        except (httpx.TimeoutException, httpx.TransportError) as e:
            if i == attempts - 1:
                raise
            last = e
        await asyncio.sleep(base * (2**i))
    raise last  # pragma: no cover


def salvage_json(text: str) -> dict | None:
    """Best-effort parse of model JSON: strip code fences, take the first balanced
    {...}, then json.loads. Small models often wrap JSON in prose/fences."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class BaseProvider:
    default_model: str = ""        # serves agent runs
    orchestrator_model: str = ""   # serves NL->spec compilation
    prefers_structured: bool = False  # small/local models: drive a constrained decision loop

    def resolve(self, model: str | None) -> str:
        return model or self.default_model

    async def stream_turn(self, **kwargs) -> AsyncIterator[dict]:  # pragma: no cover
        raise NotImplementedError
        yield  # makes this an async generator

    async def parse_json(self, **kwargs) -> dict | None:  # pragma: no cover
        raise NotImplementedError


def _local_resolve(provider: BaseProvider, model: str | None) -> str:
    """For non-Anthropic backends: honor only this provider's own model names so a
    Claude-defaulted spec.model never leaks to Ollama/OpenAI; otherwise fall back."""
    if model in (provider.default_model, provider.orchestrator_model):
        return model  # type: ignore[return-value]
    return provider.default_model


# ───────────────────────── Anthropic ─────────────────────────
class AnthropicProvider(BaseProvider):
    def __init__(
        self, default_model: str = "claude-sonnet-4-6", orchestrator_model: str = "claude-opus-4-8"
    ) -> None:
        from veldra_llm.chat import get_client

        self.client = get_client()
        self.default_model = default_model
        self.orchestrator_model = orchestrator_model

    # Anthropic: trust any Claude model name (per-agent choice is valid).
    def resolve(self, model: str | None) -> str:
        return model or self.default_model

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
            # Cache the (stable) system prompt: it's identical across a turn's tool loop
            # and across multi-turn history, so it caches after turn 1 — cache reads bill
            # at ~10% of input. A no-op on the other providers.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": self._to_native(messages),
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": effort},
        }
        if tools:
            # Mark the end of the (stable) tool block as a cache breakpoint too.
            cached = [dict(t) for t in tools]
            cached[-1] = {**cached[-1], "cache_control": {"type": "ephemeral"}}
            kwargs["tools"] = cached
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
        u = getattr(final, "usage", None)
        usage = {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        } if u else {}
        yield {"type": "final", "turn": Turn(text, calls, stop, raw=final.content, usage=usage)}

    async def parse_json(self, *, model, system, messages, schema, max_tokens, meter=None) -> dict | None:
        resp = await self.client.messages.create(
            model=self.resolve(model),
            max_tokens=max_tokens,
            # Cache the (stable) system prompt here too, matching stream_turn.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=self._to_native(messages),
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if meter is not None:
            u = getattr(resp, "usage", None)
            if u:
                meter.add({
                    "input_tokens": getattr(u, "input_tokens", 0) or 0,
                    "output_tokens": getattr(u, "output_tokens", 0) or 0,
                    "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                    "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
                })
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


# ───────────────────────── Ollama (local) ─────────────────────────
class OllamaProvider(BaseProvider):
    prefers_structured = True  # local models: use the constrained decision loop

    def __init__(
        self, base_url: str, model: str, orchestrator_model: str = "", think: bool = False
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = model
        self.orchestrator_model = orchestrator_model or model
        # Off by default: small thinking models (qwen3) over-reason while STREAMING and
        # never emit the answer (content stays empty). Disabling gives direct, reliable
        # output and is harmless on non-thinking models. Set VELDRA_OLLAMA_THINK=true to re-enable.
        self.think = think

    def resolve(self, model: str | None) -> str:
        return _local_resolve(self, model)

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
            "think": self.think,
            "messages": self._to_native(system, messages),
            "options": {"num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = self._to_native_tools(tools)

        text = ""
        raw_calls: list[dict] = []
        usage: dict = {}
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
                        usage = {
                            "input_tokens": chunk.get("prompt_eval_count", 0) or 0,
                            "output_tokens": chunk.get("eval_count", 0) or 0,
                        }
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
        yield {"type": "final", "turn": Turn(text, calls, stop, raw=raw, usage=usage)}

    async def parse_json(self, *, model, system, messages, schema, max_tokens, meter=None) -> dict | None:
        payload = {
            "model": self.resolve(model),
            "stream": False,
            "think": self.think,
            "messages": self._to_native(system, messages),
            "format": schema,  # Ollama constrains output to this JSON schema
            "options": {"num_predict": max_tokens, "temperature": 0},  # greedy: stable for tiny models
        }
        async def _call():
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{self.base_url}/api/chat", json=payload)
                r.raise_for_status()
                return r.json()

        data = await _with_retries(_call)
        if meter is not None:
            meter.add({"input_tokens": data.get("prompt_eval_count", 0) or 0,
                       "output_tokens": data.get("eval_count", 0) or 0})
        return salvage_json((data.get("message") or {}).get("content", ""))


# ───────────────────────── OpenAI-compatible (OpenAI / Groq / OpenRouter / vLLM / LM Studio) ──
def _openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": t["input_schema"]}}
        for t in tools
    ]


class OpenAICompatProvider(BaseProvider):
    prefers_structured = True  # treat as a local/small-model tier; use the decision loop

    def __init__(self, base_url: str, api_key: str, model: str, orchestrator_model: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = model
        self.orchestrator_model = orchestrator_model or model

    def resolve(self, model: str | None) -> str:
        return _local_resolve(self, model)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _to_native(self, system: str, messages: list[dict]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            if role == "assistant":
                msg: dict = {"role": "assistant", "content": m.get("content") or None}
                raw = m.get("raw") or {}
                if raw.get("tool_calls"):
                    msg["tool_calls"] = raw["tool_calls"]
                out.append(msg)
            elif role == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    async def stream_turn(
        self, *, model, system, messages, tools, effort, max_tokens
    ) -> AsyncIterator[dict]:
        payload: dict = {
            "model": self.resolve(model), "stream": True,
            "stream_options": {"include_usage": True},  # final chunk carries token usage
            "messages": self._to_native(system, messages), "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = _openai_tools(tools)
        text = ""
        slots: dict[int, dict] = {}
        usage: dict = {}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    obj = json.loads(data)
                    if obj.get("usage"):  # usage chunk (choices is usually empty here)
                        u = obj["usage"]
                        usage = {
                            "input_tokens": u.get("prompt_tokens", 0) or 0,
                            "output_tokens": u.get("completion_tokens", 0) or 0,
                        }
                    delta = ((obj.get("choices") or [{}])[0]).get("delta") or {}
                    if delta.get("content"):
                        text += delta["content"]
                        yield {"type": "text", "text": delta["content"]}
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        slot = slots.setdefault(idx, {"id": f"call_{idx}", "name": "", "args": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["args"] += fn["arguments"]
        calls, raw_calls = [], []
        for idx in sorted(slots):
            s = slots[idx]
            try:
                args = json.loads(s["args"]) if s["args"] else {}
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=s["id"], name=s["name"], arguments=args))
            raw_calls.append({"id": s["id"], "type": "function",
                              "function": {"name": s["name"], "arguments": s["args"] or "{}"}})
        raw = {"role": "assistant", "content": text or None}
        if raw_calls:
            raw["tool_calls"] = raw_calls
        yield {"type": "final",
               "turn": Turn(text, calls, "tool_use" if calls else "end_turn", raw=raw, usage=usage)}

    async def parse_json(self, *, model, system, messages, schema, max_tokens, meter=None) -> dict | None:
        payload = {
            "model": self.resolve(model), "stream": False, "temperature": 0,
            "messages": self._to_native(system, messages), "max_tokens": max_tokens,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "Decision", "schema": schema, "strict": True}},
        }
        async def _call():
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
                )
                r.raise_for_status()
                return r.json()

        data = await _with_retries(_call)
        if meter is not None and data.get("usage"):
            u = data["usage"]
            meter.add({"input_tokens": u.get("prompt_tokens", 0) or 0,
                       "output_tokens": u.get("completion_tokens", 0) or 0})
        return salvage_json((data["choices"][0]["message"].get("content")) or "")


@functools.lru_cache
def get_provider() -> BaseProvider:
    kind = os.getenv("VELDRA_LLM_PROVIDER", "anthropic").lower()
    if kind == "ollama":
        return OllamaProvider(
            os.getenv("VELDRA_OLLAMA_BASE_URL", "http://localhost:11434"),
            os.getenv("VELDRA_OLLAMA_MODEL", "qwen3.5:0.8b"),
            os.getenv("VELDRA_OLLAMA_ORCHESTRATOR_MODEL", ""),
            think=os.getenv("VELDRA_OLLAMA_THINK", "false").lower() in ("1", "true", "yes"),
        )
    if kind == "openai":
        return OpenAICompatProvider(
            os.getenv("VELDRA_OPENAI_BASE_URL", "https://api.openai.com/v1"),
            os.getenv("OPENAI_API_KEY", ""),
            os.getenv("VELDRA_OPENAI_MODEL", "gpt-4o-mini"),
            os.getenv("VELDRA_OPENAI_ORCHESTRATOR_MODEL", ""),
        )
    return AnthropicProvider(
        os.getenv("VELDRA_WORKER_MODEL", "claude-sonnet-4-6"),
        os.getenv("VELDRA_ORCHESTRATOR_MODEL", "claude-opus-4-8"),
    )
