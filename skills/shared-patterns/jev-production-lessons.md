# Jev production rules

Concrete rules for sending Jev requests in production. Numbers marked "example" come from jev-sap (a 311-item catalog search through Vercel AI Gateway, measured 2026-09-22). Following these rules took that search from ~250–300k tokens with frequent fallback to ~49k tokens, every search verified, 0.3 s to first results and ~1.2 s total. Put your own project's numbers in its AGENTS.md, not here.

## Four facts first

1. **Use Vercel AI Gateway.** Set `JEV_TRANSPORT=vercel` (`auto` also picks it when `AI_GATEWAY_API_KEY` is set). Do not fall back to the direct API.
2. **Too much context is the most common failure.** Oversized requests fail consistently; small ones return fine. So never send one: split it into as many requests as it takes (2, 15, ...), each carrying the same state, sent at once, and merge the answers. The toolkit does this for you: `jev_transport.evaluate` and `jev_vercel.evaluate` split any request over `jev_limits.MAX_REQUEST_TOKENS` (4,500) into requests of at most `TARGET_REQUEST_TOKENS` (3,500) with `jev_limits.split_and_run`, at most 16 in flight, and record it in `_meta.split`. A failed part raises; partial answers are never returned as complete. Only a state too large for even one question is refused (`request_too_large`): shrink the state (bound fields, send only what the questions need); never raise the cap.
3. **A small request is the first diagnostic.** When calls start failing, send a ~100-token request with one question. If it returns, the cause is request size, not an outage: shrink or split. If it fails too, look at the key, the credits, or the service.
4. **Rate limits are normal.** 429, 503, and 529 happen; retry them with jittered backoff (rule 5) and move on. Redesign only when the budget check (rule 2) shows the run itself is over budget.

## Pre-ship checklist

- [ ] Transport is Vercel AI Gateway, and oversized requests are split into several small ones, never sent whole (fact 2).
- [ ] Every request is at or under the largest reliable size from `jev-size-probe.py` on the production transport (2.5–4k tokens via Gateway until measured otherwise).
- [ ] `jev-budget-check.py` on one run: under ~50k tokens per run, and peak tokens/s under 25% of 250k.
- [ ] A unit test builds the worst-case run and asserts total tokens and per-request size.
- [ ] More than ~50 items: screen then detail (rule 3). Every item is screened.
- [ ] Each stage's independent requests are sent at once. The instance in-flight cap comes from the rule 4 formula.
- [ ] Retries follow the rule 5 table: attempts, per-attempt timeout, run deadline, and retry budget set.
- [ ] Missing or malformed answers count as failed; partial results are not cached.
- [ ] Results are cached per normalized query under a `QUESTIONS_VERSION`.
- [ ] One log line per run with the rule 9 fields.
- [ ] Any eval is priced and paced per rule 7 before it runs.
- [ ] Multi-step loops send a bounded ledger (goal, checkpoint, facts, dead ends), not raw history, since the request cap forces compression.

Used by `building-with-jev`, `grill-jev`, `browser-jev-automation`, `jev-design`, and `d`.

## Limits

| Limit | Value | Source |
|---|---|---|
| Tokens per request (state + every question) | 64,000 | models.md |
| State + longest single question | 32,000 | models.md |
| Input tokens per second, whole account | 250,000 | models.md |
| Requests per minute, whole account | 1,200 | models.md |
| Tokens per request with a low transient-failure rate via Gateway | **~2.5–4k** | measured 2026-09-22 (re-measure) |

The account limits are shared by every request, retry, user, eval, and other app on the account.

## 1. Keep every request at 2.5–4k input tokens

Through Vercel AI Gateway, identical requests fail with a fast (~300 ms) HTTP 503 more often as input tokens grow. Question count and concurrency do not matter:

| Tokens per request | Failed, one at a time |
|---|---|
| ~1.6k | 0/8 |
| ~3k | ~1/8 |
| ~5k | 3/8 |
| ~13k | 5/8 |

A retry resends the whole request, so 2.5–4k tokens gives the fewest tokens per answer.

