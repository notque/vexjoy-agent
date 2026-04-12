# Testing Reference
<!-- Loaded by react-native-engineer when task involves tests, RNTL, Maestro, Detox, jest, testing-library -->

> **Scope**: React Native test setup, React Native Testing Library (RNTL) patterns, Maestro E2E, native module mocking, and Expo test configuration.
> **Version range**: React Native 0.72+, RNTL 12+, Expo SDK 50+
> **Generated**: 2026-04-12 — verify against current @testing-library/react-native release notes

---

## Overview

React Native testing has three distinct layers: unit/component tests via RNTL, integration via jest with native module mocks, and E2E via Maestro or Detox. The most common failure mode is testing implementation details (renders, re-renders, internal state) instead of user-observable behavior. Native modules require manual mocking; RNTL's `render` does not invoke native code.

---

## Pattern Table

| Tool | Version | Use When | Avoid When |
|------|---------|----------|------------|
| `@testing-library/react-native` | `12+` | component behavior, user interactions | testing animation internals, native rendering |
| `jest-expo` | `SDK 50+` | Expo managed workflow tests | bare RN without Expo — use `react-native` preset |
| `Maestro` | `1.36+` | E2E flows on device/simulator | unit-level component logic |
| `Detox` | `20+` | E2E when Maestro yaml DSL is insufficient | simple flows — Maestro is faster to author |
| `@react-native-community/async-storage/jest/async-storage-mock` | any | mocking AsyncStorage in unit tests | leave AsyncStorage unmocked — causes silent hang |

---

## Correct Patterns

### Test User Behavior, Not Implementation

Query by accessible labels and roles, not test IDs or internal component names.

```tsx
import { render, fireEvent, screen } from '@testing-library/react-native'
import { LoginScreen } from './LoginScreen'

it('submits login with valid credentials', () => {
  render(<LoginScreen onSuccess={jest.fn()} />)

  fireEvent.changeText(screen.getByLabelText('Email'), 'user@example.com')
  fireEvent.changeText(screen.getByLabelText('Password'), 'hunter2')
  fireEvent.press(screen.getByRole('button', { name: 'Log in' }))

  expect(screen.getByText('Logging in...')).toBeTruthy()
})
```

**Why**: `getByLabelText` and `getByRole` query what a screen reader sees. If you rename a component but keep its accessible label, the test still passes. If you rename the label, the test correctly fails.

---

### Mock Native Modules at the jest Config Level

Native modules that don't exist in the jest environment must be mocked globally — not inside individual test files — so every test file gets the mock automatically.

```js
// jest.config.js
module.exports = {
  preset: 'jest-expo',  // or 'react-native'
  setupFilesAfterFramework: ['./jest.setup.ts'],
  moduleNameMapper: {
    // mock native camera module
    'react-native-vision-camera': '<rootDir>/__mocks__/react-native-vision-camera.ts',
  },
}
```

```ts
// __mocks__/react-native-vision-camera.ts
export const Camera = jest.fn(() => null)
export const useCameraDevices = jest.fn(() => ({ back: {}, front: {} }))
```

**Why**: Native modules throw "Cannot read properties of null" in jest because the native bridge doesn't exist. Module-level mocks prevent test pollution across files.

---

### Use `waitFor` for Async State Changes

Avoid `setTimeout` delays. Use `waitFor` from RNTL which polls until assertion passes or timeout expires.

```tsx
import { render, waitFor, screen } from '@testing-library/react-native'

it('shows loaded data after fetch', async () => {
  render(<UserProfile userId="123" />)

  // Wrong: arbitrary delay
  // await new Promise(r => setTimeout(r, 500))

  // Correct: poll until assertion passes
  await waitFor(() => {
    expect(screen.getByText('Jane Doe')).toBeTruthy()
  })
})
```

**Why**: Arbitrary delays make tests either flaky (too short) or slow (too long). `waitFor` exits as soon as the assertion passes, bounding wait time without hardcoding delays.

---

### Set Up AsyncStorage Mock Globally

AsyncStorage calls that hit the real module in jest hang indefinitely with no error.

```ts
// jest.setup.ts
import mockAsyncStorage from '@react-native-async-storage/async-storage/jest/async-storage-mock'
jest.mock('@react-native-async-storage/async-storage', () => mockAsyncStorage)
```

**Why**: The real AsyncStorage module requires native bridge. Without the mock, `getItem`/`setItem` calls return `Promise<never>` — the test hangs until jest timeout kills it.

---

## Anti-Pattern Catalog

### ❌ Querying by `testID` Instead of Accessible Attributes

**Detection**:
```bash
grep -rn 'getByTestId\|findByTestId' --include="*.test.tsx" --include="*.spec.tsx"
rg 'getByTestId|findByTestId' --type tsx
```

**What it looks like**:
```tsx
const button = screen.getByTestId('submit-button')
fireEvent.press(button)
```

**Why wrong**: `testID` is invisible to users and screen readers. Tests using it break if the component is refactored even when behavior is unchanged. They also don't verify accessibility — a button with no label passes the test but fails assistive technology users.

**Fix**:
```tsx
const button = screen.getByRole('button', { name: 'Submit' })
fireEvent.press(button)
```

