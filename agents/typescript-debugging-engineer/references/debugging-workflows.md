# TypeScript Debugging Workflows

Systematic debugging methodology for TypeScript applications combining scientific method with TypeScript-specific tooling.

## Workflow 1: Debugging Race Conditions

**Goal**: Identify and fix async operations that race unexpectedly.

### Phase 1: REPRODUCE
- [ ] Create minimal test case that forces the race
- [ ] Add artificial delays to control timing
- [ ] Confirm race occurs reliably

**Detection**:
```typescript
// Add delays to force specific order
async function testRace() {
  const promise1 = fetchData().then(async (data) => {
    await new Promise(r => setTimeout(r, 1000)) // Force delay
    setState(data)
  })

  const promise2 = clearState()

  // Does clearState() win the race?
  await Promise.all([promise1, promise2])
}
```

### Phase 2: IDENTIFY
- [ ] Map all async operations in component/module
- [ ] Identify which promises are racing
- [ ] Determine correct ordering

**Pattern Recognition**:
- Cleanup running before async complete
- Multiple setState calls racing
- Unmounted component updates

### Phase 3: FIX
- [ ] Add cleanup tracking (abort controllers)
- [ ] Use discriminated unions for state
- [ ] Implement proper cancellation

**Solution Pattern**:
```typescript
useEffect(() => {
  const controller = new AbortController()

  async function load() {
    try {
      const data = await fetchData({ signal: controller.signal })
      setState({ status: 'success', data })
    } catch (error) {
      if (error.name !== 'AbortError') {
        setState({ status: 'error', error: error.message })
      }
    }
  }

  load()

  return () => controller.abort() // Cleanup
}, [])
```

### Phase 4: VERIFY
- [ ] Test passes with artificial delays
- [ ] Test passes without delays
- [ ] No regressions

---

## Workflow 2: Debugging Type Errors

**Goal**: Resolve complex TypeScript type mismatches.

### Phase 1: DECODE
- [ ] Read full error message
- [ ] Identify TS error code (e.g., TS2322)
- [ ] Note which types don't match

**Common Codes**:
- `TS2322`: Type not assignable
- `TS2345`: Argument type mismatch
- `TS2339`: Property doesn't exist
- `TS2571`: Object is possibly null/undefined

### Phase 2: COMPARE
- [ ] Examine both type definitions
- [ ] Find structural differences
- [ ] Check for optional vs required fields

**Investigation**:
```typescript
// Error: Type X is not assignable to Y
// Step 1: Print both types
type ShowType<T> = {
  [K in keyof T]: T[K]
}

type UserActual = ShowType<typeof userData>
type UserExpected = ShowType<User>

// Step 2: Compare field by field
// - Missing fields?
// - Wrong types?
// - Optional vs required?
```

### Phase 3: RESOLVE
- [ ] Add missing fields
- [ ] Fix type definitions
- [ ] Add runtime validation if external data

**Solutions**:
```typescript
// Option 1: Add missing fields
const user: User = {
  ...partialData,
  missingField: defaultValue
}

// Option 2: Make fields optional
interface User {
  id: string
  name?: string // Optional
}

// Option 3: Use utility types
const user: Partial<User> = partialData

// Option 4: Validate with Zod
const user = UserSchema.parse(untrustedData)
```

---

## Workflow 3: Debugging Production Runtime Errors

**Goal**: Diagnose and fix errors that only occur in production.

### Phase 1: CAPTURE
- [ ] Set up error tracking (Sentry, LogRocket)
- [ ] Ensure source maps uploaded
- [ ] Capture full error context

**Sentry Setup**:
```typescript
import * as Sentry from '@sentry/react'

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  integrations: [
    new Sentry.BrowserTracing(),
    new Sentry.Replay()
  ],
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  beforeSend(event, hint) {
    // Add custom context
    event.extra = {
      ...event.extra,
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`
    }
    return event
  }
})
```

### Phase 2: ANALYZE
- [ ] Review stack trace (ignore node_modules)
- [ ] Check error frequency/pattern
- [ ] Identify commonalities (browser, OS, user flow)

**Key Questions**:
- Does it happen in specific browsers?
- Does it happen after specific user actions?
- Are there null/undefined values?
- Is it a race condition (timing-dependent)?

### Phase 3: REPRODUCE
- [ ] Recreate locally with same conditions
- [ ] Add logging at suspected points
- [ ] Use debugger breakpoints

**Reproduction Checklist**:
```typescript
// Add debug logging
console.log('[DEBUG] Component mounted', { props, state })
console.log('[DEBUG] Before API call', { params })
console.log('[DEBUG] API response', { data })

// Add assertions
if (!user) {
  console.error('[ASSERTION] User should exist', { context })
  throw new Error('User undefined in unexpected location')
}
```

### Phase 4: FIX
- [ ] Add defensive checks
- [ ] Add error boundaries
- [ ] Validate data earlier

**Fix Patterns**:
```typescript
// Error Boundary
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    Sentry.captureException(error, { extra: info })
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />
    }
    return this.props.children
  }
}

// Defensive Checks
function processUser(user: User | null) {
  if (!user) {
    console.error('[ERROR] User is null', { trace: new Error().stack })
    return null
  }
  // Safe to use user
}
```

---

## Workflow 4: Debugging Async/Await Issues

**Goal**: Fix waterfall requests, floating promises, and error swallowing.

### Phase 1: MAP
- [ ] Identify all async operations
- [ ] Check for proper error handling
- [ ] Detect sequential vs parallel patterns

**Detection Script**:
```bash
# Find floating promises (missing await/return)
grep -rn "^\s*[a-zA-Z].*\.then(" src/ --include="*.ts" --include="*.tsx"

