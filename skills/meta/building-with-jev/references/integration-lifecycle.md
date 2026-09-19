# Integration lifecycle

## Three tiers

| Tier | Owner | Work |
|---|---|---|
| 1 | programs | regex, counting, parsing, tests, builds, fingerprints, budgets |
| 2 | Jev | classification, scoring, triage, gates: pick one, score this, yes or no |
| 3 | LLM | code, prose, diagnosis, synthesis |

Apply the lowest tier that can do the job. Jev runs after programs, not instead of them: a program extracts or computes the available evidence, then Jev judges the residual. The LLM receives tier 1 and 2 findings as input and does not re-judge them, except in the bounded, benchmarked residual-review stage. Jev pricing and latency are workload and model dependent; measure them from actual runs rather than relying on a universal promise. An LLM call commonly costs more and can rationalize a wrong answer.

## Hook points

Start every program as an on-demand command. A hook multiplies cost by its firing rate: every firing bills the state plus every question's text. Measure the event rate in the target environment before promotion. Promote a program to a hook when all four hold:

1. Code decides the obvious cases first; Jev receives the residual.
2. A labeled set shows the answers are right.
3. The finding rate shows the answers carry information: when answers are overwhelmingly constant on representative data, measure whether a deterministic rule can replace the call.
4. Something acts on the answer, and a log shows how often the answer changed the action.

Promote one hook at a time and read `scripts/jev-cost-report.py` after a day of use.

| Event | Firing rate | Fits when |
|---|---|---|
| UserPromptSubmit | once per request | the answer changes how the request is handled (routing) |
| session.compact (plugin) | at a context threshold | Jev replaces messages directly |
| PreToolUse, PostToolUse | every tool call | code has already narrowed the input to a rare, undecided case |
| SubagentStop, Stop | every agent or reply | a later step reads the stored finding and acts on it |

Registered events live in `.claude/settings.json`. Hooks exit 0 on their own errors and print a warning rather than fail the tool.

## Reader, storage, action

Every integration needs all three:

1. Reader: a hook or script that runs Jev on the evidence and extracts structured findings.
2. Storage: findings persist where something reads them (state file, injection, return value). Findings only in stderr are invisible.
3. Action: something changes behavior (retry, block, stop iterating, inject).

A SubagentStop hook that writes to a state file nobody reads has no action. When the action cannot happen at the same hook point, bridge it: a later hook reads the state file and injects at a point that supports injection. A PreToolUse secret scan has all three in one step.

## Thread prior assessments

Each tool's result flows into the next call's state as bounded, labeled evidence: the completion validator sees that scope-creep flagged three files; the quality loop sees that the slop scan found hedges. Extract actionable fields (which dimensions fired, at what confidence, the aggregate), not the full prior JSON.

## Jev assesses, policy decides

A pure function `policy(state, assessment) -> action` reads probabilities and returns block, warn, allow, retry, or escalate. It never calls Jev. Threshold constants live in the policy, so a threshold change is a unit test without a mocked API. Keep the call and the policy in different functions, ideally different modules.

## Failure modes

| Check type | When Jev is unavailable or the response is invalid |
|---|---|
| advisory (commit readiness, scope creep, output triage) | fail open: skip silently |
| safety (secret scan, breaking change) | fail to warn: inject "Jev safety check unavailable, manual review recommended" |
| blocking (secret scan at severity >= 4) | fail to warn, never fail to block: an unavailable Jev must not stop work |

Validate every response with `validate_jev_response` between the call and the policy.

Validation failure, a missing answer, or an unavailable service is `unknown`, not `no`, pass, or a zero score. Persist a failure receipt separately from assessment metrics: stage, request/evidence identity, error, timestamps, and retry outcome. The policy must branch explicitly on `unknown`; it must never silently default it into a quality or action result.

Availability check: `typesafe_available()` requires both `TYPESAFE_API_KEY` and the enabled plugin (`JEV_KEY_ONLY=1` for standalone CLI use). Never log the key or the Authorization header.

## Persist for calibration

Append each assessment's key fields (tool, evidence-bundle ID/version and source IDs, question values and version, full distributions, verdict, model/version, attempt/retry fields, deadline/cap, wall latency, model-call duration, usage, timestamp) to a bounded, rotating store: a session-scoped JSONL pruned after 24 hours, or `learning.db`. Persist the request and response references where policy permits. This enables false-positive measurement, threshold tuning on real data, drift detection when the model changes, replay, and A/B comparison of question versions. Log full Choice distributions, not just the pick.

For a high-throughput runner, keep two clocks: wall time for user-visible completion and accumulated model call time, the sum of each attempt's duration. Report throughput against a named clock (`rows/wall-second`, `KB/call-second`); concurrency can make wall time low while accumulated call time remains high. Record keep, refer, decline, retry, timeout, and final-action rates beside cost, so a low average price cannot hide an expensive referral tail.

Claims are not evidence; the engine's record is. A plugin log line says what the plugin believes it did; the transcript's `compact_boundary` row (`preTokens`, `postTokens`, `durationMs`) says what happened. Record both and show them side by side (`scripts/jev-compact-evidence.py`).

## Compaction specifics

- Compaction is deletion, not generation: Jev judges each tool call (referenced later? input still constraining? reproducible by re-running?), stale items are deleted verbatim, nothing is rewritten.
- Threshold-gate; do not fire every turn. The Jev call may be inexpensive relative to compaction, and editing a cached prefix can make the next request a cold write. Select a context threshold from measured workload cost and behavior.
- Use two stages when measurement supports it: Jev prunes while there is slack; the built-in summarizer runs when Jev alone cannot get under the line. Measure retained tokens and downstream quality for both stages on the target workload.
- A self-triggered compaction (`event.trigger == "plugin"`) that finds nothing to prune returns skip; on `auto` or `manual`, let core fall back.
- The function-hook plugin owns compaction for the main session.

## Deployment checklist

- [ ] Reader, storage, action all present; the action is observable.
- [ ] Policy is a pure function with named thresholds.
- [ ] Failure mode matches the check type.
- [ ] Response validated before the policy runs.
- [ ] Assessments persisted with distributions and usage.
- [ ] Live API call in the test run, not only mocked responses.
- [ ] Enforcement tested on its failure path, not assumed from registration.
- [ ] Unknown answers and failure receipts are excluded from quality/pass metrics and handled by an explicit policy branch.
