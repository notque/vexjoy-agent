# Repository guidance generation

Generate guidance from observed repository evidence: build manifests, task
scripts, tested commands, directory boundaries, and existing local policy.
Never guess commands or overwrite an existing `CLAUDE.md`; write a comparison
candidate unless replacement was explicitly requested.

Keep only repository-specific commands, architecture boundaries, conventions,
and hazards that alter agent behavior. Validate every mentioned path and run
safe documented checks. Scan the candidate for credentials and machine-local
paths before delivery. Monorepo subdirectory guidance must narrow or extend the
root contract without contradicting it.
