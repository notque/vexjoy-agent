#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Worktree Edit Guard (ADR: worktree-edit-guard)

Blocks Write/Edit/MultiEdit/NotebookEdit calls made by a worktree-isolated agent
that target files in the SHARED main working tree instead of the agent's own
worktree copy. Worktree agents repeatedly Read/Edit absolute main-repo paths
(e.g. /home/feedgen/road-to-aew/src/foo.ts) bypassing their worktree CWD, which
writes into the main tree and destroys isolation. Advisory skill text failed to
stop this; this hook enforces it.

Block rule (precise, do NOT over-block):
  - Read cwd / tool_name / tool_input.file_path from stdin JSON.
    Handle MultiEdit (top-level file_path) and NotebookEdit (notebook_path).
    Fall back to os.getcwd() if cwd absent.
  - If cwd does NOT contain "/.claude/worktrees/": ALLOW (parent session and
    non-worktree agents are entirely unaffected).
  - Otherwise derive:
      worktree_root  = path up to and including ".../.claude/worktrees/<id>"
      main_repo_root = path BEFORE "/.claude/worktrees/"
    Resolve target (relative -> join cwd; absolute -> as-is) to a realpath.
  - BLOCK only if resolved target is INSIDE main_repo_root AND NOT inside
    worktree_root. (Edits inside the worktree are allowed; /tmp, ~/.claude, and
    other out-of-repo paths are allowed -- only main-repo escapes are blocked.)

Deny mechanism: JSON permissionDecision:deny on stdout + exit 0 (matches
pretool-config-protection.py / pretool-unified-gate.py convention). The deny
message names worktree_root and the corrected path the agent should edit.

Properties: dependency-free (stdlib only). Fails OPEN on any internal error --
never blocks legitimate work due to a hook bug. Bypass:
WORKTREE_EDIT_GUARD_BYPASS=1.

Path namespace (HIGH-1): cwd is realpath-canonicalized ONCE in main() before
roots/targets are derived, so containment checks never compare a canonical
target against a raw symlinked root (which both allowed escapes and blocked
legitimate in-worktree edits under symlinked /tmp, $HOME, NFS).

Worktree-root derivation (MEDIUM-1): the worktree root comes from
`git -C <cwd> rev-parse --show-toplevel` (0.5s timeout), which is robust to
nested `.../worktrees/<group>/<id>/` layouts that the single-segment
string-split computed too shallow (letting sibling-worktree edits slip
through). Git is invoked ONLY when cwd is inside a worktree (rare hot path),
not on the common pass-through. Any git failure (missing, not-a-repo, timeout,
non-zero) falls back to the string-split and ultimately fails OPEN.
"""

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

try:
    from stdin_timeout import read_stdin
except Exception:  # pragma: no cover - lib import must never hard-fail the hook

    def read_stdin(timeout: int = 10) -> str:
        return sys.stdin.read()


try:
    from hook_utils import deny_tool_use
except Exception:  # pragma: no cover - lib import must never hard-fail the hook

    def deny_tool_use(event_name: str, reason: str) -> None:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event_name,
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )


_BYPASS_ENV = "WORKTREE_EDIT_GUARD_BYPASS"
_WORKTREE_MARKER = "/.claude/worktrees/"
# This hook is the SOLE PreToolUse guard covering MultiEdit and NotebookEdit
# (pretool-unified-gate.py matches only Bash|Write|Edit). The MultiEdit/
# NotebookEdit schema-parsing in _iter_target_paths and the tests that exercise
# it must never be weakened: nothing else blocks those two tools.
_GUARDED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
_GIT_TOPLEVEL_TIMEOUT_S = 0.5


def _git_worktree_root(cwd: str) -> str | None:
    """Return the realpath-resolved worktree root via `git rev-parse`, or None.

    `git -C <cwd> rev-parse --show-toplevel` returns the top of the *current*
    working tree, which for a worktree CWD is the worktree root itself
    (already realpath-resolved by git). This is the source of truth and is
    robust to ANY nesting layout under the marker.

    Returns None on any failure (git missing, not a repo, timeout, non-zero
    exit, empty output) so the caller can fall back to string-splitting and,
    ultimately, fail OPEN.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_GIT_TOPLEVEL_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    if not root:
        return None
    # Canonicalize so it shares the same resolved namespace as the (already
    # realpath'd) cwd and targets, regardless of git's own normalization.
    try:
        return os.path.realpath(root)
    except OSError:
        return root


