# Error Handling Reference
<!-- Loaded by react-native-engineer when task involves error boundaries, Sentry, crash recovery, try/catch, ErrorBoundary, error states -->

> **Scope**: Production error handling: Error Boundaries, Sentry, promise rejection capture, crash-safe rendering.
> **Version range**: React 18+, React Native 0.72+, @sentry/react-native 5+
> **Generated**: 2026-04-12

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `ErrorBoundary` (class component) | React 16+ | Render-phase errors | Async errors in event handlers |
| `react-native-error-boundary` | any | Quick ErrorBoundary with fallback UI | Custom recovery logic needed |
| `Sentry.init()` in app entry | `@sentry/react-native 5+` | Production crash reporting | Local dev |
| `unhandledRejection` global handler | RN 0.68+ | All unhandled promise rejections | Replacing proper `try/catch` |
| `InteractionManager.runAfterInteractions` | any | Deferring error-prone work past animations | Time-sensitive fetching |

---

## Correct Patterns

### Wrap Screen Roots in ErrorBoundary

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
        captureException(error, { extra: { componentStack: info.componentStack } })
      }}
    >
      <FeedContent />
    </ErrorBoundary>
  )
}
```

Without a boundary, any render-phase throw crashes the entire React tree.

---

### Initialize Sentry Before the React Tree

```ts
// index.js — before importing App
import * as Sentry from '@sentry/react-native'

Sentry.init({
  dsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
  environment: process.env.EXPO_PUBLIC_ENV ?? 'development',
  tracesSampleRate: process.env.EXPO_PUBLIC_ENV === 'production' ? 0.1 : 1.0,
  enabled: process.env.EXPO_PUBLIC_ENV !== 'development',
})

import { registerRootComponent } from 'expo'
import App from './App'
registerRootComponent(App)
```

Errors during app initialization are lost if Sentry isn't set up first.

---

### Capture Unhandled Promise Rejections

```ts
const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
  console.error('Unhandled promise rejection:', event.reason)
  captureException(event.reason, { tags: { type: 'unhandled_rejection' } })
}

// Hermes engine (RN 0.64+)
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

Fire-and-forget async calls fail silently in production without a global handler.

---

### Type Fetch Errors — Never Assume the Shape

```ts
async function fetchUser(id: string): Promise<User> {
  let res: Response

  try {
    res = await fetch(`${API_URL}/users/${id}`)
  } catch (err) {
    throw new Error(`Network error fetching user ${id}: ${String(err)}`)
  }

  if (!res.ok) {
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

`fetch` does NOT throw on 4xx/5xx. Calling `res.json()` on an HTML error page throws a misleading parse error. Wrap each phase separately for actionable Sentry messages.

---

## Pattern Catalog

### Report Errors to a Crash Service

**Detection**:
```bash
grep -rn 'console\.error' --include="*.tsx" --include="*.ts" | grep -v "\.test\." | grep -v "\.spec\."
```

**Signal**:
```tsx
try { await syncData() } catch (err) { console.error('Sync failed', err) }
```

`console.error` is stripped in production builds. Errors are invisible.

**Preferred action**: Use `captureException(err)`. Keep `console.error` only in `__DEV__`.

---

### Handle Errors in Every Catch Block

**Detection**:
```bash
grep -rn 'catch\s*(.*)\s*{\s*}' --include="*.ts" --include="*.tsx"
```

**Signal**:
```ts
try { await loadUserPreferences() } catch (err) { /* TODO */ }
```

Silent swallow. No stack trace, no fallback, inconsistent state.

**Preferred action**: Report and reset to safe default:
```ts
try { await loadUserPreferences() } catch (err) {
  captureException(err)
  await setDefaultPreferences()
}
```

---

### Wrap Navigation Root in ErrorBoundary

**Detection**:
```bash
grep -rn 'Stack.Screen\|Tabs.Screen' --include="*.tsx" | grep -v ErrorBoundary
```

**Signal**:
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

If any screen throws during render, the entire navigation tree white-screens.

**Preferred action**: Wrap each screen or the navigator root in an ErrorBoundary.

---

### Validate API Response Shape Before Accessing

**Detection**:
```bash
grep -rn '\.data\.' --include="*.ts" --include="*.tsx" | grep -v "\.test\." | grep "await fetch\|axios"
```

**Signal**:
```ts
const json = await response.json()
setUser(json.data.profile.name)  // throws if data or profile is undefined
```

**Preferred action**: Validate or use optional chaining with fallback:
```ts
if (!json.data?.profile) {
  throw new Error(`Unexpected API shape: ${JSON.stringify(json).slice(0, 200)}`)
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `TypeError: Cannot read properties of undefined` | Null access on API response | Optional chaining or null check |
| `Network request failed` | No network or wrong host | Check `__DEV__` vs production API URL |
| `JSON Parse error: Unrecognized token '<'` | Server returned HTML instead of JSON | Check `res.ok` before `res.json()` |
| `Maximum update depth exceeded` | State setter in render or effect without deps | Move to event handler or fix deps array |
| `Can't perform state update on unmounted component` | Async completes after unmount | Return cleanup from `useEffect` |
| `Invariant Violation` from native module | Native call outside main thread | Move to dedicated service |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RN 0.71 | `Promise.allSettled` default in Hermes | Use for partial results on failure |
| RN 0.73 | Improved async stack traces in Hermes | Update Sentry sourcemap upload |
| React 18 | `startTransition` errors fall back to ErrorBoundary | Transitions no longer crash whole tree |
| `@sentry/react-native` 5.0 | `Sentry.wrap(App)` deprecated | Use `Sentry.init()` then `withSentry(App)` |

---

## Detection Commands Reference

```bash
# console.error as only reporting (not in tests)
grep -rn 'console\.error' --include="*.tsx" --include="*.ts" | grep -v "\.test\.\|\.spec\."

# Empty catch blocks
grep -rn 'catch\s*(.*)\s*{\s*}' --include="*.ts" --include="*.tsx"

# Fetch without .ok check
grep -rn 'await fetch\|\.json()' --include="*.ts" --include="*.tsx" | grep -v 'res\.ok\|response\.ok'

# Deep property access without null guards
grep -rn '\.data\.\|\.result\.' --include="*.ts" --include="*.tsx" | grep -v '\?\.'

# Missing ErrorBoundary around screens
grep -rn 'Stack\.Screen\|Tabs\.Screen' --include="*.tsx" | grep -v 'ErrorBoundary'
```

---

## See Also

- `rendering-patterns.md` — Text component and conditional render crashes
- `state-management.md` — Stale state causing incorrect error recovery
