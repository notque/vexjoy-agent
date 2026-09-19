---
name: testing
description: "Testing: TDD, E2E, preferred patterns, verification, agent testing."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
  - Agent
agent: testing-automation-engineer
routing:
  not_for: "code review (use review), linting (use code-quality)"
  triggers:
    - "TDD"
    - "test first"
    - "red green refactor"
    - "write tests first"
    - "test-driven"
    - "tests before code"
    - "flaky test"
    - "brittle test"
    - "test smell"
    - "test quality issue"
    - "slow tests"
    - "over-mocking"
    - "test agents"
    - "agent testing"
    - "subagent testing"
    - "run vitest"
    - "JavaScript tests"
    - "TypeScript tests"
    - "playwright"
    - "E2E test"
    - "end-to-end"
    - "browser test"
    - "verify completion"
    - "run tests"
    - "final verification"
  category: testing
  pairs_with:
    - review
    - code-quality
    - workflow
---

# Testing

Six modes. Match the request to one mode and follow its section. Read
repository CLAUDE.md first -- project conventions override defaults here.

## Mode Selection

| Request matches | Go to |
|---|---|
| Write tests first, TDD, red-green-refactor | **TDD** |
| Flaky, brittle, test smell, over-mocking, slow tests | **Pattern Quality** |
| Test an agent, subagent testing, validate agent | **Agent Testing** |
| Run vitest, JavaScript/TypeScript tests | **Vitest Runner** |
| Playwright, E2E, end-to-end, browser test | **E2E (Playwright)** |
| Verify completion, final check, defense in depth | **Verification** |

---

## TDD

RED-GREEN-REFACTOR cycle with strict phase gates. Each feature gets its own
cycle. Do not batch multiple features into one cycle.

### Phase 1: RED -- Write a Failing Test

Write a test describing desired behavior before implementation exists. Use
Arrange-Act-Assert, descriptive names, one concept per test. Run the test and
show full output.

**Gate** -- proceed only when all true:
- Test file created and saved
- Test executed
- Output shows FAILURE (not syntax/import error)
- Failure indicates missing implementation

If test passes before implementation: assertions are too weak, or the feature
already exists. If test fails for wrong reason (syntax, import, setup): fix
those first, then re-run until it fails for the right reason.

### Phase 2: GREEN -- Minimum Implementation

Write ONLY enough code to make the failing test pass. No extra features.
Hardcoded values are acceptable initially. Run the test and the full suite;
show complete output.

**Gate** -- proceed only when all true:
- New test passes
- Full suite executed
- No other tests broken

### Phase 3: REFACTOR

Improve code quality without changing behavior. Establish a green baseline,
refactor incrementally, run tests after every step. Test behavior, not
internals.

**Gate** -- proceed only when all true:
- Full suite passes
- Code quality evaluated

### Phase 4: Commit

Commit test and implementation as an atomic unit. Run the full suite first.

### TDD Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| Test passes in RED phase | Weak assertions or feature exists | Strengthen assertions; check for existing implementation |
| Wrong failure reason | Setup incomplete, missing deps | Fix syntax/imports first, re-run |
| Tests green but feature broken | Tests miss actual usage | Add integration tests; test with real data |
| Refactoring breaks tests | Tests coupled to internals | Test behavior not implementation; refactor in smaller steps |

---

## Pattern Quality

Identify and fix testing mistakes across unit, integration, and E2E suites.
Test behavior, be reliable, run fast, fail for the right reasons.

### Phase 1: SCAN

Locate test files (`*_test.go`, `test_*.py`, `*.test.ts`, `*.spec.js`). Scan
for these 10 failure modes:

| # | Pattern | Detection Signal |
|---|---|---|
| 1 | Testing implementation details | Asserts on private fields, spy on private methods |
| 2 | Over-mocking / brittle selectors | Mock setup > 50% of test code, CSS nth-child |
| 3 | Order-dependent tests | Shared mutable state, numbered test names |
| 4 | Incomplete assertions | `!= nil`, `> 0`, `toBeTruthy()`, no value checks |
| 5 | Over-specification | Exact timestamps, hardcoded IDs, asserting defaults |
| 6 | Ignored failures | `@skip`, `.skip`, `xit`, empty catch, `_ = err` |
| 7 | Poor naming | `testFunc2`, `it('works')`, `it('handles case')` |
| 8 | Missing edge cases | Only happy path, no empty/null/boundary/error tests |
| 9 | Slow test suites | Full DB reset per test, no parallelization |
| 10 | Flaky tests | `sleep()`, `time.Sleep()`, unsynchronized goroutines |

