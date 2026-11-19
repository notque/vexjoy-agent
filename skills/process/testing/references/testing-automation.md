# Testing Automation Reference

> **Scope**: Full JavaScript/TypeScript test automation strategy: Vitest setup and config, mocks, factories, custom matchers, coverage gates, parallel execution, CI integration, Playwright visual regression, load and stress tests, Vitest benchmarks, debugging tests.
> **Not here**: Playwright-only E2E authoring (the E2E mode in this skill's `SKILL.md`). Mock external APIs; their real behavior is out of scope. Route application logic fixes to the matching language skill (`programming` or `frontend`).

## Numeric anchors

Replace vague targets with measurable ones. These are non-negotiable:

| Vague | Concrete |
|---|---|
| "Write focused tests" | Each test function tests exactly one behavior |
| "Keep tests concise" | At most 10 lines per test function (excluding setup/teardown fixtures) |
| "Test thoroughly" | At least 3 cases per public function: happy path, edge case, error case |
| "Add good messages" | Each assertion message states the expected behavior in plain English |
| "Good coverage" | 80% line AND 80% branch coverage (both required) |
| "Fast tests" | Unit suite under 30 seconds; each test under 100 ms |
| "Small test files" | At most 200 lines per test file; split beyond that |

## Hard rules

- **80% coverage minimum** on branches, functions, lines, and statements. Non-negotiable.
- **Test isolation**: every test is independent: no shared state, no order dependence, no side effects.
- **CI from the start**: every test config includes GitHub Actions or an equivalent.
- **Vitest first**: Vitest for unit and integration tests; Jest only for legacy compatibility.
- **Playwright for E2E**: no Selenium or Puppeteer.

## Defaults (on unless disabled)

- Report results factually: show test output and coverage reports, don't describe them.
- Generate `setup.ts` with global utilities, mocks, and Testing Library config.
- Configure HTML, text, and JSON coverage reports with thresholds enforced in CI.
- Run tests in a threaded pool with a sensible worker count.
- Query components the way users do (`getByRole`, `getByLabelText`), not by implementation details.
- Playwright screenshot comparison for critical UI components and flows.

## Optional (off unless enabled)

- Strict TDD (failing test before implementation; see the TDD mode in `SKILL.md`).
- Mutation testing (Stryker or similar).
- Vitest bench tests with regression detection.
- Contract testing (Pact or similar).

## Workflow

1. **Scope**: read the repository CLAUDE.md, find the test framework (or pick one), list the modules to test.
2. **Write tests**: assert a specific return value, state change, or side effect that fails for a wrong implementation. `expect(result).toBeDefined()` alone verifies nothing. Apply the numeric anchors.
3. **Stop and verify**: run the runner (pytest, vitest, go test) and keep the real output. Confirm new tests fail with the implementation removed or stubbed (`return null`). If you can't check that, say why under GAPS.
4. **Coverage**: run with branch reporting. Require 80% lines and branches. If branch coverage trails line coverage by more than 10 points, add tests for the missed conditionals.
5. **Stop and verify coverage**: for each covered function, confirm a test asserts its output; execution alone doesn't verify behavior.
6. **Adversarial review**: for every test, would it catch `>` changed to `>=`? Two arguments swapped? An empty array returned instead of null, or the reverse? An off-by-one loop bound? If any answer is no, add a test for that mutation.

## Output contract

Every testing task produces 5 sections: SCOPE, TEST INVENTORY (table), COVERAGE (before/after, line AND branch), GAPS, VERDICT (SUFFICIENT, INSUFFICIENT, or NEEDS_REVIEW). Full template, verdict criteria, and hard gate table: [testing-automation/output-contract.md](testing-automation/output-contract.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| Flaky tests | Timing, async, or race conditions | Find the root cause instead of adding waits: `waitFor` with a condition, fix the race, stabilize test data. See [testing-automation/preferred-patterns.md](testing-automation/preferred-patterns.md) section 5 |
| Low coverage | Untested paths | Run the coverage report, find untested files and branches, add edge and error cases; 80% lines and branches minimum |
| Shared state between tests | Order dependence or shared mutable state | `beforeEach` setup, own data per test, confirm each test passes alone |

## Preferred patterns

Avoid four patterns: testing implementation details (test the public API), shared test state (each test independent), over-mocking (mock only external boundaries), and assertion-free tests (`toBeDefined()` alone is never enough; assert specific values). JS/TS catalog with examples: [testing-automation/preferred-patterns.md](testing-automation/preferred-patterns.md). Language-neutral catalog: [patterns-preferred-pattern-catalog.md](patterns-preferred-pattern-catalog.md).

Testing rationalizations to reject (coverage is just a number, retry the flaky test, line coverage only, calling without asserting): [anti-rationalization-testing.md](../../../shared-patterns/anti-rationalization-testing.md).

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure.

| Situation | Why stop | Ask |
|---|---|---|
| Test requirements unclear | Need to know what to test | "What behavior should these tests verify?" |
| Several approaches | Preference | "Unit tests first or E2E first?" |
| Coverage target differs | Project standards vary | "What's the coverage target for this project?" |
| External service | Mock vs real | "Mock this API or use a test instance?" |

Verify before assuming: what counts as the critical path (business decision), the coverage threshold (project standard), whether to test implementation details (always no, but confirm), mock vs real external services (depends on the test environment).

## Reference loading table

Load only what the current task needs.

| Signal | Load | Why |
|---|---|---|
| vitest, `vi.fn`, `vi.mock`, coverage config, spy, jest to vitest, fake timers | [testing-automation/vitest-patterns.md](testing-automation/vitest-patterns.md) | Vitest 1.x/2.x config, spy lifecycle, coverage thresholds |
| async, `waitFor`, `findBy`, MSW, flaky test, setTimeout in test, userEvent | [testing-automation/async-testing.md](testing-automation/async-testing.md) | RTL and MSW async patterns, Playwright auto-wait |
| mock, over-mocking, what to mock, MSW vs mock, `spyOn`, mock boundary | [testing-automation/mocking-patterns.md](testing-automation/mocking-patterns.md) | Mock boundary decisions, over-mocking detection |
| testing implementation details, shared state, assertion-free tests, JS test smells | [testing-automation/preferred-patterns.md](testing-automation/preferred-patterns.md) | JS/TS pattern catalog |
| output format, output contract, hard gate patterns, verdict criteria | [testing-automation/output-contract.md](testing-automation/output-contract.md) | 5-section output, verdict criteria |

Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).
