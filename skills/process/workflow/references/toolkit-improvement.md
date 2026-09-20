# Toolkit improvement contract

Use the deterministic toolkit inventory and frozen evaluation cases. Independent
reviewers may inspect routing, skill contracts, agent contracts, integrations,
cost, and failure evidence in parallel; synthesis deduplicates by affected
decision and source evidence.

Rank proposals by observed failure frequency × consequence × confidence, with
implementation and regression cost shown separately. A skeptical reviewer must
attempt to falsify the top proposals against clean controls and existing
contracts. Promote only proposals with a measurable downstream action.

Consequential changes get an ADR using `adr-template.md`; its task list owns
files, order, validation commands, rollback, and compatibility work. Implement
one coherent change set, rerun frozen evals and routing/index validators, then
compare baseline vs candidate. Regressions route to remediation or rollback,
never rubric weakening.

Persist run metadata, inventory/version hashes, raw evaluator receipts, accepted
and rejected proposals, ADRs, commands, and final deltas under the run artifact
directory. `toolkit-improvement/references/agent-roster.md` is the canonical
local roster; do not copy it into prose.
