# Test-pattern exceptions

This catalog intentionally contains only action-changing exceptions. Prefer
repository conventions and framework documentation for ordinary test style.

- A spy on a boundary adapter can be the behavior under test; spying on private
  sequencing usually couples the test to implementation.
- Broad truthiness is valid for an opaque capability token, not for a value with
  a meaningful exact or structural contract.
- Time control belongs at the clock/scheduler boundary. Sleeping is acceptable
  only when real scheduling behavior is the subject and the result is repeated.
- Shared fixtures are safe when immutable. Mutable shared state requires reset
  evidence or process isolation.
- Snapshot tests need a narrow stable surface and semantic review of the diff;
  bulk snapshot acceptance is not verification.
