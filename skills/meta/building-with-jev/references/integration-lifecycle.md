# Integration lifecycle

## Three tiers

| Tier | Owner | Work |
|---|---|---|
| 1 | programs | regex, counting, parsing, tests, builds, fingerprints, budgets |
| 2 | Jev | classification, scoring, triage, gates: pick one, score this, yes or no |
| 3 | LLM | code, prose, diagnosis, synthesis |

Apply the lowest tier that can do the job. Jev runs after programs, not instead of them: the program finds the em dashes, Jev judges whether the remaining prose sounds generated. The LLM receives tier 1 and 2 findings as input and does not re-judge them. A Jev call costs about $0.042 per million input tokens and returns in under 200 ms; an LLM call costs about 100x more and can rationalize a wrong answer.

## Hook points

Start every program as an on-demand command. A hook multiplies cost by its firing rate: a per-tool-call hook fires hundreds of times an hour, and each firing bills the state plus every question's text. Promote a program to a hook when all four hold:

1. Code decides the obvious cases first; Jev receives the residual.
2. A labeled set shows the answers are right.
3. The finding rate shows the answers carry information: when over 90% of answers are the same, move that case to code.
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

Availability check: `typesafe_available()` requires both `TYPESAFE_API_KEY` and the enabled plugin (`JEV_KEY_ONLY=1` for standalone CLI use). Never log the key or the Authorization header.

## Persist for calibration

Append each assessment's key fields (tool, question values, full distributions, verdict, latency, usage, timestamp) to a bounded, rotating store: a session-scoped JSONL pruned after 24 hours, or `learning.db`. This enables false-positive measurement, threshold tuning on real data, drift detection when the model changes, and A/B comparison of question versions. Log full Choice distributions, not just the pick.

Claims are not evidence; the engine's record is. A plugin log line says what the plugin believes it did; the transcript's `compact_boundary` row (`preTokens`, `postTokens`, `durationMs`) says what happened. Record both and show them side by side (`scripts/jev-compact-evidence.py`).

## Compaction specifics

- Compaction is deletion, not generation: Jev judges each tool call (referenced later? input still constraining? reproducible by re-running?), stale items are deleted verbatim, nothing is rewritten.
- Threshold-gate; do not fire every turn. The Jev call is cheap; the compaction is not. Editing the prefix invalidates the KV cache, so the next request is a cold write: $2.12 measured against $0.44 for a normal turn. Gate on context percent (60%).
- Result-blind pruning removes about 38% of tokens; the built-in summarizer removes about 95%. Two-stage: Jev prunes while there is slack; the summarizer runs when Jev alone cannot get under the line.
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
