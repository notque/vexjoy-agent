---
name: grill-jev
description: "Broad Jev interrogation: generate up to 50 context-specific questions about a plan, spec, design, code artifact, or any topic — using all primitive shapes and structured forms to surface hidden problems before they ship."
user-invocable: true
routing:
  force_route: true
  triggers:
    - grill
    - validate plan
    - validate spec
    - validate design
    - interrogate
    - stress test plan
    - stress test spec
    - 50 questions
    - deep validation
    - grill this
    - grill the plan
    - jev interrogation
    - sanity check plan
    - sanity check spec
    - check my plan
    - check my design
    - plan validation
    - spec validation
    - design validation
    - architecture review jev
    - verify plan
    - verify spec
    - challenge plan
    - challenge design
    - find holes
    - find gaps in plan
  not_for: "Writing new Jev programs (use building-with-jev). Routing requests (use do). Code review for quality/style (use review). Security scanning (use security). This skill runs a broad interrogation battery against a supplied artifact — it does not build Jev programs."
  pairs_with:
    - building-with-jev
    - review
  complexity: Complex
  category: meta
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Grill-Jev

Generate a context-specific Jev interrogation battery against a plan, spec, design, code artifact, or any topic. Questions are generated from the artifact itself — not from a static list — so they target the actual risks and gaps in what you provide.

## When to invoke

- User says "grill this", "validate my plan", "find holes in my spec", "sanity check", "stress test this", "50 questions", "interrogate", "grill-jev"
- **Automatically after any planning output.** When a plan, spec, or design is produced — before execution begins — pass it through grill-jev. Any structured output with phases, steps, or checklist items qualifies.
- When the user says "does this look right", "approve this", "is this ready", "review my plan"

## How it works

1. **Read the artifact** — the plan, spec, design, or code being interrogated
2. **Generate questions** — the LLM executing this skill produces up to 50 context-specific Jev questions tailored to the artifact. It writes the JSON battery to a temporary file; no secondary model call or API key is used. Questions use all structured shapes:
   - Noul with `{true: {what, examples}, false: {what, examples}}` criteria
   - Choice with `{what, not_for, examples}` per option
   - Score with `{summary, signals}` per level
   - Noul with array `compare` instructions when two state paths need comparison
3. **Send to Jev** — evaluate the questions against the artifact as state. Use Vercel AI Gateway. Too much context is the most common failure: the artifact is resent with every batch, so split the battery by estimated tokens (`jev_limits.request_tokens`), not by question count, keeping each request under the size target in `skills/shared-patterns/jev-production-lessons.md`. When the artifact alone passes the target, send the sections each question needs instead of the whole artifact.
4. **Report findings** — high-signal answers with suggested actions

## Asking good questions

Question quality depends on context and framing. The rules below were validated through 3 iterative Jev loops.

**Context inputs that improve questions:**

| Input | Why it matters | Example |
|---|---|---|
| **Audience** | Who executes or approves this? SRE, junior dev, product owner, external team? | SREs need ops-specific questions; product owners need outcome and risk questions |
| **System context** | What does the system actually do? What are its constraints? | Stateful vs. stateless changes need different risk questions |
| **Purpose** | What decision does this artifact support? | Approval gate → binary questions; exploration → broader coverage |
| **Depth wanted** | 15 sharp questions or 50 comprehensive ones? | Match count to stakes and complexity |

Pass context via `--context "audience: SRE, system: stateful payment service, known constraint: cannot have >5min downtime"`.

**Generation rules (Jev-validated):**

1. **Specific over generic** — questions must name specific steps, systems, or claims in the artifact. "Does step 4's migration define a rollback safe to run under live traffic?" beats "does this have rollback?".

2. **Mentions trigger deeper scrutiny, not shallower** — when the artifact mentions a risk, gap, or uncertainty, generate MORE targeted questions about it. Acknowledgment is not mitigation. "This is risky" without a defined mitigation is itself a finding.

3. **Audience weight** — use audience context to focus questions. An SRE needs ops questions. A junior dev needs step-clarity questions. A product owner needs outcome questions.

