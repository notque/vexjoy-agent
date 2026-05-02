---
name: e2e-testing
description: "Playwright-based end-to-end testing workflow."
user-invocable: false
agent: testing-automation-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
adr: adr/ADR-107-e2e-testing.md
routing:
  category: testing
  triggers:
    - playwright
    - E2E test
    - end-to-end
    - browser test
    - page object model
    - POM
    - test flakiness
  pairs_with:
    - testing-automation-engineer
    - typescript-frontend-engineer
    - test-driven-development
---

# E2E Testing Skill (Playwright)

Four phases: Scaffold, Build, Run, Validate. Each phase produces a saved artifact and must pass its gate before proceeding.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| async, Promise.all, race condition, waitForTimeout, fixture teardown | `async.md` | Routes to the matching deep reference |
| auth, login, storageState, OAuth, SSO, JWT, RBAC, multi-role, session expiry | `auth.md` | Routes to the matching deep reference |
| config, playwright.config.ts, POM, data-testid, CI/CD workflow | `templates.md` | Routes to the matching deep reference |
| error, timeout, tsc fail, locator, fill, missing JSON | `errors.md` | Routes to the matching deep reference |
| POM examples, waiting, multi-browser, shared auth session | `playwright-patterns.md` | Routes to the matching deep reference |
| Web3, MetaMask, wallet, addInitScript | `wallet-testing.md` | Routes to the matching deep reference |
| payment, financial, production skip, blockchain | `financial-flows.md` | Routes to the matching deep reference |
| flaky, intermittent, repeat-each, retries, quarantine | `flakiness-triage.md` | Routes to the matching deep reference |

## Instructions

### PHASE 1: SCAFFOLD

**Goal:** Verify Playwright is installed, create directory structure, generate `playwright.config.ts`.

**Actions:**
1. Check `@playwright/test`: `npx playwright --version`. If missing, run `npm install -D @playwright/test` and `npx playwright install`.
2. Create directory structure:
   ```
   tests/
     e2e/
       auth/
       features/
       api/
   pages/          <- POM classes live here
   artifacts/
     screenshots/
     traces/
     videos/
   ```
3. Write `playwright.config.ts` using template in `references/templates.md`. Defaults: `screenshot: 'only-on-failure'`, `trace: 'on-first-retry'`, `video: 'retain-on-failure'`. CI retries: `retries: process.env.CI ? 2 : 0`.
4. Validate TypeScript: `npx tsc --noEmit`. Run this deterministic check before any subjective assessment.

**Artifact:** `playwright.config.ts` + `tests/e2e/` directory structure.

**Gate:** `playwright.config.ts` exists AND `tests/e2e/` exists. If either missing, diagnose and fix.

See `references/templates.md` for full config template and multi-browser matrix.

---

### PHASE 2: BUILD

**Goal:** Write POM classes for target features, then spec files using those POMs.

Every page/feature area gets a typed Page Object class. Spec files never contain inline locators -- all selectors live in the POM. One selector change = one POM edit, not a grep-and-replace.

**Actions:**
1. Identify feature areas under test (auth, checkout, dashboard, etc.).
2. Create POM class per area in `pages/` (see `references/templates.md`). All locators must use `data-testid` via `page.getByTestId()`. CSS selectors break on style changes, XPath on DOM restructuring, text matching on copy changes. `data-testid` survives all three.
3. Write spec files in `tests/e2e/<area>/` using the POMs.
4. Run `npx tsc --noEmit` to verify compilation.
5. Fix TypeScript errors before proceeding.

**Artifact:** `tests/e2e/**/*.spec.ts` + `pages/*.ts` POM classes, compiling cleanly.

**Gate:** At least one `.spec.ts` exists under `tests/e2e/` AND `npx tsc --noEmit` exits 0.

See `references/templates.md` for POM Pattern, data-testid convention, and timing rules.

---

### PHASE 3: RUN

**Goal:** Execute the test suite, capture results JSON, identify failures/flakiness.

**Actions:**
1. Ensure application under test is running (or document required `BASE_URL`).
2. Run full suite: `npx playwright test`
3. For failures, run in isolation with `--repeat-each=5` to distinguish flaky from consistent:
   ```bash
   npx playwright test tests/e2e/auth/login.spec.ts --repeat-each=5
   ```
4. Quarantine confirmed flaky tests with `test.fixme()`. Never delete failing tests -- quarantined tests are visible debt:
   ```typescript
   test.fixme('flaky: login redirects intermittently', async ({ page }) => {
     // TODO: #123 -- investigate race condition with auth cookie
     ...
   });
   ```
5. Use `test.skip()` only for conditional environment guards (e.g., "skip on WebKit"), not for hiding failures.

**Artifact:** `playwright-results.json` (presence is the gate -- pass rate is not).

**Gate:** `playwright-results.json` exists with valid JSON. Pass rate does not block Phase 4.

See `references/templates.md` for Flaky Test Quarantine Protocol.

---

### PHASE 4: VALIDATE

**Goal:** Deterministic checks on test output, then structured report.

**Actions:**
1. **Deterministic checks first** -- facts before opinions:
   - `playwright-results.json` exists and parses as valid JSON.
   - Extract counts: `python3 -c "import json,sys; d=json.load(open('playwright-results.json')); print(d.get('stats', d))"`
   - Identify all `unexpected` (failed) and `flaky` entries.
2. **LLM triage** (only after deterministic checks pass):
   - Per failed test, classify: (a) broken assertion, (b) selector mismatch, (c) timing/async issue, (d) application bug.
   - Categorize flaky tests for quarantine vs. fix.
3. Write `e2e-report.md` using template in `references/templates.md`.

**Artifact:** `e2e-report.md`.

**Gate:** `e2e-report.md` exists.

See `references/templates.md` for report template and GitHub Actions CI/CD workflow.

---

## Error Handling

See `references/errors.md` for symptom/cause/fix matrix covering tsc failures, CI-only flakes, missing results JSON, locator timeouts, fill-vs-clear bugs, and DOM ordering issues.

---

## References

| Signal / Task Type | Load This Reference |
|--------------------|---------------------|
| async, Promise.all, race condition, waitForTimeout, fixture teardown | [async.md](references/async.md) |
| auth, login, storageState, OAuth, SSO, JWT, RBAC, multi-role, session expiry | [auth.md](references/auth.md) |
| config, playwright.config.ts, POM, data-testid, CI/CD workflow | [templates.md](references/templates.md) |
| error, timeout, tsc fail, locator, fill, missing JSON | [errors.md](references/errors.md) |
| POM examples, waiting, multi-browser, shared auth session | [playwright-patterns.md](references/playwright-patterns.md) |
| Web3, MetaMask, wallet, addInitScript | [wallet-testing.md](references/wallet-testing.md) |
| payment, financial, production skip, blockchain | [financial-flows.md](references/financial-flows.md) |
| flaky, intermittent, repeat-each, retries, quarantine | [flakiness-triage.md](references/flakiness-triage.md) |

- [ADR-107](../../adr/ADR-107-e2e-testing.md) -- Decision record for this skill
- [Playwright docs](https://playwright.dev/docs/intro) -- Official API reference
