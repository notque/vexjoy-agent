---
name: e2e-testing
description: |
  Playwright-based end-to-end testing workflow: Page Object Model structure,
  flaky test quarantine, CI/CD artifact management, and structured test
  reporting. Use when writing E2E tests against a running application through
  a real browser, validating full user flows, or fixing flaky Playwright tests.
  Do NOT use for unit/component tests (use vitest-runner), Go testing (use
  go-testing), or writing tests before implementation (use test-driven-development).
  Triggered by "playwright", "E2E test", "end-to-end", "browser test",
  "page object model", "POM", "test flakiness".
version: 1.0.0
user-invocable: true
agent: testing-automation-engineer
model: sonnet
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

## Operator Context

This skill operates as an operator for Playwright E2E testing workflows. It implements the **Pipeline** architectural pattern — four phases with explicit gates, deterministic validation before LLM judgment, and a saved artifact at each phase exit.

**Scope:** This skill is exclusively for Playwright-based E2E tests that exercise a running application through a real browser. Do NOT use it for unit/component tests, Go testing, or test-first development.

### Hardcoded Behaviors (Always Apply)
- **POM Required**: Every page or feature area gets a typed Page Object class — no inline locators in spec files
- **data-testid Selectors**: All locators use `data-testid` attributes — no CSS selectors, no XPath, no text matching for interactive elements
- **No Arbitrary Waits**: `waitForTimeout` and `setTimeout` in tests are forbidden — use condition-based waiting only
- **Deterministic Before Subjective**: Run `tsc --noEmit` and check JSON existence before any LLM triage
- **Artifacts Over Memory**: Each phase produces a file; nothing lives only in context
- **Quarantine Before Delete**: Flaky tests get `test.fixme()` and a `--repeat-each=5` reproduction attempt before removal

### Default Behaviors (ON unless disabled)
- **Multi-Browser Matrix**: Test on Chromium, Firefox, and WebKit unless project constrains otherwise
- **Screenshot on Failure**: `screenshot: 'only-on-failure'` in Playwright config
- **Trace on Retry**: `trace: 'on-first-retry'` for post-failure debugging
- **Video Retain on Failure**: `video: 'retain-on-failure'`
- **CI Retries**: `retries: process.env.CI ? 2 : 0`
- **Structured Report**: Phase 4 always produces `e2e-report.md` with pass/fail counts and artifact inventory

---

## Phases

### PHASE 1: SCAFFOLD

**Goal:** Verify Playwright is installed, create the directory structure, and generate `playwright.config.ts`.

**Actions:**
1. Check if `@playwright/test` is installed: `npx playwright --version`. If not, run `npm install -D @playwright/test` and `npx playwright install`.
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
3. Write `playwright.config.ts` using the template below.
4. Confirm `playwright.config.ts` is valid TypeScript: `npx tsc --noEmit`.

**Artifact:** `playwright.config.ts` + `tests/e2e/` directory structure.

**Gate:** `playwright.config.ts` exists AND `tests/e2e/` directory exists. If either is missing, do not proceed to Phase 2 — diagnose and fix.

