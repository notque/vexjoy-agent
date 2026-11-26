# Plan 013: stop-drift-guard runs its checks once per diff, not once per turn

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c68ac1fe..HEAD -- hooks/stop-drift-guard.py hooks/tests/test_stop_drift_guard.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Kind**: fix
- **Planned at**: commit `c68ac1fe`, 2026-11-26

## Why this matters

`hooks/stop-drift-guard.py` runs at every turn end (Stop) in the toolkit
checkout. When the working-tree diff touches `hooks/`, it runs
`scripts/smoke-test-hooks.py`, which starts all 76 registered hooks one after
another. Measured on the planning host: 5.0 s wall, 4.4 s CPU per run. Doc
count, routing and plugin checks add to it when those files are dirty.

The guard reruns every relevant check at every Stop, even when the diff has
not changed since the last Stop. Its dedup (`DiffDedup`) is consulted only
after the checks and only for diffs that drifted, so a clean result is never
remembered and a drifting one is recomputed before the message is
suppressed. A 30-turn session that edits a hook spends about 2.5 minutes of
CPU rerunning a smoke test whose answer it already has. After this plan, a
diff that was already checked is skipped before any check runs; a changed
diff runs the checks again.

## Current state

- `hooks/stop-drift-guard.py`: the Stop hook.
  - Lines 100-103, state paths:

    ```python
    # Stop-event dedup state. Absolute path so it works from any cwd the harness
    # fires in. Own state dir so this guard's dedup never collides with another hook.
    _STATE_DIR = Path.home() / ".claude" / "state" / "stop-drift-guard"
    _STATE_FILE = _STATE_DIR / "last-diff-hash.json"
    ```
  - Lines 446-452, `_dedup()` builds `DiffDedup(_STATE_DIR, _STATE_FILE)` at
    call time "so the test-suite's patching of those module-level names keeps
    working".
  - Lines 485-516 in `handle_stop`:

    ```python
    diff = _working_tree_diff(cwd)

    # Front gate: nothing reviewable -> short-circuit before any check runs.
    if not diff.strip() or not _has_reviewable_content(diff):
        sys.exit(0)

    checks = _relevant_checks(diff)
    if not checks:
        sys.exit(0)

    # Run only the relevant checks; collect those that REPORT drift.
    drifting: list[dict] = []
    for name in checks:
        result = _run_check(name, cwd)
        # None (couldn't run) and {"drift": False} both mean "no drift" (fail-open).
        if result and result.get("drift"):
            drifting.append(result)

    if not drifting:
        # Files changed but every relevant check is clean -> stay silent.
        sys.exit(0)

    # Dedup: a byte-identical diff already surfaced -> don't re-nag.
    dedup = _dedup()
    is_dup, last_iso = dedup.is_duplicate(cwd, diff)
    if is_dup:
        ts_msg = f" since {last_iso}" if last_iso else ""
        print(f"[stop-drift-guard] diff unchanged{ts_msg} — skipping", file=sys.stderr)
        sys.exit(0)

    # Record BEFORE the rewake (exit 2) so the rewake itself won't loop.
    dedup.record(cwd, diff)
    ```
- `hooks/lib/hook_utils.py:1061`, `class DiffDedup(state_dir, state_file, ttl_seconds=0)`:
  `signature(cwd, diff)` hashes cwd plus a normalized diff,
  `is_duplicate(cwd, diff) -> (bool, last_iso)`, `record(cwd, diff)` writes one
  record atomically. `security-review-hook.py` also uses this class: do not
  change it. Reuse it with a second state file.
- `hooks/tests/conftest.py:36-50`, autouse fixture `_isolate_hook_dedup_state`:
  for any test module exposing `mod._STATE_DIR`, it points `_STATE_DIR` at a
  fresh tmp dir per test. Any new state path must be derived from
  `_STATE_DIR` at call time (as `_dedup()` does) so this fixture isolates it.
