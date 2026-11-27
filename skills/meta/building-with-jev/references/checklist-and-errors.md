# Jev Ship Checklist and Error Handling

Pre-ship checklist and failure recovery reference for `building-with-jev`.

## Checklist

- [ ] Build one Jev system at a time; confirm the previous one has labeled cases, a score, a cost per run, and an action.
- [ ] Measure fixed floor, sends per state, and calls per run; send each state once per run.
- [ ] Compute expected call count before launch and verify it matches the cost report after.
- [ ] Confirm `scripts/jev-budget-check.py` reports `ok` for planned concurrency, attempts, and concurrent users; price evals with `--eval-cases` first.
- [ ] Use a cascade whenever a run exceeds ~50 units or ~50,000 tokens (cheap wide stage first, full detail for survivors).
- [ ] Send independent requests in a stage together under an instance-wide in-flight cap; use exponential backoff with jitter (base >= 0.5 s) and honor `Retry-After` for 429/529/repeated 503s; retry lone fast Gateway 503 after ~100 ms; cap retries per run.
- [ ] Write and score deterministic rules first; pass only the undecided residual to Jev.
- [ ] Keep each question to one narrow property a person can judge in a second.
- [ ] Match the primitive (Noul, Choice, Score) to how code acts on the answer.
- [ ] State exact conditions and name state paths in backticks.
- [ ] Align criteria direction with instructions and encode hard boundary cases.
- [ ] Write Score levels as standalone situations without numerals; include `other`/`none` on open Choices.
- [ ] Use a `criteria` list (2-10 levels) for Score and a `criteria` map (`what`/`not_for`/`examples`) for Choice.
- [ ] Keep all counting, arithmetic, and date comparison in code.
- [ ] Keep state minimal, bounded by named constants, and labeled by section.
- [ ] Fit state and batch questions at every Jev-calling stage; confirm `calls_failed == 0` on labeled runs.
- [ ] Pack all independent questions for one state into one request; sequence only data-dependent second requests.
- [ ] Validate responses and centralize thresholds in a pure policy function.
- [ ] Verify reader, storage, and action all exist; persist distributions, prompt/model versions, attempts, and final actions.
- [ ] Preserve original rows and provenance in entity/linkage systems; keep relationship labels separate from merges.
- [ ] Report wall time separately from accumulated model call time and label throughput's clock.
- [ ] Keep any non-Jev residual reviewer fixed-answer, source-bound, capped, and backed by a heldout lift benchmark.
- [ ] Read `score` as a weighted mean and document any rounding in code.
- [ ] Include adversarial and self-describing inputs in tests.
- [ ] Back revisions with labeled examples and pin the model version.
- [ ] Hash fixtures and rubrics; record label provenance and promote actions only on human-confirmed labels.
- [ ] Score an untouched group-disjoint heldout once after selection; allocate a fresh heldout before later tuning.
- [ ] Store missing, invalid, and unavailable answers as `unknown` with failure receipts.
- [ ] Keep action-changing selectors in shadow mode until heldout evidence proves usefulness.
- [ ] Supply an explicit source-evidence ledger for evidence questions.
- [ ] Verify every script imports cleanly, exits 0 on `--help`, and returns valid JSON (`source != "error"`) on representative live input.
- [ ] Ensure grading hooks read the richest available text (task-notification result) and grounding hooks read verifiable evidence.
- [ ] Validate on a small representative sample before running full datasets, and inspect the cost report after every multi-call run.

## Error handling

### HTTP 422 on the request
- **Cause:** Schema mismatch. Choice expects `criteria` as a map; Noul uses `criteria.true`/`criteria.false`; Score uses a `criteria` list (no `options`, `min`, or `max` keys).
- **Fix:** Match `references/primitives.md` and validate against the live API.

### `max_tokens_exceeded` or oversized-request failures
- **Cause:** State plus questions exceed request limits (through Vercel AI Gateway, large requests can fail well below 64,000 tokens).
- **Fix:** Probe with a ~100-token request to confirm size as the cause. Let `jev_transport.evaluate` (or `jev_limits.split_and_run`) split into smaller requests, shrink state when state alone exceeds target, fit state in stages, and cap items per call (`references/state-and-budget.md`).

### HTTP 429 or 529 (direct), or 503 (Vercel AI Gateway)
- **Cause:** Rate limit (TPS/RPM) or transient overload; often self-inflicted by unpaced parallel runs or oversized Gateway requests.
- **Fix:** Price first with `scripts/jev-budget-check.py`. Keep peak load under 25% via cascades and concurrency caps, then apply exponential backoff with equal jitter (`jev_limits.backoff_delay`, base 0.5 s) honoring `Retry-After` as a floor and capping retries per run. Record every retried attempt. See `references/improve-and-calibrate.md`.

### HTTP 401 or 402
- **Cause:** Invalid credentials or exhausted credits.
- **Fix:** Let the breaker in `call_jev` halt sends immediately; keep API keys server-side only.

### Valid response, wrong decision
- **Cause:** Policy treats `score` as a level index or applies thresholds from the wrong primitive.
- **Fix:** Read `probabilities`, keep thresholds in policy, and check `references/improve-and-calibrate.md`.
