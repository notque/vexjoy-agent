# Question Battery Guide

Use this guide to author a context-specific JSON battery for `grill-jev`.
The LLM executing the skill writes the battery; `scripts/grill-jev.py` only
validates and evaluates it through Jev. Do not call another model or require
an API key.

## Coverage

Choose questions that are materially relevant to the supplied artifact. A
medium artifact normally needs 25–35 questions; use up to 50 only for a
complex, high-stakes artifact. Cover the applicable topics rather than asking
one generic question per heading:

| Area | Investigate |
|---|---|
| Completeness | Success criteria, ownership, dependencies, scope, terminology, exit conditions |
| Feasibility | Timeline, capacity, unknowns, prerequisites, test environment, single points of failure |
| Risk | Data loss, irreversible work, failure propagation, external dependencies, observability |
| Boundaries | Interfaces, shared state, backwards compatibility, parallel work, change isolation |
| Verification | Acceptance criteria, smoke and regression tests, baselines, alerting, recovery evidence |
| Consistency | Contradictions, duplicate work, naming, conventions, assumptions, documentation |
| Reversibility | Rollback, migration, cleanup, rollback testing, audit trail |
| Security | Credentials, authorization, input validation, destructive actions, rate limits, logs |
| Cost & throughput | Calls, tokens, and requests per run and per second vs documented limits; fan-out; concurrency cap; retry backoff and budget; eval cost; production transport |

## Battery Format

The file must be a JSON array. Every question needs a unique `id`, a concise
`question`, and an `inspect` target. Add structured criteria when they make a
finding testable.

```json
[
  {
    "id": "success_criteria",
    "question": "Does the rollout define observable success criteria for each changed service?",
    "inspect": "artifact",
    "focus": "Named metrics, thresholds, and the owner who decides whether to proceed.",
    "criteria": {
      "true": {
        "what": "Every service has a measurable success signal and decision owner.",
        "examples": ["p95 latency stays below 200 ms", "on-call approves the next phase"]
      },
      "false": {
        "what": "Success is subjective, implied, or lacks an accountable owner.",
        "examples": ["monitor it", "should work normally"]
      }
    }
  },
  {
    "id": "rollback_safety",
    "question": "Can the data migration be rolled back safely after live writes begin?",
    "inspect": "artifact",
    "focus": "Ordering, compatibility window, backups, and irreversible transforms.",
    "criteria": {
      "summary": "Rollback readiness",
      "levels": [
        {"summary": "Unsafe", "signals": ["no rollback", "irreversible transform"]},
        {"summary": "Partial", "signals": ["rollback exists but live writes are not addressed"]},
        {"summary": "Ready", "signals": ["tested rollback and explicit compatibility window"]}
      ]
    }
  },
  {
    "id": "implementation_choice",
    "question": "Which deployment approach best matches the stated availability constraint?",
    "inspect": "artifact",
    "criteria": {
      "choices": [
        {
          "value": "phased",
          "what": "Progressive rollout with measured gates.",
          "not_for": "Changes that cannot safely run in mixed-version mode.",
          "examples": ["canary", "region-by-region"]
        },
        {
          "value": "atomic",
          "what": "One coordinated switch with a prepared rollback.",
          "not_for": "Systems that require long migration windows.",
          "examples": ["feature-flag cutover"]
        }
      ]
    }
  }
]
```

## Prompting Pattern

Ground every question in a specific claim, component, step, or omission in
the artifact. Acknowledge risks only when the plan also proves the mitigation.

| Weak | Strong |
|---|---|
| Does this have rollback? | Can step 4's schema change be rolled back after the dual-write phase begins? |
| Is testing sufficient? | Which acceptance test proves the new authorization check rejects cross-tenant reads? |
| Are dependencies known? | Does the plan name the vendor quota and an owner for obtaining the required increase before launch? |

## Shape Selection

Use the smallest structured form that makes the answer useful:

- **True/false criteria:** existence or absence of a required property.
- **Score levels:** maturity, confidence, risk, operational readiness, or
  evidence strength.
- **Choices:** mutually exclusive approaches with a fit and a non-fit.
- **Compare:** two explicitly named state paths, such as pre- and post-migration
  authorization behavior.

```json
{
  "id": "tenant_isolation_compare",
  "question": "How does tenant isolation differ before and after the cache-key change?",
  "inspect": "artifact",
  "criteria": {
    "compare": [
      {"state": "before", "look_for": "tenant identifier in every cache key"},
      {"state": "after", "look_for": "equivalent isolation in the replacement key"}
    ]
  }
}
```

