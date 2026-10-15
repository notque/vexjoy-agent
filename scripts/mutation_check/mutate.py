"""Deterministic AST mutant generation by source-span edits.

Each operator finds a node with `ast`, then edits the exact byte span in the original source, so a mutant differs
from the original by one small hunk. Ideas ported from the reference mutation harnesses: one rule broken at a time,
an anchor that cannot be located is an error (never a silent skip), and a mutant that does not parse is rejected.
"""

from __future__ import annotations

import ast
import difflib
import random
import re
import zlib
from dataclasses import dataclass, field

OPERATORS = ("cmp_flip", "bool_swap", "negate_if", "drop_branch", "const", "regex_alt", "early_return", "return_none")

CMP_TOKEN = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.In: "in",
    ast.NotIn: "not in",
    ast.Is: "is",
    ast.IsNot: "is not",
}
CMP_FLIP = {
    "==": "!=",
    "!=": "==",
    "<": ">=",
    "<=": ">",
    ">": "<=",
    ">=": "<",
    "in": "not in",
    "not in": "in",
    "is": "is not",
    "is not": "is",
}
CMP_FIND = re.compile(rb"(?<![\w])(not\s+in|is\s+not|in|is)(?![\w])|(==|!=|<=|>=|<|>)")
BOOL_FIND = re.compile(rb"(?<![\w])(and|or)(?![\w])")
DECISION_SWAPS = {
    "deny": "allow",
    "allow": "deny",
    "block": "approve",
    "approve": "block",
    "blocked": "allowed",
    "allowed": "blocked",
    "ask": "allow",
}
STR_TOKEN = re.compile(rb"^([rRbBuU]*)(['\"])(.*)\2$", re.S)
REGEX_FUNCS = {"compile", "search", "match", "fullmatch", "sub", "subn", "findall", "finditer", "split"}


class AnchorNotFound(Exception):
    """An operator could not locate its edit point in the source; reported, never skipped."""


@dataclass(frozen=True)
class Mutant:
    """One single-hunk change to a source file."""

    id: str
    operator: str
    line: int
    description: str
    source: str = field(repr=False, compare=False)
    diff: str = field(repr=False, compare=False)
    function: str = ""


@dataclass
class Generation:
    """Result of generating mutants for one file."""

    mutants: list[Mutant]
    candidates: int
    rejected_unparseable: int
    errors: list[str]
    by_operator_candidates: dict[str, int]


@dataclass(frozen=True)
class _Edit:
    operator: str
    start: int
    end: int
    repl: bytes
    line: int
    description: str
    node: ast.AST | None = field(default=None, compare=False)


class _Source:
    """Byte-offset view of a source file, matching ast's UTF-8 column offsets."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.data = text.encode("utf-8")
        starts = [0]
        for line in self.data.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))
        self.starts = starts

    def off(self, lineno: int, col: int) -> int:
        """Return the byte offset for a 1-based line and byte column."""
        return self.starts[lineno - 1] + col

    def span(self, node: ast.AST) -> tuple[int, int]:
        """Return (start, end) byte offsets of *node*."""
        return (
            self.off(node.lineno, node.col_offset),  # type: ignore[attr-defined]
            self.off(node.end_lineno, node.end_col_offset),  # type: ignore[attr-defined]
        )

    def seg(self, start: int, end: int) -> bytes:
        """Return the bytes between two offsets."""
        return self.data[start:end]


def _is_trivial_body(body: list[ast.stmt]) -> bool:
    """Return True when a body is only pass, ellipsis, or a bare string."""
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        return False
    return True


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    out: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            out[child] = parent
    return out


def _is_main_guard(node: ast.AST) -> bool:
    """Return True for `if __name__ == "__main__":`."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _inside_skipped(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Return True when *node* sits in a main guard, an f-string, an annotation, or a docstring."""
    child = node
    cur = parents.get(node)
    while cur is not None:
        if _is_main_guard(cur) or isinstance(cur, ast.JoinedStr):
            return True
        if isinstance(cur, ast.arg) and cur.annotation is child:
            return True
        if isinstance(cur, ast.AnnAssign) and cur.annotation is child:
            return True
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)) and cur.returns is child:
            return True
        if isinstance(cur, ast.Expr) and isinstance(cur.value, ast.Constant) and isinstance(cur.value.value, str):
            return True
        child, cur = cur, parents.get(cur)
    return False


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
        cur = parents.get(cur)
    return None


