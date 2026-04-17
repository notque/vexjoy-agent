# Authentication Testing Reference

> **Scope**: Patterns for testing authentication flows in Playwright — multi-role state management, OAuth/SSO, session expiry, JWT, and RBAC. The basic `storageState` setup lives in `playwright-patterns.md`; this file covers advanced scenarios.
> **Version range**: Playwright 1.25+ (worker-scoped fixtures required for multi-role)
> **Generated**: 2026-04-17

---

## Overview

Auth testing fails in two common ways: (1) tests share auth state across roles and pollute each other, and (2) tests log in via the UI for every test, spending 70%+ of runtime on login screens. The correct model is: authenticate once per role via the API, save the resulting `storageState`, and inject it into tests that need it. Session expiry, RBAC, and OAuth flows each require separate patterns.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `globalSetup` + `storageState` file | `1.0+` | Single user role, full suite | Multiple roles needed |
| Worker-scoped fixture per role | `1.25+` | Multiple roles, parallel workers | Single role only |
| `request.post('/api/login')` in setup | `1.0+` | App has API login endpoint | UI-only login required |
| `page.addInitScript` for JWT injection | `1.0+` | JWT stored in localStorage | Cookie-based auth |
| `page.route` to mock OAuth callback | `1.0+` | Testing OAuth-gated pages | Testing the OAuth provider itself |

---

## Correct Patterns

### Multi-Role Auth via Worker Fixtures (Playwright 1.25+)

Use one fixture file for all roles. Each fixture authenticates once per worker, not once per test:

```typescript
// fixtures/auth.ts
import { test as base, expect } from '@playwright/test';

type AuthFixtures = {
  adminPage: Page;
  viewerPage: Page;
};

export const test = base.extend<{}, AuthFixtures>({
  // Worker-scoped: runs once per worker process, not per test
  adminPage: [async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    // Authenticate via API — avoid UI login overhead
    const response = await page.request.post('/api/auth/login', {
      data: { email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD },
    });
    expect(response.ok()).toBeTruthy();
    await context.storageState({ path: 'playwright/.auth/admin.json' });
    await use(page);
    await context.close();
  }, { scope: 'worker' }],

  viewerPage: [async ({ browser }, use) => {
    const context = await browser.newContext({
      storageState: 'playwright/.auth/viewer.json',
    });
    const page = await context.newPage();
    await use(page);
    await context.close();
  }, { scope: 'worker' }],
});
```

```typescript
// tests/e2e/admin/dashboard.spec.ts
import { test, expect } from '../../fixtures/auth';

test('admin can delete users', async ({ adminPage }) => {
  await adminPage.goto('/admin/users');
  await adminPage.getByTestId('user-row-42').getByTestId('delete').click();
  await expect(adminPage.getByTestId('success-toast')).toBeVisible();
});

test('viewer cannot see delete button', async ({ viewerPage }) => {
  await viewerPage.goto('/admin/users');
  await expect(viewerPage.getByTestId('user-row-42').getByTestId('delete')).not.toBeVisible();
});
```

**Why**: Worker-scoped fixtures share auth state across all tests in the same worker. Login happens once per worker, not once per test — 10x faster for suites with many authenticated tests.

---

### JWT Injection via `addInitScript`

When the app reads JWT from `localStorage` on page load:

```typescript
// pages/AuthenticatedPage.ts
import { type Page } from '@playwright/test';

export async function injectJWT(page: Page, token: string) {
  await page.addInitScript((jwt) => {
    window.localStorage.setItem('auth_token', jwt);
  }, token);
}
```

```typescript
// tests/e2e/features/profile.spec.ts
import { test, expect } from '@playwright/test';
import { injectJWT } from '../../pages/AuthenticatedPage';
import { generateTestJWT } from '../../helpers/jwt';

test('profile page loads with valid JWT', async ({ page }) => {
  const token = generateTestJWT({ userId: '42', role: 'admin', expiresIn: '1h' });
  await injectJWT(page, token);
  await page.goto('/profile');
  await expect(page.getByTestId('profile-name')).toBeVisible();
});
```

**Why**: `addInitScript` runs before the page's own scripts execute, so the JWT is in `localStorage` when the app initializes. Injecting after navigation misses the initial auth check.

---

### Session Expiry Testing

Test what users see when their session expires mid-flow:

```typescript
test('expired session redirects to login with return URL', async ({ page }) => {
  // Start with valid session
  await page.context().addCookies([{
    name: 'session',
    value: 'valid-session-token',
    domain: 'localhost',
    path: '/',
  }]);
  await page.goto('/dashboard');
  await expect(page.getByTestId('dashboard-content')).toBeVisible();

  // Simulate expiry: intercept next API call and return 401
  await page.route('/api/**', route => {
    route.fulfill({ status: 401, body: JSON.stringify({ error: 'session_expired' }) });
  });

  // Trigger an authenticated action
  await page.getByTestId('load-more').click();

  // App should redirect to login, preserving return URL
  await expect(page).toHaveURL(/\/login\?returnUrl=/);
  await expect(page.getByTestId('session-expired-message')).toBeVisible();
});
```

---

### OAuth / SSO Mock (Bypass the Provider)

Never test against a real OAuth provider in E2E — mock the callback instead:

```typescript
test('OAuth login flow completes', async ({ page }) => {
  // Intercept the OAuth redirect back to the app
  await page.route('/auth/callback*', async route => {
    const url = new URL(route.request().url());
    // Simulate a successful OAuth callback with a test code
    await route.fulfill({
      status: 302,
      headers: {
        Location: '/dashboard',
        'Set-Cookie': 'session=test-oauth-session; Path=/; HttpOnly',
      },
    });
  });

  await page.goto('/login');
  await page.getByTestId('login-with-google').click();
  // Playwright follows the redirect chain; our route intercepts the callback
  await expect(page).toHaveURL('/dashboard');
  await expect(page.getByTestId('nav-user-avatar')).toBeVisible();
});
```

