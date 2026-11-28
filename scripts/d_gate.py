"""/d hard rules as code: intent receipts and dispatch reasons.

`/d` runs the routed skill in the main loop by default (plans/009, L6). Two of
its rules used to be prose only. This module makes them checks that return an
instruction the model can act on:

1. Intent receipt. `jev-intent-align.py` writes a receipt for every run (also
   on `unavailable` and `error`, so a Jev outage never blocks). The /d execute
   step (`build-dispatch.py` with `"router": "d"`) refuses to run without a
   receipt whose request hash and intent hash match `task_spec.request_verbatim`
   and `task_spec.intent`, and prints the command to run.
2. Dispatch reason. A /d dispatch must name one allowed reason, and the reason's
   precondition must hold. The worker must get the skill and its references.
   `context-budget` is measured: `task_spec.files` must name at least 10
   existing files or 50 KB.
3. Verification. A Medium or Complex /d route names `task_spec.acceptance` up
   front, plus `task_spec.scenario` when its files touch the installer, hooks,
   or routing scripts. build-dispatch prints the closing verifier step.

This is a check the model can skip by not calling the script, so it is a
tool-enforced gate, not a hook boundary. Receipts hold hashes and verdicts only,
never request or intent text. Stdlib only; never raises from `write_receipt`.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import tempfile
import time
from pathlib import Path
from typing import Any

RECEIPT_DIR_ENV = "VEXJOY_D_RECEIPT_DIR"
RECEIPT_MAX_AGE_S = 6 * 3600
# Session id resolution shared by the writer (jev_intent_align) and the reader
# (build-dispatch), so both sides key the same directory.
_SESSION_ENVS = ("JEV_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")

ROUTER_DO = "do"
ROUTER_D = "d"
VALID_ROUTERS = (ROUTER_DO, ROUTER_D)

# The only reasons /d leaves the main loop. Value = the precondition, as the
# model reads it in an error message.
DISPATCH_REASONS: dict[str, str] = {
    "fan-out": "independent parts that need fresh context, each worker with its own scope (task_spec.ownership or files)",
    "worktree": "work that needs worktree isolation (flags.worktree true)",
    "haiku-gather": "read-only gathering on haiku (model haiku)",
    "verifier": "an independent reviewer or verifier of work already done (task_spec.acceptance names what to check)",
    "overlay-agent": "work the manifest's AGENTS: section matches, run by that private overlay agent (agent names a live overlay agent)",
    "context-budget": (
        "one long job whose reading would flood this thread and is not needed afterwards: task_spec.files lists "
        "at least 10 existing files or 50 KB, and task_spec.acceptance says what the worker hands back"
    ),
}
# Reasons whose worker carries its own domain: `references` is optional for them.
REFERENCES_OPTIONAL_REASONS = frozenset({"overlay-agent"})

# context-budget: the measured floor for a dispatch that only saves main-loop context.
BUDGET_MIN_FILES = 10
BUDGET_MIN_BYTES = 50 * 1024
_BUDGET_WALK_CAP = 20000

# Paths whose changes need a real-scenario check before /d reports done: the installer,
# hooks, and the routing scripts. Unit tests passed on every one of the two blocking
# bugs PR #1156's reviewer found; only an install-then-upgrade run caught them.
SCENARIO_PREFIXES = (
    "hooks/",
    "scripts/vexinstall/",
    "skills/meta/d/",
    "skills/meta/do/",
)
SCENARIO_FILES = frozenset(
    {
        "install.sh",
        "install.ps1",
        "scripts/build-dispatch.py",
        "scripts/d_gate.py",
        "scripts/d-preflight.py",
        "scripts/jev-route.py",
        "scripts/jev_intent_align.py",
        "scripts/jev-intent-align.py",
        "scripts/pre-route.py",
        "scripts/routing-manifest.py",
        "scripts/get-routing-manifest.sh",
        "scripts/routing_index_merge.py",
    }
)
VERIFY_COMPLEXITIES = frozenset({"medium", "complex"})

ALIGN_HINT = (
    'python3 "$SDIR/jev-intent-align.py" --request-file "$REQUEST_FILE" --route-file "$ROUTE_FILE" '
    '--proposed-intent-file "$INTENT_FILE" --json-compact'
)


def resolve_router(decision: dict) -> str:
    """`do` (default, absent) or `d`. Anything else is an input error the caller raises."""
    raw = decision.get("router")
    router = str(raw).strip().lower() if raw not in (None, "") else ROUTER_DO
    if router not in VALID_ROUTERS:
        raise ValueError(f"'router' {raw!r} — must be one of {'/'.join(VALID_ROUTERS)}")
    return router


def session_id() -> str:
    for name in _SESSION_ENVS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return "no-session"


def text_hash(value: str | None) -> str:
    """Hash of the text with surrounding whitespace removed (a file and a JSON string differ by a newline)."""
    return hashlib.sha256((value or "").strip().encode("utf-8")).hexdigest()[:16]


def _user_tag() -> str:
    getuid = getattr(os, "getuid", None)
    if callable(getuid):
        return str(getuid())
    raw = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:40] or "user"


def receipt_dir() -> Path:
    override = os.environ.get(RECEIPT_DIR_ENV)
    base = Path(override) if override else Path(tempfile.gettempdir()) / f"vexjoy-d-receipts-{_user_tag()}"
    return base / re.sub(r"[^A-Za-z0-9_.-]", "_", session_id())[:80]


def receipt_path(request: str) -> Path:
    return receipt_dir() / f"{text_hash(request)}.json"


def write_receipt(request: str, intent: str, result: dict[str, Any], phase: str) -> Path | None:
    """Persist one receipt (hashes and verdict only, mode 0600). Returns the path, or None on any failure."""
    try:
        path = receipt_path(request)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
        body = {
            "request_hash": text_hash(request),
            "intent_hash": text_hash(intent),
            "phase": phase,
            "alignment": str(result.get("alignment") or "error"),
            "clarification_needed": bool(result.get("clarification_needed")),
            "issues": [str(i)[:200] for i in issues][:10],
            "questions_version": result.get("questions_version"),
            "ts": time.time(),
        }
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(body, fh)
            try:
                os.chmod(tmp_name, 0o600)
            except OSError:
                pass
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return path
    except Exception:
        return None


def _rerun(why: str) -> str:
    return (
        f"{why} Run the Phase 2 validator on the exact PROPOSED_INTENT, then rerun this command "
        f"with task_spec.intent set to that same text:\n  {ALIGN_HINT}"
    )


def check_receipt(task_spec: dict, now: float | None = None) -> str | None:
    """Return None when a matching receipt allows execution, else the instruction to act on."""
    request = task_spec.get("request_verbatim") if isinstance(task_spec, dict) else None
    intent = task_spec.get("intent") if isinstance(task_spec, dict) else None
    if not isinstance(request, str) or not request.strip():
        return "/d needs task_spec.request_verbatim: the user's message, unchanged."
    if not isinstance(intent, str) or not intent.strip():
        return "/d needs task_spec.intent: the exact PROPOSED_INTENT that Phase 2 validated."
    path = receipt_path(request)
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _rerun(
            "No intent receipt exists for this request in this session. task_spec.request_verbatim must be the "
            "same text as the validator's request file (the user's message, no /d prefix)."
        )
    if not isinstance(receipt, dict):
        return _rerun("The intent receipt is unreadable.")
    try:
        ts = float(receipt.get("ts") or 0)
    except (TypeError, ValueError):
        return _rerun("The intent receipt is unreadable.")
    age = (now if now is not None else time.time()) - ts
    if age > RECEIPT_MAX_AGE_S:
        return _rerun("The intent receipt is older than 6 hours.")
    if receipt.get("phase") != "proposed":
        return _rerun("The receipt came from a run without --proposed-intent-file.")
    if receipt.get("intent_hash") != text_hash(intent):
        return _rerun("The receipt was issued for a different intent than task_spec.intent.")
    alignment = receipt.get("alignment")
    if receipt.get("clarification_needed") and not str(task_spec.get("clarification") or "").strip():
        return (
            "Jev flagged an essential ambiguity. Ask the user one concise question and stop. After the answer, "
            "put it in task_spec.clarification (or restate the intent and rerun the validator)."
        )
    if alignment == "review" and not str(task_spec.get("gaps") or "").strip():
        issues = "; ".join(receipt.get("issues") or []) or "unspecified"
        return (
            f"Intent alignment returned review ({issues}). Correct PROPOSED_INTENT or the route and rerun the "
            "validator once; if issues remain, carry them into task_spec.gaps and rerun this command."
        )
    return None


def skill_dir(skill: str, skill_entries: dict[str, dict], roots: list[Path]) -> Path | None:
    """The skill's directory: the index `file` under each root, then the flat installed layout (`skills/<name>`)."""
    file = (skill_entries.get(skill) or {}).get("file")
    candidates: list[Path] = []
    for root in roots:
        if isinstance(file, str):
            path = Path(file)
            candidates.append((path if path.is_absolute() else root / path).parent)
        candidates.append(root / "skills" / skill)
    for cand in candidates:
        if (cand / "SKILL.md").is_file():
            return cand.resolve()
    return None


