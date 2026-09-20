# Toolkit evolution contract

Evolution starts from evidence: routing failures, repeated corrections,
evaluation regressions, dormant components, unresolved governance events, and
measured user friction. Link each proposal to its receipts and define the
expected behavior change, acceptance check, risk, and rollback.

Build only approved proposals. Compare each candidate against the incumbent on
frozen cases and confirm winners on held-out cases. Inconclusive candidates do
not ship. Record rejected or shelved proposals and their reactivation conditions
in `toolkit-evolution/evolution-history.md` so the same unsupported idea is not
re-proposed.

Repository mutation, PR creation, merge, and scheduling remain separate
authorized actions; an evolution diagnosis does not authorize them.
