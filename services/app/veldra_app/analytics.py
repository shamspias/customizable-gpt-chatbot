"""Analytics rollups over the durable runs log.

Where aura-proto's Reflex aggregates a bounded in-memory ring buffer, this queries
the full persisted history (runs + result usage + feedback) — so totals, cost, and
reward distributions are real, not a recent-window approximation. Pure functions over
plain run dicts (from repo.analytics_rows) so they're trivially testable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _dur_ms(row: dict) -> float | None:
    a, b = row.get("created_at"), row.get("finished_at")
    if isinstance(a, datetime) and isinstance(b, datetime):
        return max(0.0, (b - a).total_seconds() * 1000)
    return None


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round((p / 100) * (len(s) - 1))))
    return round(s[k], 1)


def compute(rows: list[dict]) -> dict[str, Any]:
    total = len(rows)
    by_status: dict[str, int] = {}
    durations: list[float] = []
    cost_total = 0.0
    tokens_total = 0
    by_model: dict[str, dict] = {}
    per_agent: dict[str, dict] = {}
    rewards: list[float] = []
    errors: list[dict] = []

    for r in rows:
        st = r.get("status") or "unknown"
        by_status[st] = by_status.get(st, 0) + 1

        d = _dur_ms(r)
        if d is not None and r.get("kind") == "ask":
            durations.append(d)

        usage = (r.get("result") or {}).get("usage") or {}
        cost = float(usage.get("cost_usd") or 0)
        toks = int(usage.get("total_tokens") or 0)
        cost_total += cost
        tokens_total += toks
        model = usage.get("model")
        if model:
            m = by_model.setdefault(model, {"model": model, "runs": 0, "tokens": 0, "cost_usd": 0.0})
            m["runs"] += 1
            m["tokens"] += toks
            m["cost_usd"] = round(m["cost_usd"] + cost, 6)

        aid = r.get("agent_id")
        if aid:
            a = per_agent.setdefault(aid, {
                "agent_id": aid, "name": r.get("agent_name") or "—",
                "runs": 0, "done": 0, "error": 0, "tokens": 0, "cost_usd": 0.0,
                "_rewards": [],
            })
            a["runs"] += 1
            if st == "done":
                a["done"] += 1
            elif st == "error":
                a["error"] += 1
            a["tokens"] += toks
            a["cost_usd"] = round(a["cost_usd"] + cost, 6)
            if r.get("reward") is not None:
                a["_rewards"].append(float(r["reward"]))

        if r.get("reward") is not None:
            rewards.append(float(r["reward"]))

        if st == "error" and r.get("error"):
            errors.append({
                "id": r.get("id"), "agent": r.get("agent_name") or "—",
                "error": str(r["error"])[:300], "at": r.get("created_at"),
            })

    agents = []
    for a in per_agent.values():
        rw = a.pop("_rewards")
        a["success_rate"] = round(a["done"] / a["runs"], 3) if a["runs"] else 0.0
        a["avg_reward"] = round(sum(rw) / len(rw), 2) if rw else None
        a["thumbs_up"] = sum(1 for x in rw if x > 0)
        a["thumbs_down"] = sum(1 for x in rw if x < 0)
        agents.append(a)
    agents.sort(key=lambda x: x["runs"], reverse=True)

    done = by_status.get("done", 0)
    asked = sum(1 for r in rows if r.get("kind") == "ask")
    suggestions = _suggest(agents, rows)

    return {
        "total_runs": total,
        "by_status": by_status,
        "success_rate": round(done / total, 3) if total else 0.0,
        "ask_runs": asked,
        "latency_ms": {"p50": _pct(durations, 50), "p95": _pct(durations, 95),
                       "max": round(max(durations), 1) if durations else 0.0},
        "cost_usd_total": round(cost_total, 4),
        "tokens_total": tokens_total,
        "by_model": sorted(by_model.values(), key=lambda x: x["cost_usd"], reverse=True),
        "agents": agents,
        "reward": {
            "count": len(rewards),
            "thumbs_up": sum(1 for x in rewards if x > 0),
            "thumbs_down": sum(1 for x in rewards if x < 0),
            "avg": round(sum(rewards) / len(rewards), 2) if rewards else None,
        },
        "errors": errors[:15],
        "suggestions": suggestions,
    }


def _suggest(agents: list[dict], rows: list[dict]) -> list[dict]:
    """Heuristic tuning proposals — the seed for closing the improve loop later."""
    out: list[dict] = []
    for a in agents:
        if a["runs"] >= 5 and a["error"] / a["runs"] >= 0.3:
            out.append({"agent": a["name"], "severity": "high",
                        "text": f"{a['name']}: {round(100 * a['error'] / a['runs'])}% of runs errored — "
                                "review its tools/policy or raise its step limit."})
        if a["thumbs_down"] >= 3 and (a["avg_reward"] or 0) < 0:
            out.append({"agent": a["name"], "severity": "medium",
                        "text": f"{a['name']}: consistently low ratings — consider refining its "
                                "policy or attaching a skill/KB (auto-improve can learn from 👎)."})
    return out
