# Plan-check contract

Check requirement coverage, file ownership, ordering/dependencies, executable
verification, rollback/safety, and unresolved authority. Cite the exact plan
location for every finding.

Verdicts:

- **PASS**: no blockers;
- **PASS WITH WARNINGS**: risks are explicit and execution can safely proceed;
- **BLOCK**: a missing dependency, authority, safety control, or acceptance
  check makes execution unreliable.

Revision removes a blocker only when the plan text changes or new source
evidence resolves it. Rechecking the same artifact cannot promote its verdict.