4. **Coverage balance** — aim for breadth across relevant categories (completeness, feasibility, risk, scope, verification, consistency, reversibility, security, cost and throughput). Do not cluster all questions on one category. Skip a category only when the artifact has nothing that triggers it.

5. **Scale by complexity** — simple artifact (15-20 questions), medium (25-35), complex (40-50). Hard cap: 50.

**Self-calibration loop** — if findings feel generic or off-target, use Jev to improve:
1. Run grill-jev — observe which findings feel shallow
2. Ask Jev: "Which questions were not specific to this artifact? What context would have produced better questions?"
3. Feed that context back via `--context` and re-run

## Question categories

Generate questions covering these nine areas, weighted by what the artifact contains:

| Category | What it finds |
|---|---|
| Completeness | missing phases, undefined terms, unstated assumptions |
| Feasibility | resource constraints, timeline, dependencies |
| Risk & failure modes | what happens when each step fails |
| Scope & boundaries | what's in/out, integration surfaces |
| Verification | how do we know it worked, success criteria |
| Consistency | internal contradictions, duplicate effort |
| Reversibility | can we undo this, migration risk |
| Security & safety | auth, data exposure, destructive operations |
| Cost & throughput | calls, tokens, and requests per run and per second against the provider's documented rate limits; fan-out size; concurrency; retry policy; eval cost |

## Plans that call Jev or another metered API

A plan can be complete, feasible, and safe and still fail in production because one run spends the provider's per-second limit. Grill it on arithmetic, not just on prose:

0. **Check it against the rules.** Load `skills/shared-patterns/jev-production-lessons.md` and turn every unticked pre-ship checklist item into a `cost_` Noul with `report_when: "false"`. Name the exact number in the question: "Does the plan keep every request at or under 4k tokens or a measured reliable size?", "Does it send each stage's requests at once, with an instance cap near floor(0.25 × 250,000 / tokens_per_request)?", "Does it set attempts, per-attempt timeout, run deadline, and a retry budget near 4 × requests × failure rate?"
1. **Price it first.** When the artifact calls Jev, build (or ask for) a JSON of every request one run sends and run `python3 scripts/jev-budget-check.py --payload run.json --concurrency C --concurrent-runs N --attempts A`, plus `--eval-cases N` for any eval the plan runs. A `fail` is a high-signal finding on its own; a `warn` goes in the report. Put the check's summary in state under `budget` so battery questions can inspect it.
2. **Ask about throughput explicitly.** Include Cost & throughput questions (see `references/question-battery.md`): does the plan state tokens per run and per second against the documented limits (250,000 input tokens per second and 1,200 requests per minute for Jev on 2026-09-22)? Does it fan full detail out over every unit, or cascade? Is in-flight concurrency capped? Do retries use jittered exponential backoff with a per-run budget? Is the eval priced and paced? Which errors mean "back off" on the production transport (Vercel AI Gateway reports upstream overload as 503)?
3. **Treat "each request fits" as unproven.** A plan that shows every request under the per-request limit has not shown the run fits. Look for the per-second number.
4. **Diagnoses need measurements.** When the artifact explains a failure (an outage, a size cap, a bad payload), ask whether it measured the run's own rate and retry count and tested a small known-good request on the same transport before concluding.

## Question generation prompt

Use this system prompt to generate the question battery:

```
You are generating a Jev question battery to interrogate an artifact.
The artifact is provided as state at key "artifact".

Generate between 20 and 50 questions. Scale the count to the artifact's
complexity — a 3-step bug fix needs fewer questions than a multi-service
migration plan.

For each question, choose the most appropriate Jev primitive:
- Noul: yes/no probability. Use when you want to know whether something
  is true or absent. Always add structured criteria (true/false with
  what + examples) when the boundary is non-obvious.
- Choice: pick one from a known set. Use for risk levels, categories,
  reversibility classifications.
- Score: position on a spectrum. Use for completeness, timeline
  realism, detection speed.

Use array compare instructions when two or more fields in the state
need to be compared side by side.

Focus questions on the actual content of the artifact. A plan with no
database steps needs no database migration questions. A plan with a
single deploy step needs no multi-service blast radius question.

Output a JSON dict of question_id -> question definition.
```

