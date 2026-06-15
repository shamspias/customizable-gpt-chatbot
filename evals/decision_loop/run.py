"""Decision-loop reliability eval — measures the constrained loop on the live model.

    python -m evals.decision_loop.run        (needs the stack + Ollama running, API on :8000)

To isolate *loop* reliability from *build* flakiness, agents and the KB doc are seeded
DIRECTLY (repo + ingest), not compiled from NL. Each case then runs the real ask SSE
(`/api/agents/{id}/ask`) and we measure, per case:
  • answered      — produced a non-empty final answer
  • called        — invoked the tool the case requires (the right one)
  • nonempty_args — no tool call went out with an all-blank argument (the empty-query bug)
  • halluc        — tool calls outside the granted set (must be 0 — enum makes it impossible)
  • cited         — a RAG case returned citations
  • contains      — the answer contains the expected ground-truth token

Pass bar: answered ≥ 80%, hallucinated == 0, and every case called its tool with non-empty args.
Also asserts `enum` survives `prepare_json_schema` (the property the whole loop rests on).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx
from veldra_app import repo
from veldra_app.config import DEFAULT_TENANT_ID
from veldra_app.db import get_sessionmaker
from veldra_app.rag import ingest_document
from veldra_spec import AgentSpec, ToolBinding

BASE = os.getenv("VELDRA_API_BASE_URL", "http://localhost:8000")
GRANTED = {"kb.search", "math.eval", "http.fetch", "fs.read", "fs.write", "fs.list", "time.now"}

KB_DOC = b"""# Acme Plans

## Free plan
The Free plan includes 1 project and community support only.

## Pro plan
The Pro plan includes unlimited projects, priority email support, and a 30-day
money-back guarantee. It costs 20 dollars per month.
"""


def sse(path: str, payload: dict) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    with httpx.Client(timeout=400) as c, c.stream("POST", BASE + path, json=payload) as r:
        r.raise_for_status()
        ev = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                d = line[5:].strip()
                if d:
                    out.append((ev, json.loads(d)))
    return out


async def seed_agent(name: str, tools: list[str], kbs: list[str], prompt: str) -> str:
    spec = AgentSpec(
        name=name,
        description="eval",
        system_prompt=prompt,
        model="x",  # provider resolves unknown ids to its default model
        thinking_method="react",
        tools=[ToolBinding(name=t, permission_mode="auto") for t in tools],
        knowledge_bases=kbs,
    )
    sm = get_sessionmaker()
    async with sm() as s:
        agent_id, _ = await repo.upsert_agent_spec(
            s, DEFAULT_TENANT_ID, name, spec.model_dump(mode="json"), note="eval"
        )
        await s.commit()
    return agent_id


async def seed_kb() -> str:
    res = await ingest_document(KB_DOC, "acme-plans.md", "text/markdown", DEFAULT_TENANT_ID,
                               kb_name="eval-plans")
    return res.kb_id


CASES = [
    {"name": "eval-rag", "tools": ["kb.search"], "needs_kb": True, "expect_tool": "kb.search",
     "contains": "money-back",
     "prompt": "Answer strictly from the documents and cite the page. If absent, say you "
               "don't know.",
     "ask": "What does the Pro plan include?"},
    {"name": "eval-math", "tools": ["math.eval"], "expect_tool": "math.eval", "contains": "1728",
     "prompt": "Use the math tool to compute; never compute in your head.",
     "ask": "What is 144 * 12?"},
    {"name": "eval-notool", "tools": [],
     "prompt": "A friendly assistant. Reply in one short line.",
     "ask": "Say hello."},
    # Harder: a vague question that is NOT a clean search query — the harness must still
    # ground (proactive kb.search) and fill a non-empty query (U1/U2/U3).
    {"name": "eval-rag-vague", "tools": ["kb.search"], "needs_kb": True, "expect_tool": "kb.search",
     "contains": "money-back",
     "prompt": "Answer only from the documents and cite the page. If absent, say you don't know.",
     "ask": "I'm thinking about paying for the better plan — anything I should know first?"},
    # Harder: a multi-step chain — read the Pro price from the KB, then compute the yearly
    # total. Gate only requires grounding (kb.search) with non-empty args; the 240 synthesis
    # is the stretch goal shown in the table (tests U3/U4 tool-chaining).
    {"name": "eval-chain", "tools": ["kb.search", "math.eval"], "needs_kb": True,
     "expect_tool": "kb.search", "contains": "240",
     "prompt": "Use the documents for facts and the math tool for any calculation. Cite the page.",
     "ask": "The Pro plan price is monthly. What would a full year cost?"},
]


async def run_case(c: dict) -> dict:
    kbs = [await seed_kb()] if c.get("needs_kb") else []
    aid = await seed_agent(c["name"], c["tools"], kbs, c["prompt"])
    payload = {"message": c["ask"], "history": []}
    evs = await asyncio.to_thread(sse, f"/api/agents/{aid}/ask", payload)

    tool_uses = [(d["name"], d.get("input") or {}) for e, d in evs if e == "tool_use"]
    cites = next((d["citations"] for e, d in evs if e == "citations"), [])
    answer = next((d for e, d in evs if e == "done"), {}).get("answer", "") or ""

    hallucinated = [n for n, _ in tool_uses if n not in GRANTED]
    nonempty = all(any(str(v).strip() for v in args.values()) or not args for _, args in tool_uses)
    called = (c.get("expect_tool") in [n for n, _ in tool_uses]) if c.get("expect_tool") else True
    contains = (c["contains"].lower() in answer.lower()) if c.get("contains") else True
    return {
        "name": c["name"], "answered": bool(answer.strip()), "called": called,
        "nonempty_args": nonempty, "halluc": len(hallucinated),
        "cited": (len(cites) > 0) if c.get("needs_kb") else True,
        "contains": contains, "tools": [n for n, _ in tool_uses],
    }


def assert_enum_survives() -> bool:
    from veldra_llm.providers import prepare_json_schema
    s = prepare_json_schema({
        "type": "object", "additionalProperties": False, "required": ["action"],
        "properties": {"action": {"type": "string", "enum": ["a", "b", "final"]}},
    })

    def has_enum(node) -> bool:
        if isinstance(node, dict):
            return "enum" in node or any(has_enum(v) for v in node.values())
        if isinstance(node, list):
            return any(has_enum(v) for v in node)
        return False

    ok = has_enum(s)
    print(f"enum_survives_prepare_json_schema = {ok}")
    return ok


async def main() -> int:
    enum_ok = assert_enum_survives()
    rows = [await run_case(c) for c in CASES]
    print(f"\n{'case':12} answered called nonempty halluc cited contains tools")
    for r in rows:
        print(f"{r['name']:12} {str(r['answered']):8} {str(r['called']):6} "
              f"{str(r['nonempty_args']):8} {r['halluc']:6} {str(r['cited']):5} "
              f"{str(r['contains']):8} {r['tools']}")
    answered = sum(r["answered"] for r in rows) / len(rows)
    halluc = sum(r["halluc"] for r in rows)
    loop_ok = all(r["called"] and r["nonempty_args"] for r in rows)
    ok = enum_ok and answered >= 0.8 and halluc == 0 and loop_ok
    print(f"\nanswered_rate={answered:.0%}  hallucinated_tools={halluc}  "
          f"loop_ok={loop_ok}  ->  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