# ----------------------------------------------------------------------------------------------- operators


def _cmp_flip(src: _Source, node: ast.Compare) -> list[_Edit]:
    edits = []
    operands = [node.left, *node.comparators]
    for i, op in enumerate(node.ops):
        expected = CMP_TOKEN[type(op)]
        start = src.span(operands[i])[1]
        end = src.span(operands[i + 1])[0]
        found = CMP_FIND.search(src.seg(start, end))
        if found is None:
            raise AnchorNotFound(f"line {node.lineno}: comparison operator {expected!r} not found")
        token = re.sub(rb"\s+", b" ", found.group(0)).decode()
        if token != expected:
            raise AnchorNotFound(f"line {node.lineno}: expected {expected!r}, found {token!r}")
        flipped = CMP_FLIP[expected]
        edits.append(
            _Edit(
                "cmp_flip",
                start + found.start(),
                start + found.end(),
                flipped.encode(),
                node.lineno,
                f"`{expected}` -> `{flipped}`",
                node,
            )
        )
    return edits


def _bool_swap(src: _Source, node: ast.BoolOp) -> list[_Edit]:
    edits = []
    expected = "and" if isinstance(node.op, ast.And) else "or"
    for i in range(len(node.values) - 1):
        start = src.span(node.values[i])[1]
        end = src.span(node.values[i + 1])[0]
        found = BOOL_FIND.search(src.seg(start, end))
        if found is None or found.group(1).decode() != expected:
            raise AnchorNotFound(f"line {node.lineno}: boolean operator {expected!r} not found")
        swapped = "or" if expected == "and" else "and"
        edits.append(
            _Edit(
                "bool_swap",
                start + found.start(),
                start + found.end(),
                swapped.encode(),
                node.lineno,
                f"`{expected}` -> `{swapped}`",
                node,
            )
        )
    return edits


def _negate_test(src: _Source, node: ast.If | ast.IfExp) -> list[_Edit]:
    test = node.test
    start, end = src.span(test)
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = src.seg(*src.span(test.operand))
        repl = inner
        what = "drop `not` from condition"
    else:
        repl = b"not (" + src.seg(start, end) + b")"
        what = "negate condition"
    return [_Edit("negate_if", start, end, repl, node.lineno, what, node)]


def _drop_body(src: _Source, body: list[ast.stmt], label: str, node: ast.AST) -> list[_Edit]:
    if not body or _is_trivial_body(body):
        return []
    start = src.span(body[0])[0]
    end = src.span(body[-1])[1]
    return [_Edit("drop_branch", start, end, b"pass", body[0].lineno, f"replace {label} body with `pass`", node)]


def _const(src: _Source, node: ast.Constant) -> list[_Edit]:
    value = node.value
    start, end = src.span(node)
    text = src.seg(start, end)
    line = node.lineno
    if isinstance(value, bool):
        return [_Edit("const", start, end, str(not value).encode(), line, f"`{value}` -> `{not value}`", node)]
    if isinstance(value, int):
        new = 1 if value == 0 else (0 if value in (1, 2) else value + 1)
        return [_Edit("const", start, end, str(new).encode(), line, f"`{value}` -> `{new}`", node)]
    if isinstance(value, str) and value in DECISION_SWAPS:
        match = STR_TOKEN.match(text)
        if match is None or match.group(3).decode() != value:
            return []
        swapped = DECISION_SWAPS[value]
        repl = match.group(1) + match.group(2) + swapped.encode() + match.group(2)
        return [_Edit("const", start, end, repl, line, f'"{value}" -> "{swapped}"', node)]
    return []


