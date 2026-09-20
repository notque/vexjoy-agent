# TDD diagnostic examples

Keep the failure receipt, not a language tutorial.

- Expected RED: assertion reaches the target boundary and fails because the new
  behavior is absent.
- Invalid RED: import, syntax, fixture, dependency, or environment failure.
- Unexpected green: behavior already exists or the assertion does not observe
  it; investigate before implementation.
- Valid GREEN: focused test passes and the affected suite remains green after
  the smallest behavior change.
- Invalid GREEN: assertion weakened, case skipped, mock made tautological, or
  retry concealed nondeterminism.

Refactoring begins from a recorded green command and ends by rerunning that same
command plus the affected broader gate.
