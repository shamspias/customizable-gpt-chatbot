"""Agent routing: given a free-text message and the workspace's agent roster, pick the
best existing agent — or signal that none fits so the caller can build one. A cheap,
constrained classification reusing the provider's structured-output path."""

from __future__ import annotations

from veldra_llm import get_provider

ROUTE_THRESHOLD = 0.45  # below this confidence we propose building a new agent

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["agent_id", "confidence"],
    "properties": {
        "agent_id": {"type": ["string", "null"],
                     "description": "id of the best-matching agent, or null if none fits"},
        "confidence": {"type": "number", "description": "0..1 how well it fits"},
        "reason": {"type": "string"},
    },
}

_SYSTEM = (
    "You route a user's message to the single best existing agent for the job. "
    "Match on what each agent is for (its name and description). If no agent is a good "
    "fit, return agent_id=null with low confidence — do not force a poor match."
)


async def route_message(message: str, roster: list[dict]) -> dict:
    """Return {action: route|create, agent_id, confidence, reason, candidates}."""
    candidates = [
        {"id": str(a["id"]), "name": a.get("name") or "",
         "description": (a.get("description") or "")[:200]}
        for a in roster
    ][:40]
    if not candidates:
        return {"action": "create", "agent_id": None, "confidence": 0.0,
                "reason": "No agents yet — build one.", "candidates": []}

    listing = "\n".join(
        f'- id={c["id"]} · "{c["name"]}": {c["description"] or "(no description)"}'
        for c in candidates
    )
    provider = get_provider()
    try:
        data = await provider.parse_json(
            model=provider.resolve(None),
            system=_SYSTEM,
            messages=[{"role": "user",
                       "content": f"Message:\n{message}\n\nAgents:\n{listing}\n\n"
                                  "Return the best agent's id (verbatim) or null."}],
            schema=_SCHEMA,
            max_tokens=200,
        ) or {}
    except Exception:  # noqa: BLE001 — routing must never hard-fail the request
        data = {}

    ids = {c["id"] for c in candidates}
    agent_id = data.get("agent_id")
    confidence = float(data.get("confidence") or 0.0)
    matched = agent_id in ids and confidence >= ROUTE_THRESHOLD
    return {
        "action": "route" if matched else "create",
        "agent_id": agent_id if matched else None,
        "confidence": confidence,
        "reason": data.get("reason", ""),
        "candidates": candidates[:5],
    }
