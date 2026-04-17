# Vitest Patterns Reference

> **Scope**: Vitest 1.x/2.x configuration, test lifecycle, spy/mock APIs, and coverage setup. Does NOT cover React component rendering (see async-testing.md) or Playwright E2E.
> **Version range**: Vitest 1.0+ (stable API); Vitest 2.0+ notes flagged inline
> **Generated**: 2026-04-15 — verify against current vitest.dev release notes

---

## Overview

Vitest is the primary test framework for this agent. Its Jest-compatible API allows migration but introduces breaking differences around fake timers, module mocking, and snapshot serializers. The most common failure mode is treating Vitest as if it were Jest: `jest.mock()` calls silently fail, `jest.fn()` is missing, and `beforeAll` ordering differs in concurrent mode.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `vi.fn()` | 1.0+ | Creating a spy / mock function | `jest.fn()` (not available) |
| `vi.mock('module')` | 1.0+ | Auto-mocking an entire module | Mocking only one export (use `vi.spyOn`) |
| `vi.spyOn(obj, 'method')` | 1.0+ | Spying on an existing method | Creating a standalone mock function |
| `vi.useFakeTimers()` | 1.0+ | Testing `setTimeout`, `setInterval`, `Date` | Tests with real network/async I/O |
| `vi.importActual()` | 1.0+ | Partial module mock preserving real implementations | Full module replacement |
| `pool: 'forks'` | 1.1+ | Node APIs needing true process isolation | Browser-mode tests |
| `browser: true` mode | 2.0+ | Running tests in real browser (Chromium/Firefox) | Unit tests (use jsdom) |

---

## Correct Patterns

### Vitest Configuration — vitest.config.ts

Required coverage provider and threshold setup. Missing `provider: 'v8'` causes silent 0% branch coverage.

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',         // or 'node' for backend tests
    coverage: {
      provider: 'v8',             // 'istanbul' also valid; v8 is faster
      reporter: ['text', 'html', 'json'],
      thresholds: {
        lines: 80,
        branches: 80,             // REQUIRED — do not omit
        functions: 80,
        statements: 80,
      },
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/**/*.stories.*'],
    },
    globals: false,               // explicit imports preferred over globals
    setupFiles: ['./src/test/setup.ts'],
  },
})
```

**Why**: Without `thresholds.branches`, Vitest reports lines only. A function with `if/else` and only the happy path tested reads 100% lines but 50% branches — the threshold won't catch it.

---

### Spy Setup and Teardown

```typescript
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as api from '../api/users'

describe('UserService', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    fetchSpy = vi.spyOn(api, 'fetchUser').mockResolvedValue({ id: 1, name: 'Alice' })
  })

  afterEach(() => {
    vi.restoreAllMocks()  // REQUIRED — restores original implementations
  })

  it('calls fetchUser with the correct id', async () => {
    await getUserById(1)
    expect(fetchSpy).toHaveBeenCalledWith(1)
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })
})
```

**Why**: `vi.restoreAllMocks()` in `afterEach` prevents spy state leaking between tests. `vi.clearAllMocks()` resets call counts only; `vi.restoreAllMocks()` also removes mock implementations.

---

### Partial Module Mock with vi.importActual

```typescript
vi.mock('../services/email', async () => {
  const actual = await vi.importActual<typeof import('../services/email')>('../services/email')
  return {
    ...actual,
    sendEmail: vi.fn().mockResolvedValue({ success: true }),  // only mock sendEmail
  }
})
```

**Why**: Without `vi.importActual`, all exports become `undefined`. This is the correct pattern when you want to mock one function but keep the rest of the module real.

---

### Fake Timers for setTimeout/setInterval

```typescript
import { vi, it, expect, beforeEach, afterEach } from 'vitest'

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })  // always restore

it('fires callback after 1 second delay', () => {
  const cb = vi.fn()
  scheduleCallback(cb, 1000)

  expect(cb).not.toHaveBeenCalled()
  vi.advanceTimersByTime(1000)
  expect(cb).toHaveBeenCalledTimes(1)
})

it('tests a Date.now() timestamp', () => {
  vi.setSystemTime(new Date('2026-01-01T00:00:00Z'))
  const result = getTimestamp()
  expect(result).toBe('2026-01-01')
})
```

---

## Anti-Pattern Catalog

### ❌ Using jest.mock() or jest.fn() in Vitest files

**Detection**:
```bash
grep -rn 'jest\.mock\|jest\.fn\|jest\.spyOn' --include="*.test.ts" --include="*.test.tsx" --include="*.spec.ts"
rg 'jest\.(mock|fn|spyOn|clearAllMocks|resetAllMocks)' --type ts
```

**What it looks like**:
```typescript
// BAD: jest.fn() is undefined in Vitest
const mockFn = jest.fn()
jest.mock('../utils')
jest.spyOn(console, 'error')
```

**Why wrong**: Vitest does not polyfill the `jest` global by default. These calls throw `ReferenceError: jest is not defined` at runtime or produce silent `undefined` if `globals: true` is configured with a partial shim.

**Do instead:**
```typescript
import { vi } from 'vitest'
const mockFn = vi.fn()
vi.mock('../utils')
vi.spyOn(console, 'error')
```

**Version note**: Vitest 1.0+ provides a `jest` compatibility shim via `globals: true` + `@vitest/compat`, but this is opt-in and not recommended for new code.

---

### ❌ Missing vi.restoreAllMocks() — Spy Leak Between Tests

**Detection**:
```bash
grep -rn 'vi\.spyOn' --include="*.test.ts" --include="*.test.tsx" -l | xargs grep -L 'restoreAllMocks\|resetAllMocks'
rg 'vi\.spyOn' --type ts -l | xargs rg -l 'restoreAllMocks' --files-without-match
```

**What it looks like**:
```typescript
describe('Suite A', () => {
  it('mocks fetch', () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response('{}'))
    // NO afterEach/vi.restoreAllMocks()
  })
})