def _split_worktree(cwd: str) -> tuple[str, str] | None:
    """Given a cwd inside a worktree, return (main_repo_root, worktree_root).

    `cwd` is expected to already be realpath-canonicalized by the caller so
    that roots and targets are compared in one resolved namespace.

    main_repo_root = everything before "/.claude/worktrees/".
    worktree_root  = the worktree's own toplevel. Preferred source is
                     `git rev-parse --show-toplevel` (robust to nested
                     `.../<group>/<id>/` layouts). If git is unavailable we
                     fall back to the single-segment string-split, and if that
                     also fails we return None -> ALLOW (fail open).

    Returns None if cwd is not inside a worktree.
    """
    idx = cwd.find(_WORKTREE_MARKER)
    if idx == -1:
        return None
    main_repo_root = cwd[:idx]
    if not main_repo_root:
        return None

    # Preferred: ask git for the worktree's true toplevel. This handles nested
    # worktree-id layouts (e.g. ".../worktrees/<group>/<id>/") that the
    # single-segment string-split computes too shallow, which would let edits
    # into a SIBLING worktree slip through (the exact clobber this hook stops).
    git_root = _git_worktree_root(cwd)
    if git_root is not None and _is_inside(cwd, git_root):
        # Sanity: the git toplevel must itself live under the worktrees marker
        # of this main repo. Otherwise git resolved to something unexpected
        # (e.g. cwd is inside the marker dir but not an actual worktree) and we
        # fall back to the string-split below.
        if _is_inside(git_root, f"{main_repo_root}{_WORKTREE_MARKER}".rstrip("/")):
            return main_repo_root, git_root

    # Fallback: single-segment string-split. This assumes the worktree id is a
    # single path segment directly after the marker. For a nested layout this
    # computes worktree_root too shallow; we keep it only as a degraded path
    # when git is unavailable, and ultimately fail OPEN if even this fails.
    after = cwd[idx + len(_WORKTREE_MARKER) :]
    worktree_id = after.split("/", 1)[0]
    if not worktree_id:
        return None
    worktree_root = f"{main_repo_root}{_WORKTREE_MARKER}{worktree_id}"
    return main_repo_root, worktree_root


def _is_inside(child: str, parent: str) -> bool:
    """True if realpath `child` is `parent` or nested within `parent`.

    Uses os.path.commonpath on normalized absolute paths to avoid the
    "/repo-evil" startswith("/repo") false positive.
    """
    try:
        child_n = os.path.normpath(child)
        parent_n = os.path.normpath(parent)
        return os.path.commonpath([child_n, parent_n]) == parent_n
    except (ValueError, TypeError):
        # commonpath raises ValueError for mixed absolute/relative or drives.
        return False


