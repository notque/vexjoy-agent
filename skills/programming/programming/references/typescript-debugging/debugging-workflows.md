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

Workflows 4-6 (async/await, git bisect, memory leaks) and the systematic debugging checklist: [debugging-workflows-async-memory.md](debugging-workflows-async-memory.md).
