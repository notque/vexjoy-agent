# Plan 005: The subagent completion guard blocks in the format SubagentStop honors

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 871f6499..HEAD -- hooks/subagent-completion-guard.py hooks/tests/test_subagent_completion_guard.py hooks/tests/test_hook_output_contract.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Kind**: fix
- **Planned at**: commit `871f6499`, 2026-11-16

## Why this matters

`hooks/subagent-completion-guard.py` runs on every `SubagentStop` event. It
checks three things: the subagent did not leave work on the default branch, a
`reviewer-*` agent did not write files, and protected-org workflow gates were
followed. When it finds a violation it prints
`{"permissionDecision": "deny", ...}`. Claude Code ignores that key on
`SubagentStop`: the event is controlled by a top-level
`{"decision": "block", "reason": "..."}`. So the guard detects violations and
enforces none of them. The repo already records this as known bug "B-01" in a
non-strict xfail. After this plan, a violation makes the subagent continue with
the violation text as its instruction, once per stop.

## Current state

- `hooks/subagent-completion-guard.py` (555 lines): the guard. The block path
  is in `main()`:

  ```python
  # hooks/subagent-completion-guard.py:532-542
          if violations:
              separator = "\n" + "=" * 60 + "\n"
              message = separator.join(violations)
              print(message, file=sys.stderr)
              # SubagentStop uses top-level permissionDecision (not wrapped in hookSpecificOutput)
              deny_output = {
                  "permissionDecision": "deny",
                  "permissionDecisionReason": message,
              }
              print(json.dumps(deny_output))
              sys.exit(0)
  ```

  The module docstring repeats the wrong contract:

  ```python
  # hooks/subagent-completion-guard.py:38
  - Uses exit 0 + JSON permissionDecision:deny to feed blocking message back to the subagent
  ```

  The parsed stdin payload is the local variable `event` in `main()` (for
  example `cwd = event.get("cwd", str(Path.cwd()))` at line 492).

- `hooks/tests/test_subagent_completion_guard.py`: unit and subprocess tests.
  One test pins the wrong format:

  ```python
  # hooks/tests/test_subagent_completion_guard.py:925-932
  class TestMainTranscriptSelection:
      def test_agent_transcript_with_nested_edit_denies(self, tmp_path):
          agent = _make_transcript(_reviewer_wrote_transcript())
          result = _run_hook(_stop_event(tmp_path, "reviewer-code", agent_transcript_path=agent), tmp_path)
          assert result.returncode == 0
          out = json.loads(result.stdout)
          assert out["permissionDecision"] == "deny"
          assert "Edit(/repo/src/app.py)" in out["permissionDecisionReason"]
  ```

- `hooks/tests/test_hook_output_contract.py`: runs every hook registered in
  `.claude/settings.json` and checks its stdout against the event's contract.
  It excuses this hook:

  ```python
  # hooks/tests/test_hook_output_contract.py:150-156
  # Known violations owned by other findings. Non-strict, so the fix landing in
  # another PR does not turn this suite red.
  _KNOWN = {
      ("SubagentStop", "subagent-completion-guard.py"): (
          "B-01: the guard prints a top-level permissionDecision, which SubagentStop ignores"
      ),
  }
  ```

- Convention: hooks never crash the session. They exit 0 on internal errors and
  block only on a detected violation. Keep that. Exemplar: the `except` clauses
  at `hooks/subagent-completion-guard.py:547-549`.
- The contract test already accepts the target shape and rejects the current
  one for this event:

  ```python
  # hooks/tests/test_hook_output_contract.py:441
          ("SubagentStop", '{"decision": "block", "reason": "fix it"}'),
  # hooks/tests/test_hook_output_contract.py:454
          ("SubagentStop", '{"permissionDecision": "deny", "reason": "x"}', "unknown top-level key 'permissionDecision'"),
  ```

