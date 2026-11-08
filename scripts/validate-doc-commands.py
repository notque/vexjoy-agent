#!/usr/bin/env python3
"""Validate that bash/python command examples in docs reference real files.

Extracts ```bash``` and ```python``` fenced code blocks and inline code spans from
docs/ + the root guides, finds invocations of `python3 path/to/script.py` and
`./path/to/script.sh`, and verifies each referenced script exists on disk.

An installed path (`~/.claude/scripts/X.py`, `$HOME/.codex/hooks/X.py`, and the other
runtime homes) is checked as the repo file it is installed from (`scripts/X.py`,
`hooks/X.py`), so a doc cannot keep running a script the repo deleted.

Skips:
- Other home and system paths (`~/tools/...`, `/tmp/...`) and paths outside the repo (`../`)
- Variables, environment placeholders ($HOME, $VAR) outside the installed homes
- External commands without paths (gh, git, ls, claude, codex, etc.)

Exits 0 when every script-by-path reference resolves; exits 1 otherwise.

`--scope toolkit` checks skills/, agents/ and commands/ markdown instead: each
`python3 <path>.py ...` call in a shell fence or inline code span must name a script
that exists, a known subcommand, and options the script's argparse accepts. Scripts
are parsed with ast, never run. Known exceptions live in scripts/doc-command-allowlist.txt.

Usage:
    python3 scripts/validate-doc-commands.py
    python3 scripts/validate-doc-commands.py --json
    python3 scripts/validate-doc-commands.py --scope toolkit [--json]
    python3 scripts/validate-doc-commands.py --check-sdir   # /do SKILL.md $SDIR portability
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ROOT_MARKDOWN = [
    "README.md",
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    "hooks/README.md",
    ".local.example/README.md",
]

FENCE = re.compile(r"```(bash|sh|python|console)\s*\n(.*?)\n```", re.DOTALL)
ANY_FENCE = re.compile(r"```[^\n]*\n.*?\n```", re.DOTALL)
INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")

# python3 scripts/foo.py | python3 ~/path/foo.py
PY_INVOKE = re.compile(r"python3?\s+([^\s|;&<>]+\.py)")
# ./scripts/foo.sh | ./install.sh (not the tail of ../x.sh or an elided .../x.sh)
SH_INVOKE = re.compile(r"(?<![\w./])(\./[\w./-]+\.(?:sh|py))")
# The installer fills each runtime home's scripts/ and hooks/ from the repo dirs of the same name.
INSTALLED = re.compile(
    r"^(?:~|\$HOME|\$\{HOME\})/\.(?:claude|codex|factory|hermes|reasonix|gemini)/(scripts|hooks)/([^\s]+)$"
)

EXTERNAL_PREFIXES = (
    "~/",
    "$HOME",
    "/tmp/",
    "/dev/",
    "/etc/",
    "/var/",
    "../",
)


def collect_markdown_files() -> list[Path]:
    files = []
    if DOCS_DIR.is_dir():
        files.extend(sorted(DOCS_DIR.rglob("*.md")))
    for name in ROOT_MARKDOWN:
        p = REPO_ROOT / name
        if p.is_file():
            files.append(p)
    return files


def is_repo_local(path: str) -> bool:
    return not path.startswith(EXTERNAL_PREFIXES) and "$" not in path


def resolve_repo_path(invocation: str) -> Path:
    p = invocation.lstrip("./")
    return REPO_ROOT / p


def repo_file_for(invocation: str) -> Path | None:
    """The repo file a doc invocation runs, or None when it points outside the repo."""
    installed = INSTALLED.match(invocation)
    if installed:
        return REPO_ROOT / installed.group(1) / installed.group(2)
    if not is_repo_local(invocation):
        return None
    return resolve_repo_path(invocation)


def invocations(text: str) -> list[str]:
    """Script paths run in fenced bash/sh/python/console blocks and in inline code spans."""
    snippets = [fence.group(2) for fence in FENCE.finditer(text)]
    snippets.extend(span.group(1) for span in INLINE_CODE.finditer(ANY_FENCE.sub("", text)))
    found: list[str] = []
    for snippet in snippets:
        found.extend(match.group(1) for match in PY_INVOKE.finditer(snippet))
        found.extend(match.group(1) for match in SH_INVOKE.finditer(snippet))
    return found


# ---------------------------------------------------------------------------
# $SDIR portability (--check-sdir)
#
# The /do SKILL.md must invoke its scripts as "$SDIR/name.py", never as
# repo-relative `python3 scripts/name.py`: from a non-repo cwd the mandatory
# builder then fails silently. Each $SDIR script must exist and start from a
# non-repo cwd (`--help` exits 0, or 2 for an argparse usage error).
# ---------------------------------------------------------------------------

DO_SKILL_MD = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"
SDIR_REF = re.compile(r"\$SDIR/([a-zA-Z0-9_-]+\.py)")
BARE_SCRIPT_INVOKE = re.compile(r"python3 scripts/[a-zA-Z0-9_-]+\.py")
MIN_SDIR_SCRIPTS = 2  # pre-route.py and build-dispatch.py; guards a regex that silently matches nothing


def check_sdir(skill_md: Path = DO_SKILL_MD, scripts_dir: Path = REPO_ROOT / "scripts") -> list[str]:
    """Return failures for $SDIR script references in the /do SKILL.md."""
    import tempfile

    text = skill_md.read_text(encoding="utf-8")
    names = sorted(set(SDIR_REF.findall(text)))
    failures = [f"bare repo-relative invocation (use $SDIR): {b}" for b in BARE_SCRIPT_INVOKE.findall(text)]
    if len(names) < MIN_SDIR_SCRIPTS:
        failures.append(f"expected at least {MIN_SDIR_SCRIPTS} $SDIR scripts, found {names}")
    with tempfile.TemporaryDirectory() as cwd:
        for name in names:
            script = scripts_dir / name
            if not script.is_file():
                failures.append(f"$SDIR/{name}: missing from {scripts_dir}")
                continue
            result = subprocess.run(
                [sys.executable, str(script), "--help"], capture_output=True, text=True, cwd=cwd, timeout=10
            )
            if result.returncode not in (0, 2):
                failures.append(f"$SDIR/{name}: exit {result.returncode} from a non-repo cwd: {result.stderr[:300]}")
    return failures


# ---------------------------------------------------------------------------
# Toolkit scope (--scope toolkit)
#
# Agents follow script calls written in skills/, agents/ and commands/
# markdown. This scope checks each `python3 <path>.py <args>` call in a shell
# fence or an inline code span against the script's real argparse interface:
# the script must exist, the first positional must be a known subcommand when
# the parser has subparsers, and every option must be one the parser accepts.
# Scripts are parsed with ast and never executed. A script with no argparse,
# raw sys.argv, or several root parsers is checked for existence only. A parser
# handed to an imported helper still has its subcommands checked, but not its
# options.
# ---------------------------------------------------------------------------

TOOLKIT_DIRS = ("skills", "agents", "commands")
TOOLKIT_ALLOWLIST = Path("scripts") / "doc-command-allowlist.txt"  # relative to the checked root
SHELL_LANGS = frozenset({"", "bash", "sh", "shell", "zsh", "console"})
FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
PYTHON_EXE = re.compile(r"^(?:\S*/)?python(?:3(?:\.\d+)?)?$")
SDIR_VARS = ("${SDIR}/", "$SDIR/")
SKILL_DIR_VARS = ("${CLAUDE_SKILL_DIR}/", "$CLAUDE_SKILL_DIR/", *SDIR_VARS)
PLACEHOLDER_CHARS = frozenset("<>{}[]$*|…`")
SHELL_PUNCT = frozenset("();<>|&")
NO_VALUE_ACTIONS = frozenset({"store_true", "store_false", "store_const", "append_const", "count", "help", "version"})
ANGLE_PLACEHOLDER = re.compile(r"(?<![<\w])<([A-Za-z][^<>\n]*?)>")
VARIADIC = object()  # nargs '?', '*', '+' or REMAINDER: how many tokens follow is unknown


@dataclass
class ParserSpec:
    """One argparse parser as seen by a static parse."""

    options: dict[str, object] = field(default_factory=dict)  # option -> value count or VARIADIC
    subcommands: dict[str, ParserSpec] | None = None
    dynamic_subcommands: bool = False  # add_parser with a computed name, or the group left the module
    positionals_before_subparsers: bool = False
    has_subparsers: bool = False
    is_open: bool = False  # options were added where the parse cannot see them
    allow_abbrev: bool = True
    parents: list[ParserSpec] = field(default_factory=list)
    is_child: bool = False
    is_parent: bool = False
    takes_pool_options: bool = False  # handed to a local helper that adds options through a parameter
    takes_pool_subcommands: bool = False  # its subparsers group was handed to a local helper

    def all_options(self) -> dict[str, object]:
        """Options of this parser plus those inherited through `parents=`."""
        merged: dict[str, object] = {}
        for parent in self.parents:
            merged.update(parent.all_options())
        merged.update(self.options)
        return merged

    def open_through_parents(self) -> bool:
        """True when this parser or any parent has options the parse cannot see."""
        return self.is_open or any(parent.open_through_parents() for parent in self.parents)


@dataclass
class _SubGroup:
    owner: ParserSpec


@dataclass
class ScriptInterface:
    """The parsed CLI of one script, or the reason it cannot be checked."""

    root: ParserSpec | None
    reason: str = ""
    flags_checkable: bool = True


def _const_str(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _kwarg(call: ast.Call, name: str) -> ast.AST | None:
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def _value_count(call: ast.Call) -> object:
    action = _kwarg(call, "action")
    if action is not None:
        if _const_str(action) in NO_VALUE_ACTIONS:
            return 0
        if isinstance(action, ast.Attribute) and action.attr == "BooleanOptionalAction":
            return 0
    nargs = _kwarg(call, "nargs")
    if nargs is None:
        return 1
    if isinstance(nargs, ast.Constant) and isinstance(nargs.value, int):
        return nargs.value
    return VARIADIC


class _ArgparseReader(ast.NodeVisitor):
    """Collect argparse parsers, subcommands and options from one module, in source order."""

    def __init__(self, tree: ast.Module) -> None:
        self.parsers: list[ParserSpec] = []
        self.names: dict[str, ParserSpec | _SubGroup] = {}
        self.seen: dict[int, ParserSpec | _SubGroup | None] = {}
        self.local_functions = {
            node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.pool = ParserSpec()  # parsers built inside local helpers whose receiver the parse cannot follow
        self.pool_used = False
        self.known_args_parse = False
        self.raw_argv = False
        self.loop_values: dict[str, list[str]] = {}  # `for name in ("a", "b"):` while inside that loop

    def visit_For(self, node: ast.For) -> None:
        values = None
        if isinstance(node.target, ast.Name) and isinstance(node.iter, (ast.List, ast.Tuple)):
            consts = [_const_str(element) for element in node.iter.elts]
            values = [value for value in consts if value is not None] if None not in consts else None
        if values is None or not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return
        self.loop_values[node.target.id] = values
        self.generic_visit(node)
        self.loop_values.pop(node.target.id, None)

    def _scoped(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        saved = dict(self.names)
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            self.names.pop(arg.arg, None)
        self.generic_visit(node)
        self.names = saved

    visit_FunctionDef = _scoped
    visit_AsyncFunctionDef = _scoped
    visit_Lambda = _scoped

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        value = self.seen.get(id(node.value)) if isinstance(node.value, ast.Call) else None
        if isinstance(node.value, ast.Name):
            value = self.names.get(node.value.id)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if value is None:
                    self.names.pop(target.id, None)
                else:
                    self.names[target.id] = value

    def visit_Subscript(self, node: ast.Subscript) -> None:
        index = node.slice
        if (
            isinstance(node.value, ast.Attribute)
            and node.value.attr == "argv"
            and isinstance(index, ast.Constant)
            and isinstance(index.value, int)
            and index.value != 0
        ):
            self.raw_argv = True  # sys.argv[1] and friends: dispatch the parse cannot see
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._eval(node)
        self.generic_visit(node)

    def _receiver(self, node: ast.AST) -> ParserSpec | _SubGroup | None:
        if isinstance(node, ast.Name):
            return self.names.get(node.id)
        if isinstance(node, ast.Call):
            return self._eval(node)
        return None

    def _new_parser(self, call: ast.Call) -> ParserSpec:
        spec = ParserSpec()
        abbrev = _kwarg(call, "allow_abbrev")
        if isinstance(abbrev, ast.Constant) and abbrev.value is False:
            spec.allow_abbrev = False
        parents = _kwarg(call, "parents")
        if parents is not None:
            elements = parents.elts if isinstance(parents, (ast.List, ast.Tuple)) else [parents]
            for element in elements:
                parent = self._receiver(element)
                if isinstance(parent, ParserSpec):
                    parent.is_parent = True
                    spec.parents.append(parent)
                else:
                    spec.is_open = True
        self.parsers.append(spec)
        return spec

    def _eval(self, call: ast.Call) -> ParserSpec | _SubGroup | None:
        if id(call) in self.seen:
            return self.seen[id(call)]
        self.seen[id(call)] = None
        func = call.func
        result: ParserSpec | _SubGroup | None = None
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        if name == "ArgumentParser":
            result = self._new_parser(call)
        elif isinstance(func, ast.Attribute):
            result = self._method(call, func, name)
        else:
            self._escape_args(call, local=name in self.local_functions)
        self.seen[id(call)] = result
        return result

    def _method(self, call: ast.Call, func: ast.Attribute, name: str) -> ParserSpec | _SubGroup | None:
        receiver = self._receiver(func.value)
        if name in {"parse_known_args", "parse_known_intermixed_args"}:
            self.known_args_parse = True
        if name == "add_subparsers" and isinstance(receiver, ParserSpec):
            receiver.has_subparsers = True
            if receiver.subcommands is None:
                receiver.subcommands = {}
            return _SubGroup(receiver)
        if name in {"add_argument_group", "add_mutually_exclusive_group"} and isinstance(receiver, ParserSpec):
            return receiver
        if name == "add_parser":
            return self._add_parser(call, receiver)
        if name == "add_argument":
            self._add_argument(call, receiver if isinstance(receiver, ParserSpec) else None)
            return None
        self._escape_args(call, local=name in self.local_functions)
        return None

    def _add_parser(self, call: ast.Call, receiver: ParserSpec | _SubGroup | None) -> ParserSpec:
        child = self._new_parser(call)
        child.is_child = True
        if isinstance(receiver, _SubGroup):
            owner = receiver.owner
        else:
            self.pool_used = True
            owner = self.pool
        if owner.subcommands is None:
            owner.subcommands = {}
        first = call.args[0] if call.args else None
        if isinstance(first, ast.Name) and first.id in self.loop_values:
            for loop_name in self.loop_values[first.id]:
                owner.subcommands[loop_name] = child
            return child
        name = _const_str(first) if first is not None else None
        if name is None:
            owner.dynamic_subcommands = True
            return child
        owner.subcommands[name] = child
        aliases = _kwarg(call, "aliases")
        if isinstance(aliases, (ast.List, ast.Tuple)):
            for alias in aliases.elts:
                alias_name = _const_str(alias)
                if alias_name is None:
                    owner.dynamic_subcommands = True
                else:
                    owner.subcommands[alias_name] = child
        return child

    def _add_argument(self, call: ast.Call, spec: ParserSpec | None) -> None:
        target = spec if spec is not None else self.pool
        if spec is None:
            self.pool_used = True
        names: list[str] = []
        for arg in call.args:
            text = _const_str(arg)
            if text is None:
                target.is_open = True
                return
            names.append(text)
        if not names or not names[0].startswith("-"):
            if not target.has_subparsers:
                target.positionals_before_subparsers = True
            return
        count = _value_count(call)
        for option in names:
            target.options[option] = count
        action = _kwarg(call, "action")
        if isinstance(action, ast.Attribute) and action.attr == "BooleanOptionalAction":
            for option in names:
                if option.startswith("--"):
                    target.options["--no-" + option[2:]] = 0

    def _escape_args(self, call: ast.Call, *, local: bool) -> None:
        """A parser handed to another function may gain options the parse cannot see."""
        for arg in [*call.args, *(kw.value for kw in call.keywords)]:
            value = self._receiver(arg)
            if isinstance(value, _SubGroup):
                if local:
                    value.owner.takes_pool_subcommands = True
                else:
                    value.owner.dynamic_subcommands = True
            elif isinstance(value, ParserSpec):
                if local:
                    value.takes_pool_options = True
                else:
                    value.is_open = True


def read_interface(script: Path) -> ScriptInterface:
    """Statically parse a script's argparse CLI; never runs the script."""
    try:
        tree = ast.parse(script.read_text(encoding="utf-8", errors="replace"), filename=str(script))
    except (SyntaxError, ValueError) as err:
        return ScriptInterface(None, f"unparseable: {err}")
    reader = _ArgparseReader(tree)
    reader.visit(tree)
    if reader.raw_argv:
        return ScriptInterface(None, "reads sys.argv directly")
    roots = [spec for spec in reader.parsers if not spec.is_child and not spec.is_parent]
    if not roots:
        return ScriptInterface(None, "no argparse parser")
    if len(roots) > 1:
        return ScriptInterface(None, f"{len(roots)} root parsers")
    if reader.pool_used:
        _share_pool(reader.parsers, reader.pool)
    return ScriptInterface(roots[0], flags_checkable=not reader.known_args_parse)


