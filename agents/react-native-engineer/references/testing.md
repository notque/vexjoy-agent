# Testing Reference
<!-- Loaded by react-native-engineer when task involves tests, RNTL, Maestro, Detox, jest, testing-library -->

> **Scope**: RNTL patterns, Maestro E2E, native module mocking, Expo test config.
> **Version range**: React Native 0.72+, RNTL 12+, Expo SDK 50+
> **Generated**: 2026-04-12

---

## Pattern Table

| Tool | Version | Use When | Avoid When |
|------|---------|----------|------------|
| `@testing-library/react-native` | `12+` | Component behavior, user interactions | Animation internals, native rendering |
| `jest-expo` | `SDK 50+` | Expo managed workflow | Bare RN without Expo |
| `Maestro` | `1.36+` | E2E flows on device/simulator | Unit-level component logic |
| `Detox` | `20+` | E2E when Maestro yaml is insufficient | Simple flows |
| `async-storage-mock` | any | Mocking AsyncStorage | Leave unmocked = silent hang |

---

## Correct Patterns

### Test User Behavior, Not Implementation

```tsx
import { render, fireEvent, screen } from '@testing-library/react-native'

it('submits login with valid credentials', () => {
  render(<LoginScreen onSuccess={jest.fn()} />)
  fireEvent.changeText(screen.getByLabelText('Email'), 'user@example.com')
  fireEvent.changeText(screen.getByLabelText('Password'), 'hunter2')
  fireEvent.press(screen.getByRole('button', { name: 'Log in' }))
  expect(screen.getByText('Logging in...')).toBeTruthy()
})
```

`getByLabelText` and `getByRole` query what a screen reader sees. Renaming a component but keeping its label: test passes. Renaming the label: test correctly fails.

---

### Mock Native Modules at jest Config Level

```js
// jest.config.js
module.exports = {
  preset: 'jest-expo',
  setupFilesAfterFramework: ['./jest.setup.ts'],
  moduleNameMapper: {
    'react-native-vision-camera': '<rootDir>/__mocks__/react-native-vision-camera.ts',
  },
}
```

```ts
// __mocks__/react-native-vision-camera.ts
export const Camera = jest.fn(() => null)
export const useCameraDevices = jest.fn(() => ({ back: {}, front: {} }))
```

Native modules throw "Cannot read properties of null" in jest. Module-level mocks prevent test pollution.

---

### Use `waitFor` for Async State Changes

```tsx
it('shows loaded data after fetch', async () => {
  render(<UserProfile userId="123" />)
  await waitFor(() => {
    expect(screen.getByText('Jane Doe')).toBeTruthy()
  })
})
```

Arbitrary delays make tests flaky or slow. `waitFor` exits as soon as assertion passes.

---

### Set Up AsyncStorage Mock Globally

```ts
// jest.setup.ts
import mockAsyncStorage from '@react-native-async-storage/async-storage/jest/async-storage-mock'
jest.mock('@react-native-async-storage/async-storage', () => mockAsyncStorage)
```

Real AsyncStorage requires native bridge. Without mock, `getItem`/`setItem` return `Promise<never>` — test hangs.

---

## Pattern Catalog

### Query by Accessible Attributes

**Detection**:
```bash
grep -rn 'getByTestId\|findByTestId' --include="*.test.tsx" --include="*.spec.tsx"
```

**Signal**: `screen.getByTestId('submit-button')` — invisible to users and screen readers. Breaks on refactor, doesn't verify accessibility.

**Preferred action**: `screen.getByRole('button', { name: 'Submit' })`

**Note**: RNTL 7+ requires `accessible={true}` or a role for `getByRole`. Add `accessibilityRole="button"` to `Pressable`.

---

### Import Test Utilities from @testing-library/react-native

**Detection**:
```bash
grep -rn "from 'react-native'" --include="*.test.tsx" | grep -v "^.*//.*from 'react-native'"
```

`react-native` doesn't export `render`. These imports cause module errors or wrong `act` semantics.

**Preferred action**: `import { render, fireEvent, screen, act, waitFor } from '@testing-library/react-native'`

---

### Mock Navigation Globally in __mocks__

**Detection**:
```bash
grep -rn "jest.mock.*navigation\|jest.mock.*router" --include="*.test.tsx"
```

Repeated local mocks diverge. Create a single mock in `__mocks__/@react-navigation/native.ts` or wrap in `NavigationContainer`:

```tsx
function renderWithNavigation(ui: React.ReactElement) {
  return render(<NavigationContainer>{ui}</NavigationContainer>)
}
```

---

### Test Specific Output Instead of Snapshots

**Detection**:
```bash
grep -rn 'toMatchSnapshot\|toMatchInlineSnapshot' --include="*.test.tsx"
```

Snapshots fail on every styling change, assert nothing about behavior. Test user-visible output:
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
| `TurboModuleRegistry.getEnforcing(...)` | Native module without mock | Add to `moduleNameMapper` or mock in setup |
| `Unable to find element with text` | Async data not resolved | Wrap in `await waitFor(...)` |
| `update not wrapped in act(...)` | State update after test ended | Use `await act(async () => { ... })` or `waitFor` |
| `Cannot find module '@testing-library/react-native'` | Not installed | `npm install -D @testing-library/react-native` |
| `Element type is invalid: expected string or function` | Mock returns wrong shape | Check `__mocks__` default/named exports |
| `jest did not exit one second after test run` | Unmocked async module holds handle | Mock all native async modules in `jest.setup.ts` |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| RNTL 12.0 | `userEvent` API — real user gestures | Prefer `userEvent.press()` over `fireEvent.press()` |
| RNTL 12.4 | `screen` query object stable | Use `screen.getByText()` |
| Expo SDK 50 | `jest-expo` supports new architecture (JSI) | Check version match on SDK 50 |
| RN 0.73 | New Architecture (Fabric) default | Some library mocks break |

---

## Detection Commands Reference

```bash
grep -rn 'getByTestId\|findByTestId' --include="*.test.tsx" --include="*.spec.tsx"
grep -rn 'toMatchSnapshot\|toMatchInlineSnapshot' --include="*.test.tsx"
grep -rn 'jest.mock.*native' --include="*.test.tsx" | grep -v "__mocks__"
grep -rn 'setTimeout.*[0-9]' --include="*.test.tsx" --include="*.spec.tsx"
grep -rn "from 'react-native/test-utils'\|from 'react-test-renderer'" --include="*.test.tsx"
```

---

## See Also

- `rendering-patterns.md` — Text component rules affecting RNTL queries
- `list-performance.md` — FlashList/LegendList test setup for virtualization
