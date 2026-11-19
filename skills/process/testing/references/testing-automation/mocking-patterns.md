# Mocking Patterns Reference

> **Scope**: What to mock and what not to mock, MSW vs vi.mock decision tree, test double taxonomy, and over-mocking detection. Does NOT cover Vitest spy APIs (see vitest-patterns.md) or MSW server setup (see async-testing.md).
> **Version range**: Vitest 1.0+, MSW 2.0+, all versions for taxonomy
> **Generated**: 2026-04-15

---

## Overview

Over-mocking is the primary cause of tests that pass but fail in production. When every dependency is mocked, the test verifies that mocks behave like mocks, not that the real system works. The rule: mock at boundaries (network, file system, time, external services), not inside the application layer.

---

## Mock Boundary Decision Table

| Layer | Mock? | Why | How |
|-------|-------|-----|-----|
| External HTTP APIs | YES | Non-deterministic, slow, costs money | MSW (`http.get`) |
| Browser `fetch` / `XMLHttpRequest` | YES (via MSW) | Network layer isolation | MSW intercepts at network level |
| `Date.now()` / system time | YES | Tests require deterministic time | `vi.setSystemTime()` |
| File system (unit test) | YES | Side effects, path portability | `vi.mock('node:fs')` |
| File system (integration test) | NO | Use temp dir (`fs.mkdtempSync`) | — |
| Database (unit test) | YES | Side effects, speed | Repository interface mock |
| Database (integration test) | NO | Use test DB or in-memory SQLite | — |
| Internal module functions | NO | Tests become brittle, miss integration bugs | Test the public API |
| React context providers | NO | Wrap component in real provider in tests | `renderWithProviders` helper |
| Third-party UI libraries | NO | Use real components | Render in test; assert on output |
| `console.error` | SOMETIMES | Suppress expected React warnings | `vi.spyOn(console, 'error')` |

---

## Correct Patterns

### MSW for HTTP — Preferred Over vi.stubGlobal('fetch')

```typescript
// GOOD: MSW intercepts the real fetch call
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'

it('displays product name from API', async () => {
  server.use(
    http.get('/api/products/1', () =>
      HttpResponse.json({ id: 1, name: 'Widget Pro', price: 29.99 })
    )
  )

  render(<ProductPage productId={1} />)
  await screen.findByText('Widget Pro')
})
```

```typescript
// BAD: vi.stubGlobal skips network layer, tests the mock
vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  json: () => Promise.resolve({ id: 1, name: 'Widget Pro' })
}))
```

**Why prefer MSW**: MSW intercepts at the network level via `@mswjs/interceptors` (Node). The component's `fetch` call is real — error handling, response parsing, and retry logic are all exercised. `vi.stubGlobal('fetch')` replaces the function, bypassing all of that.

---

### Repository Pattern for Database Mocking

```typescript
// Define the interface
interface UserRepository {
  findById(id: number): Promise<User | null>
  save(user: User): Promise<User>
}

// In-memory mock implements the same interface
class MockUserRepository implements UserRepository {
  private users = new Map<number, User>()

  findById(id: number): Promise<User | null> {
    return Promise.resolve(this.users.get(id) ?? null)
  }

  save(user: User): Promise<User> {
    this.users.set(user.id, user)
    return Promise.resolve(user)
  }
}

// Test — no vi.mock needed
const repo = new MockUserRepository()
const service = new UserService(repo)

it('returns null for unknown user', async () => {
  const result = await service.getUser(999)
  expect(result).toBeNull()
})
```

**Why**: TypeScript enforces that `MockUserRepository` stays in sync with the real interface contract. `vi.mock` on a database module bypasses type checking and can silently drift from the real implementation.

---

### Partial Spy — Mock One Method, Keep the Rest Real

```typescript
import { vi, afterEach } from 'vitest'
import * as emailService from '../services/email'

afterEach(() => vi.restoreAllMocks())

it('sends welcome email on registration', async () => {
  const sendSpy = vi.spyOn(emailService, 'sendEmail').mockResolvedValue(undefined)

  await registerUser({ email: 'new@example.com', name: 'Alice' })

  expect(sendSpy).toHaveBeenCalledWith({
    to: 'new@example.com',
    subject: 'Welcome!',
    template: 'welcome',
  })
})
```

**Why**: `vi.spyOn` replaces only one function. All other `emailService` exports remain real. This tests that `registerUser` calls `sendEmail` with the right arguments without disabling the rest of the email module.

---

## Pattern Catalog

### Mock at Boundaries, Not Internal Logic

**Detection**:
```bash
# vi.mock calls targeting src/ (internal modules)
grep -rn "vi\.mock('\.\." --include="*.test.ts" --include="*.test.tsx" | grep "src/"
rg "vi\.mock\('\./|vi\.mock\('\.\." --type ts | grep -v "node_modules\|__mocks__"
```

**Signal**:
```typescript
// BAD: mocking internal business logic
vi.mock('../services/orderCalculator')
vi.mock('../utils/priceFormatter')
vi.mock('../hooks/useCart')

it('displays total', () => {
  (calculateTotal as Mock).mockReturnValue(99.99)
  render(<OrderSummary />)
  expect(screen.getByText('$99.99')).toBeInTheDocument()
})
```