Document each finding with file:line, severity, issue, and impact.

**Gate**: At least one quality issue identified with file:line reference.

### Phase 2: PRIORITIZE

1. **HIGH** -- Flaky, order-dependent, ignored failures (erode trust)
2. **MEDIUM** -- Over-mocking, incomplete assertions, missing edges (false confidence)
3. **LOW** -- Poor naming, over-specification, slow suites (maintenance burden)

Fix one pattern at a time. Preserve test intent. Prevent over-engineering.

**Gate**: Findings ranked. User agrees on fix scope.

### Phase 3: FIX

For each issue (highest priority first): show current code, show fixed code,
apply fix, run tests. Guide toward behavior testing:
- Asserts on private fields -> test the public behavior those fields enable
- Spies on `_getUser()` -> test what happens when a user exists or not
- Checks exact regex -> test that validation succeeds/fails for representative inputs

Run the specific fixed test first, then the full file or package. If a fix
breaks a previously-passing test, investigate before proceeding.

**Gate**: Each fix verified. Tests pass after each change.

### Phase 4: VERIFY

Run full suite. Verify flaky tests are now deterministic (run 3x). Confirm no
no tests were accidentally removed or disabled. Report: bad patterns fixed,
files modified, tests affected, suite status.

**Gate**: Full suite passes. Summary delivered.

### Pattern Error Recovery

| Problem | Fix |
|---|---|
| Cannot determine if pattern is a quality issue | Check comments, consider test layer, flag MEDIUM with trade-offs |
| Fix changes test behavior | Identify original intent, write correct assertion, note as separate finding |
| Suite has hundreds of quality issues | Fix HIGH severity first, recommend TDD going forward, suggest fix-on-touch |

---

## Agent Testing

TDD methodology applied to agent development. Test what the agent DOES, not
what the prompt SAYS. Each test runs in a fresh subagent to avoid context
pollution.

### Minimum Test Counts

| Agent Type | Min Tests | Coverage |
|---|---|---|
| Reviewer | 6 | 2 real issues, 2 clean, 1 edge, 1 ambiguous |
| Implementation | 5 | 2 typical, 1 complex, 1 minimal, 1 error |
| Analysis | 4 | 2 standard, 1 edge, 1 malformed |
| Routing/orchestration | 4 | 2 correct route, 1 ambiguous, 1 invalid |

No agent is simple enough to skip testing.

### Phase 1: RED -- Observe Current Behavior

Read the agent file and referenced skills. Extract testable claims (inputs,
output structure, routing triggers, error conditions). Write a test plan to a
file. Dispatch subagent via Task tool with test inputs. Capture results verbatim.
Identify failure patterns.

**Gate**: All cases executed. Outputs captured. Failures documented.

### Phase 2: GREEN -- Fix Agent Definition

Prioritize failures by severity. Make one fix at a time. Re-run ALL test cases
after each fix. If a fix causes regression, revert and try a different approach.

**Gate**: All cases pass. No regressions.

### Phase 3: REFACTOR -- Edge Cases and Robustness

Add edge case tests (empty, large, unusual, ambiguous inputs). Run consistency
tests (same input 3x; outputs should have same structure and key findings). Run
full regression suite.

**Gate**: Edge cases handled. Consistency verified. Full suite green.

---

## Vitest Runner

Run existing Vitest tests and report results. A check-only request does not
authorize changing tests, assertions, dependencies, or configuration.

Check `package.json`, `vitest.config.*`, and `vite.config.*` to confirm Vitest.
Use the installed project version; avoid implicit npx downloads. If Vitest is
unavailable, report setup needed rather than installing it. Always use `run`;
bare `vitest` enters watch mode.

| Scope | Command |
|---|---|
| Full suite | `npx vitest run --reporter=verbose 2>&1` |
| File or directory | `npx vitest run path/to/test.ts 2>&1` |
| Test-name pattern | `npx vitest run -t "pattern" 2>&1` |
| Coverage | `npx vitest run --coverage 2>&1` |

Capture exit code and full output. Report pass/fail, scope, counts, duration.
For failures: retain file, test name, assertion diff, relevant stack. Nonzero
exit is failure; partial output is not a passing run.

### Vitest Recovery

