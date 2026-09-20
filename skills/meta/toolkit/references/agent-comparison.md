# Agent comparison contract

Compare agents on identical frozen tasks, repository state, permissions, and
acceptance checks. Run variants in isolated outputs and blind their identity
during qualitative grading. Deterministic tests and artifact validity outrank
style preferences.

The programs in `scripts/agent-comparison/` define task schemas, snapshots, and
optimization records. Read their help/source before a run. Preserve every raw
output and failed attempt. Report paired per-task results, total calls/tokens,
wall time, test failures, grader evidence, and uncertainty from small samples.

Optimization may alter only the declared target. Select on training cases and
confirm once on held-out cases; an inconclusive result keeps the incumbent.