- Measure your own curve before choosing a size, and again whenever failures change:
  ```bash
  python3 ~/.claude/scripts/jev-size-probe.py --payload run.json --rounds 10 --variants 4
  ```
  It sends real requests of different sizes plus a one-question control, round-robin, one at a time, with retries and cache off. It prints failures per size, tokens per answer, and the largest reliable size. Cost is about rounds × the variants' tokens (10 rounds of 4 variants at ~3k is ~120k tokens).
- **Direct TypeSafe API:** the curve has not been measured there. Start at the same 2.5–4k target, run `jev-size-probe.py` with `JEV_TRANSPORT=direct`, and raise the size only if larger requests measure as reliable. The direct API returns 429 (rate) and 529 (overload), not 503.

- Pack by estimated tokens, not by item count: `Math.ceil(JSON.stringify({state, questions}).length / 4)`. Billed tokens run about 1.1× this estimate.
- Start a new request when adding the next item would pass the target.
- Put shared rules in `state.rules` once per request. Keep each question to one line that names the rule and the path (``Following `rules.fit`, is `products.p3` relevant to `query`?``).
- Omit `criteria` on high-volume screening Nouls. It is optional, and at ~30 tokens per question it dominates cost.

## 2. Price the whole run before shipping

Dump every request one run sends, then:

```bash
python3 ~/.claude/scripts/jev-budget-check.py --payload run.json \
  --concurrency <in-flight> --concurrent-runs <users> --attempts 2 --latency 0.4
```

- Target: under ~50k tokens per run.
- Add a unit test that builds the worst-case run from real data and asserts the token total and per-request sizes (example: jev-sap `tests/jev-budget.test.ts`).
- Price evals the same way (`--eval-cases N`). Example: 81 cases at ~300k tokens each was ~24M tokens, which tripped the limits the eval was measuring.

## 3. Over ~50 items: screen, then detail

Never ask the full question set about every item.

| Stage | Items | State per item | Questions per item |
|---|---|---|---|
| Screen | all | name, area, one line (~30 tokens) | 1 Noul, no criteria |
| Detail | top ~30 | full detail + evidence | the full set (fit, primary, exclusion, ...) |

- Survivors are:
  - Pinned items first: the top ~6 matches from code (lexical or rules). They always get detail.
  - Then screen passes at ≥ 0.3, by probability, capped at ~30. Tune the floor on labeled cases so no labeled positive is dropped.
  - Then any items the policy needs alongside a survivor (example: the current successor of a legacy product).
- Word the screen rule for recall: "when unsure, answer yes; a second pass decides with full detail".
- Ask conditional heads only when an earlier answer allows it. Example: skip discovery questions when the scope Noul rules exploration out.

## 4. Send every independent request at once

- Stage 1, all at once: scope, every screen request, and detail for the pinned items.
- Stage 2, all at once: detail for the remaining survivors.
- Do not cap in-flight requests within one run below the number of requests in the stage. A cap of 6 on 17 requests raised p50 from ~1 s to 1.9 s.
- Put one shared in-flight cap on the process or instance, so simultaneous runs cannot burst together. Derive it from the per-second budget:
  `instance_cap = floor(0.25 × 250,000 / tokens_per_request)`, which is ~20 at 3k tokens per request. Requests finish in well under a second, so this bounds tokens started per second to 25% of the account limit, retries included, because retries take slots too.
  - Make sure one run's largest stage fits under the cap. If it doesn't, cut tokens per run (rule 3); do not lower the cap.
- Stream results after each detail request lands.

## 5. Retry by failure type

| Response | Action |
|---|---|
| 503 via Gateway, single, fast | retry after `50 + random() * 100` ms |
| 429, 529, or every third 503 in a run | backoff `step = min(4000, 500 * 2**attempt)`, wait `step/2 + random()*step/2`, `Retry-After` as a floor; halve in-flight (minimum 4) |
| 401, 402, 422 | stop; never retry |
| timeout | retry within the run deadline |

Limits that worked:

| Setting | Value |
|---|---|
| Attempts per request | 4 |
| Per-attempt timeout | 3 s |
| Instance in-flight cap | 20 (rule 4 formula at 3k tokens) |
| Run deadline | 10 s |
| Retries per run | 16 |