describe('Suite B', () => {
  it('uses real fetch — but it is still mocked!', async () => {
    // fetch is still the spy from Suite A
  })
})
```

**Why wrong**: Spy state persists across test files in the same worker thread. Tests in unrelated files fail with unexpected mock behavior. Produces order-dependent failures that are hard to reproduce.

**Do instead:** Always pair `vi.spyOn` with `afterEach(() => vi.restoreAllMocks())`. Or configure globally:
```typescript
test: { restoreMocks: true }  // auto-restore after each test in vitest.config.ts
```

---

### ❌ No Branch Coverage Threshold

**Detection**:
```bash
grep -rn 'thresholds' vitest.config.ts vitest.config.js
rg 'thresholds' vitest.config.ts | grep -v branches
```

**What it looks like**:
```typescript
coverage: {
  thresholds: {
    lines: 80,
    functions: 80,
    // branches MISSING — silently passes with 0% branch coverage
  }
}
```

**Why wrong**: A function with `if (user.isAdmin)` tested only with admin users shows 100% line coverage but 0% branch coverage. The non-admin code path is completely untested. CI passes, bugs ship.

**Do instead:** Always include `branches: 80` in thresholds (see Correct Patterns section above).

---

### ❌ External Snapshot Files Instead of Inline

**Detection**:
```bash
find . -name "*.snap" | grep -v node_modules | wc -l
rg 'toMatchSnapshot\(\)' --type ts
```

**What it looks like**:
```typescript
it('renders correctly', () => {
  const { container } = render(<Button label="Click me" />)
  expect(container).toMatchSnapshot()  // creates external .snap file
})
```

**Why wrong**: External `.snap` files are updated with `--updateSnapshot` without review. Developers mindlessly accept them in CI, converting regression detectors into rubber stamps.

**Do instead:** Use inline snapshots or explicit behavioral assertions:
```typescript
// Inline snapshot — diff visible in the PR
expect(button).toMatchInlineSnapshot(`<button class="btn">Click me</button>`)

// Better — test the behavior
expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `ReferenceError: jest is not defined` | `jest.fn()` called instead of `vi.fn()` | Replace `jest.` with `vi.` throughout |
| `Error: Cannot mock a module that has no exports` | `vi.mock()` path is wrong | Verify import path matches exactly |
| `Your test suite must contain at least one test` | Only `describe` blocks, no `it`/`test` | Add at least one `it()` call |
| `Coverage threshold not met: branches (X% < 80%)` | Conditional paths not tested | Add tests for `else`/`catch` branches |
| `Cannot access 'X' before initialization` in mock | Hoisting issue with `vi.mock` factory accessing outer variable | Move variable inside the factory function |
| `TypeError: Cannot redefine property: default` | Mocking ES module default export | Use `vi.spyOn` on the object or `vi.importActual` pattern |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Vitest 1.0 | Stable `vi` API replaces `jest` compat shim | All new code should use `vi.*` |
| Vitest 1.1 | `pool: 'forks'` option added for process isolation | Use for tests requiring `process.env` mutation |
| Vitest 1.3 | `vi.waitFor()` added | Replaces custom polling loops in unit tests |
| Vitest 2.0 | Browser mode stable; `jsdom` no longer default environment | Set `environment: 'jsdom'` explicitly in config |
| Vitest 2.0 | `coverage.provider` defaults to `'v8'`; `'c8'` removed | Remove deprecated `provider: 'c8'` references |

---

## Detection Commands Reference

```bash
# jest.* calls that should be vi.*
grep -rn 'jest\.' --include="*.test.ts" --include="*.test.tsx" --include="*.spec.ts"

# Spy files missing restoreAllMocks
grep -rn 'vi\.spyOn' --include="*.test.ts" -l | xargs grep -L 'restoreAllMocks'

# Missing branch threshold in vitest config
grep -A5 'thresholds' vitest.config.ts | grep -v branches

# External snapshot files (prefer inline)
find . -name "*.snap" | grep -v node_modules

# Test files with no assertions
rg 'it\(' --type ts -l | xargs rg -L 'expect\('
```

---

## See Also

- `async-testing.md` — waitFor, async component testing, MSW setup
- `mocking-patterns.md` — what to mock, MSW vs vi.mock, test doubles taxonomy
