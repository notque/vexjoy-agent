#!/usr/bin/env python3
# hook-version: 1.4.0
"""
PreToolUse:Bash Hook: Private Name Leak Gate

Blocks git commit, git push, and gh pr create/edit/comment/merge when the
text they would publish contains the name of a private component installed
from ~/private-skills (or ~/pgh/private-skills). Private component names must never reach this repo,
its commits, or its PR text.

This is a HARD GATE — exits 0 with JSON permissionDecision:deny to block the
Bash tool.

LOCAL-ONLY BY DESIGN: the private-name set is derived at runtime from the
local ~/private-skills tree. Shipping the set with the repo would itself be
the leak, so CI and public installs (no ~/private-skills) get a graceful
no-op. This gate cannot and should not run in CI.

Term set, three sources:

1. LEAF component names (interior reference/asset dir names and bare file
   stems inside packages are noise, not component names):
   - Directories directly containing SKILL.md; for nested
     <name>/skill/SKILL.md packages, the package dir <name>
   - Stems of *.md files directly inside an agents/ dir
   - MINUS structural basenames (SKILL, README, references, ...)
   - MINUS names shorter than 4 chars
   - MINUS tracked public skill names from skills/INDEX.json (project copy
     first, then ~/.claude/skills/INDEX.json) — public homonyms never block
   - MINUS the toolkit's own name (pyproject `name` and its first hyphen
     segment). This is the only "already public" exemption: exempting every
     name already in the tracked tree made a leak self-perpetuating.
   - MINUS harness built-in and slash commands (_BUILTIN_COMMANDS)
   - MINUS common words that appear routinely in documentation or code (_COMMON_WORDS)
2. BRAND terms: a first hyphen segment shared by at least 2 private leaf
   names, at least 4 chars, not a common word (_COMMON_WORDS), not the
   toolkit's own name, and not a segment of any public skill or agent name.
3. OWNER terms: optional ~/private-skills/.private-terms, one term per
   line, `#` comments. Local only; never ships.

Brand and owner terms are never exempted for being already public. They
match case-insensitively at word or CamelCase boundaries, so a bare term,
`Term voice`, `MyTerm`, and `TermVoice` all block. Leaf names keep
kebab-aware boundaries.

Scanned text per command:
- always: the command text itself (covers -m/--title/--body args)
- git commit: staged diff (git diff --cached), -F/--file message files
- git push: outgoing commit messages (@{upstream}..HEAD, else last 20)
- gh pr create/edit/comment/merge: --body-file/-F file contents

Block messages REDACT the matched term (first char + … + last char) so the
gate never echoes a private name into transcripts.

Allow-through conditions:
- Command matches none of the gated shapes
- ~/private-skills is absent (public install, CI)
- Effective cwd is not inside a toolkit-shaped repo (agents/ + skills/)
- Effective cwd is inside ~/private-skills itself (self-scan would
  always block that repo's own commits)
- No private name found in any scanned text
- Every remote the text can reach is a private GitHub repo, checked only
  after a match, through `gh api repos/OWNER/REPO` (owner, 2026-11-08:
  private name checks don't count for private repos). `git push` checks
  the remote it pushes to; `git commit` and `gh pr` check every remote (or
  the `--repo` value or PR URL). gh must answer visibility "private";
  "internal" does not count. Anything the parser does not fully
  understand counts as public and the gate still blocks: no remote, a
  non-GitHub URL, more than _MAX_VISIBILITY_LOOKUPS repos, a gh error or
  timeout (one 5 s budget), subshells, `$(...)`, backticks, a `cd`,
  `pushd` or `env` before a gated command, a git global option other
  than `-C <same dir>`, or any GIT_*/GH_* prefix or redirecting env var.
  Limit: an exempted commit's file contents are not re-scanned if that
  history is later pushed to a public remote (push scans only commit
  messages). Run scripts/private-term-audit.py before publishing a repo.
- PRIVATE_NAME_GATE_BYPASS=1 as an env var OR as an inline command prefix
  (`PRIVATE_NAME_GATE_BYPASS=1 git push ...`). The hook runs in the
  harness process, so an inline prefix never reaches os.environ — it is
  detected in the command string itself. Owner approval only; every
  bypass is logged to stderr.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard gate
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(2)

import json
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error, record_governance
from stdin_timeout import read_stdin

_BYPASS_ENV = "PRIVATE_NAME_GATE_BYPASS"

# Private skills repo locations, first existing wins (same list as vexinstall/migrate.py).
_PRIVATE_CANDIDATES = (Path.home() / "private-skills", Path.home() / "pgh" / "private-skills")
# Patched by tests. Runtime source of the private-name set.
_PRIVATE_DIR = next((p for p in _PRIVATE_CANDIDATES if p.is_dir()), _PRIVATE_CANDIDATES[0])
# Fallback public-skill index when the project has no skills/INDEX.json.
_USER_INDEX = Path.home() / ".claude" / "skills" / "INDEX.json"

# Gated command shapes. `gh pr merge` is matched broadly; a merge without
# --body carries no new text and passes the scan anyway.
# git global options may sit between `git` and the verb (`git -C dir push`,
# `git -c k=v commit`, `git --no-pager push`).
_GIT_OPTS = r"\bgit(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)|--?(?![Cc]\s)[A-Za-z][\w-]*(?:=\S+)?))*\s+"
_CMD_RE = re.compile(_GIT_OPTS + r"(?:commit|push)\b|\bgh\s+pr\s+(?:create|edit|comment|merge)\b")
_GIT_COMMIT_RE = re.compile(_GIT_OPTS + r"commit\b")
_GIT_PUSH_RE = re.compile(_GIT_OPTS + r"push\b")
_GH_PR_RE = re.compile(r"\bgh\s+pr\s+(?:create|edit|comment|merge)\b")

# Structural basenames that name file roles, not private components.
_STOPLIST = frozenset(
    {
        "skill",
        "skills",
        "agent",
        "agents",
        "readme",
        "index",
        "license",
        "changelog",
        "contributing",
        "claude",
        "references",
        "reference",
        "assets",
        "scripts",
        "docs",
        "templates",
        "template",
        "examples",
        "example",
        "hooks",
        "lib",
        "tests",
        "test",
        "notes",
        "archive",
        "private-skills",
    }
)
_MIN_NAME_LEN = 4
# Owner-kept extra terms, one per line; lives only in the private tree.
_OWNER_TERMS_FILE = ".private-terms"
# Brand derivation: a shared first segment is a brand only if it is not an
# ordinary word — `voice-a` + `voice-b` share "voice", not a brand.
_BRAND_MIN_SHARED = 2
_COMMON_WORDS = frozenset(
    {
        "anti",
        "auto",
        "base",
        "blog",
        "check",
        "code",
        "content",
        "core",
        "data",
        "deep",
        "deploy",
        "docs",
        "draft",
        "edit",
        "editor",
        "file",
        "five",
        "full",
        "game",
        "image",
        "images",
        "main",
        "news",
        "open",
        "pipeline",
        "post",
        "quick",
        "research",
        "review",
        "social",
        "story",
        "teach",
        "test",
        "text",
        "tool",
        "tools",
        "user",
        "video",
        "voice",
        "wizard",
        "write",
        "writer",
        "writing",
    }
)

_BUILTIN_COMMANDS = frozenset(
    {
        "goal",
        "compact",
        "schedule",
        "browser",
        "plan",
        "grill-me",
        "teamwork",
        "learn",
        "boost",
        "help",
        "clear",
        "cost",
        "doctor",
        "init",
        "login",
        "logout",
        "review",
        "pr-comments",
        "bug",
    }
)

# File-content arguments: commit message files and PR body files.
_COMMIT_FILE_FLAGS = {"-F", "--file"}
_PR_BODY_FILE_FLAGS = {"-F", "--body-file"}


_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _bypass_requested(command: str) -> str | None:
    """Return "env" or "inline" when the bypass is requested, else None.

    The hook runs in the harness process: an inline `PRIVATE_NAME_GATE_BYPASS=1
    git push ...` prefix never reaches os.environ, so the documented inline
    form must be detected in the command string. Only leading env-assignment
    tokens of a command segment count — the string inside a commit message
    does not bypass.
    """
    if os.environ.get(_BYPASS_ENV) == "1":
        return "env"
    for segment in re.split(r"&&|\|\||;", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        seen_bypass = False
        rest = tokens
        for i, token in enumerate(tokens):
            if not _ENV_ASSIGN_RE.match(token):
                rest = tokens[i:]
                break
            if token == f"{_BYPASS_ENV}=1":
                seen_bypass = True
        # The assignment must actually prefix a gated command — a stray
        # `; {_BYPASS_ENV}=1 ...` fragment inside message text does not
        # disarm the gate.
        if seen_bypass and _CMD_RE.search(" ".join(rest)):
            return "inline"
    return None


def _extract_effective_cwd(command: str, default_cwd: str | None) -> str | None:
    """Extract the effective working directory from a command string.

    Detects `cd <path> && ...` / `cd <path> ; ...` and `git -C <path>`.
    Same convention as pretool-branch-safety.
    """
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p
    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)
    return default_cwd


def _find_toolkit_root(cwd: str | None) -> Path | None:
    """Walk up from cwd to the nearest dir with agents/ AND skills/.

    Same toolkit-shape convention as pretool-adr-creation-gate. Returns None
    when cwd is not inside a toolkit repo — the gate stays dormant there.
    """
    if not cwd:
        return None
    try:
        candidate = Path(cwd).resolve()
    except OSError:
        return None
    for _ in range(8):
        try:
            if (candidate / "agents").is_dir() and (candidate / "skills").is_dir():
                return candidate
        except OSError:
            return None
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _public_skill_names(toolkit_root: Path) -> set[str]:
    """Public skill names from skills/INDEX.json (project first, then user).

    Tolerates the v2 dict format ({"skills": {name: ...}}) and a list of
    {"name": ...} entries. Missing or malformed index yields an empty set —
    the gate then errs toward blocking, never toward leaking.
    """
    names: set[str] = set()
    for index_path in (toolkit_root / "skills" / "INDEX.json", _USER_INDEX):
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        skills = data.get("skills", data) if isinstance(data, dict) else data
        if isinstance(skills, dict):
            names.update(k.lower() for k in skills)
        elif isinstance(skills, list):
            for entry in skills:
                if isinstance(entry, dict) and entry.get("name"):
                    names.add(str(entry["name"]).lower())
        if names:
            break
    return names


def _toolkit_identity(toolkit_root: Path) -> set[str]:
    """The toolkit's own public name: pyproject `name` plus its first segment.

    Some private leaf components share the toolkit's name. That one name is
    public by definition and must never block. Nothing else gets an
    "already public" exemption. Falls back to the root dir name.
    """
    name = ""
    try:
        m = re.search(
            r'^name\s*=\s*"([^"]+)"',
            (toolkit_root / "pyproject.toml").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if m:
            name = m.group(1)
    except OSError:
        pass
    name = (name or toolkit_root.name).lower()
    return {name, name.split("-")[0]}


def _public_segments(toolkit_root: Path, private_leaves: set[str]) -> set[str]:
    """Hyphen segments of every public skill and agent name.

    Public names are skills/INDEX.json keys plus agents/*.md stems in the
    toolkit root. Names that are also private leaves are skipped, so a
    private agent installed into the repo cannot launder its brand segment.
    """
    public = set(_public_skill_names(toolkit_root))
    try:
        public.update(p.stem.lower() for p in (toolkit_root / "agents").glob("*.md"))
    except OSError:
        pass
    public -= private_leaves
    segments: set[str] = set()
    for name in public:
        segments.add(name)
        segments.update(name.split("-"))
    return segments


def _frontmatter_name(skill_md: Path) -> str | None:
    """``name:`` from a SKILL.md frontmatter block, or None."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    m = re.search(r"^name:\s*[\"']?([A-Za-z0-9_-]+)", text.split("\n---", 1)[0], re.MULTILINE)
    return m.group(1) if m else None


def _raw_leaf_names() -> set[str]:
    """Lowercased LEAF component names under _PRIVATE_DIR, stoplist removed.

    Leaf components: dirs directly containing SKILL.md (a dir literally named
    `skill` is the nested <name>/skill/SKILL.md package layout — use <name>),
    plus stems of *.md files directly inside an agents/ dir. Interior
    reference/asset dir names and bare file stems inside packages are noise,
    not component names, and only produce false blocks.
    """
    raw: set[str] = set()
    try:
        for dirpath, dirnames, filenames in os.walk(_PRIVATE_DIR):
            # Skip VCS internals.
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            base = Path(dirpath)
            if "SKILL.md" in filenames:
                # A nested <dir>/skill/SKILL.md deploys under its frontmatter
                # name; a bare dir name can be an ordinary word.
                name = _frontmatter_name(base / "SKILL.md") or base.name
                if name.lower() == "skill" and base != _PRIVATE_DIR:
                    name = base.parent.name
                raw.add(name)
            if base.name == "agents":
                raw.update(Path(f).stem for f in filenames if f.endswith(".md"))
    except OSError:
        return set()
    names = {n.lower() for n in raw}
    names -= _STOPLIST
    return {n for n in names if len(n) >= _MIN_NAME_LEN and not n.startswith(".")}


def _private_names(toolkit_root: Path) -> set[str]:
    """Runtime private LEAF-name set, minus public homonyms and the toolkit name.

    Also the source of truth for scripts/generate-routing-map.py.
    """
    names = _raw_leaf_names()
    names -= _public_skill_names(toolkit_root)
    names -= _toolkit_identity(toolkit_root)
    names -= _BUILTIN_COMMANDS
    names -= _COMMON_WORDS
    return names


def _brand_terms(toolkit_root: Path, leaves: set[str]) -> set[str]:
    """First hyphen segments shared by >= 2 private leaf names.

    A segment qualifies only when it is at least _MIN_NAME_LEN chars, not a
    common word, not the toolkit's own name, and not a segment of any
    public skill or agent name.
    """
    counts: dict[str, int] = {}
    for name in leaves:
        if "-" in name:
            seg = name.split("-", 1)[0]
            counts[seg] = counts.get(seg, 0) + 1
    candidates = {
        seg
        for seg, n in counts.items()
        if n >= _BRAND_MIN_SHARED and len(seg) >= _MIN_NAME_LEN and seg not in _COMMON_WORDS and seg not in _STOPLIST
    }
    if not candidates:
        return set()
    candidates -= _toolkit_identity(toolkit_root)
    candidates -= _public_segments(toolkit_root, leaves)
    return candidates


def _owner_terms() -> set[str]:
    """Terms from ~/private-skills/.private-terms (one per line, # comments)."""
    try:
        text = (_PRIVATE_DIR / _OWNER_TERMS_FILE).read_text(encoding="utf-8")
    except OSError:
        return set()
    terms: set[str] = set()
    for line in text.splitlines():
        term = line.split("#", 1)[0].strip().lower()
        if len(term) >= 2:
            terms.add(term)
    return terms


def private_terms(toolkit_root: Path) -> tuple[set[str], set[str]]:
    """(leaf_names, strong_terms) for this machine. Shared with the audit script.

    strong_terms = brand terms + owner terms. They are never exempted for
    already appearing in the public tree.
    """
    leaves = _private_names(toolkit_root)
    strong = _brand_terms(toolkit_root, _raw_leaf_names() - _BUILTIN_COMMANDS) | _owner_terms()
    return leaves, strong


def term_pattern(leaves: set[str], strong: set[str]) -> re.Pattern[str] | None:
    """One compiled pattern for both term kinds, or None when both are empty.

    Leaf names: kebab-aware boundaries, so a name inside a longer kebab
    identifier does not match. Strong terms: case-insensitive, matched at a
    word boundary or a CamelCase hump on the left, and not followed by a
    lowercase letter (an optional plural `s` is allowed). That catches
    `term`, `Term voice`, `MyTerm`, `TermVoice`, `term-writer`, `term.com`.
    """
    parts: list[str] = []
    if leaves:
        alt = "|".join(re.escape(n) for n in sorted(leaves, key=len, reverse=True))
        parts.append(rf"(?<![A-Za-z0-9_-])(?i:{alt})(?![A-Za-z0-9_-])")
    if strong:
        alt = "|".join(re.escape(t) for t in sorted(strong, key=len, reverse=True))
        parts.append(rf"(?:(?<![A-Za-z0-9])|(?<=[a-z0-9])(?=[A-Z]))(?i:{alt})s?(?![a-z])")
    if not parts:
        return None
    return re.compile("|".join(parts))


def _redact(name: str) -> str:
    """First char + ellipsis + last char, e.g. `v…z`. Never the full name."""
    if len(name) <= 1:
        return "…"
    return f"{name[0]}…{name[-1]}"


def _file_args(command: str, flags: set[str]) -> list[str]:
    """Paths passed via file flags, handling both `-F p` and `--flag=p`."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    paths: list[str] = []
    for i, token in enumerate(tokens):
        if token in flags and i + 1 < len(tokens):
            paths.append(tokens[i + 1])
            continue
        for flag in flags:
            if flag.startswith("--") and token.startswith(flag + "="):
                paths.append(token[len(flag) + 1 :])
    return paths


def _run_git(args: list[str], cwd: str | None) -> str:
    """Run a git command; empty string on any failure (fail open)."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd or None,
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _added_side(diff: str) -> str:
    """Added lines and new paths of a unified diff.

    Removed lines are dropped: a commit that deletes a leaked name must pass.
    """
    keep = ("+", "rename to ", "copy to ")
    return "\n".join(line for line in diff.splitlines() if line.startswith(keep))


def _collect_scan_targets(command: str, cwd: str | None) -> list[tuple[str, str]]:
    """(location, text) pairs to scan for the matched command."""
    targets: list[tuple[str, str]] = [("command text", command)]

    file_paths: list[tuple[str, str]] = []
    if _GIT_COMMIT_RE.search(command):
        targets.append(("staged diff", _added_side(_run_git(["diff", "--cached"], cwd))))
        file_paths += [("commit message file", p) for p in _file_args(command, _COMMIT_FILE_FLAGS)]
    if _GIT_PUSH_RE.search(command):
        messages = _run_git(["log", "@{upstream}..HEAD", "--format=%B"], cwd)
        if not messages:
            # No upstream yet (first push of a branch): scan recent messages.
            messages = _run_git(["log", "-20", "--format=%B"], cwd)
        targets.append(("outgoing commit messages", messages))
    if _GH_PR_RE.search(command):
        file_paths += [("PR body file", p) for p in _file_args(command, _PR_BODY_FILE_FLAGS)]

    for label, path_str in file_paths:
        path = Path(path_str)
        if not path.is_absolute() and cwd:
            path = Path(cwd) / path
        try:
            targets.append((f"{label} {path_str}", path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return targets


# Private-repo exemption. Looked up only after a term matched, so clean
# commands never call gh. Any doubt counts as public: a command shape this
# parser does not fully understand blocks exactly as before.
_MAX_VISIBILITY_LOOKUPS = 4
# One budget for the whole exemption, well inside the 10 s hook timeout:
# a killed hook does not block.
_EXEMPTION_BUDGET = 5.0
_SCP_RE = re.compile(r"^(?:[^@/]+@)?([^:/]+):(?!//)(.+)$")
_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", re.IGNORECASE)
_PR_URL_RE = re.compile(r"^https?://([^/]+)/([^/]+)/([^/]+)/pull/\d+", re.IGNORECASE)
# Raw text that can hide a second command or change where one runs.
_OPAQUE_RE = re.compile(r"\$\(|`|<\(|>\(|\r")
_SEPARATORS = {"&&", "||", ";", "|", "&", "|&"}
_REDIRECT_RE = re.compile(r"[<>]+&?|&>>?")
# git push options that take a separate value.
_PUSH_VALUE_OPTS = {"-o", "--push-option", "--receive-pack", "--exec"}
# Environment that redirects git or gh to another repo or config.
_REDIRECT_ENV_RE = re.compile(r"^(GIT_|GH_|GITHUB_)")


def _parse_slug(url: str) -> tuple[str, str, str] | None:
    """(host, owner, repo) for a GitHub-style remote URL, or None."""
    url = url.strip()
    m = _URL_RE.match(url) or _SCP_RE.match(url)
    if not m:
        return None
    parts = m.group(2).strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return m.group(1).lower(), parts[0], parts[1]


def _parse_repo_flag(value: str) -> tuple[str, str, str] | None:
    """`gh --repo` value: OWNER/REPO, HOST/OWNER/REPO, or a URL."""
    if "://" in value or "@" in value:
        return _parse_slug(value)
    parts = value.strip("/").removesuffix(".git").split("/")
    if len(parts) == 2 and all(parts):
        return "github.com", parts[0], parts[1]
    if len(parts) == 3 and all(parts):
        return parts[0].lower(), parts[1], parts[2]
    return None


class _Unknown(Exception):
    """The command shape is not understood; treat the target as public."""


def _line_tokens(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError as exc:
        # An unclosed quote spans lines; too opaque to judge.
        raise _Unknown from exc


def _strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc body lines; they are input text, not commands.

    Heredoc operators are found in shell tokens, so a quoted `<<EOF` inside a
    message does not hide the lines after it. An unquoted heredoc still
    expands `$(...)` and backticks, which _OPAQUE_RE catches first.
    """
    out: list[str] = []
    pending: list[tuple[bool, str]] = []
    for line in command.split("\n"):
        if pending:
            strip_tabs, delim = pending[0]
            if (line.lstrip("\t") if strip_tabs else line) == delim:
                pending.pop(0)
            continue
        out.append(line)
        tokens = _line_tokens(line)
        for i, token in enumerate(tokens):
            if token == "<<" and i + 1 < len(tokens):
                delim = tokens[i + 1]
                strip_tabs = delim.startswith("-")
                pending.append((strip_tabs, delim[1:] if strip_tabs else delim))
            elif token.startswith("<<"):
                raise _Unknown
    if pending:
        raise _Unknown
    return "\n".join(out)


def _segments(command: str) -> list[list[str]]:
    """Shell-split command segments, or _Unknown for anything opaque.

    Splits on every list and pipe operator so each gated command is checked
    on its own. Subshells, substitutions and unknown operators are _Unknown.
    """
    if _OPAQUE_RE.search(command):
        raise _Unknown
    command = _strip_heredoc_bodies(command)
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segments: list[list[str]] = [[]]
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise _Unknown from exc
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in _SEPARATORS:
            segments.append([])
        elif _REDIRECT_RE.fullmatch(token):
            if segments[-1] and segments[-1][-1].isdigit():
                segments[-1].pop()
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            # A write to a real file could rewrite repo config.
            if ">" in token:
                # `>&N` and `>&-` move or close a stream; `>& word` writes a file.
                stream = token.endswith("&") and (target.isdigit() or target == "-")
                if not stream and target != "/dev/null":
                    raise _Unknown
            i += 1
        elif token and set(token) <= set("()<>&|;"):
            raise _Unknown
        else:
            segments[-1].append(token)
        i += 1
    return [seg for seg in segments if seg]


def _git_out(args: list[str], cwd: str | None, deadline: float) -> str:
    """git output within the exemption budget; _Unknown on failure."""
    budget = deadline - time.monotonic()
    if budget <= 0.2:
        raise _Unknown
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=budget,
            cwd=cwd or None,
            env=_clean_env(),
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise _Unknown from exc
    if result.returncode != 0:
        raise _Unknown
    return result.stdout


def _clean_env() -> dict[str, str]:
    """Hook environment without variables that redirect git or gh."""
    return {k: v for k, v in os.environ.items() if not _REDIRECT_ENV_RE.match(k)}


def _remote_names(cwd: str | None, deadline: float) -> list[str]:
    return _git_out(["remote"], cwd, deadline).split()


def _remote_urls(remote: str, cwd: str | None, deadline: float) -> list[str]:
    """URLs `git push <remote>` contacts, after insteadOf/pushInsteadOf rewrites."""
    urls = [u for u in _git_out(["remote", "get-url", "--push", "--all", remote], cwd, deadline).splitlines() if u]
    if not urls:
        raise _Unknown
    return urls


def _all_remote_urls(cwd: str | None, deadline: float) -> list[str]:
    names = _remote_names(cwd, deadline)
    if not names:
        raise _Unknown
    return [u for name in names for u in _remote_urls(name, cwd, deadline)]


def _same_dir(path: str, cwd: str | None) -> bool:
    if not cwd:
        return False
    if path == cwd:
        return True
    base = Path(cwd)
    try:
        return (base / path).resolve() == base.resolve()
    except OSError:
        return False


def _git_push_urls(args: list[str], cwd: str | None, deadline: float) -> list[str]:
    """URLs a `git push <args>` contacts; positional repository beats --repo, as in git."""
    positional: str | None = None
    repo_opt: str | None = None
    i = 0
    while i < len(args):
        token = args[i]
        if re.fullmatch(r"-[A-Za-z]{2,}", token):
            raise _Unknown
        if token in _PUSH_VALUE_OPTS:
            i += 2
            continue
        if token == "--repo":
            if i + 1 >= len(args):
                raise _Unknown
            repo_opt = args[i + 1]
            i += 2
            continue
        if token.startswith("--repo="):
            repo_opt = token[len("--repo=") :]
        elif token == "--":
            positional = args[i + 1] if i + 1 < len(args) else None
            break
        elif not token.startswith("-"):
            positional = token
            break
        i += 1
    target = positional or repo_opt
    names = _remote_names(cwd, deadline)
    if target is None:
        ref = _git_out(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}"], cwd, deadline).strip()
        target = next((n for n in sorted(names, key=len, reverse=True) if ref.startswith(n + "/")), None)
        if target is None:
            raise _Unknown
    if target in names:
        return _remote_urls(target, cwd, deadline)
    # A raw URL; ls-remote --get-url applies the same insteadOf rewrites git push does.
    return [_git_out(["ls-remote", "--get-url", target], cwd, deadline).strip() or target]


def _segment_slugs(seg: list[str], cwd: str | None, deadline: float) -> set[tuple[str, str, str]]:
    """GitHub repos one gated segment can reach; _Unknown on any doubt."""
    words = list(seg)
    while words and _ENV_ASSIGN_RE.match(words[0]):
        if words[0].startswith(f"{_BYPASS_ENV}="):
            words.pop(0)
            continue
        raise _Unknown
    if not words:
        raise _Unknown
    if words[0] == "git":
        rest = words[1:]
        while rest and rest[0].startswith("-"):
            if rest[0] == "-C" and len(rest) > 1 and _same_dir(rest[1], cwd):
                rest = rest[2:]
            elif rest[0] in ("--no-pager", "-P"):
                rest = rest[1:]
            else:
                raise _Unknown
        if not rest:
            raise _Unknown
        if rest[0] == "commit":
            urls = _all_remote_urls(cwd, deadline)
        elif rest[0] == "push":
            urls = _git_push_urls(rest[1:], cwd, deadline)
        else:
            raise _Unknown
    elif words[0] == "gh":
        if len(words) < 3 or words[1] != "pr" or words[2] not in ("create", "edit", "comment", "merge"):
            raise _Unknown
        slugs: set[tuple[str, str, str]] = set()
        args = words[3:]
        for i, token in enumerate(args):
            value = None
            if token in ("-R", "--repo"):
                if i + 1 >= len(args):
                    raise _Unknown
                value = args[i + 1]
            elif token.startswith("--repo="):
                value = token[len("--repo=") :]
            elif token.startswith("-R") and len(token) > 2:
                value = token[2:].removeprefix("=")
            elif m := _PR_URL_RE.match(token):
                slugs.add((m.group(1).lower(), m.group(2), m.group(3)))
            if value is not None:
                slug = _parse_repo_flag(value)
                if slug is None:
                    raise _Unknown
                slugs.add(slug)
        if slugs:
            return slugs
        urls = _all_remote_urls(cwd, deadline)
    else:
        raise _Unknown
    slugs = set()
    for url in urls:
        slug = _parse_slug(url)
        if slug is None:
            raise _Unknown
        slugs.add(slug)
    return slugs


def _target_slugs(command: str, cwd: str | None, deadline: float) -> set[tuple[str, str, str]]:
    """Every GitHub repo the gated text can reach; _Unknown on any doubt.

    Only a leading `cd <cwd> &&` may change directory, and every gated
    segment must run in that directory.
    """
    if any(k.startswith(("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG", "GH_REPO", "GH_HOST")) for k in os.environ):
        raise _Unknown
    slugs: set[tuple[str, str, str]] = set()
    gated = 0
    for index, seg in enumerate(_segments(command)):
        if _CMD_RE.search(" ".join(seg)):
            gated += 1
            slugs |= _segment_slugs(seg, cwd, deadline)
        elif index == 0 and seg[0] == "cd" and len(seg) == 2 and _same_dir(seg[1], cwd):
            continue
        elif not _harmless(seg):
            # Anything else could change the directory, config, branch, or
            # environment the gated command runs with.
            raise _Unknown
    if not gated or not slugs:
        raise _Unknown
    return slugs


# Segments allowed beside a gated command: they read or print, and cannot
# change where a commit or push lands.
# None of these writes a file on its own; redirects are checked separately.
_HARMLESS_COMMANDS = frozenset({"echo", "printf", "true", "tail", "head", "grep", "wc", "cat"})
_HARMLESS_GIT = frozenset({"add", "status", "diff", "log", "show"})


def _harmless(seg: list[str]) -> bool:
    if seg[0] in _HARMLESS_COMMANDS:
        return True
    if len(seg) < 2 or seg[0] != "git" or seg[1] not in _HARMLESS_GIT:
        return False
    # `git log/diff/show --output=<file>` writes a file.
    return not any(arg.startswith(("--output", "-o")) for arg in seg[2:])


def _gh_visibility(slug: tuple[str, str, str], deadline: float) -> str:
    host, owner, repo = slug
    budget = deadline - time.monotonic()
    if budget <= 0.2:
        return ""
    try:
        proc = subprocess.run(
            ["gh", "api", "--hostname", host, f"repos/{owner}/{repo}", "--jq", ".visibility"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=budget,
            check=False,
            env=_clean_env(),
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _targets_all_private(command: str, cwd: str | None) -> bool:
    """True only when every repo the command can reach reports visibility "private".

    "internal" (visible across an enterprise) counts as not private. Any
    error, timeout, or crash returns False, so the gate blocks.
    """
    deadline = time.monotonic() + _EXEMPTION_BUDGET
    try:
        slugs = _target_slugs(command, cwd, deadline)
        if len(slugs) > _MAX_VISIBILITY_LOOKUPS:
            return False
        with ThreadPoolExecutor(max_workers=len(slugs)) as pool:
            answers = list(pool.map(lambda s: _gh_visibility(s, deadline), sorted(slugs)))
        return all(a == "private" for a in answers)
    except Exception:
        return False


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)

    command = event.get("tool_input", {}).get("command", "")
    if not command or not _CMD_RE.search(command):
        sys.exit(0)

    bypass = _bypass_requested(command)
    if bypass:
        # Always logged — a bypass is an audit event, not a debug detail.
        print(f"[private-name-leak-gate] BYPASSED ({bypass}) via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    # Graceful no-op: no private tree on this machine (public install, CI).
    if not _PRIVATE_DIR.is_dir():
        if debug:
            print("[private-name-leak-gate] No private tree — dormant", file=sys.stderr)
        sys.exit(0)

    default_cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    cwd = _extract_effective_cwd(command, default_cwd)

    # Never scan the private repo's own commits — every one names itself.
    if cwd:
        try:
            if Path(cwd).resolve().is_relative_to(_PRIVATE_DIR.resolve()):
                sys.exit(0)
        except OSError:
            pass

    toolkit_root = _find_toolkit_root(cwd)
    if toolkit_root is None:
        if debug:
            print("[private-name-leak-gate] Not a toolkit repo — allowing", file=sys.stderr)
        sys.exit(0)

    leaves, strong = private_terms(toolkit_root)
    pattern = term_pattern(leaves, strong)
    if pattern is None:
        sys.exit(0)

    for location, text in _collect_scan_targets(command, cwd):
        if not text:
            continue
        match = pattern.search(text)
        if match:
            if _targets_all_private(command, cwd):
                # Repo names can be private terms too; never echo them.
                print(
                    "[private-name-leak-gate] Allowing: every target remote is a private GitHub repo",
                    file=sys.stderr,
                )
                sys.exit(0)
            redacted = _redact(match.group(0))
            print(
                f"[private-name-leak-gate] BLOCKED: private term ({redacted}) found in {location}.",
                file=sys.stderr,
            )
            record_governance(
                "policy_violation",
                hook_name="pretool-private-name-leak-gate",
                tool_name="Bash",
                hook_phase="pre",
                severity="high",
                blocked=True,
                command=command,
            )
            deny_tool_use(
                "PreToolUse",
                f"Private term ({redacted}) found in {location}. "
                "Private skill names and brand terms must not reach commits, pushes, or PR text. "
                "Remove the reference and retry. "
                f"Bypass with {_BYPASS_ENV}=1 (env var or inline command prefix) "
                "only with explicit owner approval.",
            )
            sys.exit(0)

    if debug:
        print("[private-name-leak-gate] Clean — allowing", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        hook_error("pretool-private-name-leak-gate", e)
    finally:
        sys.exit(0)
