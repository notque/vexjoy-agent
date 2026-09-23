#!/usr/bin/env python3
# hook-version: 1.2.0
"""
PreToolUse:Bash Hook: Private Name Leak Gate

Blocks git commit, git push, and gh pr create/edit/comment/merge when the
text they would publish contains the name of a private component installed
from ~/private-skills. Private component names must never reach this repo,
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
- PRIVATE_NAME_GATE_BYPASS=1 as an env var OR as an inline command prefix
  (`PRIVATE_NAME_GATE_BYPASS=1 git push ...`). The hook runs in the
  harness process, so an inline prefix never reaches os.environ — it is
  detected in the command string itself. Owner approval only; every
  bypass is logged to stderr.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error, record_governance
from stdin_timeout import read_stdin

_BYPASS_ENV = "PRIVATE_NAME_GATE_BYPASS"

# Patched by tests. Runtime source of the private-name set.
_PRIVATE_DIR = Path.home() / "private-skills"
# Fallback public-skill index when the project has no skills/INDEX.json.
_USER_INDEX = Path.home() / ".claude" / "skills" / "INDEX.json"

# Gated command shapes. `gh pr merge` is matched broadly; a merge without
# --body carries no new text and passes the scan anyway.
_CMD_RE = re.compile(r"\bgit\s+commit\b|\bgit\s+push\b|\bgh\s+pr\s+(?:create|edit|comment|merge)\b")
_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")
_GIT_PUSH_RE = re.compile(r"\bgit\s+push\b")
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
        "test",
        "text",
        "tool",
        "tools",
        "user",
        "video",
        "voice",
        "write",
        "writer",
        "writing",
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
                name = base.name
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
    strong = _brand_terms(toolkit_root, _raw_leaf_names()) | _owner_terms()
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


def _collect_scan_targets(command: str, cwd: str | None) -> list[tuple[str, str]]:
    """(location, text) pairs to scan for the matched command."""
    targets: list[tuple[str, str]] = [("command text", command)]

    file_paths: list[tuple[str, str]] = []
    if _GIT_COMMIT_RE.search(command):
        targets.append(("staged diff", _run_git(["diff", "--cached"], cwd)))
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
