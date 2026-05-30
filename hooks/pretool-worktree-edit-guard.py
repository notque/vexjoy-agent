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

Properties: dependency-free (stdlib only), <300ms (no subprocess), fails OPEN on
any internal error -- never blocks legitimate work due to a hook bug.
Bypass: WORKTREE_EDIT_GUARD_BYPASS=1.
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

try:
    from stdin_timeout import read_stdin
except Exception:  # pragma: no cover - lib import must never hard-fail the hook

    def read_stdin(timeout: int = 10) -> str:
        return sys.stdin.read()


_BYPASS_ENV = "WORKTREE_EDIT_GUARD_BYPASS"
_WORKTREE_MARKER = "/.claude/worktrees/"
_GUARDED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def _split_worktree(cwd: str) -> tuple[str, str] | None:
    """Given a cwd inside a worktree, return (main_repo_root, worktree_root).

    worktree_root  = main_repo_root + "/.claude/worktrees/<id>"
    main_repo_root = everything before "/.claude/worktrees/"

    Returns None if cwd is not inside a worktree.
    """
    idx = cwd.find(_WORKTREE_MARKER)
    if idx == -1:
        return None
    main_repo_root = cwd[:idx]
    after = cwd[idx + len(_WORKTREE_MARKER) :]
    # Assumes the worktree id is a single path segment directly after the marker
    # (e.g. ".../.claude/worktrees/<id>/..."). If a layout nests the id deeper,
    # worktree_root is computed too shallow -> we under-block (fail-open direction).
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

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
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
