# Error Handling Reference
<!-- Loaded by react-native-engineer when task involves error boundaries, Sentry, crash recovery, try/catch, ErrorBoundary, error states -->

> **Scope**: Production error handling in React Native: Error Boundaries, Sentry integration, promise rejection capture, and crash-safe rendering patterns.
> **Version range**: React 18+, React Native 0.72+, @sentry/react-native 5+
> **Generated**: 2026-04-12 — verify Sentry DSN config patterns against current @sentry/react-native docs

---

## Overview

React Native apps crash hard on unhandled errors — there's no browser error overlay to recover from. A production crash closes the app. The three failure modes are: (1) synchronous render errors without an `ErrorBoundary`, (2) unhandled promise rejections that swallow failures silently, and (3) native module errors that surface as cryptic red boxes during development but silent crashes in production builds.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `ErrorBoundary` (class component) | React 16+ | catching render-phase errors | async errors inside event handlers |
| `react-native-error-boundary` | any | quick ErrorBoundary with fallback UI | you need custom recovery logic |
| `Sentry.init()` in app entry | `@sentry/react-native 5+` | production crash reporting | local dev — noise ratio is high |
| `unhandledRejection` global handler | RN 0.68+ | catching all unhandled promise rejections | replacing proper `try/catch` per call |
| `InteractionManager.runAfterInteractions` | any | deferring error-prone work past animation frames | time-sensitive data fetching |

---

## Correct Patterns

### Wrap Screen Roots in ErrorBoundary

Every screen-level component should be wrapped in an `ErrorBoundary`. A crash in one screen should not bring down the entire app.

```tsx
import { ErrorBoundary } from 'react-error-boundary'

function FeedScreen() {
  return (
    <ErrorBoundary
      fallbackRender={({ error, resetErrorBoundary }) => (
        <View style={styles.errorContainer}>
          <Text>Something went wrong.</Text>
          <Pressable onPress={resetErrorBoundary}>
            <Text>Try again</Text>
          </Pressable>
        </View>
      )}
      onError={(error, info) => {
        // report to Sentry or your crash service
        captureException(error, { extra: { componentStack: info.componentStack } })
      }}
    >
      <FeedContent />
    </ErrorBoundary>
  )
}
```

**Why**: Without a boundary, any render-phase throw (null dereference, bad prop type, failed deserialization) crashes the entire React tree. The boundary catches it, renders fallback UI, and lets the user recover without restarting the app.

---

### Initialize Sentry Before the React Tree

Sentry must be initialized before `AppRegistry.registerComponent` — before any React component mounts. Errors during app startup are otherwise invisible.

```ts
// index.js (app entry — before importing App)
import * as Sentry from '@sentry/react-native'

Sentry.init({
  dsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
  environment: process.env.EXPO_PUBLIC_ENV ?? 'development',
  // Sample at 10% in production to control event volume
  tracesSampleRate: process.env.EXPO_PUBLIC_ENV === 'production' ? 0.1 : 1.0,
  enabled: process.env.EXPO_PUBLIC_ENV !== 'development',
})

// Then import and register App
import { registerRootComponent } from 'expo'
import App from './App'
registerRootComponent(App)
```

**Why**: Errors that occur during app initialization (config load, font loading, initial navigation mount) are lost if Sentry isn't set up first. `EXPO_PUBLIC_*` variables are safe to embed in the bundle — do not use secret keys here.

---

### Capture Unhandled Promise Rejections

React Native 0.68+ surfaces unhandled rejections as yellow warnings in dev, but in production they silently swallow errors. Install a global handler.

```ts
// App.tsx or index.js setup
const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
  console.error('Unhandled promise rejection:', event.reason)
  captureException(event.reason, { tags: { type: 'unhandled_rejection' } })
  // Don't call event.preventDefault() — let RN's default handling also run
}

// Node-style (Hermes engine, RN 0.64+)
if (global.HermesInternal) {
  const tracking = require('promise/setimmediate/rejection-tracking')
  tracking.enable({
    allRejections: true,
    onUnhandled: (id: number, rejection: unknown) => {
      captureException(rejection, { tags: { rejection_id: id } })
    },
  })
}
```

