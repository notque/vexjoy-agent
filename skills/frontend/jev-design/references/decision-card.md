# Decision card

- Unit: one bounded screen brief with up to eight named requirements.
- Baseline: first deterministically compatible component per requirement and first recipe.
- Judgments: one Choice per requirement, one Choice for the complete style recipe, and independent absolute-fitness Nouls for every candidate.
- Policy: accept only in-catalog choices whose selected fitness is at least `0.62`; the threshold is provisional. Otherwise abstain.
- Failure: missing, partial, malformed, non-finite, out-of-range, unavailable, or storage failures abstain with a baseline and next action.
- Bounds: 12,000-character brief, eight requirements, six candidates per requirement, one send, no automatic retry.
- Versions: model `jev-1.13.0`, rubric `jev-design-rubric-v1`, policy `jev-design-policy-v1`, catalog `v1`.
- Falsifier: remain advisory until group-disjoint human labels show at least 80% accepted component plans without accepting any deterministic incompatibility.
- Safety: the planner cannot install components, edit product files, verify accessibility, inspect screenshots, or establish visual quality.