- `hooks/tests/test_stop_drift_guard.py`: drives `mod.main()` in-process via
  `_run(stdin, diff=..., check_results=...)` (lines 121-160); `_CheckSpy`
  (line 168) records which checks ran; `TestDedup` (lines 376-397) expects a
  repeated drifting diff to exit 0 with no rewake. Match these helpers.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Hook tests | `python3 -m pytest hooks/tests/test_stop_drift_guard.py -n 0 -q` | all pass |
| Guard header check | `python3 scripts/hook-pyguard.py --check` | exit 0 |
| Hook health | `python3 scripts/validate-hook-health.py --ci` | exit 0 |
| Lint job | `bash scripts/ci-local.sh` | exit 0 |

## Scope

**In scope** (the only files to modify):
- `hooks/stop-drift-guard.py`
- `hooks/tests/test_stop_drift_guard.py`

**Out of scope** (do not touch, though they look related):
- `hooks/lib/hook_utils.py` (`DiffDedup` is shared with `security-review-hook.py`).
- `scripts/smoke-test-hooks.py` and the other check scripts.
- The per-check timeout (`_run_script(..., timeout=30)`, line 305) against
  the 20 s Stop registration: see Maintenance notes.

## Git workflow

- Branch: `perf/drift-guard-checked-diff-cache`.
- One commit. Message: one lowercase past-tense sentence, no type prefix, no
  trailing period, then a blank line and `Verified-By: tests`. Example from
  `git log`: `dropped the trivial intent skip so every /d route runs the intent check again, trivial ones included, at the owner's call`.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the failing tests

In `hooks/tests/test_stop_drift_guard.py`, add `class TestCheckedDiffCache`
with four tests. Use `_diff_for("hooks/foo.py")` for a diff that selects the
smoke check, and `_CheckSpy` (or a counting `side_effect`) to count
`_run_check` calls across two `_run(...)` calls in one test:

1. `test_clean_diff_is_checked_once`: two Stops with the same diff, every
   check clean → `_run_check` called on the first Stop only; both exit 0.
2. `test_drifting_diff_is_checked_once`: two Stops with the same diff, smoke
   drifting → the first exits 2 (as `TestDedup` shows), the second calls no
   check, exits 0, and `_rewake_summary(out2) is None`.