**Why**: Fire-and-forget async calls (`fetchUser()` without `await` or `.catch()`) fail silently in production. The global handler catches them for visibility without requiring every call site to add error handling.

---

### Type Fetch Errors — Never Assume the Shape

Network errors in React Native come in three shapes: `Error` instances from `fetch` throwing on network failure, JSON parse errors when the server returns HTML (503 page), and valid JSON with an error status code.

```ts
async function fetchUser(id: string): Promise<User> {
  let res: Response

  try {
    res = await fetch(`${API_URL}/users/${id}`)
  } catch (err) {
    // Network failure — no response at all
    throw new Error(`Network error fetching user ${id}: ${String(err)}`)
  }

  if (!res.ok) {
    // Server returned 4xx/5xx — body may not be JSON
    const text = await res.text().catch(() => '<unreadable>')
    throw new Error(`HTTP ${res.status} fetching user ${id}: ${text.slice(0, 200)}`)
  }

  try {
    return res.json() as Promise<User>
  } catch (err) {
    throw new Error(`Invalid JSON for user ${id}: ${String(err)}`)
  }
}
```

**Why**: `fetch` does NOT throw on 4xx/5xx status codes. Calling `res.json()` on a 503 HTML error page throws a parse error with a misleading message. Wrapping each phase separately gives actionable error messages in Sentry.

---

## Anti-Pattern Catalog

### ❌ Using `console.error` as the Only Error Reporting

**Detection**:
```bash
grep -rn 'console\.error' --include="*.tsx" --include="*.ts" | grep -v "\.test\." | grep -v "\.spec\."
rg 'console\.error' --type ts --type tsx | grep -v test
```

**What it looks like**:
```tsx
try {
  await syncData()
} catch (err) {
  console.error('Sync failed', err)  // invisible in production
}
```

**Why wrong**: `console.error` is stripped or suppressed in production builds. Errors logged this way are invisible to on-call and never trigger alerts. Crashes go undetected until users report them.

**Fix**:
```tsx
import { captureException } from '@sentry/react-native'

try {
  await syncData()
} catch (err) {
  captureException(err, { tags: { operation: 'sync' } })
  // optionally also console.error in dev
  if (__DEV__) console.error('Sync failed', err)
}
```

---

### ❌ Empty Catch Blocks

**Detection**:
```bash
grep -rn 'catch\s*(.*)\s*{\s*}' --include="*.ts" --include="*.tsx"
rg 'catch\s*\(.*\)\s*\{\s*\}' --type ts
```

**What it looks like**:
```ts
try {
  await loadUserPreferences()
} catch (err) {
  // TODO: handle this
}
```

**Why wrong**: Silent swallow. The error is gone. The app is now in an inconsistent state — preferences were not loaded, but no error boundary fired, no fallback rendered, no alert triggered. These are the hardest bugs to diagnose because there's no stack trace.

**Fix**: At minimum, report and reset to a safe default:
```ts
try {
  await loadUserPreferences()
} catch (err) {
  captureException(err)
  // explicit fallback state
  await setDefaultPreferences()
}
```

---

### ❌ Missing Error Boundary at Navigation Root

**Detection**:
```bash
grep -rn 'Stack.Screen\|Tabs.Screen' --include="*.tsx" | grep -v ErrorBoundary
rg 'NavigationContainer' --type tsx | grep -B5 -A10 'NavigationContainer'
```

**What it looks like**:
```tsx
export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="(tabs)" component={TabsLayout} />
      <Stack.Screen name="profile" component={ProfileScreen} />
    </Stack>
  )
}
```

**Why wrong**: If `ProfileScreen` throws during render, it unwinds the entire navigation tree. With no boundary, the app white-screens. Users must force-quit.