def _share_pool(parsers: list[ParserSpec], pool: ParserSpec) -> None:
    """Give pooled options and subcommands to the parsers that may own them.

    Parsers handed to a local helper take the pool. When no parser is marked,
    the pool's owner is unknown, so every parser takes it rather than risk a
    false finding.
    """
    option_takers = [spec for spec in parsers if spec.takes_pool_options] or parsers
    group_takers = [spec for spec in parsers if spec.takes_pool_subcommands] or [
        spec for spec in parsers if spec.has_subparsers
    ]
    if pool.options or pool.is_open:
        for spec in option_takers:
            spec.parents.append(pool)
    for spec in group_takers:
        spec.has_subparsers = True
        spec.subcommands = {**(pool.subcommands or {}), **(spec.subcommands or {})}
        spec.dynamic_subcommands = spec.dynamic_subcommands or pool.dynamic_subcommands


def _is_placeholder(token: str) -> bool:
    return any(ch in PLACEHOLDER_CHARS for ch in token) or "..." in token


def _is_placeholder_word(token: str) -> bool:
    """A positional that stands for a value: `<name>`, `{a,b}`, `FILE`."""
    return _is_placeholder(token) or (token.isupper() and any(ch.isalpha() for ch in token))


def _match_option(token: str, options: dict[str, object], allow_abbrev: bool) -> tuple[str | None, str]:
    """Return (matched option, problem) for one option token, as argparse would resolve it."""
    name = token.split("=", 1)[0]
    if name in options or name in {"-h", "--help"}:
        return name, ""
    if not name.startswith("--") and len(name) > 2 and name[:2] in options:
        return name[:2], ""  # -n5 or -vx
    if allow_abbrev and name.startswith("--"):
        hits = [opt for opt in options if opt.startswith(name)]
        if len(hits) == 1:
            return hits[0], ""
        if len(hits) > 1:
            return None, f"ambiguous option {name} (matches {', '.join(sorted(hits))})"
    return None, f"unknown option {name}"


