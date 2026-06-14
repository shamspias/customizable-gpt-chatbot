"""First-party builtin tools so agents can actually *do* and *create* things.

All bounded and local-first (no shell, no arbitrary code execution): fs.* is
confined to a per-tenant workspace under data/workspace/<tenant>, http.fetch is
GET-only with a size cap, math.eval is an AST evaluator (no names/calls). The
v1 sandbox is what unlocks untrusted code execution; until then these are the
safe, useful primitives. Depend only on veldra_mcp (leaf).
"""

from __future__ import annotations

import ast
import datetime
import json as _json
import operator
import re as _re
from pathlib import Path

import httpx
from veldra_mcp import Tool, ToolContext, ToolResult

WORKSPACE_ROOT = Path("data/workspace")
HTTP_CAP = 8000
READ_CAP = 16000

# ───────────────────────── time ─────────────────────────
async def _time_now(args: dict, ctx: ToolContext) -> ToolResult:
    now = datetime.datetime.now(datetime.UTC)
    return ToolResult(content=f"Current time (UTC): {now.isoformat(timespec='seconds')}")


# ───────────────────────── math ─────────────────────────
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


async def _math_eval(args: dict, ctx: ToolContext) -> ToolResult:
    expr = str(args.get("expression", "")).strip()
    try:
        return ToolResult(content=str(_eval_node(ast.parse(expr, mode="eval").body)))
    except Exception as exc:
        return ToolResult(content=f"Error: {exc}", is_error=True)


# ───────────────────────── http ─────────────────────────
async def _http_fetch(args: dict, ctx: ToolContext) -> ToolResult:
    url = str(args.get("url", ""))
    if not url.startswith(("http://", "https://")):
        return ToolResult(content="Error: url must start with http:// or https://", is_error=True)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Veldra/0.1"})
        return ToolResult(content=f"HTTP {r.status_code} {url}\n\n{r.text[:HTTP_CAP]}")
    except Exception as exc:
        return ToolResult(content=f"Error fetching {url}: {exc}", is_error=True)


# ───────────────────────── workspace files ─────────────────────────
def _resolve(tenant_id: str, rel: str) -> tuple[Path, Path]:
    base = (WORKSPACE_ROOT / tenant_id).resolve()
    target = (base / rel).resolve()
    if base not in target.parents and target != base:
        raise ValueError("path escapes the workspace")
    return base, target


async def _fs_write(args: dict, ctx: ToolContext) -> ToolResult:
    try:
        base, p = _resolve(ctx.tenant_id, str(args["path"]))
        content = str(args.get("content", ""))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return ToolResult(
            content=f"Wrote {p.relative_to(base)} ({len(content)} bytes).",
            data={"path": str(p.relative_to(base))},
        )
    except Exception as exc:
        return ToolResult(content=f"Error: {exc}", is_error=True)


async def _fs_read(args: dict, ctx: ToolContext) -> ToolResult:
    try:
        _, p = _resolve(ctx.tenant_id, str(args["path"]))
        if not p.is_file():
            return ToolResult(content=f"No such file: {args['path']}", is_error=True)
        return ToolResult(content=p.read_text()[:READ_CAP])
    except Exception as exc:
        return ToolResult(content=f"Error: {exc}", is_error=True)


async def _fs_list(args: dict, ctx: ToolContext) -> ToolResult:
    base = (WORKSPACE_ROOT / ctx.tenant_id).resolve()
    if not base.exists():
        return ToolResult(content="(workspace empty)")
    files = sorted(str(f.relative_to(base)) for f in base.rglob("*") if f.is_file())
    return ToolResult(content="\n".join(files) or "(workspace empty)")


# ───────────────────────── data shaping (deterministic, no IO) ─────────────────────────
def _walk_path(data, path: str):
    """Resolve a dotted/bracket path like 'items[0].price' over parsed JSON."""
    cur = data
    for part in _re.findall(r"[^.\[\]]+", path or ""):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(part)
    return cur


async def _json_query(args: dict, ctx: ToolContext) -> ToolResult:
    """Extract a value from a JSON string by path (e.g. 'data.items[0].name')."""
    try:
        data = _json.loads(args.get("json") or "")
    except _json.JSONDecodeError as exc:
        return ToolResult(content=f"Error: invalid JSON ({exc}).", is_error=True)
    path = (args.get("path") or "").strip()
    if not path:
        return ToolResult(content=_json.dumps(data)[:READ_CAP])
    try:
        val = _walk_path(data, path)
    except (KeyError, IndexError, ValueError):
        return ToolResult(content=f"Error: path '{path}' not found.", is_error=True)
    return ToolResult(content=val if isinstance(val, str) else _json.dumps(val))


async def _regex_extract(args: dict, ctx: ToolContext) -> ToolResult:
    """Return all matches of a regex pattern in text (group 1 if present, else whole match)."""
    pattern = args.get("pattern") or ""
    text = args.get("text") or ""
    try:
        rx = _re.compile(pattern)
    except _re.error as exc:
        return ToolResult(content=f"Error: bad pattern ({exc}).", is_error=True)
    out = [m.group(1) if m.groups() else m.group(0) for m in rx.finditer(text)]
    return ToolResult(content=_json.dumps(out))


_STR = {"type": "string"}


def build_tools() -> list[Tool]:
    return [
        Tool("time.now", "Return the current UTC time.",
             {"type": "object", "additionalProperties": False, "properties": {}}, _time_now, True),
        Tool("math.eval", "Evaluate an arithmetic expression (e.g. '12*30 + 7').",
             {"type": "object", "additionalProperties": False,
              "properties": {"expression": _STR}, "required": ["expression"]}, _math_eval, True),
        Tool("http.fetch", "Fetch the text content of a URL (HTTP GET, truncated).",
             {"type": "object", "additionalProperties": False,
              "properties": {"url": _STR}, "required": ["url"]}, _http_fetch, True),
        Tool("fs.write", "Create or overwrite a file in the agent's workspace.",
             {"type": "object", "additionalProperties": False,
              "properties": {"path": _STR, "content": _STR}, "required": ["path", "content"]},
             _fs_write, False),
        Tool("fs.read", "Read a file from the agent's workspace.",
             {"type": "object", "additionalProperties": False,
              "properties": {"path": _STR}, "required": ["path"]}, _fs_read, True),
        Tool("fs.list", "List files in the agent's workspace.",
             {"type": "object", "additionalProperties": False, "properties": {}}, _fs_list, True),
        Tool("json.query",
             "Extract a value from a JSON string by path, e.g. 'data.items[0].name'.",
             {"type": "object", "additionalProperties": False,
              "properties": {"json": _STR, "path": _STR}, "required": ["json"]}, _json_query, True),
        Tool("regex.extract", "Return all regex matches in text (capture group 1 if present).",
             {"type": "object", "additionalProperties": False,
              "properties": {"pattern": _STR, "text": _STR}, "required": ["pattern", "text"]},
             _regex_extract, True),
    ]
