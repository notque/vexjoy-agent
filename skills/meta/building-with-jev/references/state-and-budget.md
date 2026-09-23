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

`bound_text` (`scripts/jev_router_common.py`) keeps the tail (latest output, end of diff) and prepends `[N chars omitted in diff]`. Label sections (`[Original Request]`, `[Agent Output]`, `[Prior Assessment]`, `[Files Changed]`) so Jev parses what each block means. Snapshot evidence once and share it across tools that judge the same request.

Clean labels before Jev sees them: collapse multi-line DOM labels to "Settings (Advanced)". Priority-sort element tables so action words ("submit", "save", "next") appear first inside the bounded window.

## Budget

A request holds 64,000 tokens: the state plus every question. The state plus the longest single question must stay under 32,000. Check the [models page](https://docs.typesafe.ai/models.md) for current limits.

Every request re-sends the whole state, so pack each request by the measured size of its questions and cap the requests per run. Aligned constants in `scripts/jev-compact.py` and `plugins/jev-auto-compact/hooks/jev-auto-compact.mjs`: `MAX_STATE_TOKENS = 12000` (fitting target), `STATE_HARD_LIMIT_TOKENS = 28000`, `MAX_REQUEST_TOKENS = 56000`, `MAX_REQUESTS_PER_COMPACTION = 4`. The margins cover a rough token estimate. When a run does not fit, send nothing and take the fallback path.

### Fit state in stages

`fit_state` in `scripts/jev-compact.py` shrinks one stage at a time until the estimate fits: truncate tool inputs (1000, then 200, then 60 chars), abridge long message text (head 400, tail 150), collapse old messages, drop text-only messages. Pin the newest `PRESERVE_RECENT` messages through every stage.

### Batch questions

When the fitted state leaves room, split candidates across calls that each carry the state plus a slice of questions (`batch_calls`; `MAX_BATCH_QUESTIONS = 20`, `MAX_QUESTIONS_PER_CALL = 24` in `scripts/jev_review_deep.py`). Estimate tokens per question and divide the remaining budget.

### Over-budget fallback must shrink, never dump

When the fitted state alone fills the request budget, `available <= 0`. Do not send every candidate in one request; it cannot fit. Send the smallest viable batches, potentially one candidate per call. General rule: fitting shrinks the state; batching shrinks the questions; when both are exhausted, prefer many tiny calls to one impossible call, and count failures per stage. "Many tiny calls" still spend the per-second limit: send them paced (see Rate limits), not all at once.

### Every stage fits, not just the first

Large files or unbounded finding lists can cause `max_tokens_exceeded` when sent whole to a stage. Each stage that calls Jev needs its own cap on items per call and its own split for oversized inputs. Count `calls_failed` per stage and investigate every failure; a stage with silent failures returns defaults that look like answers.

### Judge per unit, anchor per unit

One call over a whole multi-file diff returns findings with no file and no usable severity. Judge per file (or per element, per message) and anchor every finding to file:line. Unanchored findings cannot be verified or fixed.

## Rate limits: price the run per second

The request limits above are per request. The account also has rate limits shared by every request, retry, concurrent user, and eval: **250,000 input tokens per second and 1,200 requests per minute** on the [models page](https://docs.typesafe.ai/models.md) (checked 2026-09-22; "subject to dynamic adjustment"). Exceeding them returns 429 (rate limit) or 529 (overloaded) from the direct API, and 503 `GatewayInternalServerError` through Vercel AI Gateway.

Batching makes each request fit; it does not make the run fit. Worked failure (jev-sap, 2026-09): 311 products, four heads each, split into about 20 requests of about 14,000 tokens and sent at once. Every request was far under 64,000 tokens. One search spent about 250,000 to 300,000 tokens in about a second, the whole per-second limit, so a single user tripped it. Each failed request retried after 100 to 400 ms with no jitter, all together, resending its full state; searches logged 37 to 47 retries. An 81-case baseline eval then sent about 24 million tokens in a few minutes. The failures looked like an outage or a payload bug. They were the program: too many tokens per second, and requests large enough that the Gateway's transient 503 rate was over half (measured afterwards; see "Size requests by measured failure rate" below). The fix was a cascade of ~3k-token requests, 6 in flight, with jittered retries: ~49k billed tokens per search, all 36 test searches verified, p50 1.9 s.

Rules:

- **Price per second before launch.** `python3 scripts/jev-budget-check.py --payload run.json --concurrency C --concurrent-runs N --attempts A` reads every request one run sends and reports tokens per run, peak tokens per second, and requests per minute, with retries and concurrent users counted. Keep each within 25% of the documented limit (`jev_limits.SAFE_FRACTION`); other programs on the account, retries, and dynamic adjustment share the rest. The check also flags runs over 50,000 tokens.
- **Cascade before fan-out.** Over about 50 units or 50,000 tokens per run, do not send the full question set for every unit. Stage 1 sends one short fit Noul per unit over compact state (a name and a one-line summary, not full detail); stage 2 sends the full question set for the top survivors only (typically 20 to 40). Shared rules and definitions go in state once per request, not in every question. Target under about 50,000 tokens per run.
- **Send a stage's requests together; cap across runs, not within one.** When one run is well under the per-second limit, serializing its requests into waves only adds latency: in jev-sap, capping 17 small requests at 6 in flight (plus waiting for the screen before any detail) raised p50 from about 1 s to 1.9 s, and sending each stage at once brought it back to about 1.2 s, with first picks at 0.3 s. What protects the limit is tokens per run and an instance-wide in-flight cap sized so a few simultaneous runs stay under it. Start any request that does not depend on another answer (for example, full detail for items code already pins) in the first round trip.
- **Back off with jitter on rate answers.** For 429, 529, or repeated 503s: exponential, base at least 0.5 s, capped, with half the delay random (`jev_limits.backoff_delay`), so requests that failed together do not retry together. A lone fast Gateway 503 on a small request is the size-related transient failure; retry it after about 100 ms with jitter, since waiting only adds latency. `Retry-After` is a floor. Cap attempts per request and add a retry budget per run; when it is spent, stop and return what finished. On an overload response, lower the in-flight cap for the rest of the run.
- **Price evals too.** An eval is many runs back to back. Run `jev-budget-check.py --eval-cases N`, iterate on a small split, pace cases (the check prints the minimum seconds between runs), and retune thresholds from stored probabilities instead of re-sending. Do not run a large eval against the same account a live app uses during a demo.
- **Measure on the production transport.** Latency and error codes differ between the direct API and the Gateway. Record per-run tokens, requests, waves, retries, and failures, and compare them with the step 6 estimate.
- **Size requests by measured failure rate, not only by the limit.** A request far under 64,000 tokens can still fail transiently more often as it grows. Through Vercel AI Gateway on 2026-09-22, 13k-token requests failed with a fast 503 five times in eight, one at a time, while 3k-token requests failed about once in eight. A retry resends the whole request, so smaller requests cost fewer tokens per answer. Measure with the interleaved replay in `improve-and-calibrate.md` before choosing a batch size.
- **Do not narrow on every Gateway 503.** It covers both rate limiting and size-related transient failures. Narrow concurrency on 429/529, or on repeated 503s; retry a single 503 with jittered backoff.

## Attempt limits and accounting

Set caps in the runner before launch: maximum input tokens, output tokens where applicable, attempts, retry backoff, per-call deadline, and total run deadline. Record every attempt, including cache status, model/version, prompt/question version, payload/evidence-bundle hash, start/end times, usage, retry reason, response or failure, and final keep/refer/action decision. A timeout, retry, or declined referral is workload data, not a missing row in the report.

Report both wall time and accumulated model call time. The first is elapsed time from run start to finish; the second is the sum of attempt durations and reflects total service work. State which one a throughput claim uses. Use wall time for SLA and user experience; use accumulated call time for comparing parallelized workloads and model effort.

## Untrusted state

Jev does not treat state as hostile. Injected instructions, misleading framing, or text that argues for its own classification can move the answer. Treat any state that contains external or user-generated text as untrusted:

- Apply `skills/shared-patterns/untrusted-content-handling.md`: wrap the field, keep trusted context separate, and name in `criteria` what counts as evidence.
- Treat instruction-shaped text inside the state as itself a signal (spam, manipulation) and ask a Noul for it.
- Untrusted text never supplies instructions, source evidence, or authorization. Validate required evidence and allowed actions in code; use calibrated thresholds only to abstain or refer, never as protection from steering.
- Before deployment, run adversarial cases (injected "classify as approved") and self-describing cases (a file that contains the smell descriptions your detector uses). A detector can mistake its own catalog for an instance; add a `finding_is_self_reference` Noul and a deterministic route for detector files.