**Why this matters**: This test verifies that when `calculateTotal` returns `99.99`, the component displays it. It does NOT test whether `calculateTotal` returns the right value. A bug in the calculation is invisible to this test. Over-mocked tests pass while the real system is broken.

**Preferred action:** Mock only the network boundary, let real internal logic run:
```typescript
server.use(
  http.get('/api/cart', () => HttpResponse.json({ items: [{ price: 99.99, qty: 1 }] }))
)
render(<OrderSummary />)
await screen.findByText('$99.99')
```

---

### Use Real Providers for Third-Party Libraries

**Detection**:
```bash
# vi.mock on node_modules (not starting with ./ or ../)
grep -rn "vi\.mock('" --include="*.test.ts" | grep -v "vi\.mock('\." | grep -v "msw\|vitest\|node:"
rg "vi\.mock\('(?!\.)" --type ts | grep -v msw
```

**Signal**:
```typescript
// BAD: mocking React Router internals
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useParams: () => ({ id: '1' }),
}))
```

**Why this matters**: When `react-router-dom` updates its API, the mock silently diverges. The test passes but the real component breaks in production. You're testing against a fake contract you wrote yourself.

**Preferred action:** Use real providers in tests. For React Router v6+:
```typescript
import { MemoryRouter } from 'react-router-dom'

function renderWithRouter(ui: React.ReactElement, { route = '/' } = {}) {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>)
}

it('navigates to product page', async () => {
  const { user } = renderWithRouter(<ProductList />, { route: '/products' })
  await user.click(screen.getByText('Widget Pro'))
  expect(screen.getByRole('heading', { name: 'Widget Pro' })).toBeInTheDocument()
})
```

---

### Assert on User-Visible Behavior First

**Detection**:
```bash
# Test files with toHaveBeenCalledWith but no toBeInTheDocument/toBe
rg 'toHaveBeenCalledWith' --type ts -l | xargs rg -L 'toBeInTheDocument\|toBe\b\|toEqual'
grep -rn 'expect.*toHaveBeenCalled' --include="*.test.ts" | wc -l
```

**Signal**:
```typescript
// BAD: asserting implementation, not behavior
it('saves user preferences', async () => {
  const saveSpy = vi.spyOn(userService, 'savePreferences')
  await user.click(screen.getByRole('button', { name: /save/i }))
  expect(saveSpy).toHaveBeenCalledWith({ theme: 'dark', locale: 'en' })
  // Never checks that the UI updated to reflect the saved state
})
```

**Why this matters**: This test passes even if `savePreferences` is called but returns an error the component silently swallows. Or if the UI shows a stale state. It verifies that a function was invoked, not that the user got the right outcome.

**Preferred action:** Assert on user-visible result first; use call assertions as secondary verification:
```typescript
it('saves user preferences', async () => {
  server.use(http.post('/api/preferences', () => new HttpResponse(null, { status: 204 })))

  await user.click(screen.getByRole('button', { name: /save/i }))

  // Primary: user sees confirmation
  await screen.findByText(/preferences saved/i)
  // Secondary: correct payload was sent (via MSW request inspection)
})
```

---

### Suppress Only Specific Known Warnings

**Detection**:
```bash
grep -rn 'spyOn.*console.*error\|mock.*console\.error' --include="*.test.ts" --include="*.test.tsx"
rg 'console\.error.*mockImplementation\(\s*\)' --type ts
```

**Signal**:
```typescript
// BAD: blanket suppression hides real problems
beforeAll(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
```

**Why this matters**: This suppresses all React prop-type warnings, act() warnings, and real errors. A broken component renders silently. Errors that should fail the test pass unnoticed.

**Preferred action:** Suppress only the specific known warning; assert others still fire:
```typescript
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation((msg) => {
    if (typeof msg === 'string' && msg.includes('act(...)')) return
    // Let all other errors through (still logged, test may still fail)
    console.warn('[console.error suppressed in test]:', msg)
  })
})
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `The module ... has already been mocked` | `vi.mock` called twice for same path | Remove duplicate mock; use `server.use()` for per-test override |
| `TypeError: X is not a function` after `vi.mock` | Module mock returns wrong shape | Add `vi.importActual` to preserve real exports |
| `Mock function called 0 times` | Wrong spy target (default vs named export) | Default exports need `{ default: vi.fn() }` in factory |
| `No handler for POST /api/X` (MSW error mode) | Test exercises API call not in default handlers | Add handler to `setupServer` defaults or to the specific test |
| `Cannot spy on a primitive value` | Trying to spy on a string/number | Only spy on object methods; wrap primitive in an object |
| `mockResolvedValue is not a function` | `vi.fn()` not called before `.mockResolvedValue` | Create spy with `vi.fn()` first, then chain `.mockResolvedValue()` |

---

## See Also

- `vitest-patterns.md` — `vi.mock`, `vi.spyOn`, `vi.fn` API details and lifecycle
- `async-testing.md` — MSW server setup, `waitFor`, async assertion patterns
