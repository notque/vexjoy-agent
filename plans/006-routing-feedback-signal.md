# Plan 006: Find out why routing outcomes never record a real signal

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 871f6499..HEAD -- hooks/routing-outcome-finalizer.py hooks/routing-outcome-stop-fallback.py hooks/routing-outcome-recorder.py hooks/lib/routing_outcome_score.py hooks/lib/routing_outcome_state.py`
> This plan changes no source file. If a listed file changed, re-read it before
> you rely on the excerpts below.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: direction
- **Kind**: investigate
- **Planned at**: commit `871f6499`, 2026-11-16

## Why this matters

The toolkit's router is meant to learn from results: each `/do` dispatch gets
an outcome, and outcomes move a route's confidence. On the owner's machine the
loop records no real signal. `python3 scripts/learning-db.py route-health`
printed this on 2026-11-16:

```
Route Health: 7/133 entries have outcomes (5%)
Feedback loop: OPEN (95% entries have no outcome data)
Outcome basis: 0 strong-feedback vs 315 default-success
  rejection_detected   0
  tool_errors_only     0
  acceptance_detected  0
  default_no_complaint 315
  repeat_dispatch_weak 16 (weak-positive; outside the share below)
Silent-success share: 100% of scored outcomes (315/315)
Correction rate: not instrumented (0 user-correction rows; no hook writes them)
Misroute rate: not instrumented (0 rows; only a hand-run scripts/record-misroute.py writes them)
```

Zero rejections, zero acceptances, and zero tool errors across 315 outcomes is
not believable for real use. One cause is already known and fixed: the stop
fallback used to close every pending outcome at `Stop`, before the user's next
message existed. Its docstring records 291 of 291 outcomes scored that way.
The counts are cumulative, so most of the 315 may predate that fix. Nobody has
measured whether outcomes recorded since the fix carry a real signal. Until that is known, every routing
metric built on outcomes measures nothing. This plan finds the cause and writes
it down with counts. It fixes nothing.

## Current state

- `hooks/routing-outcome-finalizer.py`: runs on `UserPromptSubmit`. It reads
  the session's pending dispatches, classifies the new prompt, and scores each
  pending entry.

  ```python
  # hooks/routing-outcome-finalizer.py:441-450
          session_id = event.get("session_id") or ""
          # Atomic read-AND-clear: makes finalization idempotent — a re-delivered
          # or duplicate prompt finds an empty pending list and scores nothing.
          pending = finalize_pending_outcomes(session_id)
          if not pending:
              return  # no routed dispatches awaiting resolution this turn

          prompt = (event.get("prompt") or "").strip()
          rejected = is_rejection(prompt)
          accepted = is_acceptance(prompt)
  ```

  ```python
  # hooks/routing-outcome-finalizer.py:546-555
              errors = bool(item.get("errors"))
              takes_reaction = attributable and not errors and not reaction_spent and (rejected or accepted)
              reaction_failure = rejected and takes_reaction
              reaction_success = accepted and takes_reaction and not rejected
              if takes_reaction:
                  reaction_spent = True
              if errors or reaction_failure:
                  outcome = "failure"
              elif reaction_success:
                  outcome = "success"
  ```

  The patterns are `_REJECTION_PATTERNS` (line 159), `_ACCEPTANCE_PATTERNS`
  (line 199), and `_BARE_ACCEPTANCE_RE` (line 214). The classifiers are
  `is_rejection` (line 333) and `is_acceptance` (line 377).

- `hooks/routing-outcome-stop-fallback.py`: registered on `Stop`
  (`.claude/settings.json:611`) and `SessionEnd` (`:638`). Its docstring
  (lines 4-30) says `Stop` now resolves only errored entries and entries older
  than `STOP_STALE_AGE_SEC`, and `SessionEnd` resolves every pending entry. It
  calls `finalize_pending_outcomes` at line 102.
- `hooks/routing-outcome-recorder.py`: registered on `SubagentStop`
  (settings line 551). It calls `drain_pending_outcomes` at line 167. What it
  does with the drained entries is not yet read: establish it in step 2.
- `hooks/lib/routing_outcome_score.py:114-137`: `outcome_basis(errors,
  reaction_failure, reaction_success)` returns the four labels shown in the
  report.
- `hooks/lib/routing_outcome_state.py`: pending-list storage
  (`finalize_pending_outcomes`, `requeue_pending_outcomes`,
  `revalidate_pending_outcomes`).
- `hooks/lib/route_events.py`: the route event log (`route-events.jsonl`).
  Read it to find the log's path.
- `docs/route-loop-validation.md`: the record of why the routing actuator was
  dropped (no negative signal ever existed). Read its "Decision" and "Sensor
  mechanism" sections before step 2.

Three hypotheses to test, in this order:

| # | Hypothesis | What would show it |
|---|---|---|
| H1 | Most of the 315 predate the stop-fallback fix; since the fix, entries still close without a reaction (at `SessionEnd`, as stale at `Stop`, or drained by the recorder on `SubagentStop`) | The fix commit's date (`git log -S"291" --format='%h %cs' -- hooks/routing-outcome-stop-fallback.py`), then OUTCOME events before and after it, counted by source |
| H2 | The reaction is rarely attributable: most turns have several route keys pending, so `takes_reaction` is false | Count of finalizer turns with one route key versus several |
| H3 | The patterns miss how the owner phrases a rejection or acceptance | Low recall on a hand-written corpus of realistic follow-ups |

`errors` being zero in 315 outcomes is a fourth question: find where
`item["errors"]` is set and whether any code path can set it true.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Baseline report | `python3 scripts/learning-db.py route-health` | prints the block above with current counts |
| Signal check | `python3 scripts/route-signal-check.py; echo "exit=$?"` | prints a verdict; exit 0 or 3 |
| Finalizer tests | `nice -n 10 python3 -m pytest hooks/tests/test_acceptance_detector.py -q -n 0` | all pass |

All three are read-only.

## Scope

**In scope** (the only file to create or modify):
- `plans/006-findings.md` (create)
- `plans/README.md` (status row only)

**Out of scope**:
- Every source file. This plan changes no code and no hook registration.
- The learning database and `route-events.jsonl`: read only. Never write,
  migrate, compact, or delete rows.
- Session transcripts and prompt text: do not open transcripts. Do not copy
  any prompt, row value, session ID, or path under a home directory into the
  findings file. Counts and labels only. The findings file is committed to a
  public repo.

## Git workflow

- Branch: `advisor/006-routing-feedback-signal`.
- One commit holding `plans/006-findings.md` and the index row. Message style:
  one lowercase past-tense sentence, no type prefix, no trailing period.
  Example: `added the four improve plans and their index as the record of this run`
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Record the baseline

Run the baseline report and the signal check. Copy the count lines into the
findings file under "Baseline".

**Verify**: `test -s plans/006-findings.md && grep -c "default_no_complaint" plans/006-findings.md` → 1 or more.

### Step 2: Trace who closes a pending outcome (H1)

Read `hooks/routing-outcome-stop-fallback.py`,
`hooks/routing-outcome-recorder.py`, and the pending-list functions in
`hooks/lib/routing_outcome_state.py`. Write down, with `file:line`: which hook
writes a pending entry, which hooks clear one, and on which event each runs.
Find the date of the stop-fallback fix with the `git log -S` command in the
H1 row. Then count OUTCOME events in the route event log, split before and
after that date, by their `reason` or source field with a short read-only Python snippet (`json.loads` per line; print a
`collections.Counter`). Report counts only.

**Verify**: the findings file has an "H1" section with a table of event, hook, `file:line`, and count, and the before and after counts, and one sentence that says "H1 holds" or "H1 does not hold".

### Step 3: Measure attributability (H2)

From the same log, count finalizer turns by the number of distinct route keys
pending. If the log does not carry that, say so and name the field that would
need adding.

**Verify**: the findings file has an "H2" section with the two counts (single key, several keys) or the named missing field, and a verdict sentence.

### Step 4: Measure detector recall (H3)

Write 30 follow-up prompts yourself, in the findings file: 12 rejections
("no, that broke the build", "revert that", "that's not what I asked"), 12
acceptances ("works, thanks", "perfect, ship it"), 6 neutral new-topic
prompts. Invent them; do not take them from any transcript. Load the finalizer
with `importlib.util.spec_from_file_location` (exemplar:
`hooks/tests/test_posttool_security_scan.py:27-31`) and run `is_rejection` and
`is_acceptance` on each. Record recall for each class and the false positives
on the neutral set.

**Verify**: the findings file has an "H3" section with three numbers: rejection recall out of 12, acceptance recall out of 12, false positives out of 6.

### Step 5: Trace the `errors` flag

Find every write of the pending entry's `errors` key
(`grep -rn '"errors"' hooks/*.py hooks/lib/*.py`). State which tool results
set it true and whether a failed subagent dispatch does.

**Verify**: the findings file has an "Errors flag" section with at least one `file:line` and a sentence that says whether a failing dispatch can set it.

### Step 6: Rank the causes and propose fixes

End the findings file with "Causes, ranked" and "Proposed fixes". Each
proposed fix names its files, its effort (S, M, or L), and the number from
steps 2-5 that justifies it. Do not implement any.

**Verify**: `grep -c "^## " plans/006-findings.md` → 7 or more (Baseline, H1, H2, H3, Errors flag, Causes ranked, Proposed fixes).

## Test plan

No code changes, so no new tests. The finalizer test command must still pass,
which proves you edited nothing: `nice -n 10 python3 -m pytest hooks/tests/test_acceptance_detector.py -q -n 0` → all pass.

## Done criteria

- [ ] `plans/006-findings.md` exists with the seven sections
- [ ] Each hypothesis section ends in a verdict sentence backed by a count
- [ ] `git status --short` shows only `plans/006-findings.md` and `plans/README.md`
- [ ] `grep -nE "/home/|session_id\"?: \"|@" plans/006-findings.md` returns no matches
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The route event log or the learning database is missing or unreadable. Report the path you tried.
- Answering a step would need opening a session transcript or quoting a stored prompt.
- A step would need a write to the database, the event log, a hook, or `.claude/settings.json`.
- `route-health` no longer reports 100% silent success: the picture changed, and the owner should see the new numbers first.

## Maintenance notes

- The findings file feeds a follow-up fix plan. Write that plan with
  `/improve plan <description>` after the owner reads the findings.
- `docs/route-loop-validation.md` says to re-propose the actuator on the first
  routing-relevant failure event, and `route-health` now reports one. Do not
  re-propose it from this plan: with zero strong outcomes the actuator still
  has nothing to act on. Say so in "Proposed fixes".
- Correction rate and misroute rate are not instrumented
  (`scripts/learning-db.py:979,1078`). If H1-H3 show the reaction signal cannot
  be made reliable, an explicit correction channel is the alternative; name it
  as an option, not a recommendation.