## Running the battery

```bash
# File artifact
python3 scripts/grill-jev.py --file task_plan.md --mode plan

# Inline text
python3 scripts/grill-jev.py --text "$(cat task_plan.md)" --mode plan

# The executing LLM writes /tmp/grill-questions.json, then Jev evaluates it.
python3 scripts/grill-jev.py --file design.md --questions-file /tmp/grill-questions.json
```

The executing LLM owns question generation; the script only evaluates a supplied battery through Jev. Without `--questions-file`, it uses the static fallback battery. The compact guide in `references/question-battery.md` provides:
- Example shapes for the LLM question generator
- Fallback when generation is unavailable
- Test fixture for unit tests

## Output

```
GRILL-JEV FINDINGS — mode: plan — 31 questions (generated)
============================================================
HIGH SIGNAL (requires attention):
  [completeness/has_success_criteria] noul=0.89 TRUE — no measurable success criteria
    → add explicit success criteria: observable outcomes, not "it works"
  [risk/migration_live_safety] noul=0.84 TRUE — migration runs against live traffic
    → add maintenance window or use online migration tool

CATEGORY SUMMARY:
  completeness  2 findings   risk  1 finding

OVERALL READINESS: 1.4/3 — partially complete; address findings before executing
```

## Primitive shapes — quick reference

```python
# Noul with structured criteria
"has_success_criteria": {
    "type": "noul",
    "instructions": {"question": "Does the plan define measurable success criteria?",
                     "inspect": "artifact"},
    "criteria": {
        "true":  {"what": "Specific, observable outcomes are named",
                  "examples": ["all tests pass", "p95 latency < 200ms"]},
        "false": {"what": "Success is vague or absent",
                  "examples": ["it works", "done"]}
    }
}

# Choice with what/not_for/examples
"overall_risk": {
    "type": "choice",
    "instructions": {"question": "What is the overall risk level?",
                     "focus": "Weigh irreversibility, dependency count, blast radius."},
    "criteria": {
        "low":  {"what": "Reversible, few dependencies, limited blast radius",
                 "not_for": "Any step that cannot be undone",
                 "examples": ["adding an optional config flag"]},
        "medium": {"what": "Some irreversibility or cross-system dependencies",
                   "examples": ["schema migration with rollback plan"]},
        "high": {"what": "Irreversible steps, wide blast radius",
                 "examples": ["deleting a table", "replacing auth system"]}
    }
}

# Score with summary/signals levels
"completeness": {
    "type": "score",
    "instructions": {"question": "How complete is this plan?",
                     "note": "Judge whether a competent engineer could execute it without guessing."},
    "criteria": [
        {"summary": "Critically incomplete",
         "signals": ["missing phases", "undefined terms", "no rollback"]},
        {"summary": "Partially complete",
         "signals": ["main path clear", "some steps vague"]},
        {"summary": "Mostly complete",
         "signals": ["all phases named", "minor details missing"]},
        {"summary": "Complete",
         "signals": ["all steps actionable", "success criteria defined"]}
    ]
}

# Noul with array compare instructions
"assumption_vs_reality": {
    "type": "noul",
    "instructions": {
        "question": "Do the plan's assumptions conflict with the known system context?",
        "compare": ["artifact", "context"],
        "focus": "Look for things the plan takes for granted that could be false."
    }
}
```

Question-authoring guide: `references/question-battery.md`.

## Integration into planning workflows

Any skill or agent that produces a plan should call grill-jev before declaring it complete:

```python
import subprocess

result = subprocess.run(
    ["python3", "scripts/grill-jev.py", "--file", plan_path, "--mode", "plan", "--questions-file", questions_path],
    capture_output=True, text=True
)
print(result.stdout)
# Non-zero exit when HIGH SIGNAL findings exceed threshold
```
