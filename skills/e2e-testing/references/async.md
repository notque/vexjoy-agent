# Async Patterns Reference

> **Scope**: Async coordination patterns for Playwright tests — parallel execution, race conditions, and timing anti-patterns. Does not cover basic `await` usage or condition-based waiting (see `playwright-patterns.md`).
> **Version range**: Playwright 1.20+ (Node 18+)
> **Generated**: 2026-04-17

---

## Overview

Async bugs are the primary source of intermittent E2E failures. The three failure modes are: (1) missing `await` causes assertions to run before actions complete, (2) `waitForTimeout` hard-codes delays that break on slow CI, and (3) uncoordinated parallel requests cause race conditions. Playwright's `Promise.all` and `waitForResponse` patterns eliminate all three by synchronizing on observable events rather than time.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `Promise.all([waitForResponse, click])` | `1.0+` | Action triggers network request | No network call involved |
| `page.waitForEvent('dialog')` | `1.0+` | Click opens browser dialog | Dialog never appears |
| `test.setTimeout(ms)` | `1.0+` | Single test needs extended timeout | All tests are slow (fix root cause) |
| `expect.poll()` | `1.38+` | Polling an external state change | Element is already in DOM |
| `Promise.race([success, error])` | Node | Two mutually exclusive outcomes | One outcome is always expected |

---

## Correct Patterns

### Parallel Request + Click Coordination

Clicking before registering the `waitForResponse` listener misses the response — it fires during the click, before the listener is set up.

```typescript
// Register listener BEFORE the action that triggers it
const [response] = await Promise.all([
  page.waitForResponse(r => r.url().includes('/api/save') && r.status() === 200),
  page.getByTestId('save-button').click(),
]);
const body = await response.json();
expect(body.id).toBeDefined();
```

**Why**: `waitForResponse` is a promise that resolves on the *next* matching response. If the click fires first, the response arrives before the promise is created and `.waitForResponse` hangs until timeout.

---

### Parallel Independent Actions in Setup

When setup requires multiple independent async steps, run them in parallel:

```typescript
test.beforeEach(async ({ page, request }) => {
  // Sequential (slow) — each waits for the previous
  // await seedUser(request);
  // await seedProducts(request);
  // await page.goto('/dashboard');

  // Parallel (fast) — all start at once
  await Promise.all([
    seedUser(request),
    seedProducts(request),
    page.goto('/dashboard'),
  ]);
});
```

**Why**: Sequential setup multiplies latency. Three 200ms API calls take 600ms sequentially vs 200ms in parallel.

---

### Polling External State with `expect.poll`

For state that changes outside the browser (background job, webhook, database update):

```typescript
// Playwright 1.38+
await expect.poll(
  async () => {
    const res = await request.get('/api/orders/123/status');
    return (await res.json()).status;
  },
  { timeout: 30_000, intervals: [1000, 2000, 5000, 10000] }
).toBe('completed');
```

**Why**: `expect.poll` retries the predicate on the given intervals without blocking the event loop between checks, unlike a sleep loop.

---

### Dialog Handling

Dialogs must be registered before the action that opens them, or they close the browser context:

```typescript
page.on('dialog', async dialog => {
  expect(dialog.message()).toContain('Are you sure?');
  await dialog.accept();
});
await page.getByTestId('delete-button').click();
await expect(page).toHaveURL('/items');
```

**Why**: An unhandled `alert`/`confirm` causes Playwright to auto-dismiss and log a warning. If the dialog is required for the flow, unhandled = broken test.

---

## Anti-Pattern Catalog

### ❌ `waitForTimeout` as a Timing Fix

**Detection**:
```bash
grep -rn 'waitForTimeout' --include="*.ts" --include="*.spec.ts"
rg 'waitForTimeout\(' --type ts
```

**What it looks like**:
```typescript
await page.getByTestId('save-button').click();
await page.waitForTimeout(2000); // "give it time to save"
await expect(page.getByTestId('success-banner')).toBeVisible();
```

**Why wrong**: Hard-coded delays fail silently on slow CI (timeout too short) or waste time on fast machines (timeout too long). `waitForTimeout` is a symptom of not knowing what observable event to wait for.

**Fix**:
```typescript
await Promise.all([
  page.waitForResponse(r => r.url().includes('/api/save')),
  page.getByTestId('save-button').click(),
]);
await expect(page.getByTestId('success-banner')).toBeVisible();
```

