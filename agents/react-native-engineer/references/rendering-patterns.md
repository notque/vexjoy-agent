# Rendering Patterns Reference
<!-- Loaded by react-native-engineer when task involves conditional rendering, &&, Text components, React Compiler, memoization -->

## Use Ternary or Explicit Boolean for Conditional Rendering
**Impact:** CRITICAL — prevents hard crash in production

`{value && <Component />}` crashes React Native when `value` is `0` or an empty string. These are falsy but JSX-renderable — React Native tries to render them as text outside a `<Text>` component, causing a hard crash. This is a React Native-specific issue (not a concern on web).

**Instead of:**
```tsx
function Profile({ name, count }: { name: string; count: number }) {
  return (
    <View>
      {name && <Text>{name}</Text>}   // crashes if name is ""
      {count && <Text>{count} items</Text>}  // crashes if count is 0
    </View>
  )
}
```

**Use (ternary with null):**
```tsx
function Profile({ name, count }: { name: string; count: number }) {
  return (
    <View>
      {name ? <Text>{name}</Text> : null}
      {count > 0 ? <Text>{count} items</Text> : null}
    </View>
  )
}
```

**Use (explicit boolean coercion):**
```tsx
{!!name && <Text>{name}</Text>}
{count > 0 && <Text>{count} items</Text>}
```

**Use (early return — clearest):**
```tsx
function Profile({ name }: { name: string }) {
  if (!name) return null
  return <View><Text>{name}</Text></View>
}
```

Enable `react/jsx-no-leaked-render` from `eslint-plugin-react` to catch this pattern automatically.

---

## Wrap All Strings in Text Components
**Impact:** CRITICAL — prevents runtime crash

Strings must be rendered inside `<Text>`. React Native throws a hard error if a string is a direct child of `<View>` or any non-Text component.

**Instead of:**
```tsx
function Greeting({ name }: { name: string }) {
  return <View>Hello, {name}!</View>
  // Error: Text strings must be rendered within a <Text> component
}
```

**Use:**
```tsx
function Greeting({ name }: { name: string }) {
  return (
    <View>
      <Text>Hello, {name}!</Text>
    </View>
  )
}
```

This applies to string literals, template literals, and any expression that could evaluate to a string.

---

## Destructure Functions Early in Render (React Compiler)
**Impact:** HIGH — stable references, fewer re-renders from unstable cache keys

When using the React Compiler, destructure functions from hooks and props at the top of render scope. The compiler keys its cache on the variables you read — dotting into objects uses the object reference (which changes each render), not the stable function reference.

**Instead of:**
```tsx
function SaveButton(props) {
  const router = useRouter()

  // compiler keys on "props" and "router" — both change each render
  const handlePress = () => {
    props.onSave()
    router.push('/success')
  }
  return <Button onPress={handlePress}>Save</Button>
}
```

**Use:**
```tsx
function SaveButton({ onSave }) {
  const { push } = useRouter()

  // good: compiler keys on "onSave" and "push" — stable references
  const handlePress = () => {
    onSave()
    push('/success')
  }
  return <Button onPress={handlePress}>Save</Button>
}
```

This rule only applies when the React Compiler is enabled. Without the compiler, use standard `useCallback` patterns.

---

## Memoization Patterns Without React Compiler

When React Compiler is **not** enabled, use `memo()` and `useCallback` manually:

```tsx
// Memoize list items to prevent re-renders when parent re-renders
const UserRow = memo(function UserRow({ name, isActive }: Props) {
  return <View>{/* ... */}</View>
})

// Stable callback references
const handlePress = useCallback((id: string) => {
  dispatch({ type: 'SELECT', id })
}, [dispatch])

// Memoize expensive computations
const sorted = useMemo(
  () => items.toSorted((a, b) => a.name.localeCompare(b.name)),
  [items]
)
```

When React Compiler **is** enabled, `memo()` and `useCallback()` are handled automatically. You can remove them, but leaving them in is harmless. Object reference stability for virtualized lists still matters regardless of the compiler.

---

## Hoist Intl Formatters to Module Scope
**Impact:** LOW-MEDIUM — avoids expensive formatter instantiation on every render

`Intl.NumberFormat`, `Intl.DateTimeFormat`, and `Intl.RelativeTimeFormat` are expensive to instantiate — each parses locale data and builds internal lookup tables. Hoist them to module scope when locale and options are static.

**Instead of:**
```tsx
function Price({ amount }: { amount: number }) {
  const formatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
  return <Text>{formatter.format(amount)}</Text>  // new formatter every render
}
```

**Use:**
```tsx
// hoisted to module scope — created once
const currencyFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

function Price({ amount }: { amount: number }) {
  return <Text>{currencyFormatter.format(amount)}</Text>
}
```

For dynamic locales that change at runtime, memoize instead:
```tsx
const dateFormatter = useMemo(
  () => new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }),
  [locale]
)
```
