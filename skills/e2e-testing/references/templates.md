## Templates

### playwright.config.ts Template

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

### POM Pattern

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

### data-testid Convention

- **Format**: `<component>-<element>` -- e.g., `login-email`, `checkout-submit`, `nav-profile-link`
- **Scope**: Add `data-testid` to interactive elements and status regions the tests need to assert on
- **Stability**: `data-testid` attributes must not change with styling or refactoring -- they are a testing contract

### Waiting and Timing

Never use `waitForTimeout()` or `setTimeout()` in tests. Arbitrary waits pass slowly on fast machines and fail on slow ones -- they encode a guess about timing instead of observing the actual condition. Use condition-based waiting instead:

| Instead of | Use |
|-----------|-----|
| `await page.waitForTimeout(2000)` | `await expect(locator).toBeVisible()` or `await page.waitForResponse(...)` |
| `await page.waitForTimeout(0)` to "flush" | `await page.waitForLoadState('networkidle')` |
| `page.click('button')` without waiting | `locator.click()` -- Playwright auto-waits for actionability |

Each test must own its own setup in `beforeEach`. Tests sharing state via global variables break parallel execution because Playwright runs specs concurrently by default.

### Flaky Test Quarantine Protocol

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

### e2e-report.md Template

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
