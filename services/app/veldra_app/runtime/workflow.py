"""Deterministic workflow executor (Dify-class graph).

Interprets an AgentSpec.workflow_graph, carrying a typed variable pool between nodes.
Strings template with {var}. Node types:
  start / end            — entry + terminal (end returns output_var or 'output')
  llm                    — prompt an LLM, streaming tokens (per-node model override)
  kb_search              — retrieve from KBs (+ citations); optional mode override
  condition              — legacy substring branch → true/false
  if_else                — operator branch (==, !=, >, <, contains, regex, …) → true/false
  code                   — sandboxed safe-expression transform over variables
  tool                   — invoke a built-in tool (math.eval, time.now, http.fetch, …)
  http                   — HTTP request
  template               — render a text template
  aggregator             — merge several variables/branch outputs into one
  classifier             — LLM intent routing → branches via the chosen class name

Yields the same SSE events as the agent loop so the UI is identical.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from veldra_llm import get_provider
from veldra_mcp import ToolContext
from veldra_spec import AgentSpec

from veldra_app.events import ev
from veldra_app.rag import search as rag_search
from veldra_app.runtime.agent import _log_step
from veldra_app.runtime.sandbox import SandboxError, safe_eval
from veldra_app.tools_registry import get_registry

NODE_MAX_TOKENS = 8192
MAX_STEPS = 96
HTTP_CAP = 16_000

_VAR = re.compile(r"\{(\w+)\}")


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(v)
    return str(v)


def _tmpl(s: str, pool: dict) -> str:
    return _VAR.sub(lambda m: _stringify(pool.get(m.group(1), m.group(0))), s or "")


def _inputs(cfg, pool: dict) -> dict[str, str]:
    """Resolve a node's named inputs (templated) into {name: value}."""
    return {i.name: _tmpl(i.value, pool) for i in cfg.inputs if i.name}


def _compare(op: str, left: Any, right: str) -> bool:
    ls = _stringify(left)
    if op == "contains":
        return right.lower() in ls.lower()
    if op == "not_contains":
        return right.lower() not in ls.lower()
    if op == "empty":
        return not ls.strip()
    if op == "not_empty":
        return bool(ls.strip())
    if op == "regex":
        try:
            return re.search(right, ls) is not None
        except re.error:
            return False
    if op in ("eq", "ne"):
        try:
            equal = float(ls) == float(right)
        except ValueError:
            equal = ls == right
        return equal if op == "eq" else not equal
    if op in ("gt", "lt", "gte", "lte"):
        try:
            a, b = float(ls), float(right)
        except ValueError:
            a, b = ls, right
        return {"gt": a > b, "lt": a < b, "gte": a >= b, "lte": a <= b}[op]
    return False


def _next(edges_from: dict, node_id: str, branch: str | None = None) -> str | None:
    edges = edges_from.get(node_id, [])
    if branch is not None:
        for e in edges:
            if e.when == branch:
                return e.target
    for e in edges:
        if e.when is None:
            return e.target
    return edges[0].target if edges else None