3. `test_unrun_check_is_retried`: the first Stop's `_run_check` returns
   `None` (couldn't run) → the second Stop with the same diff calls
   `_run_check` again.
4. `test_changed_diff_is_checked_again`: `hooks/a.py` then `hooks/b.py`, both
   clean → `_run_check` called on both Stops.

**Verify**: `python3 -m pytest hooks/tests/test_stop_drift_guard.py -n 0 -q -k TestCheckedDiffCache` → tests 1, 2 fail (checks run twice); 3, 4 pass.

### Step 2: Skip a diff that was already checked

In `hooks/stop-drift-guard.py`:

1. After `_dedup()` (line 452), add:

   ```python
   def _checked() -> DiffDedup:
       """Remembers the last diff whose relevant checks all ran, clean or drifting.

       A separate file from the advisory dedup, built from _STATE_DIR at call time
       so the test-suite's state isolation covers it too.
       """
       return DiffDedup(_STATE_DIR, _STATE_DIR / "last-checked-diff.json")
   ```
2. In `handle_stop`, right after `if not checks: sys.exit(0)`, add:

   ```python
       # The checks are a pure function of the diff: one already checked has its answer,
       # clean or drifting, so skip the 5 s smoke run instead of recomputing it every turn.
       checked = _checked()
       seen, last_iso = checked.is_duplicate(cwd, diff)
       if seen:
           ts_msg = f" since {last_iso}" if last_iso else ""
           print(f"[stop-drift-guard] diff already checked{ts_msg}, skipping", file=sys.stderr)
           sys.exit(0)
   ```
3. In the check loop, track whether every check ran:

   ```python
       complete = True
       for name in checks:
           result = _run_check(name, cwd)
           if result is None:
               complete = False
           # None (couldn't run) and {"drift": False} both mean "no drift" (fail-open).
           if result and result.get("drift"):
               drifting.append(result)

       # Remember the diff only when every check gave an answer; a check that could
       # not run (timeout, missing script) is retried at the next Stop.
       if complete:
           checked.record(cwd, diff)
   ```
4. Leave the advisory dedup below (`_dedup()`, `is_duplicate`, `record`)
   unchanged.

**Verify**: `python3 -m pytest hooks/tests/test_stop_drift_guard.py -n 0 -q` → all pass, including the 4 new tests and the existing `TestDedup`.

### Step 3: Measure the second Stop

From the worktree root, with a throwaway HOME so the live state dir is never
written:

A tracked change under `hooks/` selects the smoke check; `hooks/README.md`
is tracked and is not a hook, so use it:

```bash
H=$(mktemp -d) && echo "<!-- bench -->" >> hooks/README.md && \
P="{\"hook_event_name\":\"Stop\",\"session_id\":\"bench-drift-1\",\"cwd\":\"$PWD\",\"stop_hook_active\":false}" && \
for i in 1 2; do /usr/bin/time -f "stop $i: %e s" env HOME="$H" python3 hooks/stop-drift-guard.py <<< "$P" > /dev/null; done; \
git checkout -- hooks/README.md && rm -rf "$H"
```

**Verify**: `stop 1` takes several seconds (the smoke test runs); `stop 2`
takes under 0.5 s. `git status --short` shows no change to `hooks/README.md`
afterwards.

### Step 4: Run the gates

**Verify**:
- `python3 scripts/hook-pyguard.py --check` → exit 0.
- `python3 scripts/validate-hook-health.py --ci` → exit 0.
- `bash scripts/ci-local.sh` → exit 0.

## Test plan

- New class `TestCheckedDiffCache` in `hooks/tests/test_stop_drift_guard.py`:
  clean diff checked once, drifting diff checked once with no second rewake,
  an unrun check retried, a changed diff rechecked.
- Model after `TestDedup` and `TestRelevanceGate` in the same file.
- Verification: `python3 -m pytest hooks/tests/test_stop_drift_guard.py -n 0 -q` → all pass, including 4 new tests.

## Done criteria

- [ ] `python3 -m pytest hooks/tests/test_stop_drift_guard.py -n 0 -q` exits 0
- [ ] Step 3 printed a second Stop under 0.5 s
- [ ] `grep -n "def _checked" hooks/stop-drift-guard.py` returns 1 line
- [ ] `git diff --stat -- hooks/lib/hook_utils.py` is empty
- [ ] `bash scripts/ci-local.sh` exits 0
- [ ] `git status --short` shows no file outside the in-scope list
- [ ] `plans/README.md` row for 013 updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list, including `hook_utils.py`.
- An existing test in `test_stop_drift_guard.py` expects the checks to run
  again for an unchanged diff: that is a behavior someone chose; report it.
- Step 3's first Stop does not run the smoke test (for example
  `_is_toolkit_repo` is false in the worktree): report the output instead of
  changing the identity gate.

## Maintenance notes

- The cache key is the cwd plus the normalized diff against HEAD, the same
  key the advisory dedup uses. A commit that moves HEAD while leaving a
  byte-identical diff would reuse the old answer; CI still runs the same
  checks on every PR.
- Deferred: `_run_script` gives each check up to 30 s, and up to four run in
  sequence, while the Stop registration allows 20 s. A guard killed by that
  timeout records nothing and retries next Stop. A shared deadline (budget
  about 18 s, each check gets the remainder) would fix it; plan it if the
  guard ever logs timeouts.
- Reviewer: check that a check returning `None` leaves no record, and that
  the new state file sits under `_STATE_DIR`.