**Fix**: Wrap each screen's content component in an ErrorBoundary, or add a root-level boundary around the entire navigator:
```tsx
export default function RootLayout() {
  return (
    <ErrorBoundary fallback={<AppCrashFallback />} onError={captureException}>
      <Stack>
        <Stack.Screen name="(tabs)" component={TabsLayout} />
        <Stack.Screen name="profile" component={ProfileScreen} />
      </Stack>
    </ErrorBoundary>
  )
}
```

---

### ❌ Accessing `.data` on an Unvalidated API Response

**Detection**:
```bash
grep -rn '\.data\.' --include="*.ts" --include="*.tsx" | grep -v "\.test\." | grep "await fetch\|axios\|useFetch"
rg '(await\s+\w+\(.*\))\.data\.' --type ts
```

**What it looks like**:
```ts
const response = await fetch('/api/user')
const json = await response.json()
setUser(json.data.profile.name)  // throws if data or profile is undefined
```

**Why wrong**: API contracts break. A server returns `{ error: "not found" }` instead of `{ data: { profile: ... } }`. The chain `.data.profile.name` throws `Cannot read properties of undefined (reading 'profile')` — a crash with a misleading error message.

**Fix**: Validate the response shape before accessing nested paths, or use optional chaining with a fallback:
```ts
const json = await response.json()
if (!json.data?.profile) {
  throw new Error(`Unexpected API shape: ${JSON.stringify(json).slice(0, 200)}`)
}
setUser(json.data.profile.name)
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `TypeError: Cannot read properties of undefined (reading 'X')` | Null/undefined accessed via property chain after API response | Add optional chaining or explicit null check before deep access |
| `Network request failed` | No network or wrong host in dev | Check `__DEV__` vs production API URL; verify device can reach the API host |
| `JSON Parse error: Unrecognized token '<'` | Server returned HTML (error page) instead of JSON | Check `res.ok` before calling `res.json()` — server returned 4xx/5xx |
| `Maximum update depth exceeded` | State setter called inside render or effect without dependency guard | Move setter into event handler or add correct deps array to `useEffect` |
| `Warning: Can't perform a React state update on an unmounted component` | Async operation completes after component unmounts | Return cleanup function from `useEffect` that cancels in-flight request |
| `Unhandled promise rejection: Error: Invariant Violation` | Native module call outside the main thread context | Move native module calls to a dedicated service, not inside callbacks |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RN 0.71 | `Promise.allSettled` enabled by default in Hermes | Use `allSettled` instead of `all` when you want partial results on failure |
| RN 0.73 | Unhandled rejection handling improved in Hermes | Stack traces from async errors are now preserved — update Sentry sourcemap upload |
| React 18 | `startTransition` errors fall back to nearest ErrorBoundary | Transitions that throw no longer crash the whole tree |
| `@sentry/react-native` 5.0 | `Sentry.wrap(App)` deprecated — use `Sentry.init()` then `withSentry(App)` | Update app entry if using older Sentry integration pattern |

---

## Detection Commands Reference

```bash
# Find console.error used as only error reporting (not in tests)
grep -rn 'console\.error' --include="*.tsx" --include="*.ts" | grep -v "\.test\.\|\.spec\."

# Find empty catch blocks
grep -rn 'catch\s*(.*)\s*{\s*}' --include="*.ts" --include="*.tsx"

# Find fetch calls without .ok check
grep -rn 'await fetch\|\.json()' --include="*.ts" --include="*.tsx" | grep -v 'res\.ok\|response\.ok'

# Find deep property access on API responses without null guards
grep -rn '\.data\.\|\.result\.' --include="*.ts" --include="*.tsx" | grep -v '\?\.'

# Find missing ErrorBoundary around screen components (Expo Router pattern)
grep -rn 'Stack\.Screen\|Tabs\.Screen' --include="*.tsx" | grep -v 'ErrorBoundary'
```

---

## See Also

- `rendering-patterns.md` — Text component crashes and conditional render crashes during render phase
- `state-management.md` — Stale state that causes incorrect error recovery