# Find missing error handlers
grep -rn "await.*fetch" src/ -A 5 | grep -v "catch\|try"
```

### Phase 2: IDENTIFY ISSUES

**Floating Promises**:
```typescript
// ❌ Bad - Promise not awaited or returned
function saveData() {
  api.save(data) // Floats away, errors swallowed
}

// ✅ Good
async function saveData() {
  await api.save(data)
}
```

**Waterfall Requests**:
```typescript
// ❌ Bad - Sequential when could be parallel
async function load() {
  const users = await fetchUsers() // Wait
  const posts = await fetchPosts() // Then wait again
  return { users, posts }
}

// ✅ Good - Parallel
async function load() {
  const [users, posts] = await Promise.all([
    fetchUsers(),
    fetchPosts()
  ])
  return { users, posts }
}
```

**Error Swallowing**:
```typescript
// ❌ Bad - Errors disappear
try {
  await riskyOperation()
} catch (error) {
  console.log(error) // Logged but not handled
}

// ✅ Good
try {
  await riskyOperation()
} catch (error) {
  setError(error.message)
  Sentry.captureException(error)
  throw error // Re-throw if needed
}
```

### Phase 3: FIX
- [ ] Add proper await/return
- [ ] Parallelize independent operations
- [ ] Handle all errors

### Phase 4: VERIFY
- [ ] All promises awaited
- [ ] ESLint no-floating-promises passes
- [ ] Performance improved (if parallelized)

---

## Workflow 5: Git Bisect for Regressions

**Goal**: Find exact commit that introduced a bug.

### Phase 1: SETUP
- [ ] Identify last known good commit
- [ ] Identify first known bad commit
- [ ] Create automated test for bug

```bash
# Start bisect
git bisect start
git bisect bad HEAD  # Current broken state
git bisect good abc123  # Last working commit
```

### Phase 2: TEST
- [ ] Run automated test at each step
- [ ] Mark commit as good or bad

```bash
# At each bisect step
npm install
npm run build
npm test  # Or manual test

# Mark result
git bisect good  # If test passes
git bisect bad   # If test fails
```

### Phase 3: AUTOMATE
- [ ] Create test script
- [ ] Let bisect run automatically

```bash
# Automated bisect
git bisect run npm test

# Or custom script
git bisect run ./test-for-bug.sh
```

**Test Script Example**:
```bash
#!/bin/bash
# test-for-bug.sh

set -e
npm install --silent
npm run build --silent

# Test for specific bug
npm test -- --grep "user login" || exit 1

exit 0
```

### Phase 4: ANALYZE
- [ ] Review commit that introduced bug
- [ ] Understand what changed
- [ ] Fix or revert

```bash
# Found problematic commit
git bisect reset
git show <commit-hash>  # Review changes
```

---

## Workflow 6: Debugging Memory Leaks

**Goal**: Identify and fix JavaScript/TypeScript memory leaks.

### Phase 1: DETECT
- [ ] Profile with Chrome DevTools
- [ ] Take heap snapshots
- [ ] Compare snapshots over time

```typescript
// Add memory monitoring
if (process.env.NODE_ENV === 'development') {
  setInterval(() => {
    if (performance.memory) {
      console.log('Memory:', {
        used: Math.round(performance.memory.usedJSHeapSize / 1048576) + ' MB',
        total: Math.round(performance.memory.totalJSHeapSize / 1048576) + ' MB'
      })
    }
  }, 5000)
}
```

### Phase 2: IDENTIFY
Common leak sources:
- Event listeners not removed
- Timers not cleared
- Global references
- Closures capturing large objects

**Detection**:
```typescript
// Check for leaked listeners
function checkListeners() {
  const listeners = (window as any).getEventListeners?.(document)
  console.log('Active listeners:', listeners)
}

// Check for leaked timers
const originalSetInterval = window.setInterval
let activeTimers = 0
window.setInterval = function(...args) {
  activeTimers++
  console.log(`Active timers: ${activeTimers}`)
  return originalSetInterval(...args)
}
```

### Phase 3: FIX
- [ ] Remove event listeners in cleanup
- [ ] Clear timers and intervals
- [ ] Break circular references

**Fix Patterns**:
```typescript
// React cleanup
useEffect(() => {
  const handler = () => console.log('resize')
  window.addEventListener('resize', handler)

  return () => {
    window.removeEventListener('resize', handler)
  }
}, [])

// Timer cleanup
useEffect(() => {
  const timer = setInterval(() => {
    console.log('tick')
  }, 1000)

  return () => clearInterval(timer)
}, [])

// Abort controller
useEffect(() => {
  const controller = new AbortController()

  fetch('/api/data', { signal: controller.signal })
    .then(r => r.json())
    .then(data => setState(data))

  return () => controller.abort()
}, [])
```

### Phase 4: VERIFY
- [ ] Heap snapshots show no growth
- [ ] Memory usage stable over time
- [ ] All cleanup functions called

---

## Systematic Debugging Checklist

Before proceeding with any fix, verify:

1. **Root Cause Identified**
   - [ ] Hypothesis stated clearly
   - [ ] Evidence supports hypothesis
   - [ ] Reproduction case exists

2. **Fix Validated**
   - [ ] Reproduction case now passes
   - [ ] No new errors introduced
   - [ ] Performance not degraded

3. **Prevention Added**
   - [ ] Test added to prevent regression
   - [ ] Type safety improved
   - [ ] Error handling comprehensive

4. **Documentation Updated**
   - [ ] Comments explain why, not what
   - [ ] Error messages actionable
   - [ ] Logging sufficient for future debugging
