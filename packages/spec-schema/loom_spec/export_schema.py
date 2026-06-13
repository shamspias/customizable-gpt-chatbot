"""Export the AgentSpec JSON Schema for the web client to consume.

    python -m loom_spec.export_schema [out_path]

Defaults to apps/web/src/generated/agentspec.schema.json relative to the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from loom_spec.models import AgentSpec


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_out()
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = AgentSpec.model_json_schema()
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out}")


def _default_out() -> Path:
    # packages/spec-schema/loom_spec/export_schema.py -> repo root is parents[3]
    root = Path(__file__).resolve().parents[3]
    return root / "apps" / "web" / "src" / "generated" / "agentspec.schema.json"


if __name__ == "__main__":
    main()