async def run_workflow(
    spec: AgentSpec, user_input: str, *, tenant_id: str, run_id: str
) -> AsyncIterator[dict]:
    graph = spec.workflow_graph
    provider = get_provider()
    registry = get_registry()
    ctx = ToolContext(tenant_id=tenant_id, knowledge_bases=spec.knowledge_bases)
    node_by_id = {n.id: n for n in graph.nodes}
    edges_from: dict[str, list] = {}
    for e in graph.edges:
        edges_from.setdefault(e.source, []).append(e)

    pool: dict[str, Any] = {"input": user_input}
    current = graph.entrypoint if graph.entrypoint in node_by_id else None
    if current is None:
        starts = [n.id for n in graph.nodes if n.type == "start"]
        current = starts[0] if starts else (graph.nodes[0].id if graph.nodes else None)

    def _put(cfg, value: Any) -> None:
        pool[cfg.output_var or "output"] = value
        pool["output"] = value  # last value-producing node = default end output

    ordinal = 0
    steps = 0
    while current and steps < MAX_STEPS:
        steps += 1
        node = node_by_id.get(current)
        if node is None:
            break
        cfg = node.config
        branch: str | None = None
        yield ev("node", id=node.id, type=node.type, label=node.label or node.type)

        if node.type == "kb_search":
            text, cites = await rag_search(
                query=_tmpl(cfg.query or "{input}", pool),
                kb_ids=spec.knowledge_bases, tenant_id=tenant_id, k=cfg.k,
                mode=cfg.mode or None,
            )
            pool[cfg.output_var or "context"] = text
            pool["context"] = text
            pool["output"] = text
            if cites:
                yield ev("citations", citations=cites)

        elif node.type == "llm":
            prompt = _tmpl(cfg.prompt or "{input}", pool)
            text = ""
            async for e2 in provider.stream_turn(
                model=cfg.model or spec.model, system=spec.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                tools=[], effort=spec.effort, max_tokens=NODE_MAX_TOKENS,
            ):
                if e2["type"] == "text":
                    text += e2["text"]
                    yield ev("token", text=e2["text"])
                elif e2["type"] == "final":
                    text = e2["turn"].text or text
            _put(cfg, text)

        elif node.type == "condition":
            val = _stringify(pool.get(cfg.var, "")).lower()
            branch = "true" if cfg.contains and cfg.contains.lower() in val else "false"

        elif node.type == "if_else":
            hit = _compare(cfg.op, pool.get(cfg.var), _tmpl(cfg.value, pool))
            branch = "true" if hit else "false"

        elif node.type == "code":
            variables = {k: v for k, v in pool.items() if k.isidentifier()}
            try:
                result = safe_eval(cfg.code, variables)
            except SandboxError as exc:
                result = f"(code error: {exc})"
            _put(cfg, result)

        elif node.type == "tool":
            args = _inputs(cfg, pool)
            yield ev("tool_use", name=cfg.tool, input=args)
            if registry.has(cfg.tool):
                res = await registry.call(cfg.tool, args, ctx)
                _put(cfg, res.content)
                if res.data.get("citations"):
                    yield ev("citations", citations=res.data["citations"])
                yield ev("tool_result", name=cfg.tool, ok=not res.is_error)
            else:
                _put(cfg, f"(unknown tool: {cfg.tool})")
                yield ev("tool_result", name=cfg.tool, ok=False)

        elif node.type == "http":
            try:
                headers = _inputs_named(cfg.headers, pool)
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    r = await client.request(
                        cfg.method, _tmpl(cfg.url, pool),
                        headers=headers or None,
                        content=_tmpl(cfg.body, pool) or None,
                    )
                _put(cfg, r.text[:HTTP_CAP])
            except Exception as exc:  # network/parse errors shouldn't kill the run
                _put(cfg, f"(http error: {exc})")

        elif node.type == "template":
            _put(cfg, _tmpl(cfg.template, pool))

        elif node.type == "aggregator":
            parts = [v for v in _inputs(cfg, pool).values() if v and v.strip()]
            _put(cfg, "\n\n".join(parts))

        elif node.type == "classifier":
            choice = await _classify(provider, spec, cfg, pool)
            pool[cfg.output_var or "class"] = choice
            pool["output"] = choice
            branch = choice
            yield ev("thinking", text=f"Classified as: {choice}")

        elif node.type == "end":
            answer = _stringify(pool.get(cfg.output_var or "output", pool.get("output", "")))
            ordinal += 1
            await _log_step(run_id, ordinal, "node", node.type, {"id": node.id})
            yield ev("done", answer=answer)
            return

        ordinal += 1
        await _log_step(run_id, ordinal, "node", node.type, {"id": node.id, "branch": branch})
        current = _next(edges_from, current, branch)

    yield ev("done", answer=_stringify(pool.get("output", "")))


def _inputs_named(items, pool: dict) -> dict[str, str]:
    return {i.name: _tmpl(i.value, pool) for i in items if i.name}


async def _classify(provider, spec: AgentSpec, cfg, pool: dict) -> str:
    """Pick one of cfg.classes via constrained decoding (reliable on small models)."""
    classes = [c for c in cfg.classes if c.strip()]
    if not classes:
        return ""
    prompt = _tmpl(cfg.prompt or "Classify the input.", pool)
    text = _stringify(pool.get(cfg.var) or pool.get("input", ""))
    schema = {
        "type": "object", "additionalProperties": False, "required": ["choice"],
        "properties": {"choice": {"type": "string", "enum": classes}},
    }
    user = f"{prompt}\n\nInput:\n{text}\n\nCategories: {classes}"
    data = await provider.parse_json(
        model=cfg.model or spec.model,
        system=f"{spec.system_prompt}\n\nChoose exactly one category for the input.",
        messages=[{"role": "user", "content": user}],
        schema=schema, max_tokens=256,
    )
    choice = (data or {}).get("choice", "")
    return choice if choice in classes else classes[0]
