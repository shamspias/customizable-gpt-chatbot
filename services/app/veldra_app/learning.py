"""Self-improvement (Reflexion). The honest "learns and fixes itself" loop for a
spec-driven harness whose model weights we don't train: after a run, reflect on what
happened + the user's feedback to produce ONE concrete lesson (episodic memory) and,
when auto_improve is on, an improved policy. Lessons are injected into the agent's
system prompt at runtime (`lessons_block`) so it stops repeating mistakes over time.
"""

from __future__ import annotations

import json

from veldra_llm import get_provider
from veldra_spec import AgentSpec

from veldra_app import repo
from veldra_app.db import get_sessionmaker
from veldra_app.orchestrator import selfmod

REFLECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["lesson"],
    "properties": {
        "lesson": {
            "type": "string",
            "description": "ONE concrete, actionable instruction that would make the agent "
            "do better next time (e.g. 'Always cite the page number when answering from docs').",
        },
        "improved_prompt": {
            "type": "string",
            "description": "Optional: a better full system_prompt incorporating the lesson; "
            "leave empty to keep the current one.",
        },
    },
}

_MAX_STEPS_IN_CONTEXT = 24


def _transcript(run: dict, steps: list[dict]) -> str:
    lines = [f"Run kind: {run.get('kind')} · status: {run.get('status')}"]
    if run.get("input"):
        lines.append(f"User input: {json.dumps(run['input'])[:600]}")
    for s in steps[:_MAX_STEPS_IN_CONTEXT]:
        payload = json.dumps(s.get("payload") or {})[:200]
        lines.append(f"  [{s['ordinal']}] {s['type']} {s.get('name') or ''} {payload}")
    if run.get("result"):
        lines.append(f"Final answer: {json.dumps(run['result'])[:600]}")
    if run.get("error"):
        lines.append(f"Error: {run['error']}")
    reward = run.get("reward")
    if reward is not None:
        verdict = "👎 negative" if reward < 0 else ("👍 positive" if reward > 0 else "neutral")
        lines.append(f"User rating: {verdict} ({reward})")
    if run.get("feedback"):
        lines.append(f"User note: {run['feedback']}")
    return "\n".join(lines)


def lessons_block(lessons: list[dict]) -> str:
    """Render lessons for injection into a system prompt."""
    if not lessons:
        return ""
    items = "\n".join(f"- {lvl['content']}" for lvl in lessons)
    return f"\n\n## Lessons from experience (apply these)\n{items}"


async def reflect(agent_id: str, run_id: str, tenant_id: str) -> dict:
    """Reflect on one run → store a lesson; if auto_improve, also improve the policy."""
    sm = get_sessionmaker()
    async with sm() as s:
        spec_dict = await repo.get_spec(s, agent_id)
        run = await repo.get_run(s, run_id)
        steps = await repo.get_run_steps(s, run_id)
    if spec_dict is None or run is None:
        raise ValueError("agent or run not found")
    spec = AgentSpec.model_validate(spec_dict)

    provider = get_provider()
    system = (
        "You are an expert coach improving an AI agent. Read what the agent did and the "
        "user's feedback, then write ONE concrete, actionable lesson that would make it do "
        "better next time. Be specific and short. The agent's current policy is:\n\n"
        f"{spec.system_prompt}"
    )
    data = await provider.parse_json(
        model=provider.orchestrator_model, system=system,
        messages=[{"role": "user", "content": _transcript(run, steps)}],
        schema=REFLECT_SCHEMA, max_tokens=600,
    ) or {}
    lesson = str(data.get("lesson", "")).strip()
    improved = str(data.get("improved_prompt", "")).strip()

    if lesson:
        async with sm() as s:
            await repo.add_lesson(s, tenant_id, agent_id, lesson, source_run_id=run_id)
            await repo.insert_audit(
                s, tenant_id, "orchestrator", "reflect", "agent", agent_id,
                {"run_id": run_id, "lesson": lesson},
            )
            await s.commit()

    applied = False
    # Only auto-rewrite the policy when the user opted in; this is a cosmetic edit
    # (prompt only) so it passes the self-mod gate. Tools/teams are never auto-granted.
    if spec.auto_improve and improved and improved != spec.system_prompt:
        try:
            new = spec.model_copy(update={"system_prompt": improved}).model_dump()
            await selfmod.apply(agent_id, new, tenant_id)
            applied = True
        except Exception:  # never let an improvement failure surface to the user
            applied = False

    return {"lesson": lesson, "applied_policy_update": applied}
