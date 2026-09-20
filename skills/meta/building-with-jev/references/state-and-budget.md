# Jev state and budget

State is the evidence boundary. Include only fields a head can inspect, with labels, units, source/provenance, and explicit missingness. Compute counts, dates, candidate sets, and deterministic matches before the call. Mark untrusted text as quoted data and never let it redefine questions or policy.

Current design limits: total state plus all questions <= 64,000 tokens; state plus the longest single question <= 32,000. Verify current limits in TypeSafe docs. Question text is the fixed billed floor and output is free.

Fit in this order: remove unused fields; replace raw corpora with code-selected evidence spans plus provenance; bound each list/string; split independent units into separately accounted requests. An over-budget fallback must shrink or abstain, never dump an unbounded alternative. Every retry/cascade stage needs its own bound and send cap.

For repeated items, keep the rubric shared and the unit explicit. Do not compare judgments anchored to different units as though they share a scale. Preserve original source rows through joins; inferred relationships are evidence fields, not authority to merge identities.
