---
name: testing
description: "Testing: TDD, E2E, test automation strategy (Vitest, coverage, CI), preferred patterns, test-value audits, verification, agent testing."
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
agent: general-purpose
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
    - "test audit"
    - "audit tests"
    - "low-value tests"
    - "prune tests"
    - "test bloat"
    - "delete useless tests"
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
    # from testing-automation
    - "testing"
    - "E2E"
    - "vitest"
    - "test automation"
    - "visual regression"
  category: testing
  pairs_with:
    - review
    - code-quality
    - workflow
---

# Testing

Eight modes. Match the request to one mode and follow its section. Read
repository CLAUDE.md first -- project conventions override defaults here.

## Mode Selection

| Request matches | Go to |
|---|---|
| Write tests first, TDD, red-green-refactor | **TDD** |
| Flaky, brittle, test smell, over-mocking, slow tests | **Pattern Quality** |
| Audit or prune low-value, duplicate, or implementation-coupled tests | **Test Audit** |
| Test an agent, subagent testing, validate agent | **Agent Testing** |
| Run vitest, JavaScript/TypeScript tests | **Vitest Runner** |
| Playwright, E2E, end-to-end, browser test | **E2E (Playwright)** |
| Verify completion, final check, defense in depth | **Verification** |
| Test automation strategy: Vitest setup, coverage gates, CI integration, visual regression, mocks and factories | **Test Automation**: load `references/testing-automation.md` and follow its anchors, workflow, and output contract |

---

## TDD

RED-GREEN-REFACTOR cycle with strict phase gates. Each feature gets its own
cycle. Do not batch multiple features into one cycle.

### Phase 1: RED -- Write a Failing Test

Write a test describing desired behavior before implementation exists. Use
Arrange-Act-Assert, descriptive names, one concept per test. Run the test and
show full output.

Every new or changed test, in any mode, must first pass the authoring gate in
`references/audit-test-value.md`.

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

Run the full suite first. Commit only when the user asked for commits: then commit test and
implementation together as one unit, with a one-sentence lowercase message in the AGENTS.md
writing style (what changed and why). Otherwise leave the change uncommitted and report it.

### TDD Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| Test passes in RED phase | Weak assertions or feature exists | Strengthen assertions; check for existing implementation |
| Wrong failure reason | Setup incomplete, missing deps | Fix syntax/imports first, re-run |
| Tests green but feature broken | Tests miss actual usage | Add integration tests; test with real data |
| Refactoring breaks tests | Tests coupled to internals | Test behavior not implementation; refactor in smaller steps |

---

## Pattern Quality, Agent Testing, and E2E (Playwright)

Load `references/mode-playbooks.md` for full phase playbooks and error recovery:
- **Pattern Quality:** SCAN (10 failure modes) -> PRIORITIZE (HIGH/MEDIUM/LOW) -> FIX (behavior assertions) -> VERIFY (3x flaky confirmation).
- **Agent Testing:** TDD in fresh subagents (min counts: Reviewer 6, Implementation 5, Analysis 4, Routing 4) across RED -> GREEN -> REFACTOR.
- **E2E (Playwright):** SCAFFOLD (`playwright.config.ts`) -> BUILD (POM + `data-testid`) -> RUN (`--repeat-each=5` flaky isolation, `test.fixme()` quarantine) -> VALIDATE (`e2e-report.md`).

---

## Test Audit

Find and remove tests that do not earn their maintenance cost, and the
test-only production seams they keep alive. Load
`references/audit-test-value.md` and follow it; it holds the authoring gate,
junk patterns, retention bar, evidence fields, validation, and handoff.

Use Pattern Quality to fix a test that guards real behavior badly. Use Test
Audit to decide whether a test should exist at all.

| Scope | Sub-mode |
|---|---|
| Writing or changing a test | Authoring gate |
| Focused sweep of a few candidates | Audit |
| Every test one subsystem owns | Campaign |

**Gate**: Every deletion has all candidate evidence fields recorded. Owner and
full suites pass. Production and test LOC reported separately.

To find hook or validator tests that miss real bugs, run
`python3 scripts/mutation-check.py --hook hooks/<name>.py` (`--all`, `--json`).
For local-only cosmic-ray mutation testing of `scripts/jev_limits.py` and
`scripts/jev_router_common.py` (commands and 2026-10-30 baselines), load
`references/mutation-testing.md`.

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
| Full suite | `npx --no vitest run --reporter=verbose 2>&1` |
| File or directory | `npx --no vitest run path/to/test.ts 2>&1` |
| Test-name pattern | `npx --no vitest run -t "pattern" 2>&1` |
| Coverage | `npx --no vitest run --coverage 2>&1` |

`--no` makes npx fail instead of downloading Vitest when the project has none.

Capture exit code and full output. Report pass/fail, scope, counts, duration.
For failures: retain file, test name, assertion diff, relevant stack. Nonzero
exit is failure; partial output is not a passing run.

### Vitest Recovery

| Problem | Fix |
|---|---|
| Vitest missing / no node_modules | Report setup needed. `npm install` (declared deps) or `npm install -D vitest` (edits `package.json`) only when the user asks |
| No test files found | Check naming (`*.test.ts`, `*.spec.ts`) and include/exclude globs |
| Missing DOM environment | Check for `jsdom`/`happy-dom` in config; suggest devDependency |
| Out of memory | Batch by directory, use `--pool=forks` or `--shard=1/N` |
| Failing assertions | Report mismatch; if fixing authorized, determine whether implementation or test is wrong |

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
| New-test gate, test audits, pruning campaigns | `references/audit-test-value.md` | Authoring gate, junk patterns, retention bar, evidence, validation |
| Agent dispatch patterns | `references/agents-testing-patterns.md` | Dispatch, negative, A/B |
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
| Test automation strategy, Vitest, coverage gates, CI, numeric anchors | `references/testing-automation.md` | Hard rules, workflow, output contract; routes to `testing-automation/` (Vitest, async, mocking, JS patterns, output contract) |
| Pattern Quality, Agent Testing, E2E (Playwright) phase playbooks | `references/mode-playbooks.md` | Full scan/prioritize/fix/verify, agent TDD, and Playwright E2E phases |
| Cosmic-ray mutation testing for `jev_limits.py` and `jev_router_common.py` | `references/mutation-testing.md` | Disposable venv commands, operator filters, and baseline scores |

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