def available_references(skill_dir: Path | None) -> list[str]:
    if skill_dir is None:
        return []
    refs = skill_dir / "references"
    if not refs.is_dir():
        return []
    return sorted(p.relative_to(skill_dir).as_posix() for p in refs.rglob("*.md"))


def resolve_references(
    skill: str, raw: object, skill_entries: dict[str, dict], roots: list[Path]
) -> tuple[list[str], str | None]:
    """Validate `references` for a /d dispatch. Returns (absolute paths, problem or None)."""
    found = skill_dir(skill, skill_entries, roots)
    if found is None:
        return [], f"cannot find skill {skill!r}'s directory to hand over its references; check the skill name"
    available = available_references(found)
    names = [str(r).strip() for r in raw] if isinstance(raw, list) else []
    names = [n for n in names if n]
    if not available:
        return [], None  # nothing to hand over; the skill alone carries the domain
    if not names:
        listed = ", ".join(available[:15]) + (" ..." if len(available) > 15 else "")
        return [], (
            f"A /d dispatch must hand the worker the skill and its reference. Set 'references' to one or more "
            f"files from skill {skill!r}: {listed}"
        )
    resolved: list[str] = []
    for name in names:
        norm = name.replace("\\", "/")
        candidates = [norm, f"references/{norm}", f"references/{norm}.md"]
        hit = next((c for c in candidates if c in available), None)
        if hit is None:
            stem_hits = [a for a in available if Path(a).stem == Path(norm).stem]
            hit = stem_hits[0] if len(stem_hits) == 1 else None
        if hit is None:
            return [], f"reference {name!r} is not a file under skill {skill!r}'s references/ directory"
        if str(found / hit) not in resolved:
            resolved.append(str(found / hit))
    return resolved, None