def _resolve_target(file_path: str, cwd: str) -> str:
    """Resolve a tool target path to a realpath.

    Relative paths are joined against cwd; absolute paths are used as-is.
    realpath collapses symlinks and `..` so escapes cannot hide behind them.
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)
    return os.path.realpath(file_path)


def _iter_target_paths(tool_name: str, tool_input: dict):
    """Yield every file path a guarded tool intends to write.

    Write/Edit: tool_input["file_path"]
    MultiEdit:  top-level tool_input["file_path"] (single file, many edits);
                also tolerate the alternate edits[].file_path shape.
    NotebookEdit: tool_input["notebook_path"] (fall back to file_path).
    """
    if tool_name == "NotebookEdit":
        fp = tool_input.get("notebook_path") or tool_input.get("file_path")
        if fp:
            yield fp
        return

    fp = tool_input.get("file_path")
    if fp:
        yield fp

    # MultiEdit historically may carry per-edit file_path entries.
    for edit in tool_input.get("edits", []) or []:
        if isinstance(edit, dict):
            efp = edit.get("file_path")
            if efp:
                yield efp


def _deny(target_real: str, main_repo_root: str, worktree_root: str, tool_name: str) -> None:
    """Emit JSON permissionDecision:deny naming the corrected worktree path; exit 0."""
    # Compute the relative path from the main repo so we can point the agent at
    # the equivalent file inside its own worktree.
    try:
        rel = os.path.relpath(target_real, main_repo_root)
    except ValueError:
        rel = os.path.basename(target_real)
    corrected = os.path.join(worktree_root, rel)

    reason = (
        f"[worktree-edit-guard] BLOCKED: this worktree agent tried to edit a MAIN-REPO file "
        f"({target_real}) instead of its own worktree copy. That contaminates the shared "
        f"main working tree and destroys isolation. Your worktree root is {worktree_root}. "
        f"Edit {corrected} instead (use a path relative to your CWD, never an absolute main-repo path). "
        f"Bypass only if intentional: WORKTREE_EDIT_GUARD_BYPASS=1."
    )
    print(reason, file=sys.stderr)

    # Best-effort governance record; never let it prevent the block.
    try:
        from learning_db_v2 import record_governance_event

        record_governance_event(
            "policy_violation",
            tool_name=tool_name,
            hook_phase="pre",
            severity="high",
            blocked=True,
        )
    except Exception:
        pass

    deny_tool_use("PreToolUse", reason)
    sys.exit(0)


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[worktree-edit-guard] Bypassed via WORKTREE_EDIT_GUARD_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        sys.exit(0)  # Fail open on malformed payload.
    if not isinstance(event, dict):
        sys.exit(0)

    tool_name = event.get("tool_name") or event.get("tool", "")
    if tool_name not in _GUARDED_TOOLS:
        sys.exit(0)

    tool_input = event.get("tool_input", event.get("input", {}))
    if not isinstance(tool_input, dict):
        sys.exit(0)

    # cwd from event; fall back to process cwd if absent.
    cwd = event.get("cwd") or os.getcwd()
    if not isinstance(cwd, str) or not cwd:
        sys.exit(0)

    # HIGH-1 fix: canonicalize cwd ONCE here so the worktree/main roots derived
    # from it and the realpath'd targets are compared in the SAME resolved
    # namespace. Without this, a symlinked path (macOS /tmp->/private/tmp,
    # symlinked $HOME, NFS) makes _is_inside compare canonical-vs-raw, which
    # both allows out-of-worktree escapes and blocks legitimate in-worktree
    # edits. Fail OPEN if realpath raises.
    try:
        cwd = os.path.realpath(cwd)
    except OSError:
        sys.exit(0)

    split = _split_worktree(cwd)
    if split is None:
        sys.exit(0)  # Not a worktree agent -> never interfere.
    main_repo_root, worktree_root = split

    for fp in _iter_target_paths(tool_name, tool_input):
        if not isinstance(fp, str) or not fp:
            continue
        target_real = _resolve_target(fp, cwd)
        # BLOCK only if inside the main repo AND not inside the worktree.
        if _is_inside(target_real, main_repo_root) and not _is_inside(target_real, worktree_root):
            if debug:
                print(
                    f"[worktree-edit-guard] {tool_name} escape: {target_real} "
                    f"(main={main_repo_root}, wt={worktree_root})",
                    file=sys.stderr,
                )
            _deny(target_real, main_repo_root, worktree_root, tool_name)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Preserve intentional exit code (0).
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[worktree-edit-guard] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN -- never block tools on a hook bug.
        sys.exit(0)