def _has_attached_value(token: str, matched: str) -> bool:
    """True for a short option with its value or more flags joined on, such as -n5 or -vx."""
    return not token.startswith("--") and len(token.split("=", 1)[0]) > len(matched)


def _subcommands_with(spec: ParserSpec, option: str) -> list[str]:
    """Names of the subcommands of `spec` that accept `option`, for a finding hint."""
    return sorted(name for name, sub in (spec.subcommands or {}).items() if option in sub.all_options())


def check_call(interface: ScriptInterface, args: list[str]) -> list[str]:
    """Problems with one call's arguments against a parsed interface."""
    if interface.root is None:
        return []
    spec = interface.root
    problems: list[str] = []
    positional_known = not spec.positionals_before_subparsers
    i = 0
    while i < len(args):
        token = args[i]
        i += 1
        if token == "--" or token in {"-h", "--help"}:
            break
        if token.startswith("-") and len(token) > 1 and not token[1].isdigit():
            options = spec.all_options()
            name, inline, _ = token.partition("=")
            if _is_placeholder(name) or not interface.flags_checkable or spec.open_through_parents():
                # Only an exact match has a known value count here: an unseen option may share the prefix.
                # A value given after `=` is the whole value, so nothing after the token is consumed.
                exact = name
                if inline:
                    count = 0
                elif not _is_placeholder(name) and exact in options:
                    count = options[exact]
                else:
                    count = VARIADIC
            else:
                matched, problem = _match_option(token, options, spec.allow_abbrev)
                if matched is None:
                    owners = _subcommands_with(spec, token.split("=", 1)[0])
                    if owners:
                        problem += f" before a subcommand (accepted by: {', '.join(owners)})"
                    problems.append(problem)
                    continue
                count = options.get(matched, 0)
                exact = matched
            if not isinstance(count, int):
                positional_known = False  # how many words the option takes is unknown
            elif "=" not in token and not _has_attached_value(token, exact):
                i += count
            continue
        if not spec.has_subparsers:
            continue
        if not positional_known or _is_placeholder_word(token):
            break  # this word may pick the subcommand, so the parser for the rest is unknown
        subcommands = spec.subcommands or {}
        if token in subcommands:
            spec = subcommands[token]
            positional_known = not spec.positionals_before_subparsers
            continue
        if not spec.dynamic_subcommands:
            choices = ", ".join(sorted(subcommands)) or "none"
            problems.append(f"unknown subcommand {token!r} (choices: {choices})")
        break  # past an unknown subcommand the parser for the rest is unknown
    return problems