def _regex_alternatives(body: str) -> list[tuple[int, int]]:
    """Return (start, end) spans in *body* to delete so that exactly one alternative of one group is removed.

    The span includes the adjoining `|`. Escapes, character classes, and non-capturing group prefixes are honoured;
    flag groups and lookbehind-style groups keep their prefix untouched.
    """
    alts: list[list[int]] = [[0]]  # per open group: start index of each alternative
    bars: list[list[int]] = [[]]  # per open group: index of each `|`
    spans: list[tuple[int, int]] = []
    n = len(body)

    def close(alt_starts: list[int], bar_idx: list[int], end: int) -> None:
        if len(alt_starts) < 2:
            return
        for k, a_start in enumerate(alt_starts):
            a_end = bar_idx[k] if k < len(bar_idx) else end
            if a_end == a_start:
                continue  # an empty alternative makes the group optional; leave it alone
            spans.append((a_start, a_end + 1) if k < len(bar_idx) else (bar_idx[k - 1], a_end))

    i = 0
    while i < n:
        c = body[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            j = i + 1
            if j < n and body[j] == "^":
                j += 1
            if j < n and body[j] == "]":
                j += 1
            while j < n and body[j] != "]":
                j += 2 if body[j] == "\\" else 1
            i = j + 1
            continue
        if c == "(":
            j = i + 1
            if body.startswith("?", j):
                if body.startswith(("?:", "?=", "?!"), j):
                    j += 2
                elif body.startswith(("?<=", "?<!"), j):
                    j += 3
                elif body.startswith("?P<", j):
                    k = body.find(">", j)
                    j = k + 1 if k != -1 else n
                else:
                    k = body.find(")", j)
                    i = k + 1 if k != -1 else n
                    continue
            alts.append([j])
            bars.append([])
            i = j
            continue
        if c == "|":
            alts[-1].append(i + 1)
            bars[-1].append(i)
        elif c == ")" and len(alts) > 1:
            close(alts.pop(), bars.pop(), i)
        i += 1
    close(alts[0], bars[0], n)
    return spans


def _regex_candidates(tree: ast.AST) -> set[int]:
    """Return ids of string Constant nodes that reach a `re.*` call as the pattern."""
    names: set[str] = set()
    direct: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
            and node.func.attr in REGEX_FUNCS
        ):
            pattern = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "pattern"), None)
            if isinstance(pattern, ast.Constant) and isinstance(pattern.value, str):
                direct.add(id(pattern))
            elif isinstance(pattern, ast.Name):
                names.add(pattern.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            if any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                direct.add(id(node.value))
    return direct


def _regex_alt(src: _Source, node: ast.Constant) -> list[_Edit]:
    start, end = src.span(node)
    text = src.seg(start, end)
    match = STR_TOKEN.match(text)
    if match is None:
        return []  # implicit concatenation, triple quotes, or f-string: no single literal to edit
    prefix, quote, inner = match.group(1), match.group(2), match.group(3)
    if b"|" not in inner or inner.startswith(quote * 2):
        return []
    if b"\\" in inner and b"r" not in prefix.lower():
        return []  # escapes in a non-raw literal change what the regex sees
    body = inner.decode()
    base = start + len(prefix) + 1
    edits = []
    for a, b in _regex_alternatives(body):
        a_b = len(body[:a].encode())
        b_b = len(body[:b].encode())
        removed = body[a:b].strip("|")
        edits.append(
            _Edit(
                "regex_alt",
                base + a_b,
                base + b_b,
                b"",
                node.lineno,
                f"drop regex alternative `{removed[:40]}`",
                node,
            )
        )
    return edits


def _early_return(src: _Source, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[_Edit]:
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if len(body) < 3:
        return []
    stmt = body[len(body) // 2]
    line_start = src.starts[stmt.lineno - 1]
    indent = src.seg(line_start, src.off(stmt.lineno, stmt.col_offset))
    if indent.strip():
        return []
    return [
        _Edit(
            "early_return",
            line_start,
            line_start,
            indent + b"return\n",
            stmt.lineno,
            f"insert `return` before line {stmt.lineno} of `{fn.name}`",
            fn,
        )
    ]


def _return_none(src: _Source, node: ast.Return) -> list[_Edit]:
    value = node.value
    if value is None or (isinstance(value, ast.Constant) and value.value is None):
        return []
    start, end = src.span(value)
    return [_Edit("return_none", start, end, b"None", node.lineno, "return `None` instead of the value", node)]


def collect_edits(source: str) -> tuple[list[_Edit], list[str]]:
    """Return every candidate edit in *source* and the anchor errors hit while collecting."""
    tree = ast.parse(source)
    src = _Source(source)
    parents = _parents(tree)
    regex_ids = _regex_candidates(tree)
    edits: list[_Edit] = []
    errors: list[str] = []

    def add(fn, *args) -> None:
        try:
            edits.extend(fn(src, *args))
        except AnchorNotFound as err:
            errors.append(str(err))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.expr_context)):
            continue
        if _inside_skipped(node, parents) and not isinstance(node, ast.Constant):
            continue
        if isinstance(node, ast.Compare):
            add(_cmp_flip, node)
        elif isinstance(node, ast.BoolOp):
            add(_bool_swap, node)
        elif isinstance(node, (ast.If, ast.IfExp)):
            if isinstance(node, ast.If):
                if _is_main_guard(node):
                    continue
                add(_drop_body, node.body, "`if`", node)
                if node.orelse and not (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)):
                    add(_drop_body, node.orelse, "`else`", node)
            add(_negate_test, node)
        elif isinstance(node, ast.ExceptHandler):
            add(_drop_body, node.body, "`except`", node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(_early_return, node)
        elif isinstance(node, ast.Return):
            add(_return_none, node)
        elif isinstance(node, ast.Constant):
            if _inside_skipped(node, parents):
                continue
            if id(node) in regex_ids:
                add(_regex_alt, node)
            add(_const, node)
    return edits, errors


def apply_edit(source: str, edit: _Edit) -> str:
    """Return *source* with one edit applied."""
    data = source.encode("utf-8")
    return (data[: edit.start] + edit.repl + data[edit.end :]).decode("utf-8")


def make_diff(original: str, mutated: str, name: str) -> str:
    """Return a unified diff with 3 lines of context."""
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            mutated.splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            n=3,
        )
    )