| Problem | Fix |
|---|---|
| Vitest missing / no node_modules | `npm install` or `npm install -D vitest` |
| No test files found | Check naming (`*.test.ts`, `*.spec.ts`) and include/exclude globs |
| Missing DOM environment | Check for `jsdom`/`happy-dom` in config; suggest devDependency |
| Out of memory | Batch by directory, use `--pool=forks` or `--shard=1/N` |
| Failing assertions | Report mismatch; if fixing authorized, determine whether implementation or test is wrong |

---

## E2E (Playwright)

Playwright-based E2E testing: Scaffold, Build, Run, Validate. Each phase
produces an artifact and must pass its gate.

### Phase 1: SCAFFOLD

1. Verify `@playwright/test` installed: `npx playwright --version`. If missing:
   `npm install -D @playwright/test && npx playwright install`.
2. Create directory structure: `tests/e2e/{auth,features,api}/`, `pages/`,
   `artifacts/{screenshots,traces,videos}/`.
3. Write `playwright.config.ts`. Bake in failure diagnostics: `screenshot: 'only-on-failure'`,
   `trace: 'on-first-retry'`, `video: 'retain-on-failure'`. CI retries:
   `retries: process.env.CI ? 2 : 0`.
4. Verify: `npx tsc --noEmit`.

**Gate**: `playwright.config.ts` exists AND `tests/e2e/` exists.

### Phase 2: BUILD

Write POM classes in `pages/` for each feature area. All locators use
`data-testid` via `page.getByTestId()`. No inline locators in spec files.
Write spec files in `tests/e2e/<area>/`. Verify: `npx tsc --noEmit`.

**Gate**: At least one `.spec.ts` under `tests/e2e/` AND `npx tsc --noEmit`
exits 0.

### Phase 3: RUN

1. Ensure app is running (or document `BASE_URL`).
2. Run: `npx playwright test`.
3. If failures, isolate with `--repeat-each=5` to distinguish flaky from broken.
4. Quarantine confirmed flaky tests with `test.fixme()` and a tracking TODO.
   Never delete a failing test. Use `test.skip()` only for environment guards.

**Gate**: `playwright-results.json` exists and parses as valid JSON.

### Phase 4: VALIDATE

1. Deterministic checks first: parse JSON, extract counts, identify `unexpected`
   and `flaky` entries.
2. LLM triage: classify each failure as (a) broken assertion, (b) selector
   mismatch, (c) timing/async, or (d) application bug.
3. Write `e2e-report.md`.

**Gate**: `e2e-report.md` exists.

### E2E Error Recovery

| Symptom | Fix |
|---|---|
| `npx tsc --noEmit` fails | Check `@playwright/test` in devDeps, verify tsconfig includes test dir |
| Pass locally, fail CI | `npx playwright install --with-deps` in CI; verify `BASE_URL` |
| Results JSON missing | Check JSON reporter in config; check for OOM/process kill |
| Locator timeout on existing element | `await expect(locator).toBeVisible()` before interaction; check overlays |
| `fill()` appends | `locator.clear()` then `locator.fill()` |
| Flaky (4/5 pass) | Quarantine with `test.fixme()`, reproduce with `--repeat-each=10`, check missing `waitFor` |

Confirm flaky vs. broken: `--repeat-each=5 --retries=0`. If fails at least once
in 5, it is flaky. Fix if root cause is clear; quarantine otherwise. Verify fix
with `--repeat-each=10 --retries=0` (must pass 10/10).

---

## Verification

Defense-in-depth verification before declaring any task complete. Match checks
to affected behavior and repository requirements.

### Steps

1. **Inspect changes.** `git status --short` and `git diff`. Read changed code;
   check imports, error handling, compatibility, unintended edits.
2. **Run required checks.** Tests, build, lint, format per repository config.
   Start with relevant tests; run full affected suite when shared behavior
   changed. Do not substitute syntax checks for behavior tests.
3. **Verify artifacts.** Check generated artifacts at expected paths. For
   integrations, verify four levels: **EXISTS** on disk, **SUBSTANTIVE**
   implementation, **WIRED** into callers, real **DATA FLOWS** through it. An
   unused file or hardcoded empty result is not a working feature.
4. **Inspect diff for problems.** Debug code, secrets, placeholders, unfinished
   work. Review in context: an intentional `pass` is not automatically a stub.
5. **Fix and rerun.** Fix failures within authorized scope; rerun affected
   checks. A failed required build or test blocks a success claim.
