# Testing Mode Playbooks: Pattern Quality, Agent Testing, and E2E

Detailed phase playbooks for `testing` skill modes. Load the section matching your selected mode.

## Pattern Quality

Identify and fix testing mistakes across unit, integration, and E2E suites so tests check behavior, stay reliable, run fast, and fail for real causes.

### Phase 1: SCAN

Locate test files (`*_test.go`, `test_*.py`, `*.test.ts`, `*.spec.js`) and scan for these 10 failure modes:

| # | Pattern | Detection Signal |
|---|---|---|
| 1 | Testing implementation details | Asserts on private fields, spy on private methods |
| 2 | Over-mocking / brittle selectors | Mock setup > 50% of test code, CSS nth-child |
| 3 | Order-dependent tests | Shared mutable state, numbered test names |
| 4 | Incomplete assertions | `!= nil`, `> 0`, `toBeTruthy()`, missing value checks |
| 5 | Over-specification | Exact timestamps, hardcoded IDs, asserting defaults |
| 6 | Ignored failures | `@skip`, `.skip`, `xit`, empty catch, `_ = err` |
| 7 | Poor naming | `testFunc2`, `it('works')`, `it('handles case')` |
| 8 | Missing edge cases | Happy path only, missing empty/null/boundary/error tests |
| 9 | Slow test suites | Full DB reset per test, single-threaded runs |
| 10 | Flaky tests | `sleep()`, `time.Sleep()`, unsynchronized goroutines |

Document each finding with `file:line`, severity, issue, and impact. **Gate:** at least one quality issue documented with `file:line`.

### Phase 2: PRIORITIZE

1. **HIGH:** flaky, order-dependent, ignored failures
2. **MEDIUM:** over-mocking, incomplete assertions, missing edge cases
3. **LOW:** poor naming, over-specification, slow suites

Fix one pattern at a time while preserving test intent. **Gate:** findings ranked and fix scope agreed.

### Phase 3: FIX

For each issue (highest priority first), show current vs fixed code, apply the fix, and run tests. Steer assertions to public behavior rather than private fields, private spies, or exact internal regexes. Run the fixed test first, then the package suite. **Gate:** each fix verified green.

### Phase 4: VERIFY

Run the full suite. Confirm flaky fixes deterministically (3x run). Confirm every intended test remains enabled. Report fixed patterns, modified files, affected tests, and suite status. **Gate:** full suite green and summary delivered.

### Pattern Error Recovery

| Problem | Fix |
|---|---|
| Unclear if pattern is a defect | Check comments and test layer; flag MEDIUM with trade-offs |
| Fix alters test behavior | Recover original intent, write matching assertion, track as separate finding |
| Hundreds of quality issues | Fix HIGH severity first; adopt TDD going forward and fix-on-touch |

---

## Agent Testing

Apply TDD to agent definitions: test observed behavior in fresh subagents to prevent context pollution.

### Minimum Test Counts

| Agent Type | Min Tests | Coverage |
|---|---|---|
| Reviewer | 6 | 2 real issues, 2 clean, 1 edge, 1 ambiguous |
| Implementation | 5 | 2 typical, 1 complex, 1 minimal, 1 error |
| Analysis | 4 | 2 standard, 1 edge, 1 malformed |
| Routing/orchestration | 4 | 2 correct route, 1 ambiguous, 1 invalid |

### Phases

1. **RED -- Observe Current Behavior:** Read the agent file and referenced skills, extract testable claims, write a test plan, dispatch fresh subagents via Agent/Task tool, capture verbatim outputs, and classify failure patterns. **Gate:** all cases run and failures documented.
2. **GREEN -- Fix Agent Definition:** Fix highest-severity failures one at a time, re-running all test cases after each fix; revert regressions. **Gate:** all cases pass with zero regressions.
3. **REFACTOR -- Edge Cases and Robustness:** Add empty/large/unusual/ambiguous inputs, run 3x consistency checks for stable structure and findings, and run full regression. **Gate:** edge cases and consistency verified green.

---

## E2E (Playwright)

Four gated phases: Scaffold, Build, Run, Validate.

### Phase 1: SCAFFOLD

1. Verify `@playwright/test` via `npx playwright --version` (install `npm install -D @playwright/test && npx playwright install` if absent).
2. Create `tests/e2e/{auth,features,api}/`, `pages/`, `artifacts/{screenshots,traces,videos}/`.
3. Configure `playwright.config.ts` with `screenshot: 'only-on-failure'`, `trace: 'on-first-retry'`, `video: 'retain-on-failure'`, and `retries: process.env.CI ? 2 : 0`.
4. Verify with `npx tsc --noEmit`. **Gate:** `playwright.config.ts` and `tests/e2e/` exist.

### Phase 2: BUILD

Write POM classes in `pages/` using `data-testid` via `page.getByTestId()` (keep locators inside POMs). Write specs under `tests/e2e/<area>/` and run `npx tsc --noEmit`. **Gate:** at least one `.spec.ts` exists and type-check exits 0.

### Phase 3: RUN

1. Ensure the app is running (or document `BASE_URL`).
2. Run `npx playwright test`.
3. Isolate failures with `--repeat-each=5 --retries=0` to separate flaky from broken.
4. Quarantine confirmed flaky tests with `test.fixme()` plus a tracking TODO; reserve `test.skip()` for environment guards. Verify flaky fixes with `--repeat-each=10 --retries=0` (10/10 pass). **Gate:** `playwright-results.json` parses as valid JSON.

### Phase 4: VALIDATE

1. Parse JSON deterministically for counts, `unexpected`, and `flaky` entries.
2. Triage each failure as broken assertion, selector mismatch, timing/async, or application bug.
3. Write `e2e-report.md`. **Gate:** `e2e-report.md` exists.

### E2E Error Recovery

| Symptom | Fix |
|---|---|
| `npx tsc --noEmit` fails | Confirm `@playwright/test` in devDeps and tsconfig includes test dir |
| Pass locally, fail CI | Run `npx playwright install --with-deps` in CI; verify `BASE_URL` |
| Results JSON missing | Check JSON reporter config and OOM/process kills |
| Locator timeout on existing element | `await expect(locator).toBeVisible()` first; check overlays |
| `fill()` appends | Call `locator.clear()` before `locator.fill()` |
| Flaky (4/5 pass) | Quarantine with `test.fixme()`, reproduce with `--repeat-each=10`, add explicit `waitFor` |
