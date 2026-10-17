# Models, limits, and errors

Read the [models page](https://docs.typesafe.ai/models.md) and [API page](https://docs.typesafe.ai/api.md) when a number here matters. Snapshot: docs read 2026-10-16.

## Models and aliases

| Name | Points to | Use |
|---|---|---|
| `jev-1.13.0` | itself | Previous version. Jaggedness page applies. |
| `jev-1.14.0` | itself | Released 2026-10-14. Small gains everywhere, largest for non-English text. Required for Box. **Our pinned model** (owner, 2026-10-16): `JEV_MODEL` in `scripts/jev_router_common.py` for direct calls, `typesafe-ai/jev-1.14.0` in the Gateway bridge (override with `JEV_GATEWAY_MODEL`). |
| `jev-latest` | `jev-1.13.0` now; TypeSafe says it moves to `jev-1.14.0` about a week after release | SDK default. We do not send it; pin instead. |
| `jev-preview` | `jev-1.14.0` | Newest build, official or not. Moves first. |

- An alias moves without any change in your code, so answers can shift. Each response's `model` field names the versioned ID that answered: store it with every answer.
- Pin a versioned ID when a threshold, calibration set, or cached answer depends on measured behavior. Move to the new version on purpose: rerun the labeled set, then retune.
- Notice before retirement (blog, 2026-10-14): 60 days for 1.13, 30 days for 1.14. A deprecation policy page was promised and is not in the docs index yet.
- Price: $42 per billion input tokens ($0.042 per million). Output is free.
- `GET /v1/models` lists the aliases. Versioned IDs work whether or not they are listed.
- Language: English is best. Other languages, including CJK, work with lower accuracy. Test on your content and read `confidence` closely when routing.
- Jev is not fine-tuned per account and is not trained on requests. Shape answers through `state`, `instructions`, and `criteria`.

## Limits

| Limit | Value |
|---|---|
| Tokens per request (state plus every question) | 64,000 |
| Tokens per question (state plus that question) | 32,000 |
| Questions per request | no limit; the two token limits decide |
| Choice options | 255 |
| Score levels | 2 to 10 |
| Body | 32 MiB, UTF-8 JSON, no BOM; 64 nesting levels in each of `state`, `instructions`, `criteria`; finite numbers only (send IDs and exact large numbers as strings) |
| Compression | `Content-Encoding` gzip or zstd, one layer, zstd window 8 MiB or less. SDKs compress bodies of 1 KiB or more with zstd. The 32 MiB limit applies to the compressed and the decompressed body. |
| Rate limits | per organization, in tokens per second and requests per second; read the developer console |

Our constants in `scripts/jev_limits.py` (250,000 input tokens per second, 1,200 requests per minute) are the 2026-09-22 reading. The docs no longer print numbers and quote the limits per second. Treat the constants as planning defaults: `jev-budget-check.py` prices a run against them. Check the console when a run fails with 429.

### Long context (danger zone)

Send `TypeSafe-Danger-Zone-Long-Context: true` on each request that needs it. Both token limits become 262,000. It works on 1.13 and 1.14, costs the same per token, and is slower and less accurate than staying under the default limits. TypeSafe recommends limiting context.

Our position: do not use it. Filter and cascade first (`state-and-budget.md`). Our transports cap requests at 4,500 tokens for Gateway reliability and send only to the direct API or the Gateway with a fixed header set, so a long-context request needs its own code path. If a task truly needs one state over 32,000 tokens, send it direct with the header, measure accuracy against the filtered version on labeled cases, and keep the filtered version unless the long one wins.

### Other danger-zone features

`TypeSafe-Danger-Zone-Images: true` enables images and Box (`images.md`). TypeSafe says these are not production-ready and that every model is worse on images than on text: split image questions into the simplest parts. TypeSafe also offers an opt-in to share queries for debugging (they still do not train on them). We do not enable it.

## Errors and retries

| Status | Meaning | Action |
|---|---|---|
| 400 | Body breaks a rule (encoding, nesting, number, bad compression); with `max_tokens_exceeded`, the request is over the context limit | Fix the request. Shrink or split for `max_tokens_exceeded`. |
| 401 | Missing or bad key | Stop. |
| 402 | Billing failure (one direct key returned it; MMR, recorded) | Stop. Do not retry; tell the owner. |
| 413 | Body over 32 MiB | Shrink. |
| 415 | Unsupported or stacked `Content-Encoding` | Fix the header. |
| 422 | Failed validation; the body names the field | Fix the question. Never retry. |
| 429 | Rate limit | Back off, then retry. |
| 529 | Overloaded | Back off, then retry. |

Billed input tokens run about 1.25x `len(json) / 4` plus about 275 fixed per request, and more on repetitive structured text; read `usage.input_tokens` and plan with 30% headroom (`field-learnings.md`, Transport and ops).

Through Vercel AI Gateway, rate limits and overload arrive as 503 (`production lessons`, rule 5).

The Python SDK retries 408, 429, and 5xx, connection errors, and timeouts. Defaults: 2 retries, backoff 0.5 s doubling to 5 s, 25% jitter, 30 s timeout. It honors `Retry-After` and `retry-after-ms`. Errors carry `x-typesafe-request-id`: log it with the failure so TypeSafe can trace the request. `scripts/jev_router_common.py` retries 429 and 529 only, with equal jitter, and honors both headers. It does not retry 408 or other 5xx; add them only after you see them in `calls_failed`.

## Latency: direct API, Gateway, cache

Measured 2026-10-16, 4 calls each: a short text Noul took 0.05 to 0.08 s on the direct API and 0.36 to 0.41 s through the Gateway, so the Gateway adds about 0.3 s per call. Image Noul calls on the direct API took 0.09 to 0.18 s (3.3k input tokens). A direct-API run of image requests that averages 0.09 s per call against 0.45 s for Gateway text calls is a transport difference, not a cache.

`call_jev` (the direct path) has an on-disk cache keyed by a hash of the redacted payload (`JEV_CACHE_TTL_S`; 0 disables). A text request with the same payload returned in 0.004 s with `_meta.cached: true` and no `usage`. Image requests never hit it: `bind_images` gives every image a fresh uuid reference, so the payload differs each time. The same image sent 4 times billed 3,350, 3,352, 3,350, and 3,349 input tokens, returned slightly different answers (0.28, 0.30, 0.28), and carried no `cached` flag. To tell a cache hit from a fast real call, check `_meta.cached` and `usage`.

## Official SDKs and agent skill

- Python `typesafe-sdk` (0.7.5 on 2026-10-14): `response_model` for typed answers, `extra_body` for new API fields, `raw_http_response` for unknown answer kinds, `RetryPolicy`, zstd, `attach_assets` for images. Reuse one client; make one per thread under heavy load. Bodies are not redacted in debug logs.
- Our stdlib client (`jev_router_common.call_jev`) adds redaction, caching, breaker, and telemetry that the SDK lacks. Use the SDK for a standalone service, our client inside toolkit scripts.
- TypeSafe ships an agent skill: `claude plugin marketplace add typesafe-ai/skills`, then `claude plugin install typesafe@typesafe-ai` (skill `typesafe-ai`). It tells an agent to read the live docs, pick a pattern, and design judgments. This repo's skills add what it lacks: the labeled-run build procedure, per-second budgeting, Gateway sizing, shadow mode, and our scripts. When the two disagree on an API or pattern fact, the docs win; when they disagree on request size or transport, our measured rules win.
