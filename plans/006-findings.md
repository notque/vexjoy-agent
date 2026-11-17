# Plan 006 Findings: routing outcomes carry no real signal

Investigation date: 2026-11-16. Stop-fallback fix landed 2026-11-09 (commit 8b9aa025).

## Baseline

```
Route Health: 7/133 entries have outcomes (5%)
Feedback loop: OPEN (95% entries have no outcome data)
Outcome basis: 0 strong-feedback vs 316 default-success
  rejection_detected   0
  tool_errors_only     0
  acceptance_detected  0
  default_no_complaint 316
  repeat_dispatch_weak 16 (weak-positive; outside the share below)
  acceptance_shared    0 (weak-positive; outside the share below)
Silent-success share: 100% of scored outcomes (316/316)
```

Signal check: exit 3 (SIGNAL condition met: 1 routing-relevant failure, 0 would-demote/would-tiebreak).

## H1: most outcomes predate the fix; post-fix entries still close without a reaction

**Lifecycle of a pending entry:**

| Event | Hook | Action | File:line |
|---|---|---|---|
| PostToolUse:Agent | routing-decision-recorder | writes pending entry via `append_pending_outcome` | routing-decision-recorder.py:818 |
| SubagentStop | routing-outcome-recorder | drains, validates decision row, revalidates back to pending | routing-outcome-recorder.py:167 |
| UserPromptSubmit | routing-outcome-finalizer | atomic read-and-clear; scores by errors + reaction | routing-outcome-finalizer.py:444 |
| Stop | routing-outcome-stop-fallback | takes errored + stale entries only (post-fix) | routing-outcome-stop-fallback.py:104 |
| SessionEnd | routing-outcome-stop-fallback | takes every remaining entry | routing-outcome-stop-fallback.py:102 |

**Outcome events before/after the fix (from route-events.jsonl, 1591 lines total):**

| Period | Source | Reason | Count |
|---|---|---|---|
| Before fix | finalizer | neutral-new-topic | 83 |
| Before fix | finalizer | repeat-dispatch-no-failure | 17 |
| Before fix | finalizer | (no reason field) | 2 |
| Before fix | hand-written | (custom failure text) | 3 |
| Before fix | | **subtotal** | **105** |
| After fix | finalizer | neutral-new-topic | 25 |
| After fix | finalizer | repeat-dispatch-no-failure | 5 |
| After fix | | **subtotal** | **30** |

Zero outcomes from the stop fallback after the fix. Zero rejection or acceptance outcomes in either period. All 30 post-fix outcomes come from the finalizer, all scored neutral or weak-positive.

1456 decision events total; 135 outcome events total. The gap (1456 decisions vs 135 outcomes) means most dispatches never reach the finalizer: they close at Stop or SessionEnd as `default_no_complaint` through the aggregate basis counter, not through the event log. The event log records only finalizer and hand-written outcomes.

**Verdict: H1 holds.** The fix stopped the stop-fallback from draining everything, but the finalizer still scores every post-fix entry as neutral. The reaction detectors fire on zero entries.

## H2: reaction rarely attributable (multi-key turns)

The event log does not carry a per-turn pending-key count directly. Grouping outcome events by (session, rounded timestamp) as a proxy:

| Pending keys per finalizer turn | Turn count |
|---|---|
| 1 | 52 |
| 2 | 8 |
| 3 | 6 |
| 4 | 1 |
| 5 | 6 |
| 6 | 1 |
| 9 | 1 |

52 of 75 turns (69%) had a single pending key. `attributable` is true only when all live entries share one route key (finalizer.py:505). Single-key turns satisfy this. Multi-key turns (31%) force the reaction to neutral for all but the shared-acceptance path.

**Verdict: H2 does not hold as the primary cause.** Most turns are single-key and attributable. The 31% multi-key rate reduces signal but is not why acceptance and rejection are both zero. The detectors themselves never fire (H3 or the prompt content).

## H3: detector recall on invented prompts

30 invented prompts tested against `is_rejection` and `is_acceptance`:

