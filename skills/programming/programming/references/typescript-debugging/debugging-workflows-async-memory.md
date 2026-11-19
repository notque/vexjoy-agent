# TypeScript Debugging Workflows: Async, Bisect, Memory

Workflows 4-6 and the systematic debugging checklist. Workflows 1-3 (race conditions, type errors, production runtime errors): [debugging-workflows.md](debugging-workflows.md).

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
