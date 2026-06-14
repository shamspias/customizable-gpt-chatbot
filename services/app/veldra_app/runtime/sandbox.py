"""A sandboxed expression evaluator for the workflow `code` node.

This is NOT arbitrary Python — it is a deliberately small, safe expression language
(the responsible "code node" until the v1 execution sandbox lands). It evaluates a
single expression over the workflow's variables and a whitelist of pure helpers:
arithmetic, string/list/dict ops, comparisons, boolean logic, ternaries,
indexing/slicing, and comprehensions. It blocks attribute access to dunders, all
imports/lambdas, and any name or call outside the whitelist, and runs with empty
`__builtins__`. So `len(items) > 3`, `name.upper()`, `price * qty`, and
`", ".join(tags)` work; `__import__`, `open`, `().__class__` do not.
"""

from __future__ import annotations

import ast
from typing import Any

# Pure, side-effect-free helpers exposed to expressions.
SAFE_FUNCS: dict[str, Any] = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool,
    "round": round, "abs": abs, "min": min, "max": max, "sum": sum,
    "sorted": sorted, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "any": any, "all": all, "range": range, "enumerate": enumerate, "zip": zip,
    "reversed": reversed, "repr": repr,
}

# Methods callable on values (no escape via private/dunder attributes).
SAFE_METHODS = frozenset({
    # str
    "upper", "lower", "strip", "lstrip", "rstrip", "title", "capitalize",
    "split", "rsplit", "splitlines", "join", "replace", "format",
    "startswith", "endswith", "find", "rfind", "count", "zfill", "ljust", "rjust",
    "isdigit", "isalpha", "isalnum", "isspace", "encode",
    # dict / list / set
    "get", "keys", "values", "items", "index", "append", "extend",
})

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.IfExp, ast.Compare,
    ast.Call, ast.Constant, ast.Name, ast.Load, ast.List, ast.Tuple, ast.Dict,
    ast.Set, ast.Subscript, ast.Slice, ast.Index if hasattr(ast, "Index") else ast.Slice,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.Attribute, ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd, ast.Invert,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Is, ast.IsNot, ast.Starred, ast.JoinedStr, ast.FormattedValue,
)


class SandboxError(ValueError):
    pass


def _validate(node: ast.AST, allowed_names: set[str]) -> None:
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_NODES):
            raise SandboxError(f"disallowed syntax: {type(child).__name__}")
        if isinstance(child, ast.Attribute) and child.attr.startswith("_"):
            raise SandboxError("attribute access to private/dunder names is not allowed")
        if isinstance(child, ast.Attribute) and child.attr not in SAFE_METHODS:
            raise SandboxError(f"method not allowed: .{child.attr}")
        if isinstance(child, ast.Name) and child.id not in allowed_names:
            raise SandboxError(f"unknown name: {child.id}")


def safe_eval(expr: str, variables: dict[str, Any]) -> Any:
    """Evaluate a single safe expression. Raises SandboxError on anything unsafe."""
    expr = (expr or "").strip()
    if not expr:
        return ""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise SandboxError(f"syntax error: {e.msg}") from e
    allowed = set(variables) | set(SAFE_FUNCS) | {"True", "False", "None"}
    _validate(tree, allowed)
    namespace = {**SAFE_FUNCS, **variables}
    try:
        return eval(compile(tree, "<workflow-code>", "eval"), {"__builtins__": {}}, namespace)  # noqa: S307
    except SandboxError:
        raise
    except Exception as e:  # surface runtime errors (KeyError, TypeError, …) cleanly
        raise SandboxError(f"{type(e).__name__}: {e}") from e
