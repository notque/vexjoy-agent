# Jev Build Procedure, Fallback Modes, and Escalation

Deep reference for `building-with-jev`. Load when building a Jev system end to end, configuring fallback/second-opinion modes, escalating uncertain answers, or dissolving a skill.

## Fallback and second-opinion modes

A plain `evaluate`/`evaluate_packed` call still raises `JevTransportError` on failure with no alt model involved. Two scoped exceptions exist in `scripts/jev_transport.py` for the single named alt model in `scripts/jev_alt_model.py` (the Anthropic API when a key is configured, else the logged-in `claude -p` CLI). A caller opts into one mode explicitly; neither runs by default.

| Mode | Function | When it calls the alt model | Returns |
|---|---|---|---|
| Availability fallback | `jev_transport.evaluate_with_fallback(state, questions, timeout=..., alt_timeout=...)` | Only after Jev raises `JevTransportError` (no credentials, network or API failure, rate-limited, oversized request) | A normal Jev-shaped response (`answers`, `_meta`). `_meta["is_jev"]` is `True` on the Jev path, `False` on the fallback path; `_meta["fallback_reason"]` is set only on the fallback path. |
| Explicit second opinion | `jev_transport.evaluate_second_opinion(state, questions, timeout=..., alt_timeout=...)` | Always, alongside Jev, only when the caller explicitly asked for a second opinion | `{"jev": ..., "alt_model": ..., "_meta": {"mode": "second_opinion"}}`. Either side is `{"error": ..., "source": ...}` on its own failure; the other side's answer still returns. |

Rules for both modes:

- Read `_meta["is_jev"]` (fallback) or the separate `jev`/`alt_model` keys (second opinion) before reporting a number, and explicitly name the alt model in any report that uses its answer.
- Keep both `answers` dicts untouched in second-opinion mode; code that wants one number picks one side explicitly and states which.
- Raise `JevTransportError` (source `"fallback_failed"`) in `evaluate_with_fallback` when both Jev and the alt model fail; report each side's own failure in `evaluate_second_opinion`.
- Both modes are text-only and raise `JevTransportError` (source `"images_unsupported"`) on images or Box questions.
- Keep this narrow pair of modes scoped to the single named alt model rather than expanding into a provider registry.

## Build procedure

Build one Jev system at a time. A system is finished when it has labeled cases, a measured score, a measured cost per run, and an action that uses the answer. Evidence of value is a labeled run; unit tests with mocked answers prove plumbing only.

| Step | Tier | Do | Exit gate |
|---|---|---|---|
| 1. State the decision | - | Write one sentence: the decision, the unit it applies to, and the action code takes on each answer. | A person can label one unit by hand in under a minute. |
| 2. Build the grader | 1 | Collect human-confirmed labeled units `(x, y)` with label provenance. Freeze fixture copies and hash both fixtures and rubric. Split train/dev from an untouched group-disjoint heldout. | `score(predictions)` runs on dev and prints the majority-class baseline; the heldout is sealed. |
| 3. Discover signals | 1 | Run SQL or Python over train. Record accuracy against `y`, count, and slice accuracy for every computable signal. | A correlation table sorted by accuracy, with counts. |
| 4. Write the policy | 1 | Turn the table into rules: `rule(x) -> (action, sure)`. Score the rules on dev and count the residual. | Rules and dev score recorded in the run log; residual counted. |
| 5. Design the request | 1+2 | Build bounded, labeled state for residual units only, with arithmetic done in code. Write one atomic question per judgment; pack all independent questions for one state into one request. | The decision card is filled in (`references/decision-card.md`). |
| 6. Price the run | 1 | Run on a ten-word input to measure the fixed floor. Price with `python3 scripts/jev-budget-check.py --payload run.json --concurrency C --concurrent-runs N --attempts A` and `python3 scripts/jev-size-probe.py --payload run.json`. | Peak TPS and RPM stay under 25% of limits with retries and concurrent runs counted; runs over 50k tokens use a cascade. |
| 7. Smoke run | 2 | Run the three-unit set, then the dev sample. | `calls_failed` is zero, every answer parses, and `python3 scripts/jev-cost-report.py --since 1h` matches the step 6 estimate. |
| 8. Score | 1 | On dev, report rules alone, Jev on residual, and combined system per slice with Brier, calibration, false positives, recall, and judge variance. | Combined score and cost per run are in the run log. |
| 9. Improve | 1+2 | Separate code/service failures from wrong answers by inspecting exact state/questions/answers. Classify misses (`state_lacked_evidence`, `criteria_ambiguous`, `wrong_primitive`, `label_noise`) and change one lever at a time. | Each variant is logged with score and cost. |
| 10. Report | 1 | Score the untouched heldout once after selection; report p50/p95 wall time, accumulated model call time, throughput, and referral metrics if used. | One heldout number and workload metrics beside dev. |
| 11. Integrate | 1+2 | Ship an on-demand command with reader, storage, and action. Promote to a hook in shadow mode once obvious cases are handled in code, labeled accuracy is proven, distribution is non-constant, and something acts on the answer. | A day of use matches expected cost and action-changed rate. |
| 12. Next system | - | Start step 1 for the next decision. | - |

