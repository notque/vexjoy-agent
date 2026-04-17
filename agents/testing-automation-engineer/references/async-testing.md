# Async Testing Reference

> **Scope**: Async test patterns for React Testing Library, Vitest, and Playwright. Covers waitFor, act(), MSW request interception, and async error handling. Does NOT cover Vitest configuration (see vitest-patterns.md).
> **Version range**: React Testing Library 14+, Vitest 1.0+, Playwright 1.40+
> **Generated**: 2026-04-15

---

## Overview

Async testing is the primary source of flaky tests. The two failure modes are (1) not waiting for async state updates before asserting, and (2) adding arbitrary `setTimeout` delays instead of waiting for a deterministic condition. RTL's `waitFor` and Playwright's auto-waiting locators eliminate both — when used correctly.

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

**Why**: `userEvent.click` triggers the event but the state update (API call → response → re-render) happens asynchronously. Without `waitFor`, the assertion runs before the component re-renders.

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

**Why**: `findBy*` is shorthand for `waitFor(() => getBy*(...))`. Use it when an element is absent at render and appears after a data fetch. After the first `findBy*` resolves, subsequent assertions can use `getBy*` synchronously.

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

**Why**: MSW intercepts at the network layer, not the module layer. The component's actual `fetch` call runs, so error handling, response parsing, and timeout logic are all exercised. `onUnhandledRequest: 'error'` catches unexpected API calls that would otherwise silently return `undefined`.

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

**Why**: Playwright's `expect(locator).toBeVisible()` auto-waits. Using `page.waitForSelector()` manually or `page.waitForTimeout(2000)` is an anti-pattern — fixed delays are slow on fast machines and flaky on slow ones.

---

## Pattern Catalog

### ❌ setTimeout / sleep Delays in Tests

**Detection**:
```bash
grep -rn 'setTimeout\|waitForTimeout\|new Promise.*sleep' --include="*.test.ts" --include="*.test.tsx" --include="*.spec.ts"
rg 'waitForTimeout|page\.waitFor\b' --type ts
```

**What it looks like**:
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

**Why wrong**: Arbitrary delays make tests slow on fast machines and flaky on slow ones. If the operation takes 600ms instead of 500ms (CI under load), the test fails. These tests hide timing bugs rather than revealing them.

**Do instead:**
```typescript
// RTL — wait for actual DOM change
await screen.findByText(/result/i)
// or
await waitFor(() => expect(screen.getByText(/result/i)).toBeInTheDocument())

// Playwright — assert on locator (auto-waits)
await expect(page.getByText('Done')).toBeVisible()
```

---

### ❌ Un-awaited userEvent Actions (RTL 14+)

**Detection**:
```bash
grep -rn 'user\.' --include="*.test.ts" --include="*.test.tsx" | grep -v 'await user\.\|const user\|let user'
rg 'userEvent\.(click|type|clear|selectOptions)\(' --type tsx | grep -v 'await '
```

**What it looks like**:
```typescript
// BAD: missing await on user actions (RTL 14+ requires await)
const user = userEvent.setup()
user.click(button)         // fire-and-forget
user.type(input, 'hello')
expect(screen.getByText(/hello/i)).toBeInTheDocument()
```

**Why wrong**: `userEvent.setup()` returns async methods in RTL 14+. Without `await`, the events fire but React state updates haven't processed before assertions run. Test passes inconsistently depending on microtask scheduling.

**Do instead:**
```typescript
const user = userEvent.setup()
await user.click(button)
await user.type(input, 'hello')
await screen.findByText(/hello/i)
```

**Version note**: RTL 13 and earlier used synchronous `userEvent`. RTL 14+ switched to async. Un-awaited calls produce flaky tests, not immediate errors — the breakage is subtle.

---

### ❌ getBy* After Async Operations

**Detection**:
```bash
rg 'await user\.(click|submit|type)' --type ts -A1 | grep 'getBy'
```

**What it looks like**:
```typescript
await user.click(screen.getByRole('button', { name: /save/i }))
expect(screen.getByText(/saved/i)).toBeInTheDocument()  // may not exist yet
```

**Why wrong**: `user.click` resolves after the event dispatches, not after React re-renders from async work (API calls, state transitions). The `getByText` assertion runs synchronously and finds the element absent.

**Do instead:**
```typescript
await user.click(screen.getByRole('button', { name: /save/i }))
await screen.findByText(/saved/i)   // waits up to 1000ms by default
```

---

### ❌ MSW Without onUnhandledRequest: 'error'

**Detection**:
```bash
grep -rn 'server\.listen' --include="*.ts" --include="*.tsx" | grep -v 'onUnhandledRequest'
rg 'setupServer' --type ts -l | xargs rg -L 'onUnhandledRequest'
```

**What it looks like**:
```typescript
server.listen()  // no onUnhandledRequest — silent network failures
```

**Why wrong**: When a component makes an unexpected API call (wrong path, URL typo), MSW passes it through or returns undefined without failing the test. The component renders broken UI, tests assert on something unrelated, and the bug is hidden until production.

**Do instead:**
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
