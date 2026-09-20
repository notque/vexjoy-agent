# Verification failure examples

- File exists but is never imported: **exists**, not **wired**.
- Route is registered but returns a constant fixture: **wired**, no real **data
  flows**.
- Test passed before the final edit: historical evidence, not current evidence.
- Retry passed after an initial failure: flaky/unknown, not passed.
- Build succeeded while required integration tests were unavailable: build pass,
  integration check unrun.
- Worker reports success without retained command output: claim, not evidence.
- Migration exits zero but schema diff contains an unintended column: gate fails.

Reports preserve these distinctions rather than averaging them into an overall
green verdict.
