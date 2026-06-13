"""Deterministic workflow executor (Dify-style graph).

Interprets an AgentSpec.workflow_graph: start → kb_search / llm / condition → end,
carrying a variable pool between nodes. Strings template with {var}; an `llm` node
streams tokens; `kb_search` emits citations; `condition` routes on substring match.
Yields the same SSE events as the agent loop so the UI is identical.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from veldra_llm import get_provider
from veldra_spec import AgentSpec

from veldra_app.events import ev
from veldra_app.rag import search as rag_search
from veldra_app.runtime.agent import _log_step

# Generous so a thinking model has room to reason AND still emit the answer.
NODE_MAX_TOKENS = 8192
MAX_STEPS = 64

_VAR = re.compile(r"\{(\w+)\}")


def _tmpl(s: str, pool: dict) -> str:
    return _VAR.sub(lambda m: str(pool.get(m.group(1), m.group(0))), s or "")


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
    node_by_id = {n.id: n for n in graph.nodes}
    edges_from: dict[str, list] = {}
    for e in graph.edges:
        edges_from.setdefault(e.source, []).append(e)

    pool: dict[str, str] = {"input": user_input}
    current = graph.entrypoint if graph.entrypoint in node_by_id else None
    if current is None:
        starts = [n.id for n in graph.nodes if n.type == "start"]
        current = starts[0] if starts else (graph.nodes[0].id if graph.nodes else None)

    ordinal = 0
    steps = 0
    answer = ""
    while current and steps < MAX_STEPS:
        steps += 1
        node = node_by_id.get(current)
        if node is None:
            break
        cfg = node.config
        branch: str | None = None
        yield ev("node", id=node.id, type=node.type, label=node.label or node.type)

        if node.type == "kb_search":
            query = _tmpl(cfg.query or "{input}", pool)
            text, cites = await rag_search(
                query=query, kb_ids=spec.knowledge_bases, tenant_id=tenant_id, k=cfg.k
            )
            pool[cfg.output_var or "context"] = text
            pool.setdefault("context", text)
            if cites:
                yield ev("citations", citations=cites)

        elif node.type == "llm":
            prompt = _tmpl(cfg.prompt or "{input}", pool)
            text = ""
            async for e2 in provider.stream_turn(
                model=spec.model, system=spec.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                tools=[], effort=spec.effort, max_tokens=NODE_MAX_TOKENS,
            ):
                if e2["type"] == "text":
                    text += e2["text"]
                    yield ev("token", text=e2["text"])
                elif e2["type"] == "final":
                    text = e2["turn"].text or text
            pool[cfg.output_var or "output"] = text
            pool["output"] = text

        elif node.type == "condition":
            val = str(pool.get(cfg.var, "")).lower()
            branch = "true" if cfg.contains and cfg.contains.lower() in val else "false"

        elif node.type == "end":
            answer = str(pool.get(cfg.output_var or "output", pool.get("output", "")))
            ordinal += 1
            await _log_step(run_id, ordinal, "node", node.type, {"id": node.id})
            yield ev("done", answer=answer)
            return

        ordinal += 1
        await _log_step(run_id, ordinal, "node", node.type, {"id": node.id, "branch": branch})
        current = _next(edges_from, current, branch)

    yield ev("done", answer=pool.get("output", answer))
