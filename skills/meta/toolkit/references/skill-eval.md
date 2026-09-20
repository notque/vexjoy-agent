# Skill evaluation contract

Freeze representative tasks and expected observable outcomes before changing
the skill. Include activation positives, negatives, and near misses; for body
quality, compare against the same inputs in isolated workspaces.

Use `scripts/skill-creator/run_eval.py`, `eval_compare.py`, and
`aggregate_benchmark.py` as their current CLI describes. Preserve raw outputs,
errors, timing, and grader receipts. Deterministic validity gates run before
subjective grading. Keep selection tasks separate from a held-out confirmation
set; do not promote a variant that improves the training split while regressing
held-out cases.

Treat tool failure, timeout, and invalid output as evaluation failures, not low
quality scores. Report sample counts and paired task results with aggregates.