| Class | Tested | Detected | Recall |
|---|---|---|---|
| Rejection | 12 | 11 | 92% |
| Acceptance | 12 | 11 | 92% |

| Class | Tested | False positives |
|---|---|---|
| Neutral | 6 | 0 |

Missed rejection: a leading "no," clause-split hid the complaint word from the first-clause scope ("no, that broke the build" -- the comma splits "no" from "that broke the build"; the leading-no path requires a `_THATS_COMPLAINT_RE` match or a rejection pattern in clause 2, and "broke the build" fires via `you broke` only with a "you" subject). Missed acceptance: "works, thanks" -- the comma splits "works" into a bare clause too short and generic for the acceptance patterns; "thanks" in clause 2 is out of first-clause scope.

**Verdict: H3 does not hold as a primary cause.** Recall is 92% on both classes. The detectors are adequate. The problem is upstream: the owner's real follow-up prompts are almost never short reactions. They are new-task prompts (correctly scored neutral) or continuations with no verdict phrase.

## Errors flag

The `errors` flag on each pending entry is set at write time by `detect_errors` (routing-decision-recorder.py:693), which calls `is_tool_error(get_tool_result(event))` (hook_utils.py:923). `is_tool_error` checks `is_error=True` or non-zero `exitCode` on the PostToolUse event's `tool_result`.

A failed subagent dispatch sets `is_error` on the structured tool result, so a dispatch that exits non-zero or raises does set errors=True. Zero errors in 316 outcomes means no dispatched agent returned an error flag in the PostToolUse event during this period.

**Verdict:** the errors flag is correctly wired. Zero errors reflects zero tool-level failures on routed dispatches, which is plausible (agents exit 0 by design; a bad result is not a tool error).

## Causes, ranked

1. **No explicit reaction from the owner (primary).** The owner's next prompt is almost always a new task or continuation, not a verdict on the prior dispatch. The finalizer correctly scores these as neutral. The feedback loop has no signal because there is no signal to detect.
2. **Stop/SessionEnd fallback still closes most entries.** 1456 decisions vs 135 event-log outcomes means most entries never reach a UserPromptSubmit turn. They close as `default_no_complaint` through the aggregate counter at Stop or SessionEnd, adding to the 316 silent-success count without an event-log OUTCOME line.
3. **Multi-key turns suppress the reaction (secondary).** 31% of finalizer turns have multiple pending keys, forcing the reaction to neutral even when one exists. Only the shared-acceptance path applies a weak boost.
4. **Clause-splitting misses some compound reactions (minor).** A comma-separated reaction loses its complaint/acceptance word when the clause boundary falls between the filler and the keyword. Affects edge cases only.

## Proposed fixes

| # | Fix | Files | Effort | Justification |
|---|---|---|---|---|
| 1 | Add an explicit correction channel: a `/misroute` or `/bad-route` command the owner can run after a bad dispatch, writing a scored failure row directly | scripts/record-misroute.py (exists, unused), hooks or CLI entry point | M | Cause 1: the owner does not phrase reactions as verdicts; an explicit command is the only reliable negative signal |
| 2 | Record an OUTCOME event line for stop-fallback and session-end closures, with their reason | hooks/routing-outcome-stop-fallback.py, hooks/lib/route_events.py | S | Cause 2: 1321 closures leave no event-log trace, making offline analysis incomplete |
| 3 | Widen attributability: when multiple keys are pending but all share the same agent, attribute the reaction to the agent | hooks/routing-outcome-finalizer.py | S | Cause 3: 31% of turns are multi-key but many share one agent |
| 4 | Improve clause-splitting to keep "no, <complaint>" as one reaction | hooks/routing-outcome-finalizer.py | S | Cause 4: edge-case recall improvement |
| 5 | Do not re-propose the actuator yet | (none) | - | With zero strong outcomes the actuator still has nothing to act on; fix the sensor first |

If the correction channel (fix 1) proves the owner does not use it either, the reaction-based signal path is structurally unviable. The alternative is an explicit verdict prompt injected after each dispatch ("was this the right agent?"), at the cost of one extra turn per dispatch.
