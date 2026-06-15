"""Understand a request → synthesize a PROPER workflow graph (deterministic).

A sub-1B model can't reliably emit a valid 12-node Dify graph (broken edges, bad
configs — "the workflow is bad"). So the harness does the hard part: it asks the model
a SMALL, constrained question about the task *shape* (does it retrieve? does it route by
category? what are the steps?) and then ASSEMBLES a valid WorkflowGraph from that
understanding. The model understands; the harness builds the graph correctly. The result
is always schema-valid and lint-clean, or we fall back to the (also-reliable) loop.
"""

from __future__ import annotations

import re

from veldra_llm import get_provider
from veldra_spec import AgentSpec, WorkflowGraph

from veldra_app.orchestrator.catalog import lint_spec

UNDERSTAND_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["needs_retrieval", "routes", "steps"],
    "properties": {
        "needs_retrieval": {"type": "boolean"},
        "routes": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
    },
}

UNDERSTAND_SYSTEM = """You analyze a task and describe its WORKFLOW SHAPE so a graph can \
be assembled. Return JSON with exactly:
- needs_retrieval: true ONLY if answering requires searching the user's documents/knowledge base.
- routes: if the task handles different CATEGORIES of input differently (triage / classify / \
route / "if it's X do Y"), list the short lowercase category names (2-5). Otherwise [].
- steps: 2-5 short ordered step labels describing the process the agent follows. Otherwise [].
Be precise. Use empty arrays when something does not apply."""

MAX_ROUTES = 6
MAX_STEPS = 5


async def understand(nl_request: str) -> dict | None:
    """Constrained-decode the task shape (small, reliable on tiny models)."""
    provider = get_provider()
    return await provider.parse_json(
        model=provider.orchestrator_model, system=UNDERSTAND_SYSTEM,
        messages=[{"role": "user", "content": nl_request}],
        schema=UNDERSTAND_SCHEMA, max_tokens=512,
    )


def _node(nid: str, type_: str, label: str, cfg: dict) -> dict:
    return {"id": nid, "type": type_, "label": label, "config": cfg}


def _sid(s: str, i: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:20]
    return f"{base or 'route'}_{i}"


def synthesize(spec: AgentSpec, plan: dict) -> WorkflowGraph | None:
    """Build a valid WorkflowGraph from the understood shape + the spec's KBs."""
    has_kb = bool(spec.knowledge_bases)
    retrieval = bool(plan.get("needs_retrieval")) and has_kb
    routes = [r.strip() for r in (plan.get("routes") or []) if r and r.strip()][:MAX_ROUTES]
    # de-dupe routes (classifier needs distinct classes / distinct edge labels)
    routes = list(dict.fromkeys(routes))
    steps = [s.strip() for s in (plan.get("steps") or []) if s and s.strip()][:MAX_STEPS]

    nodes: list[dict] = [_node("start", "start", "Input", {})]
    edges: list[dict] = []
    cur = "start"
    if retrieval:
        nodes.append(_node("retrieve", "kb_search", "Retrieve",
                           {"query": "{input}", "output_var": "context"}))
        edges.append({"source": "start", "target": "retrieve", "when": None})
        cur = "retrieve"
    ctx = "Use the context to answer.\n\nContext:\n{context}\n\n" if retrieval else ""

    if len(routes) >= 2:
        # classify → one answer branch per route → end
        nodes.append(_node("classify", "classifier", "Classify", {
            "var": "input", "prompt": "Classify the request into one category.",
            "classes": routes, "output_var": "class",
        }))
        edges.append({"source": cur, "target": "classify", "when": None})
        for i, r in enumerate(routes):
            nid = _sid(r, i)
            nodes.append(_node(nid, "llm", r[:32], {
                "prompt": f"{ctx}This request is about '{r}'. Handle it accordingly.\n\nRequest: {{input}}",
                "output_var": "output",
            }))
            edges.append({"source": "classify", "target": nid, "when": r})
            edges.append({"source": nid, "target": "end", "when": None})
        nodes.append(_node("end", "end", "Done", {"output_var": "output"}))

    elif len(steps) >= 2 and not retrieval:
        # a linear chain — one llm node per step, each refining {output}
        prev = cur
        for i, s in enumerate(steps):
            nid = f"step_{i}"
            src = "{input}" if i == 0 else "{output}"
            nodes.append(_node(nid, "llm", s[:32],
                              {"prompt": f"{s}\n\nInput:\n{src}", "output_var": "output"}))
            edges.append({"source": prev, "target": nid, "when": None})
            prev = nid
        nodes.append(_node("end", "end", "Done", {"output_var": "output"}))
        edges.append({"source": prev, "target": "end", "when": None})

    elif retrieval:
        # a clean RAG pipeline: start → retrieve → answer → end
        nodes.append(_node("answer", "llm", "Answer", {
            "prompt": "Answer using the context. Cite the bracketed sources.\n\n"
                      "Context:\n{context}\n\nQuestion: {input}",
            "output_var": "output",
        }))
        edges.append({"source": cur, "target": "answer", "when": None})
        nodes.append(_node("end", "end", "Done", {"output_var": "output"}))
        edges.append({"source": "answer", "target": "end", "when": None})

    else:
        return None  # nothing graph-shaped → the free-form loop handles it better

    try:
        return WorkflowGraph.model_validate({"entrypoint": "start", "nodes": nodes, "edges": edges})
    except Exception:
        return None


async def build_workflow(nl_request: str, spec: AgentSpec, catalog: dict) -> WorkflowGraph | None:
    """Understand the request, synthesize a graph, and only keep it if it lints cleanly."""
    plan = await understand(nl_request)
    if not plan:
        return None
    graph = synthesize(spec, plan)
    if graph is None:
        return None
    trial = spec.model_copy(update={"workflow_graph": graph})
    if lint_spec(trial, catalog):  # referential errors → skip, fall back to the loop
        return None
    return graph
