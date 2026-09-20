# Pipeline retro contract

Input is a versioned pipeline test report plus the exact generated artifacts and
generator version. Trace each failure to one owner:

- generator rule or architecture constraint;
- template/schema;
- chain composition;
- generated artifact edited after generation;
- test target/fixture;
- infrastructure or timeout.

Fix the highest upstream owner that explains the evidence. Never patch only the
generated output when the generator would reproduce the defect. Regenerate the
same domain/fixture, rerun the same validator, and compare old/new case results.
Reject a change that creates a new regression or changes the fixture.

Report root-cause counts, changed generator surfaces, regeneration receipt,
case-by-case delta, and unresolved items. If all failures are fixture-owned,
change no generator rule.
