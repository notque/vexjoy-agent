# Async Testing Reference

> **Scope**: Async test patterns for React Testing Library, Vitest, and Playwright. Covers waitFor, act(), MSW request interception, and async error handling. Does NOT cover Vitest configuration (see vitest-patterns.md).
> **Version range**: React Testing Library 14+, Vitest 1.0+, Playwright 1.40+
> **Generated**: 2026-04-15

---

## Overview

Primary source of flaky tests: (1) asserting before async state updates, (2) arbitrary `setTimeout` delays. RTL `waitFor` and Playwright auto-waiting locators eliminate both.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `waitFor(() => expect(...))` | RTL 9+ | DOM state changes after async event | Synchronous state changes |
| `findBy*` queries | RTL 9+ | Element appears asynchronously | Element already in DOM at render |
| `getBy*` queries | RTL 9+ | Element is in DOM at time of assertion | Element appears asynchronously |
| `act()` | React 16.8+ | Wrapping state-triggering code in unit tests | RTL renders (auto-wrapped) |
| `page.getByRole()` | Playwright 1.27+ | Auto-waiting for element to be ready | Assertions on hidden elements |
| `await expect(locator).toBeVisible()` | Playwright 1.27+ | Playwright async assertions | Synchronous `expect(value).toBe()` |

---

## Correct Patterns

### React Testing Library — waitFor for Async State

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

it('shows success message after form submission', async () => {
  const user = userEvent.setup()
  render(<ContactForm />)

  await user.type(screen.getByLabelText(/email/i), 'test@example.com')
  await user.click(screen.getByRole('button', { name: /submit/i }))

  // waitFor polls until assertion passes or timeout (default 1000ms)
  await waitFor(() => {
    expect(screen.getByText(/message sent/i)).toBeInTheDocument()
  })
})
```

**Why**: Click triggers event but state update (API -> response -> re-render) is async. Without `waitFor`, assertion runs before re-render.

---

### findBy* for Elements That Appear Asynchronously

```typescript
it('loads and displays user data', async () => {
  render(<UserProfile userId={1} />)

  // findBy* = getBy* + waitFor built in. Throws if not found within timeout.
  const heading = await screen.findByRole('heading', { name: /alice/i })
  expect(heading).toBeInTheDocument()

  // After findBy* resolves, use synchronous getBy* for further assertions
  expect(screen.getByText(/alice@example.com/i)).toBeInTheDocument()
})
```

**Why**: `findBy*` = `waitFor(() => getBy*(...))`. Use when element appears after data fetch. After first `findBy*` resolves, use `getBy*` synchronously.

---

### MSW (Mock Service Worker) for API Mocking

```typescript
// src/test/server.ts
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