- Size the retry budget as about 4 × requests per run × measured failure rate, with a minimum of 4 (22 × 0.17 × 4 ≈ 16). Example: 22 requests at ~17% failure used 3–8 retries per run; a budget of 8 ran out in 2 of 12 runs, and 16 did not.
- Never retry many parallel requests on a fixed short delay. Fixed 100–400 ms retries produced 37–47 retries per search.
- Python callers use `jev_limits.backoff_delay` and `jev_limits.RETRY_STATUSES_GATEWAY` (429, 503, 529).

## 6. Validate every answer; missing means unknown

- Reject a response when any required head lacks a probability in [0, 1]. Count it as a failed request, not as "no".
- A failed screen request makes the run partial: some items were never judged. Mark the result unverified and do not cache it.

## 7. Evals: price, serialize, pause, small split

- Before an eval, run `jev-budget-check.py --payload run.json --eval-cases N` and state the total tokens.
- Run cases one at a time with a pause of at least `tokens_per_run / 62,500` seconds (25% of the per-second limit); 1.1 s covers a 50k-token run.
- Iterate on a split of ~20 cases (~1M tokens at 50k per run). Run the full set once, before shipping.
- Store every probability, then retune thresholds offline from the stored answers. This costs no calls.
- Never run an eval against a deployment someone is using or demoing: it shares the account limits.

## 8. Cache per query; precompute what does not depend on the query

- Cache verified results per normalized query. Use an in-memory LRU plus a shared cache such as Vercel Runtime Cache, namespaced by a `QUESTIONS_VERSION` that changes whenever wording or the request plan changes. Catalog-backed results can live for days.
- Warm the cache offline for common queries: every item name, every category, and the top needs from logs.
- To replace a per-query screen with a precomputed index:
  1. Write a fixed list of needs (~100–300 short phrases, e.g. "run payroll", "supplier risk").
  2. Offline, ask one Noul per item × need ("does `item` serve `need`?"), packed into 2.5–4k-token requests, and store the probabilities as JSON.
  3. At query time, ask one Noul per need over the query (a few requests). Code joins the needs above threshold to the stored item probabilities.
  4. Keep the live screen as a fallback, and switch only after recall on labeled cases matches it.

## 9. Log one line per run

Fields: tokens, requests, retries, failures by status code, screen ms, first-result ms, per-batch ms, failed batch indexes, the first provider status text (truncated), and whether the result was verified. Never log the query or the payload.

## 10. Transport facts

- Vercel AI Gateway: `experimental_evaluate({ model: "typesafe-ai/jev", state, questions, maxRetries: 0, abortSignal })`, authenticated by the Vercel OIDC token or `AI_GATEWAY_API_KEY`.
  - Gateway type `"boolean"` is Noul.
  - Set `maxRetries: 0` and own retries in code.
- The Gateway uses HTTP 503 `GatewayInternalServerError` for both overload and the size-related transient failure in rule 1.
- The direct API and the Gateway fail independently. A direct-key 401/402 says nothing about a Gateway app.
- A Gateway app has one transport in code. Do not select the transport from whether `TYPESAFE_API_KEY` exists: a leftover key in the Production env silently switches every request to the direct API. Example: jev-sap production returned 402 on every request and showed only unverified results until the key was removed and the direct path deleted. After deploying, check `vercel env ls` and one production response's model (`typesafe-ai/jev` means the Gateway).

## 11. When calls fail, measure in this order

1. **Read the per-run log line:** failures by status, retries, and which stage failed.
2. **Run `jev-budget-check.py` on one run's requests.** Over 25% of a per-second limit: cut tokens per run (rule 3).
3. **Run `jev-size-probe.py` on the production transport.** If failures rise with tokens, pack requests at or under the largest reliable size it reports. Record the curve and date in the project's AGENTS.md.
4. **Stop other spenders on the account** (evals, benchmarks) and retest.
5. **Only if steps 1–4 explain nothing:** send one tiny request. If it also fails, the provider is failing; retry later with backoff.
