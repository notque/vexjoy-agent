# Decision card

- Unit: one bounded screen brief with up to eight named requirements.
- Baseline: the tightest-fit compatible component per requirement (fewest extra capabilities, then non-legacy, then catalog order) and the recipe with the most requested traits.
- Judgments: one Choice per requirement, one Choice for the complete style recipe, and an independent absolute-fitness Noul for every candidate.
- Policy: accept only in-catalog choices whose fitness is at least `0.62` (provisional). Otherwise abstain and return the baseline and candidates.
- Failure: missing, partial, malformed, non-finite, or out-of-range answers abstain. So do an unavailable transport, any failed request, and storage failures. Partial answers from a split run are never used.
- Bounds: 1,500-character brief (down from 12,000, because the brief rides in every request), eight requirements, eight capabilities per requirement, six candidates per requirement, ten style candidates, and six style traits.
- Requests: each requirement's candidates are packed into requests of 3,500 estimated tokens or fewer, plus one style request. Nothing over 4,500 tokens is sent. A test covers the worst case: 8 requirements on the three most expensive capabilities, maximum field lengths, 4 requests, about 10.5k tokens per run, 3,266 tokens in the largest request.
- Retries: the transport retries 429, 503, and 529 with jittered backoff, 4 attempts at most. The planner makes one round of requests. The budget check warns only when it assumes every request retries 4 times within one latency window.
- Versions: served model `typesafe-ai/jev` through Vercel AI Gateway (unversioned; the served model is recorded per attempt). The v1 pin `jev-1.13.0` applied to the direct API only. Rubric `jev-design-rubric-v2`, policy `jev-design-policy-v2`, catalog `shadcn-style-catalog-v2`. The catalog has 65 components (all 63 `registry:ui` items from `https://ui.shadcn.com/r/index.json` plus the `data-table` and `date-picker` composites), 59 capabilities, and 10 recipes, fetched 2026-09-22.
- Threshold note: `0.62` was set on v1 wording. The v2 questions reference state paths and drop Noul criteria, so recalibrate on labeled briefs before promotion.
- Falsifier: stay advisory until group-disjoint human labels show at least 80% accepted component plans, with no deterministic incompatibility accepted.
- Safety: the planner cannot install components, edit product files, verify accessibility, inspect screenshots, or establish visual quality. Recipe contrast is computed from its OKLCH values, not measured on a render.