def _shell_segments(line: str) -> list[list[str]]:
    """Split one logical shell line into command segments of plain words."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for index, token in enumerate(tokens):
        if token and set(token) <= SHELL_PUNCT:
            segments.append([])
            continue
        nxt = tokens[index + 1] if index + 1 < len(tokens) else ""
        if token.isdigit() and nxt.startswith(">"):
            continue  # the fd number of a 2>&1 redirect
        segments[-1].append(token)
    return [segment for segment in segments if segment]


def line_events(line: str) -> list[tuple[str, str, list[str]]]:
    """Ordered ("cd", dir, []) and ("call", script, args) events in one shell line.

    A call is `python3 <path>.py ...` (any python executable path) or `./<path>.py ...`.
    """
    events: list[tuple[str, str, list[str]]] = []
    # `<target-url>` is a doc placeholder, not two redirects; `{PH}` keeps it one placeholder word.
    for words in _shell_segments(ANGLE_PLACEHOLDER.sub("{PH}", line)):
        if words[0] == "cd":
            events.append(("cd", words[1] if len(words) > 1 else "~", []))
            continue
        for index, word in enumerate(words):
            if PYTHON_EXE.match(word):
                rest = words[index + 1 :]
                while rest and rest[0].startswith("-") and rest[0] not in {"-m", "-c", "-"}:
                    rest = rest[1:]  # interpreter flags such as -u or -I
                if rest and rest[0].endswith(".py"):
                    events.append(("call", rest[0], rest[1:]))
                break
            if index == 0 and word.startswith("./") and word.endswith(".py"):
                events.append(("call", word, words[1:]))
                break
    return events


def _logical_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Join backslash continuations; keep the first line number."""
    joined: list[tuple[int, str]] = []
    buffer = ""
    start = 0
    for number, text in lines:
        if not buffer:
            start = number
        if text.rstrip().endswith("\\"):
            buffer += text.rstrip()[:-1] + " "
            continue
        joined.append((start, buffer + text))
        buffer = ""
    if buffer:
        joined.append((start, buffer))
    return joined