- Claude Code sets `stop_hook_active: true` in the `SubagentStop` payload when
  the subagent is already continuing because a stop hook blocked it (the
  contract test's payload carries the field at line 345). A guard that blocks
  again in that state can loop forever. Two hooks already guard on it:
  `hooks/stop-drift-guard.py:474` and `hooks/security-review-hook.py:452`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard tests | `nice -n 10 python3 -m pytest hooks/tests/test_subagent_completion_guard.py -q -n 0` | all pass |
| Contract tests | `nice -n 10 python3 -m pytest hooks/tests/test_hook_output_contract.py -q -n 0` | all pass, no xfail or xpass for `subagent-completion-guard.py` |
| Adapter compat | `nice -n 10 python3 -m pytest scripts/tests/test_codex_hooks_runtime_compat.py -q -n 0` | all pass |
| Lint | `ruff check . --config pyproject.toml` | exit 0 |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |

## Scope

**In scope** (the only files to modify):
- `hooks/subagent-completion-guard.py`
- `hooks/tests/test_subagent_completion_guard.py`
- `hooks/tests/test_hook_output_contract.py`

**Out of scope** (do not touch, though they look related):
- `.claude/settings.json`: hook registration is a safety control; the owner edits it.
- `hooks/codex-hook-adapter.py`, `hooks/agy-hook-adapter.py`: they translate
  hook output for other CLIs. If they need a change, that is a STOP condition.
- The three violation checks (`check_branch_safety`,
  `check_readonly_violation`, `check_protected_org_workflow`): detection logic
  stays as is.
- Anything under `~/.claude/`: do not install or sync the hook.

## Git workflow

- Branch: `fix/subagent-guard-block-format`.
- One commit. Message style: one lowercase past-tense sentence, no type prefix,
  no trailing period. Example from `git log`:
  `pinned pyyaml to 6.0.3 in all seven CI install lines and added a contract test that catches unpinned installs`
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Record the baseline

Run the three test commands above before editing.

**Verify**: all three exit 0. The contract run reports one `xfailed` or
`xpassed` case for `SubagentStop:subagent-completion-guard.py`. If a test
already fails, STOP.

### Step 2: Emit `decision: block`, once per stop

In `hooks/subagent-completion-guard.py`, replace lines 532-542 with this shape:

```python
        if violations:
            separator = "\n" + "=" * 60 + "\n"
            message = separator.join(violations)
            print(message, file=sys.stderr)
            # A stop hook already blocked this stop once. Blocking again can
            # loop a subagent that cannot fix the violation, so report only.
            if event.get("stop_hook_active"):
                sys.exit(0)
            # SubagentStop is controlled by top-level decision/reason.
            print(json.dumps({"decision": "block", "reason": message}))
            sys.exit(0)
```

Change the docstring line 38 to:
`- Uses exit 0 + JSON decision:block to feed the violation back to the subagent, once per stop`

**Verify**: `grep -n "permissionDecision" hooks/subagent-completion-guard.py` → no matches.

### Step 3: Update the pinned test and add the loop guard test

In `hooks/tests/test_subagent_completion_guard.py`:

1. In `test_agent_transcript_with_nested_edit_denies`, assert
   `out["decision"] == "block"` and
   `"Edit(/repo/src/app.py)" in out["reason"]`.
2. Add `test_stop_hook_active_reports_without_blocking` to
   `TestMainTranscriptSelection`. Build the same event, set
   `event["stop_hook_active"] = True`, run the hook, and assert
   `result.returncode == 0`, `result.stdout.strip() == ""`, and that the
   violation text is in `result.stderr`. Read `_stop_event` and `_run_hook` in
   the same file first and reuse them.

**Verify**: `nice -n 10 python3 -m pytest hooks/tests/test_subagent_completion_guard.py -q -n 0` → all pass, one more test than the baseline.

### Step 4: Remove the known-violation excuse

In `hooks/tests/test_hook_output_contract.py`, delete the
`("SubagentStop", "subagent-completion-guard.py")` entry so `_KNOWN` is an
empty dict. Keep the `_KNOWN` name, its comment, and the code that reads it.

**Verify**: `nice -n 10 python3 -m pytest hooks/tests/test_hook_output_contract.py -q -n 0` → all pass, zero xfailed, zero xpassed. If the `SubagentStop` case now fails, read the contract the test enforces for that event and STOP with its text: the contract and this plan disagree.

### Step 5: Check the adapters and lint

**Verify**: the adapter compat command, `ruff check`, and `ruff format --check` each exit 0.

### Step 6 (OWNER-GATED: live hook change): Install the fixed hook

Syncing this hook into `~/.claude/hooks` turns on enforcement that has never
run. Subagents that end on the default branch, and reviewer agents that write
files, will be told to continue instead of stopping. The owner decides when to
merge and install. The executor skips this step and reports it as pending.

## Test plan

- Changed: `test_agent_transcript_with_nested_edit_denies` asserts the new keys.
- New: `test_stop_hook_active_reports_without_blocking` (the loop guard).
- Regression: the contract test now checks this hook with no excuse.
- Verification: the three pytest commands above → all pass.

## Done criteria

- [ ] `grep -rn "permissionDecision" hooks/subagent-completion-guard.py` returns no matches
- [ ] `grep -n "B-01" hooks/tests/test_hook_output_contract.py` returns at most the comment inside the test payload builder, and no `_KNOWN` entry
- [ ] The three pytest commands in "Commands you will need" exit 0
- [ ] `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0
- [ ] `git status --short` shows only the three in-scope files and `plans/README.md`
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- The contract test rejects `{"decision": "block", "reason": ...}` for `SubagentStop`.
- `scripts/tests/test_codex_hooks_runtime_compat.py` fails after the change: an adapter depends on the old keys, and adapters are out of scope.
- A step's verification fails twice after a reasonable fix attempt.
- A step would need an edit to `.claude/settings.json` or anything under `~/.claude/`.

## Maintenance notes

- Reviewer: confirm the guard prints nothing to stdout when
  `stop_hook_active` is true, and that no violation check changed.
- After install, watch the first sessions for subagents that continue after a
  block and then stop cleanly. A subagent that cannot leave the default branch
  gets one block, then stops with the violation on stderr.
- Follow-up, deferred: `check_branch_safety` blocks a subagent for a state the
  parent may have created. If the first week shows false blocks, narrow that
  check; do not weaken the output format.
