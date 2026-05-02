# Rendering Patterns Reference
<!-- Loaded by react-native-engineer when task involves conditional rendering, &&, Text components, React Compiler, memoization -->

## Use Ternary or Explicit Boolean for Conditional Rendering
**Impact:** CRITICAL — prevents hard crash in production

`{value && <Component />}` crashes React Native when `value` is `0` or empty string. These are falsy but JSX-renderable — RN tries to render them as text outside `<Text>`, causing a hard crash. React Native-specific (not a web issue).

**Instead of:**
```tsx
{name && <Text>{name}</Text>}   // crashes if name is ""
{count && <Text>{count} items</Text>}  // crashes if count is 0
```

**Use:**
```tsx
{name ? <Text>{name}</Text> : null}
{count > 0 ? <Text>{count} items</Text> : null}
// Or: {!!name && <Text>{name}</Text>}
// Or: early return — if (!name) return null
```

Enable `react/jsx-no-leaked-render` ESLint rule.

---

## Wrap All Strings in Text Components
**Impact:** CRITICAL — prevents runtime crash

Strings must be inside `<Text>`. React Native throws a hard error on string children of `<View>`.

**Instead of:**
```tsx
return <View>Hello, {name}!</View>
```

**Use:**
```tsx
return <View><Text>Hello, {name}!</Text></View>
```

Applies to string literals, template literals, and expressions that evaluate to strings.

---

## Destructure Functions Early in Render (React Compiler)
**Impact:** HIGH — stable references, fewer re-renders

With React Compiler, destructure functions from hooks and props at render scope top. The compiler keys cache on read variables — dotting into objects uses the object reference (changes each render).

**Instead of:**
```tsx
function SaveButton(props) {
  const router = useRouter()
  const handlePress = () => { props.onSave(); router.push('/success') }
  return <Button onPress={handlePress}>Save</Button>
}
```

**Use:**
```tsx
function SaveButton({ onSave }) {
  const { push } = useRouter()
  const handlePress = () => { onSave(); push('/success') }
  return <Button onPress={handlePress}>Save</Button>
}
```

Only applies with React Compiler enabled. Without it, use standard `useCallback`.

---

## Memoization Patterns Without React Compiler

```tsx
const UserRow = memo(function UserRow({ name, isActive }: Props) {
  return <View>{/* ... */}</View>
})

const handlePress = useCallback((id: string) => {
  dispatch({ type: 'SELECT', id })
}, [dispatch])

const sorted = useMemo(
  () => items.toSorted((a, b) => a.name.localeCompare(b.name)),
  [items]
)
```

With React Compiler, `memo()` and `useCallback()` are handled automatically. Object reference stability still matters for virtualized lists.

---

## Hoist Intl Formatters to Module Scope
**Impact:** LOW-MEDIUM — avoids expensive instantiation per render

**Instead of:**
```tsx
function Price({ amount }: { amount: number }) {
  const formatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
  return <Text>{formatter.format(amount)}</Text>
}
```

**Use:**
```tsx
const currencyFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

function Price({ amount }: { amount: number }) {
  return <Text>{currencyFormatter.format(amount)}</Text>
}
```

For dynamic locales, memoize: `useMemo(() => new Intl.DateTimeFormat(locale, opts), [locale])`.