def shell_snippets(text: str) -> list[list[tuple[int, str]]]:
    """Shell fences and inline code spans outside fences, each a list of (line number, logical line).

    A `cd` carries to later lines of the same snippet only, so each snippet is checked on its own.
    """
    snippets: list[list[tuple[int, str]]] = []
    fence: tuple[str, str] | None = None
    body: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if fence is None:
            opener = FENCE_OPEN.match(line)
            if opener:
                fence = (opener.group(1), opener.group(2).lower())
                body = []
                continue
            snippets.extend([(number, span.group(1))] for span in INLINE_CODE.finditer(line))
            continue
        marker = fence[0]
        if stripped.startswith(marker) and not stripped.strip(marker[0]):
            if fence[1] in SHELL_LANGS:
                snippets.append(_logical_lines(body))
            fence = None
            continue
        body.append((number, stripped[2:] if stripped.startswith("$ ") else line))
    return snippets


def _owning_dirs(md: Path, root: Path) -> list[Path]:
    """Ancestor dirs of a markdown file below the repo root, nearest first."""
    return [parent for parent in md.parents if root in parent.parents]


def _skill_dirs(root: Path) -> dict[str, Path]:
    """Installed skill name -> repo skill dir (the installer links ~/.claude/skills/<name> to it)."""
    skills = root / "skills"
    if not skills.is_dir():
        return {}
    return {skill_md.parent.name: skill_md.parent for skill_md in sorted(skills.rglob("SKILL.md"))}