def _valid(original: str, mutated: str, edit: _Edit, name: str) -> bool:
    """Return True when the mutant differs from the original, compiles, and (for regex edits) still compiles as a regex."""
    if mutated == original:
        return False
    try:
        tree = compile(mutated, name, "exec", flags=ast.PyCF_ONLY_AST)
        compile(tree, name, "exec")
    except (SyntaxError, ValueError, RecursionError):
        return False
    if edit.operator == "regex_alt" and isinstance(edit.node, ast.Constant):
        src = _Source(mutated)
        start = edit.start
        # re-find the literal that now contains the edit and compile its value
        for node in ast.walk(ast.parse(mutated)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s, e = src.span(node)
                if s <= start <= e:
                    try:
                        re.compile(node.value)
                    except re.error:
                        return False
                    break
    return True


def seed_for(name: str, seed: int = 0) -> int:
    """Return a stable per-file seed."""
    return zlib.crc32(f"{name}:{seed}".encode()) & 0xFFFFFFFF


def generate(
    source: str, name: str, cap: int = 60, seed: int = 0, operators: tuple[str, ...] = OPERATORS
) -> Generation:
    """Return up to *cap* valid mutants of *source*, sampled round-robin across operators with a seeded shuffle."""
    edits, errors = collect_edits(source)
    tree = ast.parse(source)
    parents = _parents(tree)
    pools: dict[str, list[_Edit]] = {op: [] for op in operators}
    seen: set[tuple[str, int, int, bytes]] = set()
    for edit in edits:
        key = (edit.operator, edit.start, edit.end, edit.repl)
        if edit.operator in pools and key not in seen:
            seen.add(key)
            pools[edit.operator].append(edit)
    counts = {op: len(pool) for op, pool in pools.items()}
    rng = random.Random(seed_for(name, seed))
    for op in sorted(pools):
        pools[op].sort(key=lambda e: (e.start, e.end, e.repl))
        rng.shuffle(pools[op])
    chosen: list[Mutant] = []
    rejected = 0
    seen_src: set[int] = set()
    cursor = dict.fromkeys(pools, 0)
    while len(chosen) < cap and any(cursor[op] < len(pools[op]) for op in pools):
        for op in operators:
            if len(chosen) >= cap:
                break
            while cursor[op] < len(pools[op]):
                edit = pools[op][cursor[op]]
                cursor[op] += 1
                mutated = apply_edit(source, edit)
                if not _valid(source, mutated, edit, name) or hash(mutated) in seen_src:
                    rejected += 1
                    continue
                seen_src.add(hash(mutated))
                fn = _enclosing_function(edit.node, parents) if edit.node is not None else None
                chosen.append(
                    Mutant(
                        id=f"{op}-L{edit.line}-{len(chosen):03d}",
                        operator=op,
                        line=edit.line,
                        description=edit.description,
                        source=mutated,
                        diff=make_diff(source, mutated, name),
                        function=getattr(fn, "name", "") if fn is not None else "",
                    )
                )
                break
    chosen.sort(key=lambda m: (m.line, m.operator))
    return Generation(chosen, sum(counts.values()), rejected, errors, counts)
