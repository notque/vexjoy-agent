---
name: building-with-jev
version: "1.0.0"
description: "Design, integrate, measure, and improve programs using TypeSafe Jev judgments; includes this repository's calibration and skill-dissolution contracts."
user-invocable: false
routing:
  force_route: true
  triggers: [jev, typesafe, noul, choice question, score question, system one, jev answers wrong, low confidence, jev criteria, jev state, confidence threshold, dissolve skill, replace llm with jev, three tiers]
  not_for: "End-to-end browser harness runs (browser-jev-automation) or request routing (do)."
  pairs_with: [browser-jev-automation, toolkit, do]
  complexity: Complex
  category: meta
allowed-tools: [Read, Edit, Write, Bash, Glob, Grep]
---

# Building with Jev

Jev receives one `state` and evaluates all questions independently and concurrently. Heads share state, never answers. It returns judgments over caller-defined answers; it does not generate prose, count reliably, or perform serial reasoning. Code owns evidence production, arithmetic, policy, control flow, and any dependency between judgments.

Use current TypeSafe docs for API shape, models, limits, pricing, and version jaggedness: start at `https://docs.typesafe.ai/llms.txt`, append `.md` to page paths, and pin the deployed model version. Re-read its jaggedness page and rerun labels on version change.

## Choose the tier

- Program: parse, search, count, validate, or apply a known rule.
- Jev: judge evidence already present, select from bounded candidates, score, gate, or triage.
- LLM: create a new artifact.

Run deterministic filters first and send Jev only the residual. A fixed answer, score, or yes/no gate in a hook is not generative and should not require an LLM. An LLM may review frozen, source-bound residuals only when held-out evidence justifies its marginal lift, referral rate, cost, and latency.

## Primitive semantics

| Primitive | Use | Read in code |
|---|---|---|
| Noul | one clean binary condition | `noul` in `[0,1]`; distance from `.5` is uncertainty signal |
| Choice | exactly one supplied unordered option | `choice`, `probabilities`, `confidence` |
| Score | supplied ordered levels | probability-weighted mean `score`, plus `probabilities` and `confidence` |

A Score is not a selected level: `1.0` can mean certainty at level 1 or an even 0/2 split. Never interpolate a real-world quantity from it. Choice/Score confidence is distribution concentration, not correctness or authority. Thresholds do not transfer between primitives or question phrasings; even `P(A)` and `1-P(not A)` need not match.

## Design contract

1. Define the unit, judgment, possible answers, and exact action for each answer. If no action changes, omit the head.
2. Put all evidence needed for that judgment in bounded, labeled state. Compute dates, totals, matches, candidates, and provenance in code. Untrusted content is data, never instructions.
3. Ask one coherent judgment per head. Use literal scope and negation; criteria define both sides. Put independent heads in one request. If a later head's evidence or candidates depend on an earlier answer, code builds a second request.
4. Questions are billed input too. Measure the fixed question floor, total tokens, sends, retries, p50/p95 wall time, and accumulated attempt time. The request limit is 64,000 input tokens; shrink/select rather than dumping overflow.
5. Missing, malformed, or unavailable answers are `unknown`, never false, pass, or permission. Deterministic security and authorization rules outrank Jev.

Before implementation, fill `references/decision-card.md`. Full request/answer objects and question wording live in `references/primitives.md` and `references/question-design.md`; state fitting and hostile-input rules live in `references/state-and-budget.md`.

## Evidence loop

Build one judgment system at a time:

Freeze human-confirmed labels and provenance, hash fixtures/rubric, and keep a group-disjoint heldout sealed. Measure deterministic baselines, encode near-certain rules, then evaluate Jev on the residual. Report rules, residual, and combined performance with slices, calibration, failures, action changes, timing, and cost. Measure frozen-request variance before comparing close variants. Full diagnosis and revision rules are in `references/improve-and-calibrate.md`.

For an action gate with false-positive cost `C_FP` and false-negative cost `C_FN`, a starting threshold is `C_FP / (C_FP + C_FN)`; select and report it on different splits. New hooks run in shadow mode until disjoint heldout evidence shows that acting improves the outcome.

Repository runners: `scripts/jev-harness.py` (`loop`, `variance`, `sweep`) and `scripts/jev-cost-report.py`. Cache and circuit-breaker behavior are runner details, not model guarantees.

## Composition and integration

Use `references/composition-positions.md` to place the judgment relative to the function and `references/composition-patterns.md` only for the matching topology. Common local constraints:

- wide Choice -> code shortlist -> detailed Choice for routing;
- Choice picks a candidate; separate Nouls decide fitness or fan-out;
- parallel Nouls expose reusable dimensions better than an opaque composite Score;
- a second request is justified only by newly derived evidence/candidates;
- preserve source rows and provenance through joins; a relationship label never licenses identity merging.

An integration needs a reader, persisted receipt, policy/action, explicit unavailable path, and tests with fake answers plus real labeled runs. Thread reusable judgments as `prior_results`; do not make an LLM re-judge them. See `references/integration-lifecycle.md`.

## Skill distillation and artifact iteration

To replace a procedural skill, classify each phase: deterministic code, Jev judgment, or genuinely generative residue. Keep policy and side effects in code; benchmark the Jev program against the skill's EVAL/hand labels. See `references/dissolving-a-skill.md`.

For prompt/skill/rubric improvement, use `references/iteration-with-jev.md`: establish a fixed broad battery, baseline the original, revise against action-changing heads, rerun the exact battery, then make one final focused pass. Do not optimize to a single aggregate or let Jev directly edit the artifact.

## Reference router

- `primitives.md`: wire objects and answer invariants.
- `question-design.md`: instruction/criteria/option design.
- `state-and-budget.md`: evidence bounds, budgets, adversarial state.
- `decision-card.md`: required pre-code gate contract.
- `composition-patterns.md`, `composition-positions.md`: multi-judgment topology.
- `integration-lifecycle.md`: local hook, persistence, failure behavior.
- `improve-and-calibrate.md`: symptom diagnosis and labeled iteration.
- `dissolving-a-skill.md`: skill-to-program method and joy-check example.
- `iteration-with-jev.md`: controlled artifact A/B loop.