**Version note**: RNTL 7+ requires the component to have `accessible={true}` or a role for `getByRole` to find it. Add `accessibilityRole="button"` to `Pressable` components.

---

### ❌ Importing from `react-native` Instead of `@testing-library/react-native`

**Detection**:
```bash
grep -rn "from 'react-native'" --include="*.test.tsx" --include="*.spec.tsx" | grep -v "^.*//.*from 'react-native'"
```

**What it looks like**:
```tsx
import { render } from 'react-native'  // wrong — no render export
import { act } from 'react-native/test-utils'  // old pattern
```

**Why wrong**: `react-native` doesn't export `render`. These imports cause `Cannot find module` errors or silently import the wrong `act` (react vs react-native differ on batching semantics).

**Fix**:
```tsx
import { render, fireEvent, screen, act, waitFor } from '@testing-library/react-native'
```

---

### ❌ Mocking `useNavigation` Inside Individual Test Files

**Detection**:
```bash
grep -rn "jest.mock.*navigation\|jest.mock.*router" --include="*.test.tsx"
```

**What it looks like**:
```tsx
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}))
```

**Why wrong**: Repeated local mocks diverge over time. When the real API adds a new field (`navigation.setOptions`, `navigation.getId`), each test file needs updating separately. Components that call multiple navigation hooks get increasingly complex local mocks.

**Fix**: Create a single navigation mock in `__mocks__/@react-navigation/native.ts` and let jest auto-resolve it. Or use `createNavigationContainerRef` and wrap the component in a `NavigationContainer` in the test.

```tsx
import { NavigationContainer } from '@react-navigation/native'

function renderWithNavigation(ui: React.ReactElement) {
  return render(<NavigationContainer>{ui}</NavigationContainer>)
}
```

---

### ❌ Using Snapshots for UI Components

**Detection**:
```bash
grep -rn 'toMatchSnapshot\|toMatchInlineSnapshot' --include="*.test.tsx"
rg 'toMatchSnapshot' --type tsx
```

**What it looks like**:
```tsx
it('renders correctly', () => {
  const tree = render(<Card title="Hello" />).toJSON()
  expect(tree).toMatchSnapshot()
})
```

**Why wrong**: Snapshot tests fail on every styling or structure change, creating update churn. They assert nothing about behavior — a component that renders the wrong text passes if the snapshot was wrong to begin with. They're especially noisy in monorepos.

**Fix**: Test specific rendered output that reflects user-visible behavior:
```tsx
it('displays the title', () => {
  render(<Card title="Hello" />)
  expect(screen.getByText('Hello')).toBeTruthy()
})
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Invariant Violation: TurboModuleRegistry.getEnforcing(...)` | Native module accessed in jest without mock | Add module to `moduleNameMapper` in jest.config or mock in setupFilesAfterFramework |
| `Unable to find an element with the text: ...` | Component not yet rendered or async data not resolved | Wrap assertion in `await waitFor(...)` |
| `Warning: An update to ... inside a test was not wrapped in act(...)` | State update triggered after test ended or outside act | Use `await act(async () => { ... })` around the trigger, or use `waitFor` |
| `Cannot find module '@testing-library/react-native'` | Package not installed | `bun add -D @testing-library/react-native` or `npm install -D @testing-library/react-native` |
| `Element type is invalid: expected a string or class/function but got undefined` | Mocked module returns wrong shape | Check `__mocks__` file — default export may be missing or named exports wrong |
| `jest did not exit one second after the test run has completed` | Unmocked async module (AsyncStorage, NetInfo) holds open handle | Add mock in `jest.setup.ts` for all native async modules |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RNTL 12.0 | `userEvent` API added — simulates real user gestures, not synthetic events | Prefer `userEvent.press()` over `fireEvent.press()` for interaction fidelity |
| RNTL 12.4 | `screen` query object promoted to stable — no need to destructure `render()` return | Use `screen.getByText()` instead of `const { getByText } = render()` |
| Expo SDK 50 | `jest-expo` preset updated to support new architecture (JSI) | If tests hang after SDK 50 upgrade, check `jest-expo` version matches SDK |
| RN 0.73 | New Architecture (Fabric) enabled by default in new projects | Some community library mocks break under Fabric — check library's jest setup docs |

---

## Detection Commands Reference

```bash
# Find testID queries that should be role/label queries
grep -rn 'getByTestId\|findByTestId' --include="*.test.tsx" --include="*.spec.tsx"

# Find snapshot tests in component files
grep -rn 'toMatchSnapshot\|toMatchInlineSnapshot' --include="*.test.tsx"

# Find unmocked native module patterns
grep -rn 'jest.mock.*native' --include="*.test.tsx" | grep -v "__mocks__"

# Find setTimeout used as async delay in tests (should use waitFor)
grep -rn 'setTimeout.*[0-9]' --include="*.test.tsx" --include="*.spec.tsx"

# Find old act import pattern
grep -rn "from 'react-native/test-utils'\|from 'react-test-renderer'" --include="*.test.tsx"
```

---

## See Also

- `rendering-patterns.md` — Text component rules that affect what RNTL can query
- `list-performance.md` — FlashList/LegendList require specific test setup for virtualization
