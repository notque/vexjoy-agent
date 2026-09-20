# State and budget

State is the evidence Jev evaluates: the diff, the request, the element table, the error text. Rules for evaluation go in `instructions` and `criteria`, never in state. Mixing them makes questions untestable and criteria untunable.

## Send only what the questions need

- Accuracy falls as unrelated content grows. A large state also hides which input caused a miss.
- Retrieve and filter in code first. When code cannot filter, ask a relevance Noul per passage in one call and keep the passages that pass.
- Keep state structured so questions can point into it by path.
- Convert numeric encodings to words or buckets (color names, not hex; "net 30", not 30). Compute date order, durations, windows, counts, and sums in code and send the result.
- Jev does not count. One Noul per item in one request, then sum in code with your threshold.
- Dates: one Choice per part (month, day, year) with a "not stated" option; assemble and compare in code.
- Extraction: generate candidates with a regex or a generative model; Jev picks with a Choice (option values may be `null`) or verifies one with a Noul.
- Time is part of the state. Give a `settled` signal and a `still_loading` head when the page or process may not have finished.

## Evidence bundles and provenance

High-throughput pipelines prepare evidence before any model call. Code groups raw rows into bounded atoms or candidate bundles, retains every original row, and attaches stable source IDs, normalization/version metadata, and the deterministic signals that formed the bundle. The runner binds a model to this bundle; the prompt does not own the pipeline. This lets Jev and a bounded reviewer see the same evidence and makes results replayable when models change.

Keep observed facts, inferred classifications, and actions separate. A shared signal may support a linkage or ranking without authorizing a consequential action. Store each inference with its evidence and answer distribution, and apply actions only through distinct, thresholded policy. Never discard the source records or provenance that make a decision reversible.

## Bound every field

Every state field has an explicit limit as a named constant, not an ad-hoc slice.

```python
DIFF_LIMIT = 20000
OUTPUT_LIMIT = 12000
state = {"request": bound_text(request, REQUEST_LIMIT, "request"),
         "diff": bound_text(diff, DIFF_LIMIT, "diff")}
```

`bound_text` (`scripts/jev_router_common.py`) keeps the tail (latest output, end of diff) and prepends `[N chars omitted from diff]`. Label sections (`[Original Request]`, `[Agent Output]`, `[Prior Assessment]`, `[Files Changed]`) so Jev parses what each block means. Snapshot evidence once and share it across tools that judge the same request.

Clean labels before Jev sees them: collapse multi-line DOM labels to "Settings (Advanced)". Priority-sort element tables so action words ("submit", "save", "next") appear first inside the bounded window.

## Budget

A request holds 64,000 tokens: the state plus every question. The state plus the longest single question must stay under 32,000. Check the [models page](https://docs.typesafe.ai/models.md) for current limits.

Every request re-sends the whole state, so pack each request by the measured size of its questions and cap the requests per run. Aligned constants in `scripts/jev-compact.py` and `plugins/jev-auto-compact/hooks/jev-auto-compact.mjs`: `MAX_STATE_TOKENS = 12000` (fitting target), `STATE_HARD_LIMIT_TOKENS = 28000`, `MAX_REQUEST_TOKENS = 56000`, `MAX_REQUESTS_PER_COMPACTION = 4`. The margins cover a rough token estimate. When a run does not fit, send nothing and take the fallback path.

### Fit state in stages

`fit_state` in `scripts/jev-compact.py` shrinks one stage at a time until the estimate fits: truncate tool inputs (1000, then 200, then 60 chars), abridge long message text (head 400, tail 150), collapse old messages, drop text-only messages. Pin the newest `PRESERVE_RECENT` messages through every stage.

### Batch questions

When the fitted state leaves room, split candidates across calls that each carry the state plus a slice of questions (`batch_calls`; `MAX_BATCH_QUESTIONS = 20`, `MAX_QUESTIONS_PER_CALL = 24` in `scripts/jev_review_deep.py`). Estimate tokens per question and divide the remaining budget.

### Over-budget fallback must shrink, never dump

When the fitted state alone fills the request budget, `available <= 0`. Do not send every candidate in one request; it cannot fit. Send the smallest viable batches, potentially one candidate per call. General rule: fitting shrinks the state; batching shrinks the questions; when both are exhausted, prefer many tiny calls to one impossible call, and count failures per stage.

### Every stage fits, not just the first

Large files or unbounded finding lists can cause `max_tokens_exceeded` when sent whole to a stage. Each stage that calls Jev needs its own cap on items per call and its own split for oversized inputs. Count `calls_failed` per stage and investigate every failure; a stage with silent failures returns defaults that look like answers.

### Judge per unit, anchor per unit

One call over a whole multi-file diff returns findings with no file and no usable severity. Judge per file (or per element, per message) and anchor every finding to file:line. Unanchored findings cannot be verified or fixed.

## Attempt limits and accounting

Set caps in the runner before launch: maximum input tokens, output tokens where applicable, attempts, retry backoff, per-call deadline, and total run deadline. Record every attempt, including cache status, model/version, prompt/question version, payload/evidence-bundle hash, start/end times, usage, retry reason, response or failure, and final keep/refer/action decision. A timeout, retry, or declined referral is workload data, not a missing row in the report.

Report both wall time and accumulated model call time. The first is elapsed time from run start to finish; the second is the sum of attempt durations and reflects total service work. State which one a throughput claim uses. Use wall time for SLA and user experience; use accumulated call time for comparing parallelized workloads and model effort.

## Untrusted state

Jev does not treat state as hostile. Injected instructions, misleading framing, or text that argues for its own classification can move the answer. Treat any state that contains external or user-generated text as untrusted:

- Apply `skills/shared-patterns/untrusted-content-handling.md`: wrap the field, keep trusted context separate, and name in `criteria` what counts as evidence.
- Treat instruction-shaped text inside the state as itself a signal (spam, manipulation) and ask a Noul for it.
- Untrusted text never supplies instructions, source evidence, or authorization. Validate required evidence and allowed actions in code; use calibrated thresholds only to abstain or refer, never as protection from steering.
- Before deployment, run adversarial cases (injected "classify as approved") and self-describing cases (a file that contains the smell descriptions your detector uses). A detector can mistake its own catalog for an instance; add a `finding_is_self_reference` Noul and a deterministic route for detector files.