6. **Report.** Commands, observed status, counts, limitations. Retain full logs;
   show actionable excerpts. Distinguish automated, manual, and unrun checks.

### Default Commands

| Language | Tests | Build/syntax | Lint |
|---|---|---|---|
| Python | `pytest -v` | `python -m py_compile {files}` | `ruff check {files}` |
| Go | `go test ./... -v -race` | `go build ./...` | `golangci-lint run ./...` |
| JavaScript | `npm test` | `npm run build` | `npm run lint` |
| TypeScript | `npm test` | `npx tsc --noEmit` | `npm run lint` |
| Rust | `cargo test` | `cargo build` | `cargo clippy` |

### Evidence Reuse

Reuse a passing result when it covers the current task, checked files,
dependencies, and environment. Keep its command, scope, state, and log path.
After edits, rerun affected checks. Do not claim inherited results as your own.
Required CI checks still apply to the delivered commit.

### Verification Recovery

| Problem | Fix |
|---|---|
| No tests | Manual checks; state coverage gap; add regression test if warranted |
| Missing dependencies | Use repo environment; report missing tool; unrun checks are not passes |
| Build/test failure | Retain failing command and diagnostic; identify cause, fix, rerun |
| Missing wiring or data flow | Name where integration stops; repair it |

### Anti-Rationalization

| Rationalization | Required Action |
|---|---|
| "I loaded the patterns, that's enough" | Loading is not applying. Check against patterns at each gate. |
| "This task is simple, full rigor is overkill" | Apply proportionate rigor, never zero. |
| "The gate basically passes" | Either it passes with evidence or it does not. |

Completion self-check: Did I verify or assume? Did I run tests or just read
code? Did I complete everything or just the "important" parts? Can I show
evidence?

---

## Deep References

Load when the signal applies.

| Signal | Load | Content |
|---|---|---|
| TDD phase steps, language commands | `references/tdd-phase-guidance.md` | RED-GREEN-REFACTOR steps per language |
| TDD walkthroughs | `references/tdd-examples.md` | Go, Python, JavaScript worked examples |
| BAD/GOOD code per failure mode | `references/patterns-preferred-pattern-catalog.md` | Code examples per pattern per language |
| Failure mode classification | `references/patterns-quality-catalog.md` | 10 failure mode descriptions |
| Language-specific fix strategies | `references/patterns-fix-strategies.md` | Fix patterns and tooling per language |
| Test blind spots | `references/patterns-blind-spot-taxonomy.md` | 6-category gap taxonomy |
| Load test scenarios | `references/patterns-load-test-scenarios.md` | Smoke, stress, spike, soak configs |
| Agent dispatch patterns | `references/agents-testing-patterns.md` | Dispatch, negative, A/B, eval harness |
| Agent testing examples | `references/agents-examples-and-errors.md` | Worked examples and error cases |
| E2E async patterns | `references/e2e-async.md` | Promise.all, race conditions, teardown |
| E2E auth testing | `references/e2e-auth.md` | Login, storageState, OAuth, SSO, JWT |
| E2E config templates | `references/e2e-templates.md` | playwright.config.ts, POM, CI/CD |
| E2E POM and waiting | `references/e2e-playwright-patterns.md` | POM examples, multi-browser |
| E2E Web3 wallet | `references/e2e-wallet-testing.md` | MetaMask testing patterns |
| E2E financial flows | `references/e2e-financial-flows.md` | Payment flow testing |
| Stub detection | `references/verify-adversarial-methodology.md` | Four-level checks, goal-backward verification |
| Domain checklists | `references/verify-checklist.md` | Schema change, compatibility checks |
| Verification examples | `references/verify-verification-examples.md` | Bug fix, refactor, migration walkthroughs |

---

## Quick Reference: Red Flags

- `@skip`, `@ignore`, `xit`, `.skip` without expiration date
- `time.sleep()`, `setTimeout()` in test code
- Test names with sequential numbers (`test1`, `test2`)
- Global mutable state accessed by multiple tests
- Mock setup spanning 20+ lines
- Empty catch blocks in tests
- Assertions like `!= nil`, `> 0`, `toBeTruthy()` without value checks

Strict TDD prevents most quality issues: RED catches incomplete assertions,
GREEN minimum prevents over-specification, watching failure confirms you test
behavior not mocks, incremental cycles prevent interdependence, refactor phase
reveals implementation coupling.
