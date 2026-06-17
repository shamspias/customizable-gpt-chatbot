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
import itertools
import json as _json
import math
import operator
import re as _re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import regex as _rx  # engine-level match timeout (real ReDoS protection; via tiktoken dep)
from veldra_mcp import Tool, ToolContext, ToolResult, safe_request

WORKSPACE_ROOT = Path("data/workspace")
HTTP_CAP = 8000
READ_CAP = 16000
SCRAPE_CAP = 12000

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


# ───────────────────────── calculator (scientific) ─────────────────────────
# A safe, names-and-functions calculator: arithmetic + a whitelist of math functions
# and constants. No attribute access, no arbitrary names, no calls outside the list.
_CALC_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "pow": pow, "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
    "atan": math.atan, "atan2": math.atan2, "floor": math.floor, "ceil": math.ceil,
    "factorial": math.factorial, "degrees": math.degrees, "radians": math.radians,
    "hypot": math.hypot, "gcd": math.gcd, "fabs": math.fabs, "trunc": math.trunc,
}
_CALC_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}

# Compute bounds — keep calc.eval cheap so it can never block the event loop with a
# giant synchronous big-int operation (e.g. 9**9e9 or factorial(1e7)).
_MAX_POW_EXP = 4096
_MAX_FACTORIAL = 10_000
_MAX_BITS = 256_000  # ~32 KB result ceiling


def _bounded(value):
    if isinstance(value, int) and value.bit_length() > _MAX_BITS:
        raise ValueError("result too large")
    return value