## Question Bank

Select and specialize these prompts; do not copy them unchanged when the
artifact gives more precise nouns, steps, or constraints.

### Completeness

- What observable outcome defines completion for each stated phase?
- Which terms or interfaces are used without a definition or owner?
- What dependency, approval, or credential is assumed but not planned?
- Who is accountable for each decision, execution step, and validation gate?
- What is explicitly out of scope, and what prevents scope from expanding?
- Which user or operational path is not represented in the proposed flow?

### Feasibility

- Which estimate has no evidence, buffer, or dependency allowance?
- What work requires a scarce person, environment, quota, or permission?
- What happens if the first external dependency is delayed or unavailable?
- Which component is a single point of failure during the change?
- Does the test environment reproduce the production constraint being relied on?
- Which assumption would invalidate the plan if it is false?

### Risk and Safety

- What data can be lost, duplicated, leaked, or corrupted by the changed path?
- Which action is irreversible, and what evidence makes it safe to perform?
- How could an error propagate beyond the component being changed?
- What monitoring detects failure before customers report it?
- Which third-party limit, outage, or behavior change can block the plan?
- What credentials, personal data, or privileged operations could appear in logs?

### Scope and Interfaces

- Which clients, APIs, jobs, or integrations require compatibility behavior?
- What shared state can make concurrent rollout or parallel work unsafe?
- Which existing contract changes, and how are consumers notified and tested?
- What behavior differs for retries, partial failure, or a stale client?
- Which affected surface is intentionally excluded from this change and why?

### Verification and Recovery

- What acceptance test proves the user-visible outcome rather than an internal implementation detail?
- What baseline is captured before the change for later comparison?
- Which regression test protects the closest neighboring behavior?
- How quickly can an operator detect, diagnose, and reverse a failed rollout?
- What exact signal pauses progression or starts rollback?
- Who verifies recovery, and where is that evidence recorded?

### Cost and Throughput

Ask these whenever the artifact calls Jev, an LLM, or any metered API. Put
`jev-budget-check.py` output in state as `budget` when it exists.

- Does the plan state tokens per run and peak tokens per second, and compare them with the provider's documented rate limits (not only the per-request limit)?
- Does one run send the full question set for every unit in parallel, where a cheap wide stage followed by full detail for a shortlist would do?
- How many requests are in flight at once, and what caps it for many concurrent users?
- Do retries use exponential backoff with jitter, honor `Retry-After` as a floor, and stop at a per-run retry budget, or do parallel requests retry together on a short fixed delay?
- Which status codes mean "back off" on the production transport (for Jev through Vercel AI Gateway: 429, 503, 529), and which mean stop (401, 402, 422)?
- What does the eval or benchmark cost in tokens, how is it paced, and could it trip limits a live app on the same account depends on?
- Was latency and error behavior measured on the transport production uses?
- Was the request size chosen from a measured transient-failure rate at several sizes on that transport, given that a retry resends the whole request?
- When the artifact attributes a failure to an outage, size cap, or payload bug, what measurement rules out the program's own rate and retries?

Example Noul with structured criteria:

```json
{
  "id": "cost_priced_per_second",
  "report_when": "false",
  "question": "Does the plan price one run in tokens per second and requests per minute against the provider's documented rate limits, counting retries and concurrent users?",
  "inspect": "artifact",
  "criteria": {
    "true": {"what": "Per-second and per-minute numbers are stated and compared with documented limits", "examples": ["~45k tokens/run, peak ~40k tokens/s at 3 users, under 25% of 250k"]},
    "false": {"what": "Only per-request fit, or no numbers", "examples": ["each batch stays under 64k tokens", "requests run in parallel for speed"]}
  }
}
```

### Consistency and Reversibility

- Which statements, dates, or constraints contradict one another?
- What work duplicates an existing capability, policy, or source of truth?
- Which naming, configuration, or lifecycle convention does the plan violate?
- Can all persistent state return to its prior valid form?
- Has rollback been exercised under conditions close to the proposed release?

## Final Review

Before writing the JSON file, verify that the battery:

1. Names artifact-specific components or steps in most questions.
2. Includes evidence criteria for high-impact claims.
3. Avoids duplicate questions phrased differently.
4. Balances completion, feasibility, risk, verification, and recovery.
5. Includes Cost and Throughput questions when the artifact calls a metered API.
6. Fits the requested depth and never exceeds 50 questions.