#### playwright.config.ts Template

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'playwright-results.json' }],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  outputDir: 'artifacts/',
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
});
```

---

### PHASE 2: BUILD

**Goal:** Write POM classes for target feature areas, then write spec files that use those POMs.

**Actions:**
1. Identify the feature areas under test (auth, checkout, dashboard, etc.).
2. For each area, create a POM class in `pages/` (see POM Pattern below).
3. Write spec files in `tests/e2e/<area>/` using the POMs — no inline locators in specs.
4. Run `npx tsc --noEmit` to verify all files compile.
5. Fix any TypeScript errors before proceeding.

**Artifact:** `tests/e2e/**/*.spec.ts` files + `pages/*.ts` POM classes, all compiling cleanly.

**Gate:** At least one `.spec.ts` exists under `tests/e2e/` AND `npx tsc --noEmit` exits 0. If compile fails, fix errors — do not proceed to Phase 3 with broken TypeScript.

#### POM Pattern

```typescript
// pages/LoginPage.ts
import { type Page, type Locator } from '@playwright/test';

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput    = page.getByTestId('login-email');
    this.passwordInput = page.getByTestId('login-password');
    this.submitButton  = page.getByTestId('login-submit');
    this.errorMessage  = page.getByTestId('login-error');
  }

  async goto() {
    await this.page.goto('/login');
    await this.page.waitForLoadState('networkidle');
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}
```

```typescript
// tests/e2e/auth/login.spec.ts
import { test, expect } from '@playwright/test';
import { LoginPage } from '../../../pages/LoginPage';

test.describe('Login Flow', () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.goto();
  });

  test('successful login redirects to dashboard', async ({ page }) => {
    await loginPage.login('user@example.com', 'password123');
    await expect(page).toHaveURL('/dashboard');
  });

  test('invalid credentials shows error message', async () => {
    await loginPage.login('bad@example.com', 'wrong');
    await expect(loginPage.errorMessage).toBeVisible();
    await expect(loginPage.errorMessage).toContainText('Invalid credentials');
  });
});
```

#### data-testid Convention

- **Format**: `<component>-<element>` — e.g., `login-email`, `checkout-submit`, `nav-profile-link`
- **Scope**: Add `data-testid` to interactive elements and status regions the tests need to assert on
- **Stability**: `data-testid` attributes must not change with styling or refactoring — they are a testing contract
- **No CSS selectors**: `page.locator('.btn-primary')` is forbidden — CSS changes break tests silently

---

### PHASE 3: RUN

**Goal:** Execute the test suite, capture the results JSON, and identify any failing or flaky tests.

**Actions:**
1. Ensure the application under test is running (or document the `BASE_URL` required).
2. Run the full suite with JSON reporter configured in `playwright.config.ts`:
   ```bash
   npx playwright test
   ```
3. If any tests fail, run them in isolation with `--repeat-each=5` to distinguish flaky from consistently failing:
   ```bash
   npx playwright test tests/e2e/auth/login.spec.ts --repeat-each=5
   ```
4. Quarantine confirmed flaky tests with `test.fixme()`:
   ```typescript
   test.fixme('flaky: login redirects intermittently', async ({ page }) => {
     // TODO: #123 — investigate race condition with auth cookie
     ...
   });
   ```
5. Do NOT delete failing tests. Do NOT use `test.skip()` to hide broken tests — `test.skip()` is for conditional skips (e.g., environment guards), not for hiding failures.

**Artifact:** `playwright-results.json` (presence is the gate — pass rate is not).

**Gate:** `playwright-results.json` exists at the project root. The file must contain valid JSON. Pass rate does not block Phase 4 — reporting on failures is Phase 4's job.

---

### PHASE 4: VALIDATE

**Goal:** Deterministic checks on test output, then structured report generation.

**Actions:**
1. **Deterministic checks** (run these first, before any LLM summary):
   - `playwright-results.json` exists and parses as valid JSON.
   - Extract counts: `python3 -c "import json,sys; d=json.load(open('playwright-results.json')); print(d.get('stats', d))"`
   - Identify all `unexpected` (failed) and `flaky` result entries.
2. **LLM triage** (only after deterministic checks pass):
   - For each failed test, identify whether it is: (a) a broken assertion, (b) a selector mismatch, (c) a timing/async issue, or (d) an application bug.
   - Categorize flaky tests for quarantine vs. fix.
3. Write `e2e-report.md` using the report template below.

**Artifact:** `e2e-report.md`.

**Gate:** `e2e-report.md` exists. Skill is complete only when this file is written.

#### e2e-report.md Template

```markdown
# E2E Test Report

**Date**: YYYY-MM-DD
**Playwright version**: X.X.X
**Base URL**: http://...
**Browsers tested**: Chromium, Firefox, WebKit

## Summary

| Status | Count |
|--------|-------|
| Passed | N |
| Failed | N |
| Flaky (quarantined) | N |
| Skipped | N |
| **Total** | N |

## Failed Tests

### <test name>
- **File**: `tests/e2e/.../file.spec.ts`
- **Error**: <assertion or timeout message>
- **Category**: broken-assertion | selector-mismatch | timing | app-bug
- **Action**: fix | quarantine | investigate

## Quarantined (test.fixme)

| Test | Issue | Tracking |
|------|-------|----------|
| <name> | <symptom> | <issue link or TODO> |

## Artifacts

| Type | Path |
|------|------|
| HTML Report | `playwright-report/index.html` |
| JSON Results | `playwright-results.json` |
| Screenshots | `artifacts/screenshots/` |
| Traces | `artifacts/traces/` |
| Videos | `artifacts/videos/` |

## Next Actions

- [ ] Fix broken assertions in: ...
- [ ] Investigate app bugs: ...
- [ ] Unquarantine after fix: ...
```

---

## Anti-Patterns

These patterns cause flakiness or test fragility. Stop and correct immediately if encountered.

| Anti-Pattern | Why It Fails | Correct Approach |
|-------------|-------------|-----------------|
| `await page.waitForTimeout(2000)` | Arbitrary time — passes slowly, fails on lag | Use `waitForResponse`, `waitForSelector`, or `expect(locator).toBeVisible()` |
| `page.locator('.submit-btn')` | CSS breaks with restyling | `page.getByTestId('form-submit')` |
| `page.locator('text=Submit')` | Breaks with copy changes | `page.getByTestId('form-submit')` |
| `page.click('button')` without waiting | Race with rendering | Auto-wait via `locator.click()` — Playwright waits for actionability |
| `await page.waitForTimeout(0)` to "flush" | Masks async ordering bugs | Use `waitForResponse` or `waitForLoadState` |
| Tests share state via global variables | Breaks parallel execution | Each test owns its own setup in `beforeEach` |
| `test.skip()` on a broken test | Silently hides failures | Fix it, or quarantine with `test.fixme()` + tracking issue |
| Locators depending on element order (`nth(0)`) | Fragile to DOM reorder | Add `data-testid` to the specific element |
| `page.fill()` without clearing first | Appends to existing value | Use `locator.clear()` then `locator.fill()`, or pass empty string first |

---

## Flaky Test Quarantine Protocol

When a test fails intermittently:

1. **Reproduce**: `npx playwright test <file> --repeat-each=5` — if it fails at least once in 5 runs, it is flaky.
2. **Quarantine**: Replace `test(` with `test.fixme(` and add a comment with the symptom and a tracking reference.
3. **Do not delete**: Deleted tests leave coverage gaps. Quarantined tests are visible debt.
4. **Fix criteria**: Before removing `test.fixme`, the test must pass 10/10 with `--repeat-each=10`.

```typescript
// Before
test('checkout completes successfully', async ({ page }) => { ... });

// After quarantine
test.fixme('checkout completes successfully', async ({ page }) => {
  // FLAKY: intermittent race on payment confirmation response
  // TODO: #456 — investigate network timing in checkout flow
  ...
});
```

---

## CI/CD Integration

### GitHub Actions Workflow Template

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps

      - name: Start application
        run: npm run build && npm run start &
        env:
          NODE_ENV: test

      - name: Wait for application
        run: npx wait-on http://localhost:3000 --timeout 60000

      - name: Run E2E tests
        run: npx playwright test
        env:
          BASE_URL: http://localhost:3000
          CI: true

      - name: Upload test artifacts
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-artifacts
          path: |
            playwright-report/
            playwright-results.json
            artifacts/
          retention-days: 30
```

---

## What This Skill CAN Do
- Scaffold Playwright config and directory structure for a project
- Write typed POM classes and spec files for any feature area
- Execute tests and produce structured JSON + markdown reports
- Quarantine flaky tests with discipline (not deletion)
- Integrate E2E runs into GitHub Actions with artifact upload

## What This Skill CANNOT Do
- Test units or components in isolation (use `vitest-runner`)
- Write tests before the implementation exists (use `test-driven-development`)
- Run Go tests (use `go-testing`)
- Fix application bugs discovered by E2E tests (route to the appropriate engineer agent)
- Guarantee zero flakiness — it can only minimize and manage it systematically

---

## References

- [playwright-patterns.md](references/playwright-patterns.md) — POM examples, condition-based waiting, multi-browser config, financial skip guards
- [wallet-testing.md](references/wallet-testing.md) — Web3/MetaMask mock patterns with `addInitScript`
- [financial-flows.md](references/financial-flows.md) — Production skip guards, blockchain confirmation waits
- [flakiness-triage.md](references/flakiness-triage.md) — `--repeat-each`, `--retries`, quarantine decision tree
- [ADR-107](../../adr/ADR-107-e2e-testing.md) — Decision record for this skill
- [Playwright docs](https://playwright.dev/docs/intro) — Official API reference
