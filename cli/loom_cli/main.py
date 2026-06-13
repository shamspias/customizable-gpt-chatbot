"""loom — thin CLI over the same HTTP/SSE endpoints the web app uses.

    loom kb add <file>
    loom build "answer from my docs with citations"
    loom ask "what does section 3 say?"   [--agent <id>]
    loom agents
    loom selfmod <agent_id> "make answers more concise" [--apply]
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import typer
from rich.console import Console

app = typer.Typer(add_completion=False, help="Loom CLI — talk an agent into existence.")
console = Console()

STATE_DIR = Path(".loom")
LAST_AGENT = STATE_DIR / "last_agent"


def base_url() -> str:
    return os.getenv("LOOM_API_BASE_URL", "http://localhost:8000").rstrip("/")


def _save_agent(agent_id: str) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    LAST_AGENT.write_text(agent_id)


def _last_agent() -> str | None:
    return LAST_AGENT.read_text().strip() if LAST_AGENT.exists() else None


def stream_sse(path: str, payload: dict) -> Iterator[tuple[str | None, dict]]:
    with httpx.Client(timeout=None) as client:
        with client.stream("POST", base_url() + path, json=payload) as resp:
            resp.raise_for_status()
            event: str | None = None
            for line in resp.iter_lines():
                if not line:
                    event = None
                    continue
                if line.startswith(":"):  # SSE comment / heartbeat
                    continue
                if line.startswith("event:"):
                    event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    raw = line[len("data:"):].strip()
                    yield event, (json.loads(raw) if raw else {})


@app.command("kb")
def kb(action: str, path: str) -> None:
    """Knowledge base ops. Currently: `loom kb add <file>`."""
    if action != "add":
        console.print(f"[red]unknown kb action:[/] {action} (try: add)")
        raise typer.Exit(2)
    p = Path(path)
    if not p.exists():
        console.print(f"[red]no such file:[/] {path}")
        raise typer.Exit(1)
    with httpx.Client(timeout=300) as client:
        resp = client.post(
            base_url() + "/api/kb/upload",
            files={"file": (p.name, p.read_bytes(), "application/octet-stream")},
        )
    resp.raise_for_status()
    r = resp.json()
    console.print(
        f"[green]ingested[/] {r['filename']}: {r['num_pages']} pages, "
        f"{r['num_chunks']} chunks (kb {r['kb_id']})"
    )


@app.command()
def build(request: str, key: str = typer.Option(None, help="idempotency key")) -> None:
    """Design an agent from a natural-language request."""
    payload = {"request": request}
    if key:
        payload["idempotency_key"] = key
    agent_id = None
    for event, data in stream_sse("/api/agents/build", payload):
        if event == "status":
            console.print(f"[dim]· {data.get('phase')}[/]")
        elif event == "spec":
            agent_id = data.get("agent_id")
            spec = data.get("spec", {})
            console.print(f"\n[bold green]Built agent:[/] {spec.get('name')} ({agent_id})")
            console.print(f"  model: {spec.get('model')}  thinking: {spec.get('thinking_method')}")
            tools = [f"{t['mcp_server']}.{t['tool_name']}" for t in spec.get("tools", [])]
            console.print(f"  tools: {tools or 'none'}")
            console.print(f"  policy: [dim]{(spec.get('system_prompt') or '')[:160]}…[/]")
        elif event == "error":
            console.print(f"[red]{data.get('message')}[/]")
    if agent_id:
        _save_agent(agent_id)
        console.print("\n[dim](saved as default agent; use `loom ask`)[/]")


@app.command()
def ask(question: str, agent: str = typer.Option(None, help="agent id (defaults to last built)")) -> None:
    """Ask the agent a question (streamed answer with citations)."""
    agent_id = agent or _last_agent()
    if not agent_id:
        console.print("[red]no agent specified and none saved — run `loom build` first[/]")
        raise typer.Exit(1)
    citations: list[dict] = []
    console.print()
    for event, data in stream_sse(f"/api/agents/{agent_id}/ask", {"message": question}):
        if event == "token":
            console.print(data.get("text", ""), end="")
        elif event == "tool_use":
            console.print(f"\n[dim]→ {data.get('name')}({json.dumps(data.get('input'))})[/]")
        elif event == "citations":
            citations = data.get("citations", [])
        elif event == "error":
            console.print(f"\n[red]{data.get('message')}[/]")
    if citations:
        console.print("\n\n[bold]Sources:[/]")
        for c in citations:
            page = f" p.{c['page']}" if c.get("page") else ""
            console.print(f"  [{c['index']}] {c.get('filename')}{page}")


@app.command()
def agents() -> None:
    """List agents."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(base_url() + "/api/agents")
    resp.raise_for_status()
    for a in resp.json():
        console.print(f"{a['id']}  v{a['current_version']}  {a['name']}")


@app.command()
def selfmod(
    agent_id: str, instruction: str, apply: bool = typer.Option(False, help="apply if not blocked")
) -> None:
    """Propose a change to an agent; optionally apply it."""
    new_spec, blocked = None, False
    for event, data in stream_sse(f"/api/agents/{agent_id}/selfmod/propose", {"instruction": instruction}):
        if event == "status":
            console.print(f"[dim]· {data.get('phase')}[/]")
        elif event == "diff":
            new_spec = data.get("new_spec")
            blocked = data.get("blocked")
            console.print(f"\n[bold]Proposed patch[/] ({data.get('capability_class')}):")
            console.print_json(data=data.get("patch"))
            if blocked:
                console.print(f"[red]blocked:[/] {'; '.join(data.get('reasons', []))}")
        elif event == "error":
            console.print(f"[red]{data.get('message')}[/]")
    if apply and new_spec and not blocked:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                base_url() + f"/api/agents/{agent_id}/selfmod/apply", json={"spec": new_spec}
            )
        resp.raise_for_status()
        console.print(f"[green]applied[/] → version {resp.json().get('version')}")


if __name__ == "__main__":
    app()