**Version note**: `waitForTimeout` is deprecated in Playwright 1.39+ — the linter flags it as `no-wait-for-timeout`.

---

### ❌ Fire-and-Forget Click (Missing Await on Navigation)

**Detection**:
```bash
grep -rn '\.click()$' --include="*.spec.ts"
rg '\.click\(\)[^;]' --type ts
```

**What it looks like**:
```typescript
page.getByTestId('submit').click(); // missing await
await expect(page).toHaveURL('/confirmation'); // races with navigation
```

**Why wrong**: Without `await`, the click fires but the test proceeds immediately. If the URL check runs before navigation completes, it sees the old URL and fails intermittently.

**Fix**:
```typescript
await Promise.all([
  page.waitForURL('/confirmation'),
  page.getByTestId('submit').click(),
]);
```

---

### ❌ Async Fixture Without Teardown

**Detection**:
```bash
grep -rn "test\.extend" --include="*.ts" -A 10
rg 'test\.extend\b' --type ts -A 10
```

**What it looks like**:
```typescript
export const test = base.extend<{ db: Database }>({
  db: async ({}, use) => {
    const db = await Database.connect();
    await use(db);
    // Missing: await db.disconnect();  — resource leak
  },
});
```

**Why wrong**: Leaked connections accumulate across the test suite. In CI with 100 tests, this exhausts connection pools and causes later tests to fail with unrelated errors.

**Fix**:
```typescript
export const test = base.extend<{ db: Database }>({
  db: async ({}, use) => {
    const db = await Database.connect();
    try {
      await use(db);
    } finally {
      await db.disconnect(); // always runs, even if test throws
    }
  },
});
```

---

### ❌ Sequential Waits for Independent Elements

**Detection**:
```bash
grep -rn '\.waitFor(' --include="*.spec.ts" -A 1
rg 'waitFor\(' --type ts --include="*.spec.ts"
```

**What it looks like**:
```typescript
await page.getByTestId('widget-a').waitFor({ state: 'visible' });
await page.getByTestId('widget-b').waitFor({ state: 'visible' });
await page.getByTestId('widget-c').waitFor({ state: 'visible' });
```

**Why wrong**: Each wait is sequential. If each element takes 500ms to render, this adds 1.5s of latency. Elements that load independently should be awaited in parallel.

**Fix**:
```typescript
await Promise.all([
  page.getByTestId('widget-a').waitFor({ state: 'visible' }),
  page.getByTestId('widget-b').waitFor({ state: 'visible' }),
  page.getByTestId('widget-c').waitFor({ state: 'visible' }),
]);
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Timeout 30000ms exceeded waiting for...` | Hard wait wasn't long enough, or wrong observable | Replace `waitForTimeout` with event-based wait |
| `locator.click: Target closed` | Dialog auto-dismissed before handler registered | Register `page.on('dialog', ...)` before the action |
| `browserContext.storageState: Target page, context or browser has been closed` | Parallel tests sharing a single context instance | Use per-test context or `test.use({ storageState })` |
| `Error: page.waitForResponse: page closed` | Navigation completed before `waitForResponse` resolved | Wrap in `Promise.all` with the triggering click |
| `UnhandledPromiseRejection` in fixture | Missing `await` in fixture setup | Add `await` to all async calls inside `test.extend` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `1.39` | `waitForTimeout` deprecated | Linter rule `no-wait-for-timeout` flags usage |
| `1.38` | `expect.poll()` added | Use instead of `waitForFunction` for polling external state |
| `1.30` | `waitForResponse` accepts async predicate | Predicate can now `await response.json()` inline |
| `1.25` | Worker-scoped fixtures stable | Share expensive async setup (DB, auth) across tests in a worker |

---

## Detection Commands Reference

```bash
# Find all waitForTimeout usage (replace with event-based waits)
grep -rn 'waitForTimeout' --include="*.ts"

# Find unawaited clicks (potential race conditions)
grep -rn '\.click()$' --include="*.spec.ts"

# Find test.extend fixtures (review for missing teardown)
grep -rn 'test\.extend' --include="*.ts" -A 15

# Find sequential waitFor calls that could be parallelized
grep -rn '\.waitFor(' --include="*.spec.ts"
```

---

## See Also

- `playwright-patterns.md` — condition-based waiting, waitForLoadState, network request patterns
- `flakiness-triage.md` — diagnosing and quarantining intermittent failures