export const server = setupServer(
  http.get('/api/users/:id', ({ params }) => {
    return HttpResponse.json({ id: params.id, name: 'Alice', email: 'alice@example.com' })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())   // reset per-test overrides
afterAll(() => server.close())
```

```typescript
// Override default handler in one test
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'

it('shows error when user not found', async () => {
  server.use(
    http.get('/api/users/:id', () => HttpResponse.json({ error: 'Not found' }, { status: 404 }))
  )

  render(<UserProfile userId={999} />)
  await screen.findByText(/user not found/i)
})
```

**Why**: MSW intercepts at network layer. Real `fetch` runs — error handling, parsing, timeouts exercised. `onUnhandledRequest: 'error'` catches unexpected API calls.

---

### Playwright — Async Assertions

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test'
export default defineConfig({
  use: { baseURL: 'http://localhost:3000' },
  expect: { timeout: 5000 },   // per-assertion timeout
  timeout: 30_000,              // per-test timeout
})
```

```typescript
import { test, expect } from '@playwright/test'

test('submits form and shows confirmation', async ({ page }) => {
  await page.goto('/contact')

  await page.getByLabel('Email').fill('test@example.com')
  await page.getByRole('button', { name: 'Submit' }).click()

  // Auto-waits up to expect.timeout for element to be visible
  await expect(page.getByText('Message sent')).toBeVisible()

  // Playwright locators re-query on each assertion — no stale element refs
  await expect(page.getByRole('heading', { name: 'Thank you' })).toBeVisible()
})
```

**Why**: Playwright `expect(locator).toBeVisible()` auto-waits. `waitForTimeout()` is an anti-pattern — slow on fast machines, flaky on slow ones.

---

## Pattern Catalog

### Wait for Deterministic Conditions in Tests

**Detection**:
```bash
grep -rn 'setTimeout\|waitForTimeout\|new Promise.*sleep' --include="*.test.ts" --include="*.test.tsx" --include="*.spec.ts"
rg 'waitForTimeout|page\.waitFor\b' --type ts
```

**Signal**:
```typescript
// BAD: arbitrary delay in RTL
it('shows result after fetch', async () => {
  render(<DataLoader />)
  await new Promise(resolve => setTimeout(resolve, 500))  // hope it loaded
  expect(screen.getByText(/result/i)).toBeInTheDocument()
})

// BAD: Playwright explicit wait
await page.waitForTimeout(2000)
expect(await page.textContent('.result')).toBe('Done')
```

**Why this matters**: Arbitrary delays are slow on fast machines, flaky on slow ones. 600ms instead of 500ms (CI under load) = failure.

**Preferred action:**
```typescript
// RTL — wait for actual DOM change
await screen.findByText(/result/i)
// or
await waitFor(() => expect(screen.getByText(/result/i)).toBeInTheDocument())

// Playwright — assert on locator (auto-waits)
await expect(page.getByText('Done')).toBeVisible()
```

---

### Await All userEvent Actions (RTL 14+)

**Detection**:
```bash
grep -rn 'user\.' --include="*.test.ts" --include="*.test.tsx" | grep -v 'await user\.\|const user\|let user'
rg 'userEvent\.(click|type|clear|selectOptions)\(' --type tsx | grep -v 'await '
```

**Signal**:
```typescript
// BAD: missing await on user actions (RTL 14+ requires await)
const user = userEvent.setup()
user.click(button)         // fire-and-forget
user.type(input, 'hello')
expect(screen.getByText(/hello/i)).toBeInTheDocument()
```

**Why this matters**: RTL 14+ `userEvent.setup()` returns async methods. Without `await`, state updates haven't processed before assertions. Flaky, not immediate errors.

**Preferred action:**
```typescript
const user = userEvent.setup()
await user.click(button)
await user.type(input, 'hello')
await screen.findByText(/hello/i)
```

---

### Use findBy* After Async Operations

**Detection**:
```bash
rg 'await user\.(click|submit|type)' --type ts -A1 | grep 'getBy'
```

**Signal**:
```typescript
await user.click(screen.getByRole('button', { name: /save/i }))
expect(screen.getByText(/saved/i)).toBeInTheDocument()  // may not exist yet
```

**Why this matters**: `user.click` resolves after dispatch, not after React re-renders from async work. `getByText` runs synchronously, element absent.

**Preferred action:**
```typescript
await user.click(screen.getByRole('button', { name: /save/i }))
await screen.findByText(/saved/i)   // waits up to 1000ms by default
```

---

### Set onUnhandledRequest: 'error' in MSW

**Detection**:
```bash
grep -rn 'server\.listen' --include="*.ts" --include="*.tsx" | grep -v 'onUnhandledRequest'
rg 'setupServer' --type ts -l | xargs rg -L 'onUnhandledRequest'
```

**Signal**:
```typescript
server.listen()  // no onUnhandledRequest — silent network failures
```

**Why this matters**: Unexpected API calls (wrong path, typo) pass through silently. Component renders broken UI, test passes, bug hidden until production.

**Preferred action:**
```typescript
server.listen({ onUnhandledRequest: 'error' })
// Unexpected requests now throw: "Error: No handler for GET /api/typo"
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Unable to find an element with the text: X` | Assertion runs before async render | Replace `getBy*` with `await findBy*` |
| `Found multiple elements with the role "button"` | Query too broad | Add `name` option: `getByRole('button', { name: /submit/i })` |
| `Warning: An update to X inside a test was not wrapped in act(...)` | State update after test cleanup | Return the async operation or use `waitFor` |
| `Error: connect ECONNREFUSED` in Playwright | App not running on expected port | Run dev server before test; check `baseURL` in config |
| `Timeout 5000ms exceeded` in Playwright | Element never appeared | Check selector; inspect for race condition; increase `expect.timeout` only as last resort |
| `Error: No handler for GET /api/X` (MSW) | `onUnhandledRequest: 'error'` + missing handler | Add handler to `setupServer` or to the specific test |
| `act(...)` warning on unmounted component | Test doesn't await component cleanup | Add `await waitFor(() => {})` at end, or fix component cleanup |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RTL 13 → 14 | `userEvent` methods became async | Must `await` all user interactions |
| MSW 1 → 2 | `rest.get` replaced by `http.get`; `ctx.json` by `HttpResponse.json` | Update handler syntax on MSW 2 upgrade |
| Playwright 1.27 | Locator API stable; `page.$()` deprecated | Use `page.getByRole()` / `page.locator()` exclusively |
| Playwright 1.40 | `expect.soft()` added for non-fatal assertions | Use for collecting multiple failures in one test run |

---

## Detection Commands Reference

```bash
# Arbitrary delays (should use waitFor or findBy* instead)
grep -rn 'setTimeout\|waitForTimeout' --include="*.test.ts" --include="*.test.tsx"

# Un-awaited userEvent calls (RTL 14+)
grep -rn 'user\.' --include="*.test.tsx" | grep -v 'await user\.\|const user\|let user'

# MSW listeners without onUnhandledRequest guard
grep -rn 'server\.listen' --include="*.ts" | grep -v 'onUnhandledRequest'

# Synchronous getBy* immediately after async click
rg 'await user\.(click|submit)' --type ts -A1 | grep 'getBy'
```

---

## See Also

- `vitest-patterns.md` — Vitest configuration, spy lifecycle, fake timers
- `mocking-patterns.md` — when to use MSW vs vi.mock, test doubles taxonomy
