# route-events.jsonl Schema

Event schema for `<CLAUDE_LEARNING_DIR>/route-events.jsonl` (default `~/.claude/learning/route-events.jsonl`), the per-dispatch decision log consumed by the `explanation-traces` skill. Source of truth: `hooks/lib/route_events.py` — when this document and that module disagree, the module wins.

---

## File Contract

| Property | Value |
|---|---|
| Format | JSONL — one JSON object per line, compact separators, UTF-8 |
| Write mode | Append-only; POSIX per-line appends are atomic, so concurrent dispatches interleave at line granularity without a lock |
| Path | `<CLAUDE_LEARNING_DIR>/route-events.jsonl`; env var unset means `~/.claude/learning/` |
| Failure mode | Failure-safe by contract: a write error is swallowed — worst case one lost event line, never a broken hook |
| Authority | Auxiliary instrumentation; the aggregate routing rows in learning.db remain authoritative |

Why the log exists: the aggregate rows are keyed `(topic, key)` and carry no per-dispatch history, so faithful offline replay of "request → route → outcome" is impossible from them alone. This log adds that history.

Two producers:

| Producer | Hook event | Writes |
|---|---|---|
| `hooks/routing-decision-recorder.py` | PostToolUse (Agent) | DECISION event when it records a /do-routed dispatch |
| `hooks/routing-outcome-finalizer.py` | UserPromptSubmit | OUTCOME event when it finalizes a pending dispatch |

---

## DECISION Event

One per /do-routed dispatch, captured from the `[do-route]` marker at record time — never back-filled from later weights.

**Example** (illustrative values):
```json
{"type":"decision","ts":1751400000.123,"session":"abc123","request_snippet":"fix the failing router test","agent":"python-general-engineer","skill":"pr-workflow","complexity":"Medium","health_at_decision":0.62,"n":7,"failure":1,"action":"keep","alternates":["python-general-engineer:python-quality-gate"],"gate_inputs_present":true}
```

| Field | Type | Semantics |
|-------|------|-----------|
| `type` | string | Always `"decision"`. |
| `ts` | float | Epoch seconds (`time.time()`) when the event was appended. |
| `session` | string | Session id; `""` when unknown. |
| `request_snippet` | string | First 200 chars of the routed request. Private session data — keep out of PR bodies, issues, exports. |
| `agent` | string | Dispatched agent; `""` when unknown. |
| `skill` | string | Paired skill; `""` when unknown. |
| `complexity` | string | Complexity class from the marker; `""` when absent. |
| `health_at_decision` | float or null | The picked pair's confidence at decision time; `null` when the pair had no weight row or health was never evaluated — `gate_inputs_present` disambiguates (see states below). |
| `n` | int or null | Dispatch count for the pair's weight row — a demote-floor input. `null` unless a real numeric `health=` was read. |
| `failure` | int or null | Failure count for the pair's weight row — a demote-floor input. Same null rule as `n`. |
| `action` | string or null | The Step-1.5 health-gate outcome: `keep`, `demote`, or `tiebreak`. |
| `alternates` | list of strings or null | The keys offered as alternatives; `null` when none recorded. |
| `gate_inputs_present` | bool | Instrumentation signal the decommission clock reads (see states below). Additive; old readers ignore it, old lines lack it. |

The demote floor needs all three gate inputs — `confidence < 0.30 AND failure >= 3 AND n >= 5` — which is why `n` and `failure` are snapshotted alongside health: confidence alone cannot reconstruct the floor.

### The Three Health States

The `[do-route]` marker may carry a `health=` token. Its shape at record time yields three states the event must distinguish:

| State | Marker | `health_at_decision` | `gate_inputs_present` | Meaning |
|---|---|---|---|---|
| (a) numeric | `health=<float>` | the float | `true` | Health evaluated from a weight row |
| (b) no-row | `health=-` | `null` | `true` | Instrumented, but the pick had no weight row (valid expected data — e.g. a new pair) |
| (c) legacy | no `health=` token | `null` | `false` (or field absent on old lines) | Never instrumented — legacy or missing wiring. A malformed `health=` value also lands here |

`gate_inputs_present` exists because `null` health alone cannot distinguish (b) from (c). `n`, `failure`, `action`, and `alternates` stay `null` unless a real numeric `health=` was read (state a).

---

## OUTCOME Event

One per finalized dispatch. Outcome resolution happens on a later user prompt, so an outcome's `ts` is minutes-to-hours after its decision's.

**Example** (illustrative values):
```json
{"type":"outcome","ts":1751400900.456,"session":"abc123","key":"python-general-engineer:pr-workflow","outcome":"success","reason":"acceptance","routing_relevant":true}
```

| Field | Type | Semantics |
|-------|------|-----------|
| `type` | string | Always `"outcome"`. |
| `ts` | float | Epoch seconds when the outcome was finalized. |
| `session` | string | Session id; `""` when unknown. |
| `key` | string | Routing key `{agent}:{skill}`; agent-only `{agent}:` when the skill is unknown. |
| `outcome` | string | One of `success`, `failure`, `neutral`. |
| `reason` | string, optional | Short cause for the outcome, free of prompt text and secrets. Written only when given — absent in older events. Finalizer values: `tool-errors`, `rejection`, `acceptance`, `reaction-ignored-multi-dispatch`, `neutral-new-topic`; other producers may write other short strings. |
| `routing_relevant` | bool, optional | Marks whether the outcome is a routing signal the confidence loop acts on; route-value-eval counts only routing-relevant failures. Written only when asserted — absent means relevance was not asserted. |

---

## Joining Outcomes to Decisions

Match on **both** conditions:

1. Same `session`
2. Outcome `key` equals the decision's `f"{agent}:{skill}"`

File adjacency is unreliable: parallel sessions interleave lines. A decision with no matching outcome is pending (finalizer runs on the next user prompt) or was never finalized.

---

## Additive-Field History

The schema grew append-compatibly. Older lines lack newer fields:

| Fields | Absent on |
|---|---|
| `n`, `failure`, `action`, `alternates` | Decisions recorded before the health-gate inputs shipped |
| `gate_inputs_present` | Decisions recorded before the decommission-clock signal shipped |
| `reason`, `routing_relevant` | Outcomes from older or relevance-neutral callers |

Consumers treat an absent field as "not recorded then" — identical handling to `null` for health, and never a validity error.

---

## Validation Checklist

A healthy log satisfies all of these:

- [ ] Every line parses as a standalone JSON object
- [ ] Every event has `type` in `{decision, outcome}` and a float `ts`
- [ ] Every decision has `agent`, `skill`, `request_snippet` keys
- [ ] Every outcome has `key` and `outcome` in `{success, failure, neutral}`
- [ ] `health_at_decision` is numeric or `null` — a `null` with `gate_inputs_present: true` is valid data, not a defect

Detection (read-only, counts only):

```bash
LOG="${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl"
python3 - "$LOG" <<'EOF'
import json, sys, collections
c = collections.Counter(); bad = []
for i, line in enumerate(open(sys.argv[1]), 1):
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
        c[e.get("type", "?")] += 1
    except json.JSONDecodeError:
        bad.append(i)
print("by type:", dict(c), "malformed lines:", bad or "none")
EOF
```
