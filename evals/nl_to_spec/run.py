"""Run the NL→spec accuracy suite against the live compiler.

    python -m evals.nl_to_spec.run    (requires ANTHROPIC_API_KEY)

Uses a synthetic catalog (real tool list + a fake KB id) so the suite exercises
the compiler + linter + repair loop WITHOUT needing Postgres. Exits non-zero if
accuracy falls below the target.
"""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console

from evals.nl_to_spec.cases import CASES, TARGET_ACCURACY
from veldra_app.orchestrator.compiler import _system_prompt, compile_with_repair
from veldra_app.tools_registry import get_registry

console = Console()
FAKE_KB = "00000000-0000-0000-0000-0000000000ab"


def _catalog() -> dict:
    return {"tools": get_registry().catalog(), "kb_id": FAKE_KB, "kb_name": "default"}


def _check(spec, expect: dict) -> tuple[bool, str]:
    if spec is None:
        return False, "compiler returned no valid spec"
    if not (spec.name and spec.system_prompt and len(spec.system_prompt) > 40):
        return False, "name/system_prompt missing or too short"
    has_kb = "kb.search" in spec.tool_keys() and bool(spec.knowledge_bases)
    if expect.get("needs_kb") and not has_kb:
        return False, "expected kb.search + attached KB, but it was not granted"
    if expect.get("no_tools") and spec.tools:
        return False, f"expected no tools, got {sorted(spec.tool_keys())}"
    return True, "ok"


async def main() -> int:
    catalog = _catalog()
    system = _system_prompt(catalog)
    passed = 0
    for case in CASES:
        spec, errors = await compile_with_repair(
            system, [{"role": "user", "content": case["request"]}], catalog
        )
        ok, detail = _check(spec, case["expect"])
        passed += ok
        mark = "[green]PASS[/]" if ok else "[red]FAIL[/]"
        console.print(f"{mark} {case['name']}: {detail}")
        if not ok and errors:
            console.print(f"      [dim]{'; '.join(errors)}[/]")

    accuracy = passed / len(CASES)
    console.print(f"\naccuracy: {passed}/{len(CASES)} = {accuracy:.0%} (target {TARGET_ACCURACY:.0%})")
    return 0 if accuracy >= TARGET_ACCURACY else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
