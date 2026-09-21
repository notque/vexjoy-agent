# `/d` classifier contract

This file records behavior that callers/tests depend on; implementation lives in `scripts/jev-route.py` and `jev_transport.py`.

## Transport and fallback

`JEV_TRANSPORT=auto|vercel|direct`; Vercel uses `AI_GATEWAY_API_KEY`, direct uses `TYPESAFE_API_KEY`. Auto prefers direct Jev when configured, then Vercel; explicit selection never switches. Missing transport yields `fallback: true, source: unavailable`. Timeout/transport failure yields `source: error`; a non-manifest selection yields `source: invalid-pick`. Classification failures select through `/do`; required intent validation still blocks execution until aligned.

`pre-route.py` runs first and is authoritative for deterministic git/security force routes. It bypasses classification Jev calls, never the subsequent actual-intent check.

## Classification topology

Stage 1 sends one bounded state containing the verbatim request and compact entries for every manifest candidate. Independent heads provide:

- a wide candidate rank;
- a triviality gate (`gate_score`);
- task signals used by stack policy.

Below the configured gate threshold, return `source: jev-trivial-bypass`; this is a matched result requiring builder `--router-finalize` intent validation before direct handling.

When the gate clears, code forms a bounded shortlist. Stage 2 receives full detail only for that shortlist and runs a route Choice, per-candidate fitness Nouls, and fan-out/multi-select heads. Code validates membership and applies fitness thresholds; Jev never emits an executable name outside supplied candidates.

Complexity is derived in Python rather than asked as a Jev head. Force routes return null complexity for the caller's defaulting rule.

## Receipt compatibility

The field list is maintained in `SKILL.md` and emitted by `jev-route.py`. `latency_ms` contains stage and total timing; `usage` contains per-stage receipts. Consumers tolerate additive fields but never reinterpret missing/invalid answers as negative judgments.

## Fan-out rule

Only candidates returned by the script's multi-select policy and passing their individual fit check enter `agents`. The caller unions these with the research signal's agent and deduplicates. Primary route and fan-outs remain separate dispatches.

## Known risk and coupling

Jev can be confidently wrong, especially when candidate descriptions overlap or omit discriminating facts. Manifest validation prevents invented names, not semantic misrouting. Maintain realistic labeled routing corpora, per-candidate fit gates, trivial cases, and versioned thresholds.

Stage definitions are coupled to manifest descriptions and stack policy. A manifest wording, candidate set, Jev model, threshold, or question change requires the routing corpus and call-boundary checks in `EVAL.md`.

The request and manifest descriptions leave the machine through the configured Jev transport. Local-only inventories must be excluded by their existing filtering path; confidence never overrides that boundary.

## Implementation map

- `scripts/jev-route.py`: orchestration and stable receipt
- `scripts/pre-route.py`: deterministic force routes
- `scripts/routing-manifest.py`: candidate membership/details
- `scripts/jev_transport.py`, `jev_vercel.py`, `jev_gateway/jev_vercel_gateway.mjs`: transport
- `scripts/build-dispatch.py`: validated dispatch construction
- `hooks/jev-route-injector-userprompt.py`: optional classification precompute

## Required actual-intent validation

Classification and alignment are separate boundaries. The classification
receipt authorizes route preparation only. Both routers pass their actual task
spec to the builder under `required-router-protocol.md`. The builder validates
required phase/gate evidence and invokes Jev on the proposed intent and route;
baseline receipts are not accepted. Unavailable, error, review, and essential
clarification block worker dispatch and direct finalization. Manifest validity
alone cannot prove intent alignment, and aligned intent cannot prove completion.
