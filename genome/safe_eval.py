"""Safe expression evaluator for genome engagement formulas.

Evaluates arithmetic expressions containing whitelisted functions and
variables.  Uses ast.parse + a whitelist visitor — never calls eval().

Whitelisted functions: log1p, min, max, abs, sqrt, log, pow
Whitelisted variables: any key passed in the variables dict

Design decision (from exec plan): formula errors during AVO evolution
should produce a fitness penalty, not a crash.  Callers should catch
SafeEvalError and treat the result as 0 or a penalty score.
"""

from __future__ import annotations

import ast
import math
from typing import Any


class SafeEvalError(Exception):
    """Raised when an expression is rejected or fails evaluation."""


_ALLOWED_FUNCTIONS = {
    "log1p": math.log1p,
    "min": min,
    "max": max,
    "abs": abs,
    "sqrt": math.sqrt,
    "log": math.log,
    "pow": pow,
}

_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Constant,
    *(([ast.Num] if hasattr(ast, "Num") else [])),  # removed in Python 3.12
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Load,
)


class _WhitelistVisitor(ast.NodeVisitor):
    """Reject any AST node not in the whitelist."""

    def __init__(self, allowed_names: set[str]) -> None:
        self.allowed_names = allowed_names

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED_NODE_TYPES):
            raise SafeEvalError(
                f"Disallowed node type: {type(node).__name__}"
            )
        super().generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id not in self.allowed_names:
            raise SafeEvalError(f"Disallowed name: {node.id!r}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise SafeEvalError("Only direct function calls allowed")
        if node.func.id not in _ALLOWED_FUNCTIONS:
            raise SafeEvalError(f"Disallowed function: {node.func.id!r}")
        if node.keywords:
            raise SafeEvalError("Keyword arguments not allowed")
        self.generic_visit(node)


def safe_eval(expression: str, variables: dict[str, Any]) -> float:
    """Evaluate *expression* with *variables* in a sandboxed context.

    Returns a float.  Raises SafeEvalError for rejected or failing
    expressions.

    >>> safe_eval("0.50*log1p(score) + 0.35*log1p(comments)", {"score": 100, "comments": 50})
    2.66...
    """
    expr = str(expression or "").strip()
    if not expr:
        raise SafeEvalError("Empty expression")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise SafeEvalError(f"Syntax error: {exc}") from exc

    shadowed = set(variables or {}) & set(_ALLOWED_FUNCTIONS)
    if shadowed:
        raise SafeEvalError(f"Variable names shadow whitelisted functions: {shadowed}")

    allowed_names = set(_ALLOWED_FUNCTIONS) | set(variables or {})
    _WhitelistVisitor(allowed_names).visit(tree)

    namespace: dict[str, Any] = {}
    namespace.update(_ALLOWED_FUNCTIONS)
    namespace.update(variables or {})

    code = compile(tree, "<genome-formula>", "eval")
    try:
        result = eval(code, {"__builtins__": {}}, namespace)  # noqa: S307
    except Exception as exc:
        raise SafeEvalError(f"Evaluation error: {exc}") from exc

    return float(result)
