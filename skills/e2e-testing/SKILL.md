---
name: e2e-testing
description: "Playwright-based end-to-end testing workflow."
version: 1.0.0
user-invocable: false
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

Playwright-based E2E testing across four phases: Scaffold, Build, Run, Validate. Each phase produces a saved artifact and must pass its gate before the next phase begins.

## Instructions

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
3. Write `playwright.config.ts` using the template below. The config bakes in failure diagnostics by default: `screenshot: 'only-on-failure'`, `trace: 'on-first-retry'`, and `video: 'retain-on-failure'` so that every failure produces actionable artifacts without manual setup. CI retries (`retries: process.env.CI ? 2 : 0`) absorb transient infrastructure flakiness without masking real bugs.
4. Confirm `playwright.config.ts` is valid TypeScript: `npx tsc --noEmit`. Run this deterministic check before any subjective assessment of the config -- compiler errors are facts, opinions are not.

**Artifact:** `playwright.config.ts` + `tests/e2e/` directory structure.

**Gate:** `playwright.config.ts` exists AND `tests/e2e/` directory exists. If either is missing, do not proceed to Phase 2 -- diagnose and fix.

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

The multi-browser matrix (Chromium, Firefox, WebKit) is the default because cross-browser bugs caught in CI are cheaper than cross-browser bugs caught in production. Remove browsers only when the project explicitly constrains the target set.

---

### PHASE 2: BUILD

**Goal:** Write POM classes for target feature areas, then write spec files that use those POMs.

Every page or feature area gets a typed Page Object class. Spec files never contain inline locators -- all selectors live in the POM. This separation means a selector change is a one-line POM edit, not a grep-and-replace across dozens of specs.

**Actions:**
1. Identify the feature areas under test (auth, checkout, dashboard, etc.).
2. For each area, create a POM class in `pages/` (see POM Pattern below). All locators must use `data-testid` attributes via `page.getByTestId()`. CSS selectors (`page.locator('.btn-primary')`) break silently when styles change. XPath breaks on DOM restructuring. Text matching (`page.locator('text=Submit')`) breaks on copy changes. `data-testid` is a testing contract that survives all three.
3. Write spec files in `tests/e2e/<area>/` using the POMs.
4. Run `npx tsc --noEmit` to verify all files compile.
5. Fix any TypeScript errors before proceeding.

**Artifact:** `tests/e2e/**/*.spec.ts` files + `pages/*.ts` POM classes, all compiling cleanly.

**Gate:** At least one `.spec.ts` exists under `tests/e2e/` AND `npx tsc --noEmit` exits 0. If compile fails, fix errors -- do not proceed to Phase 3 with broken TypeScript.

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

- **Format**: `<component>-<element>` -- e.g., `login-email`, `checkout-submit`, `nav-profile-link`
- **Scope**: Add `data-testid` to interactive elements and status regions the tests need to assert on
- **Stability**: `data-testid` attributes must not change with styling or refactoring -- they are a testing contract

#### Waiting and Timing

Never use `waitForTimeout()` or `setTimeout()` in tests. Arbitrary waits pass slowly on fast machines and fail on slow ones -- they encode a guess about timing instead of observing the actual condition. Use condition-based waiting instead:

| Instead of | Use |
|-----------|-----|
| `await page.waitForTimeout(2000)` | `await expect(locator).toBeVisible()` or `await page.waitForResponse(...)` |
| `await page.waitForTimeout(0)` to "flush" | `await page.waitForLoadState('networkidle')` |
| `page.click('button')` without waiting | `locator.click()` -- Playwright auto-waits for actionability |

Each test must own its own setup in `beforeEach`. Tests sharing state via global variables break parallel execution because Playwright runs specs concurrently by default.

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
4. Quarantine confirmed flaky tests with `test.fixme()`. Never delete a failing test -- deleted tests leave silent coverage gaps. Quarantined tests are visible debt with tracking references:
   ```typescript
   test.fixme('flaky: login redirects intermittently', async ({ page }) => {
     // TODO: #123 -- investigate race condition with auth cookie
     ...
   });
   ```
5. Do NOT use `test.skip()` to hide broken tests. `test.skip()` is for conditional environment guards (e.g., "skip on WebKit"), not for sweeping failures under the rug.

**Artifact:** `playwright-results.json` (presence is the gate -- pass rate is not).

**Gate:** `playwright-results.json` exists at the project root. The file must contain valid JSON. Pass rate does not block Phase 4 -- reporting on failures is Phase 4's job.

#### Flaky Test Quarantine Protocol

When a test fails intermittently:

1. **Reproduce**: `npx playwright test <file> --repeat-each=5` -- if it fails at least once in 5 runs, it is flaky.
2. **Quarantine**: Replace `test(` with `test.fixme(` and add a comment with the symptom and a tracking reference.
3. **Do not delete**: Deleted tests leave coverage gaps. Quarantined tests are visible debt.
4. **Fix criteria**: Before removing `test.fixme`, the test must pass 10/10 with `--repeat-each=10`.

```typescript
// Before
test('checkout completes successfully', async ({ page }) => { ... });

// After quarantine
test.fixme('checkout completes successfully', async ({ page }) => {
  // FLAKY: intermittent race on payment confirmation response
  // TODO: #456 -- investigate network timing in checkout flow
  ...
});
```

---

### PHASE 4: VALIDATE

**Goal:** Deterministic checks on test output, then structured report generation.

**Actions:**
1. **Deterministic checks first** -- run these before any LLM summary because compiler output and JSON parsing are facts, not opinions:
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

### CI/CD Integration

#### GitHub Actions Workflow Template

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

## Error Handling

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `npx tsc --noEmit` fails after Phase 1 | Bad config template or missing types | Check `@playwright/test` is in devDependencies, verify `tsconfig.json` includes the test directory |
| Tests pass locally, fail in CI | Missing browser deps or wrong `BASE_URL` | Use `npx playwright install --with-deps` in CI; verify `BASE_URL` env var matches the running app |
| `playwright-results.json` missing after run | Reporter not configured or test runner crashed | Verify `json` reporter is in `playwright.config.ts`; check for OOM or process kill signals |
| Locator timeout on element that exists | Element present but not actionable (hidden, disabled, covered) | Use `await expect(locator).toBeVisible()` before interaction; check for overlays or modals |
| `page.fill()` appends instead of replacing | Input field has existing value | Use `locator.clear()` then `locator.fill()` |
| Flaky test passes 4/5 runs | Race condition, network timing, or animation interference | Quarantine with `test.fixme()`, reproduce with `--repeat-each=10`, check for missing `waitFor` conditions |
| Locators depending on `nth(0)` break randomly | DOM order is not stable | Add a `data-testid` to the specific element instead of relying on position |

---

## References

- [playwright-patterns.md](references/playwright-patterns.md) -- POM examples, condition-based waiting, multi-browser config, financial skip guards
- [wallet-testing.md](references/wallet-testing.md) -- Web3/MetaMask mock patterns with `addInitScript`
- [financial-flows.md](references/financial-flows.md) -- Production skip guards, blockchain confirmation waits
- [flakiness-triage.md](references/flakiness-triage.md) -- `--repeat-each`, `--retries`, quarantine decision tree
- [ADR-107](../../adr/ADR-107-e2e-testing.md) -- Decision record for this skill
- [Playwright docs](https://playwright.dev/docs/intro) -- Official API reference
