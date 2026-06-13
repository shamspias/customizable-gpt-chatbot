"""Built-in thinking methods for the MVP: ReAct and plan-and-execute."""

from __future__ import annotations

from loom_thinking.base import ThinkingMethod, register

REACT_PREAMBLE = (
    "Work in a reason→act→observe loop. Before acting, briefly reason about what "
    "you need. When the answer depends on the user's documents, call the search "
    "tool and read the results before concluding. Ground every factual claim in a "
    "tool result and cite it; if the documents don't contain the answer, say so "
    "rather than guessing."
)

PLAN_EXECUTE_PREAMBLE = (
    "First produce a short, explicit plan of the steps required. Then execute the "
    "plan step by step, using tools as needed and adjusting the plan if a step "
    "reveals new information. Do not skip the planning step for non-trivial tasks."
)


def _react() -> ThinkingMethod:
    return ThinkingMethod(
        name="react",
        preamble=REACT_PREAMBLE,
        description="Reason, act with tools, observe — the default for tool-using agents.",
    )


def _plan_execute() -> ThinkingMethod:
    return ThinkingMethod(
        name="plan_execute",
        preamble=PLAN_EXECUTE_PREAMBLE,
        description="Plan upfront, then execute step by step — used by the orchestrator.",
    )


register("react", _react)
register("plan_execute", _plan_execute)