HOME_PREFIX = r"^(?:~|\$HOME|\$\{HOME\})/\.(?:claude|codex|factory|hermes|reasonix|gemini)/"
INSTALLED_SKILL = re.compile(HOME_PREFIX + r"skills/([^/]+)/(.+)$")
INSTALLED_SKILL_DIR = re.compile(HOME_PREFIX + r"skills/([^/]+)/?$")
HOME_OR_SKILL_VAR = re.compile(HOME_PREFIX + r"|^(?:\$\{CLAUDE_SKILL_DIR\}|\$CLAUDE_SKILL_DIR|\$\{SDIR\}|\$SDIR)/")
TOOLKIT_ANCHORS = ("scripts/", "hooks/", "skills/", "agents/", "commands/")
UNKNOWN_BASE = Path("/nonexistent-cd-target")  # a `cd` the checker cannot follow: skip relative calls after it


class _Resolver:
    """Map a doc's script path to the repo file it runs, the way an agent following the doc would."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.skills = _skill_dirs(root)

    def installed(self, target: str) -> Path | None:
        """Repo path for an installed-home path, or UNKNOWN_BASE for a skill not in this repo."""
        skill = INSTALLED_SKILL.match(target)
        if skill:
            repo_dir = self.skills.get(skill.group(1))
            return repo_dir / skill.group(2) if repo_dir else UNKNOWN_BASE
        installed = INSTALLED.match(target)
        if installed:
            return self.root / installed.group(1) / installed.group(2)
        return None

    def cd(self, target: str, base: Path | None) -> Path:
        """The new base dir after `cd target`; UNKNOWN_BASE when it leaves the toolkit."""
        skill = INSTALLED_SKILL_DIR.match(target)
        if skill:
            return self.skills.get(skill.group(1), UNKNOWN_BASE)
        if target.startswith(("/", "~", "$", "-")) or _is_placeholder(target):
            return UNKNOWN_BASE
        start = base if base is not None else self.root
        candidate = start / target
        return candidate if candidate.is_dir() else UNKNOWN_BASE

    def script(self, target: str, md: Path, base: Path | None) -> Path | None:
        """The file a call runs, a missing path to report, or None when the call is out of scope."""
        if _is_placeholder(HOME_OR_SKILL_VAR.sub("", target, count=1)):
            return None
        mapped = self.installed(target)
        if mapped is not None:
            return None if mapped == UNKNOWN_BASE else mapped
        dirs = _owning_dirs(md, self.root)
        for prefix in SKILL_DIR_VARS:
            if target.startswith(prefix):
                tail = target[len(prefix) :]
                owners = [d for d in dirs if (d / "SKILL.md").is_file()]
                candidates = [owners[0] / tail] if owners else []
                if prefix in SDIR_VARS:
                    candidates.append(self.root / "scripts" / tail)  # $SDIR is the /do scripts dir
                if not candidates:
                    return None  # CLAUDE_SKILL_DIR outside a skill: the dir is unknown
                return next((c for c in candidates if c.is_file()), candidates[0])
        if target.startswith(("/", "~", "../", "$")):
            return None
        relative = target.removeprefix("./")
        if base == UNKNOWN_BASE:
            return None
        if base is not None:
            return base / relative
        candidates = [self.root / relative, *(d / relative for d in dirs)]
        found = next((c for c in candidates if c.is_file()), None)
        if found is not None:
            return found
        # A bare name (`manage.py`, `server.py`) is a file in the user's project, not the toolkit.
        return candidates[0] if relative.startswith(TOOLKIT_ANCHORS) else None


def resolve_script(target: str, md: Path, root: Path = REPO_ROOT) -> Path | None:
    """The repo file a toolkit doc call runs; None when it points outside the repo or at a placeholder."""
    return _Resolver(root).script(target, md, None)


def collect_toolkit_markdown(root: Path = REPO_ROOT) -> list[Path]:
    """Markdown under skills/, agents/ and commands/; git-tracked files only when root is a git checkout."""
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", *(f"{d}/*.md" for d in TOOLKIT_DIRS)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        listed = ""
    if listed:
        return sorted(root / name for name in listed.split("\0") if name)
    files: list[Path] = []
    for name in TOOLKIT_DIRS:
        if (root / name).is_dir():
            files.extend(sorted((root / name).rglob("*.md")))
    return files


@dataclass(frozen=True)
class AllowEntry:
    """One allowlisted doc call: fnmatch globs for the doc path and the script as written."""

    doc: str
    target: str
    reason: str

    def matches(self, doc: str, target: str) -> bool:
        """True when this entry covers `target` written in `doc`."""
        return fnmatch.fnmatchcase(doc, self.doc) and fnmatch.fnmatchcase(target, self.target)


def load_allowlist(path: Path) -> list[AllowEntry]:
    """Allowlist lines `doc-glob :: script-glob :: reason`; `#` starts a comment line."""
    entries: list[AllowEntry] = []
    if not path.is_file():
        return entries
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("::")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"{path.name}: bad allowlist line (want 'doc :: script :: reason'): {raw!r}")
        entries.append(AllowEntry(*parts))
    return entries


def check_toolkit(root: Path = REPO_ROOT, allowlist: Path | None = None) -> tuple[int, list[dict[str, object]]]:
    """Check every toolkit markdown script call. Returns (calls checked, findings).

    An allowlist entry that no longer covers a finding is itself a finding, so the list cannot go stale.
    """
    allowlist = allowlist if allowlist is not None else root / TOOLKIT_ALLOWLIST
    entries = load_allowlist(allowlist)
    used: set[AllowEntry] = set()
    resolver = _Resolver(root)
    interfaces: dict[Path, ScriptInterface] = {}
    findings: list[dict[str, object]] = []
    checked = 0
    for md in collect_toolkit_markdown(root):
        rel = md.relative_to(root).as_posix()
        for snippet in shell_snippets(md.read_text(encoding="utf-8", errors="replace")):
            base: Path | None = None
            for number, line in snippet:
                if ".py" not in line and "cd " not in line:
                    continue
                for kind, target, args in line_events(line):
                    if kind == "cd":
                        base = resolver.cd(target, base)
                        continue
                    script = resolver.script(target, md, base)
                    if script is None:
                        continue
                    checked += 1
                    if not script.is_file():
                        problems = ["script not found"]
                    else:
                        if script not in interfaces:
                            interfaces[script] = read_interface(script)
                        problems = check_call(interfaces[script], args)
                    for problem in problems:
                        entry = next((e for e in entries if e.matches(rel, target)), None)
                        if entry is not None:
                            used.add(entry)
                            continue
                        findings.append({"source": rel, "line": number, "target": target, "problem": problem})
    for entry in entries:
        if entry not in used:
            findings.append(
                {"source": allowlist.name, "line": 0, "target": entry.target, "problem": f"stale entry for {entry.doc}"}
            )
    return checked, findings


def _report_toolkit(root: Path, *, as_json: bool) -> int:
    try:
        checked, findings = check_toolkit(root.resolve())
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps({"checked": checked, "findings": findings}, indent=2))
    else:
        print(f"Checked {checked} script calls in skills/, agents/ and commands/ markdown.")
        for item in findings:
            print(f"  {item['source']}:{item['line']}: {item['target']}: {item['problem']}")
        print(f"\n{len(findings)} finding(s)" if findings else "All script calls match their scripts.")
    return 1 if findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check-sdir", action="store_true", help="check $SDIR script portability in /do SKILL.md")
    parser.add_argument(
        "--scope",
        choices=("docs", "toolkit"),
        default="docs",
        help="docs: docs/ and root guides, script existence; toolkit: skills/, agents/, commands/ calls vs argparse",
    )
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repo root for --scope toolkit (default: this checkout)"
    )
    args = parser.parse_args()

    if args.scope == "toolkit":
        return _report_toolkit(args.root, as_json=args.json)

    if args.check_sdir:
        failures = check_sdir()
        for line in failures:
            print(f"  SDIR: {line}")
        print(f"{len(failures)} $SDIR issue(s)" if failures else "SDIR: all /do scripts portable.")
        return 1 if failures else 0

    missing: list[dict] = []
    checked = 0

    for md in collect_markdown_files():
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = md.relative_to(REPO_ROOT)
        for target in invocations(text):
            repo_file = repo_file_for(target)
            if repo_file is None:
                continue
            checked += 1
            if not repo_file.is_file():
                missing.append({"source": str(rel), "target": target})

    if args.json:
        print(json.dumps({"checked": checked, "missing": missing}, indent=2))
    else:
        print(f"Checked {checked} repo-local script invocations across {len(collect_markdown_files())} files.")
        if missing:
            print(f"\nMissing: {len(missing)}")
            for m in missing:
                print(f"  {m['source']}: {m['target']}")
        else:
            print("All script references resolve.")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