### Step 9 levers and cost model

Search levers in order: evidence in state; decomposition (one Score into several Nouls); criteria wording; thresholds (`t = C_FP / (C_FP + C_FN)`, tuned from stored probabilities at zero API cost); few-shot examples in state.

Cost = calls x input tokens per call (`state + all question text`; output is free). Three governing numbers:
- **Sends per state:** one per run; stages are code thresholds; a second request travels only for new evidence.
- **Fixed floor per call:** below the typical state size (1-2 line questions; add `what`/`not_for`/`examples` only where labeled misses require them).
- **Peak tokens per second:** under 25% of the documented 250,000 (~60,000), counting retries and concurrent users, enforced via cascades and an instance-wide in-flight cap.

Measure repeatability over frozen requests before iterating. `call_jev` logs script name, session id, input tokens, question count, payload hash, cache status, and errors. Store missing/unavailable answers as `unknown` with failure receipts, and keep action-changing selectors in shadow mode until heldout results confirm improvement. Deterministic driver: `scripts/jev-harness.py` (`loop`, `variance`, `sweep`).

## Escalate when Jev is unsure

1. A Noul in 0.4 to 0.6, or a split Choice or Score, is unsettled. Run one sharpening pass: split the question, add missing evidence, tighten criteria, and re-ask on the changed state. For a Choice, merge equivalent options, drop ruled-out options, and check `p_max / p_second` (`scripts/jev_choice.py`).
2. Apply consequence gating first: low-consequence or reversible picks take the argmax at any margin. When still unsettled and leading options differ in outcome cost (irreversible, financial, owner-visible), escalate to a stronger model per model policy (Opus for code, edits, and decisions; Haiku for read-only gathering) using the same frozen evidence and fixed answer schema. After a sharpening pass, accept a flipped pick when margin >= 2 and new facts bear on the options; if still flat and consequential, escalate and log all three.
3. Treat escalation as bounded residual review: declared referral band, capped cost, heldout lift check, and logged trigger distributions.
4. Route owner-reserved decisions and safety-hook matters directly to the owner, keeping an unsure Jev answer as `unknown`.

## Dissolving a skill into a Jev program

1. **List phases:** read `SKILL.md` and write each phase on one row.
2. **Classify each phase:** deterministic (program), judgment (Jev), generation (LLM), or orchestration.
3. **Convert judgment phases:** map to Noul (gates), Choice (routing/classification), or Score (severity/quality) with criteria for edge cases.
4. **Keep deterministic phases in code:** regex, file reads, grep, counts, formatting.
5. **Isolate generation:** pass prior Jev decisions to generative LLM phases as `prior_results`.
6. **Write the policy function:** a pure `policy(assessment) -> action` with named thresholds.
7. **Prove agreement:** match or exceed the skill's accuracy on hand-labeled examples before retiring `SKILL.md`. Worked example: `references/dissolving-a-skill.md`.