def check_dispatch(
    decision: dict,
    model: str | None,
    overlay_agents: frozenset[str] | set[str] = frozenset(),
    base: Path | None = None,
) -> str | None:
    """Return None when the dispatch reason and its precondition hold, else the instruction to act on.

    `overlay_agents` is the live private overlay agent set
    (routing_index_merge.overlay_agent_items); the `overlay-agent` reason holds
    only when `decision["agent"]` is in it, so a retired, built-in, or unknown
    name never buys a dispatch.
    """
    reason = str(decision.get("dispatch_reason") or "").strip().lower()
    if reason not in DISPATCH_REASONS:
        options = "; ".join(f"{k} = {v}" for k, v in DISPATCH_REASONS.items())
        return (
            f"/d runs in the main loop unless a dispatch pays. Set execution to main, or set dispatch_reason to "
            f"one of: {options}. Got {decision.get('dispatch_reason')!r}."
        )
    flags = decision.get("flags") if isinstance(decision.get("flags"), dict) else {}
    spec = decision.get("task_spec") if isinstance(decision.get("task_spec"), dict) else {}
    if reason == "worktree" and not flags.get("worktree"):
        return "dispatch_reason worktree needs flags.worktree true."
    if reason == "haiku-gather" and model != "haiku":
        return "dispatch_reason haiku-gather needs model haiku; other work runs in the main loop."
    if reason == "fan-out" and not (str(spec.get("ownership") or "").strip() or str(spec.get("files") or "").strip()):
        return "dispatch_reason fan-out needs this worker's own scope in task_spec.ownership or task_spec.files."
    if reason == "verifier" and not str(spec.get("acceptance") or "").strip():
        return "dispatch_reason verifier needs task_spec.acceptance: what the verifier checks."
    if reason == "context-budget":
        problem = check_budget(spec, base or Path.cwd())
        if problem:
            return problem
    if reason == "overlay-agent":
        agent = str(decision.get("agent") or "").strip().lower()
        if not agent or agent not in {str(a).lower() for a in overlay_agents}:
            return (
                f"dispatch_reason overlay-agent needs 'agent' set to a live private overlay agent (one the "
                f"manifest's AGENTS: section lists); got {decision.get('agent')!r}. Otherwise run in the main loop."
            )
    return None