**Why**: Real OAuth providers add network latency, require live credentials, and may rate-limit CI. Mocking the callback tests your app's OAuth handling without testing Google/GitHub.

---

## Anti-Pattern Catalog

### ❌ UI Login in Every Test

**Detection**:
```bash
grep -rn 'getByTestId.*login\|getByTestId.*password\|getByTestId.*signin' --include="*.spec.ts"
rg '(login-email|login-password|login-submit)' --type ts --include="*.spec.ts" -l
```

**What it looks like**:
```typescript
test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByTestId('login-email').fill('user@test.com');
  await page.getByTestId('login-password').fill('password');
  await page.getByTestId('login-submit').click();
  await page.waitForURL('/dashboard');
});
```

**Why wrong**: A 10-test suite with a 3-second login flow spends 30 seconds on login alone. `storageState` eliminates this: authenticate once, reuse the session.

**Fix**: Use `globalSetup` with `storageState` (single role) or worker-scoped fixtures (multiple roles). See `playwright-patterns.md` for the single-role pattern.

---

### ❌ Sharing Auth Context Between Roles

**Detection**:
```bash
grep -rn 'storageState' --include="playwright.config.ts" -A 5
rg 'storageState.*admin.*viewer|storageState.*viewer.*admin' --type ts
```

**What it looks like**:
```typescript
// playwright.config.ts — wrong: one storageState for all tests
use: {
  storageState: 'playwright/.auth/user.json', // which user? admin or viewer?
},
```

**Why wrong**: When tests for different roles share one auth file, they run with the same permissions. An admin-privilege test passes for a viewer because the session is still admin. RBAC bugs go undetected.

**Fix**: Use per-role `projects` in `playwright.config.ts`:
```typescript
projects: [
  { name: 'admin-tests', use: { storageState: 'playwright/.auth/admin.json' } },
  { name: 'viewer-tests', use: { storageState: 'playwright/.auth/viewer.json' } },
  { name: 'unauthenticated-tests' }, // no storageState
],
```

---

### ❌ Hardcoded Credentials in Spec Files

**Detection**:
```bash
grep -rn 'password.*:.*"[^"]\+"\|fill.*"password[^"]*"' --include="*.spec.ts"
rg '(password|secret|token)\s*[:=]\s*["'"'"'][^"'"'"']+["'"'"']' --type ts --include="*.spec.ts"
```

**What it looks like**:
```typescript
await page.getByTestId('login-password').fill('MyP@ssw0rd123'); // hardcoded
```

**Why wrong**: Credentials in source code appear in git history permanently. They also break when rotated.

**Fix**:
```typescript
await page.getByTestId('login-password').fill(process.env.TEST_USER_PASSWORD!);
```
Set `TEST_USER_PASSWORD` in `.env.test` (gitignored) and in CI secrets.

---

### ❌ Testing Real OAuth Provider Endpoints

**Detection**:
```bash
grep -rn 'accounts\.google\.com\|github\.com/login/oauth\|login\.microsoftonline' --include="*.spec.ts"
rg '(google|github|microsoft|auth0)\.com' --type ts --include="*.spec.ts"
```

**What it looks like**:
```typescript
await page.goto('https://accounts.google.com/o/oauth2/auth?...');
await page.getByLabel('Email').fill(process.env.GOOGLE_TEST_EMAIL!);
```

**Why wrong**: Hits a live external service. Flaky on network issues. Requires a real test account. May trigger bot detection. Rate-limited in CI.

**Fix**: Mock the OAuth callback with `page.route` as shown in the Correct Patterns section.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `401 Unauthorized` in all API calls after test 50 | `storageState` session expired mid-suite | Re-generate auth state in `globalSetup`, or use shorter-lived tokens |
| `storageState: path does not exist` | `globalSetup` didn't run, or path mismatch | Verify `playwright.config.ts` `globalSetup` is wired; check path matches exactly |
| `Cannot read properties of undefined (reading 'token')` | JWT not in localStorage when page loaded | Use `addInitScript`, not `evaluate`, to inject JWT before page scripts run |
| `page.route` callback not triggered | Route registered after navigation started | Register routes before `page.goto()` |
| Tests pass locally, fail in CI with `403` | CI uses different `BASE_URL` hitting real auth | Check that CI env has `PLAYWRIGHT_BASE_URL` pointing to the test instance |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `1.25` | Worker-scoped fixtures stable | Multi-role auth fixtures now safe for parallel workers |
| `1.31` | `request` context available in fixtures | Can use `fixture.request.post()` for API login without launching a browser |
| `1.35` | `storageState` supports `origins` filter | Can scope saved auth to specific domains, preventing cross-domain cookie leaks |

---

## Detection Commands Reference

```bash
# Find tests doing UI login in beforeEach (migrate to storageState)
grep -rn 'beforeEach' --include="*.spec.ts" -A 10 | grep -i 'login\|password\|signin'

# Find hardcoded credentials
rg '(password|secret)\s*[:=]\s*["'"'"'][^"'"'"']+["'"'"']' --type ts --include="*.spec.ts"

# Find real OAuth provider URLs in tests
grep -rn 'accounts\.google\.com\|github\.com/login\|auth0\.com' --include="*.spec.ts"

# Find tests without any auth setup (may need storageState)
grep -rn 'test(' --include="*.spec.ts" -l | xargs grep -rL 'storageState\|adminPage\|viewerPage\|login'
```

---

## See Also

- `playwright-patterns.md` — basic `storageState` setup, single-role global auth
- `errors.md` — auth-related error symptom/cause/fix matrix