def _calc_node(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CALC_CONSTS:
        return _CALC_CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _calc_node(node.left), _calc_node(node.right)
        if (isinstance(node.op, ast.Pow) and isinstance(right, (int, float))
                and abs(right) > _MAX_POW_EXP):
            raise ValueError("exponent too large")
        return _bounded(_OPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _bounded(_OPS[type(node.op)](_calc_node(node.operand)))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _CALC_FUNCS.get(node.func.id)
        if fn is None:
            raise ValueError(f"unknown function '{node.func.id}'")
        if node.keywords:
            raise ValueError("keyword arguments are not supported")
        args = [_calc_node(a) for a in node.args]
        if node.func.id == "factorial" and args and abs(int(args[0])) > _MAX_FACTORIAL:
            raise ValueError("argument too large")
        if node.func.id == "pow" and len(args) >= 2 and isinstance(args[1], (int, float)) \
                and abs(args[1]) > _MAX_POW_EXP:
            raise ValueError("exponent too large")
        return _bounded(fn(*args))
    raise ValueError("unsupported expression")


async def _calc_eval(args: dict, ctx: ToolContext) -> ToolResult:
    expr = str(args.get("expression", "")).strip()
    try:
        value = _calc_node(ast.parse(expr, mode="eval").body)
        return ToolResult(content=str(value))
    except Exception as exc:
        return ToolResult(content=f"Error: {exc}", is_error=True)


# ───────────────────────── http ─────────────────────────
async def _http_fetch(args: dict, ctx: ToolContext) -> ToolResult:
    # SSRF-safe: rejects non-http(s) + private/internal hosts and re-validates every
    # redirect hop and the peer IP (shared guard in veldra_mcp.net).
    url = str(args.get("url", ""))
    try:
        r = await safe_request("GET", url, timeout=20, cap=HTTP_CAP)
        return ToolResult(content=f"HTTP {r.status_code} {url}\n\n{r.text}")
    except Exception as exc:
        return ToolResult(content=f"Error fetching {url}: {exc}", is_error=True)


# ───────────────────────── web scraper (readable text) ─────────────────────────
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
_BLOCK_TAGS = {"p", "div", "section", "article", "br", "li", "tr", "h1", "h2", "h3",
               "h4", "h5", "h6", "header", "footer", "ul", "ol", "table", "blockquote"}


class _TextExtractor(HTMLParser):
    """Strip a page to readable text: drop script/style, newline block elements,
    capture the <title>. Dependency-free (stdlib html.parser)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip: list[str] = []  # stack of open skip tags (recoverable, not monotonic)
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip.append(tag)
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("body", "html"):
            self._skip.clear()  # resync: never let an unclosed skip tag hide the page tail
        if tag in _SKIP_TAGS and tag in self._skip:
            # pop back to (and including) the matching open tag — tolerant of mismatches
            while self._skip and self._skip.pop() != tag:
                pass
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title += data
        text = data.strip()
        if text:
            self.parts.append(text + " ")

    def text(self) -> str:
        raw = "".join(self.parts)
        return _re.sub(r"\n{3,}", "\n\n", _re.sub(r"[ \t]+", " ", raw)).strip()


async def _web_scrape(args: dict, ctx: ToolContext) -> ToolResult:
    """Fetch a web page and return its readable text (HTML stripped to plain text)."""
    url = str(args.get("url", ""))
    cap = min(int(args.get("max_chars") or SCRAPE_CAP), 40000)
    try:
        r = await safe_request("GET", url, timeout=20, cap=200_000)
    except Exception as exc:
        return ToolResult(content=f"Error fetching {url}: {exc}", is_error=True)
    ctype = r.headers.get("content-type", "")
    if "html" not in ctype and "<html" not in r.text[:2000].lower():
        return ToolResult(content=f"{url} ({ctype or 'unknown type'})\n\n{r.text[:cap]}")
    parser = _TextExtractor()
    try:
        parser.feed(r.text)
    except Exception:  # malformed markup — return what we gathered
        pass
    title = unescape(parser.title.strip())
    body = parser.text()[:cap]
    head = f"# {title}\n{url}\n\n" if title else f"{url}\n\n"
    return ToolResult(content=head + body, data={"title": title, "url": url})


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


REGEX_TIMEOUT = 1.5          # the `regex` engine self-aborts a match after this many seconds
REGEX_TEXT_CAP = 100_000
REGEX_MATCH_CAP = 1000


async def _regex_extract(args: dict, ctx: ToolContext) -> ToolResult:
    """Return regex matches in text (group 1 if present). ReDoS-safe: the `regex` engine
    enforces a real per-match timeout (a thread guard can't — CPython `re` holds the GIL),
    plus input + match-count caps."""
    pattern = (args.get("pattern") or "")[:1000]
    text = (args.get("text") or "")[:REGEX_TEXT_CAP]
    try:
        rx = _rx.compile(pattern)
        out = [m.group(1) if m.groups() else m.group(0)
               for m in itertools.islice(rx.finditer(text, timeout=REGEX_TIMEOUT), REGEX_MATCH_CAP)]
    except TimeoutError:
        return ToolResult(content="Error: pattern timed out (too complex).", is_error=True)
    except _rx.error as exc:
        return ToolResult(content=f"Error: bad pattern ({exc}).", is_error=True)
    return ToolResult(content=_json.dumps(out))


_STR = {"type": "string"}


def build_tools() -> list[Tool]:
    return [
        Tool("time.now", "Return the current UTC time.",
             {"type": "object", "additionalProperties": False, "properties": {}}, _time_now, True),
        Tool("math.eval", "Evaluate an arithmetic expression (e.g. '12*30 + 7').",
             {"type": "object", "additionalProperties": False,
              "properties": {"expression": _STR}, "required": ["expression"]}, _math_eval, True),
        Tool("calc.eval",
             "Scientific calculator: arithmetic plus functions (sqrt, log, sin, cos, "
             "factorial, …) and constants (pi, e). E.g. 'sqrt(2) * sin(pi/4)'.",
             {"type": "object", "additionalProperties": False,
              "properties": {"expression": _STR}, "required": ["expression"]}, _calc_eval, True),
        Tool("http.fetch", "Fetch the text content of a URL (HTTP GET, truncated).",
             {"type": "object", "additionalProperties": False,
              "properties": {"url": _STR}, "required": ["url"]}, _http_fetch, True),
        Tool("web.scrape",
             "Fetch a web page and return its readable text (HTML stripped). Use for "
             "reading articles/docs; pass `url` and optional `max_chars`.",
             {"type": "object", "additionalProperties": False,
              "properties": {"url": _STR, "max_chars": {"type": "integer"}}, "required": ["url"]},
             _web_scrape, True),
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