def split_paths(raw: object) -> list[str]:
    """`task_spec.files` as a list: a list, or a string split on commas, whitespace, and newlines.

    A `path:10-40` line range is cut to the path.
    """
    items = raw if isinstance(raw, list) else re.split(r"[,\s]+", str(raw or ""))
    out: list[str] = []
    for item in items:
        text = str(item).strip().strip("`'\"")
        text = re.sub(r":\d+(-\d+)?$", "", text)
        if text and text not in out:
            out.append(text)
    return out


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def measure_scope(raw: object, base: Path) -> tuple[int, int]:
    """(file count, bytes) of the existing files and dirs `raw` names, inside `base` only.

    `base` is the repo root: a path that resolves outside it (`~`, `/`, `..`)
    counts nothing, so the floor cannot be met by pointing at the home dir.
    Every entry visited, skipped ones included, counts toward the walk cap.
    """
    root = base.resolve()
    count = size = visited = 0
    seen: set[Path] = set()
    for name in split_paths(raw):
        try:
            path = Path(name)
            path = (path if path.is_absolute() else root / path).resolve()
            if not _inside(path, root):
                continue
            if path.is_file():
                targets: list[Path] = [path]
            elif path.is_dir():
                targets = []
                for dirpath, dirnames, filenames in os.walk(path):
                    dirnames[:] = [d for d in dirnames if d != ".git"]
                    dp = Path(dirpath)
                    for fname in filenames:
                        targets.append(dp / fname)
                        if visited + len(targets) > _BUDGET_WALK_CAP:
                            break
                    if visited + len(targets) > _BUDGET_WALK_CAP:
                        break
            else:
                targets = []
            for target in targets:
                visited += 1
                if visited > _BUDGET_WALK_CAP:
                    return count, size
                try:
                    if not target.is_file():
                        continue
                    real = target.resolve()
                    if real in seen or ".git" in real.parts or not _inside(real, root):
                        continue
                    seen.add(real)
                    size += real.stat().st_size
                    count += 1
                except OSError:
                    continue
        except OSError:
            continue
    return count, size


