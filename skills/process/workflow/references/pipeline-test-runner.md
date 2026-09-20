# Pipeline test-runner contract

Load the pipeline spec, generated skill, validators, and case fixtures by exact
path and version. Missing inputs are BLOCKED, not failed behavior. Run independent
subdomain cases in parallel with isolated outputs and bounded timeouts.

For each case retain input, expected contract, actual artifact, command/tool
receipt, validation findings, duration, and PASS/PARTIAL/FAIL/BLOCKED. Validate
schema and required artifacts deterministically before qualitative judgment.
Never replace a missing validator with model confidence.

Overall PASS requires every required case to pass. PARTIAL means the artifact is
usable only within explicitly named gaps; BLOCKED remains distinct from FAIL.
The report lists failure traces and the upstream owner suitable for
`pipeline-retro.md`. Preserve outputs so regeneration can compare the exact same
fixture.