def check_budget(spec: dict, base: Path) -> str | None:
    """None when task_spec names a reading load big enough to justify a context-budget dispatch."""
    if not str(spec.get("acceptance") or "").strip():
        return "dispatch_reason context-budget needs task_spec.acceptance: what the worker hands back to this thread."
    count, size = measure_scope(spec.get("files"), base)
    if count >= BUDGET_MIN_FILES or size >= BUDGET_MIN_BYTES:
        return None
    return (
        f"dispatch_reason context-budget needs task_spec.files to name at least {BUDGET_MIN_FILES} existing files "
        f"or {BUDGET_MIN_BYTES // 1024} KB; it names {count} files, {size // 1024} KB (measured from {base}). "
        "A job that small runs in the main loop."
    )


def _scenario_hit(rel: str) -> bool:
    rel = rel.strip("/")
    if rel in SCENARIO_FILES or rel.startswith(SCENARIO_PREFIXES):
        return True
    return any(rel == p.rstrip("/") for p in SCENARIO_PREFIXES)


def scenario_paths(raw: object, base: Path | None = None) -> list[str]:
    """The named paths that need a real-scenario check (installer, hooks, routing scripts).

    Relative paths are read from the repo root. A leading ``new:`` prefix is
    stripped and ``..`` segments are normalized. An absolute path inside `base`
    is made relative to it; one outside it (another checkout or worktree)
    matches when any of its trailing segments does, erring toward a check.
    """
    root = (base or Path.cwd()).resolve()
    hits: list[str] = []
    for name in split_paths(raw):
        text = name.replace("\\", "/")
        if text.startswith("new:"):
            text = text[4:]
        if not text:
            continue
        if text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
            try:
                rel = Path(text).resolve().relative_to(root).as_posix()
            except (ValueError, OSError):
                norm_abs = posixpath.normpath(text)
                parts = [p for p in norm_abs.split("/") if p]
                rel = next(
                    ("/".join(parts[i:]) for i in range(len(parts)) if _scenario_hit("/".join(parts[i:]))), norm_abs
                )
        else:
            rel = posixpath.normpath(text)
            rel = re.sub(r"^(\./)+", "", rel)
            if rel.startswith("../") or rel == "..":
                try:
                    rel = (root / text).resolve().relative_to(root).as_posix()
                except (ValueError, OSError):
                    parts = [p for p in rel.split("/") if p and p != ".."]
                    rel = next(
                        ("/".join(parts[i:]) for i in range(len(parts)) if _scenario_hit("/".join(parts[i:]))), rel
                    )
        clean = rel.strip("/")
        if _scenario_hit(clean) and clean not in hits:
            hits.append(clean)
    return hits


def check_verify(complexity: str, spec: dict, base: Path | None = None) -> str | None:
    """Medium and Complex /d work names its acceptance up front; risky paths also name a real scenario."""
    if complexity not in VERIFY_COMPLEXITIES:
        return None
    if not str(spec.get("acceptance") or "").strip():
        return (
            f"A {complexity} /d route needs task_spec.acceptance: the command or check that proves the work, "
            "which an independent verifier runs before you report done."
        )
    hits = scenario_paths(spec.get("files"), base)
    if hits and not str(spec.get("scenario") or "").strip():
        shown = ", ".join(hits[:5]) + (" ..." if len(hits) > 5 else "")
        return (
            f"task_spec.files touches {shown}. Set task_spec.scenario to a real-scenario check, not only unit "
            "tests: for example install origin/main into a temporary HOME, switch to the branch, and run sync "
            "and doctor; or run the hook against a fresh `git archive` export."
        )
    return None


def verify_step(spec: dict) -> str:
    """The closing step build-dispatch prints for a Medium or Complex /d route."""
    scenario = str(spec.get("scenario") or "").strip()
    check = str(spec.get("acceptance") or "").strip()
    tail = f" It also runs the real scenario: {scenario.rstrip('.')}." if scenario else ""
    return (
        "Before you report done: dispatch one independent verifier (build-dispatch.py with execution dispatch, "
        "dispatch_reason verifier, a model per Model choice, and the same acceptance). Give it the change, not "
        f"your conclusion. It checks: {check}.{tail} Fix what it confirms, then report its verdict."
    )
