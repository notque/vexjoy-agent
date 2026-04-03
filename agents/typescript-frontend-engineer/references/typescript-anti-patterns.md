# TypeScript Frontend Anti-Patterns

Common mistakes and their corrections for TypeScript frontend development.

## Use Explicit Types and Zod for Runtime Safety

**What it looks like**:
```typescript
// Instead of: Using any to silence type errors
const data: any = await fetch('/api/users')
const users: any = data.json()

function handleData(input: any) {
  // No type safety whatsoever
  return input.map((item: any) => item.name)
}

// Spreads throughout codebase
interface ApiResponse {
  data: any  // Defeats the purpose
  errors: any
}
```

**Why it matters**:
- Defeats the entire purpose of TypeScript
- Loses autocomplete and IntelliSense
- Allows runtime errors that TypeScript should catch
- Makes refactoring dangerous - no compiler help
- Creates false sense of security

**✅ Correct approach**:
```typescript
// Use: Define proper types and validate
interface User {
  id: string
  name: string
  email: string
}

const UserSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email()
})

async function fetchUsers(): Promise<User[]> {
  const response = await fetch('/api/users')
  const data = await response.json()
  // Validate with Zod
  return z.array(UserSchema).parse(data)
}

// Proper API response typing
interface ApiResponse<T> {
  data: T
  message: string
  success: boolean
  errors?: Record<string, string[]>
}
```

**When to use**:
- NEVER use `any` without explicit justification
- If absolutely necessary, add a comment explaining why
- Consider `unknown` instead - forces type checking before use

---

## Reach for Built-In TypeScript Utilities First

**What it looks like**:
```typescript
// Instead of: Creating complex type utilities before you need them
type DeepReadonly<T> = {
  readonly [P in keyof T]: T[P] extends object
    ? T[P] extends Function
      ? T[P]
      : DeepReadonly<T[P]>
    : T[P]
}

type RecursivePartial<T> = {
  [P in keyof T]?: T[P] extends (infer U)[]
    ? RecursivePartial<U>[]
    : T[P] extends object
    ? RecursivePartial<T[P]>
    : T[P]
}

type DeepRequired<T> = {
  [P in keyof T]-?: T[P] extends (infer U)[]
    ? DeepRequired<U>[]
    : T[P] extends readonly (infer U)[]
    ? readonly DeepRequired<U>[]
    : T[P] extends object
    ? DeepRequired<T[P]>
    : T[P]
}

// Applying these complex types everywhere "just in case"
const config: DeepReadonly<RecursivePartial<AppConfig>> = {...}
```

**Why it matters**:
- Adds complexity without solving actual problems
- Slows down type checking significantly
- Makes error messages incomprehensible
- Premature optimization of type system
- Hard to maintain and debug

**✅ Correct approach**:
```typescript
// Use: Use simple types and built-in utilities
interface User {
  id: string
  name: string
  email: string
  preferences: {
    theme: 'light' | 'dark'
    notifications: boolean
  }
}

// Use TypeScript built-ins when needed
type PartialUser = Partial<User>
type ReadonlyUser = Readonly<User>
type UserWithoutEmail = Omit<User, 'email'>

// Only create custom utilities when you have 3+ real use cases
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P]
}

// And use it only where it solves a real problem
type PartialConfig = DeepPartial<AppConfig>
```

**When to use**:
- Create custom type utilities only after identifying repeated pattern (3+ occurrences)
- Keep utilities simple and well-documented
- Prefer composition of built-in utilities over custom complex ones

---

## Validate All External Data with Zod

**What it looks like**:
```typescript
// Instead of: Trusting API responses without validation
async function getUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${id}`)
  return response.json() as User  // Type assertion without validation
}

// Using form data directly
function handleSubmit(event: FormEvent) {
  const formData = new FormData(event.target as HTMLFormElement)
  const user = {
    name: formData.get('name'),
    email: formData.get('email')
  } as User  // Unsafe cast

  saveUser(user)  // Could be malformed!
}

// Trusting localStorage
const settings = JSON.parse(localStorage.getItem('settings')!) as Settings
```

**Why it matters**:
- Type assertions don't validate runtime data
- API can return unexpected data structure
- User input is untrusted
- Leads to runtime errors in production
- No protection against API changes

**✅ Correct approach**:
```typescript
// Use: Always validate external data with Zod
const UserSchema = z.object({
  id: z.string(),
  name: z.string().min(1),
  email: z.string().email()
})

type User = z.infer<typeof UserSchema>

async function getUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${id}`)
  const data = await response.json()
  return UserSchema.parse(data)  // Validates and throws if invalid
}

// Validate form data
const FormSchema = z.object({
  name: z.string().min(1),
  email: z.string().email()
})

function handleSubmit(event: FormEvent) {
  const formData = new FormData(event.target as HTMLFormElement)
  const result = FormSchema.safeParse({
    name: formData.get('name'),
    email: formData.get('email')
  })

  if (!result.success) {
    // Handle validation errors
    showErrors(result.error.flatten().fieldErrors)
    return
  }

  // result.data is now properly typed and validated
  saveUser(result.data)
}

// Validate localStorage with fallback
const SettingsSchema = z.object({
  theme: z.enum(['light', 'dark']),
  notifications: z.boolean()
})

const rawSettings = localStorage.getItem('settings')
const settings = rawSettings
  ? SettingsSchema.parse(JSON.parse(rawSettings))
  : { theme: 'light', notifications: true }  // Default fallback
```

**When to use**:
- ALWAYS validate data from: APIs, user input, localStorage, URL params
- Use `safeParse` for user-facing validation (returns errors, doesn't throw)
- Use `parse` for internal validation (throws on error)

---

## Fix Root Causes — Use @ts-expect-error When Unavoidable

**What it looks like**:
```typescript
// Instead of: Suppressing errors instead of fixing them
// @ts-ignore
const result = someFunction(wrongArguments)

// @ts-expect-error
window.myCustomProperty = 'value'

// Worst: File-level suppression
// @ts-nocheck

// Or in tsconfig
{
  "compilerOptions": {
    "skipLibCheck": true,  // OK for node_modules
    "noImplicitAny": false  // BAD - disables important check
  }
}
```

**Why it matters**:
- Hides real bugs
- Tech debt accumulates
- Errors become invisible during refactoring
- No explanation why error is suppressed
- Future developers don't know if it's safe to remove

**✅ Correct approach**:
```typescript
// Use: Fix the root cause or properly extend types

// Option 1: Fix the function call
const result = someFunction(correctArguments)

// Option 2: Properly extend global types
declare global {
  interface Window {
    myCustomProperty: string
    gtag?: (...args: any[]) => void  // Google Analytics
  }
}
window.myCustomProperty = 'value'

// Option 3: If absolutely necessary, explain and narrow scope
interface LegacyAPI {
  // Legacy API from third-party vendor, structure varies
  // TODO: Replace with modern API when vendor updates (ticket #123)
  [key: string]: unknown
}

const legacyData = response.data as LegacyAPI
// Then validate the specific fields you need
const validatedField = z.string().parse(legacyData.fieldName)

// Option 4: For genuinely exceptional cases, document thoroughly
// @ts-expect-error - TypeScript incorrectly infers type here due to limitations
// in conditional type inference with template literals. Verified runtime behavior
// is correct. See: https://github.com/microsoft/TypeScript/issues/xxxxx
const edgeCase = complexTypeFunction(input)
```

**When to use**:
- NEVER use `@ts-ignore` or `@ts-nocheck` without thorough justification
- If used, add detailed comment explaining WHY and what's being ignored
- Link to GitHub issue if it's a TypeScript bug
- Prefer `@ts-expect-error` over `@ts-ignore` (fails if error is fixed)

---

## Use Discriminated Unions for Exclusive State Variants

**What it looks like**:
```typescript
// Instead of: Multiple optional fields for state variants
interface RequestState<T> {
  data?: T
  error?: string
  loading?: boolean
}

// This allows invalid states:
const state: RequestState<User> = {
  loading: true,
  data: user,
  error: 'Failed'  // All three at once? Impossible!
}

// Leads to complex, error-prone checks
function render(state: RequestState<User>) {
  if (state.loading) return <Spinner />
  if (state.error) return <Error message={state.error} />
  if (state.data) return <UserProfile user={state.data} />
  // What if none are true? What if multiple are?
}
```

**Why it matters**:
- Allows impossible states
- Requires lots of null/undefined checks
- Error-prone when checking state
- TypeScript can't help narrow types
- Easy to forget to check all conditions

**✅ Correct approach**:
```typescript
// Use: Use discriminated unions for mutually exclusive states
type RequestState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }

// Now TypeScript enforces valid states
const state: RequestState<User> = { status: 'loading' }

// TypeScript narrows types in conditionals
function render(state: RequestState<User>) {
  switch (state.status) {
    case 'idle':
      return <div>Not started</div>
    case 'loading':
      return <Spinner />
    case 'success':
      // TypeScript knows state.data exists here
      return <UserProfile user={state.data} />
    case 'error':
      // TypeScript knows state.error exists here
      return <Error message={state.error} />
  }
}

// Even better: Add loading states with partial data
type RequestState<T> =
  | { status: 'idle' }
  | { status: 'loading'; data?: T }  // Optional cached data while loading
  | { status: 'success'; data: T }
  | { status: 'error'; error: string; data?: T }  // Show stale data with error
  | { status: 'refreshing'; data: T }  // Loading new data, showing old

// TypeScript ensures you handle all cases
function render(state: RequestState<User>): JSX.Element {
  switch (state.status) {
    case 'idle':
      return <button onClick={load}>Load User</button>
    case 'loading':
      return state.data ? <UserProfile user={state.data} stale /> : <Spinner />
    case 'refreshing':
      return <UserProfile user={state.data} refreshing />
    case 'success':
      return <UserProfile user={state.data} />
    case 'error':
      return (
        <>
          <Error message={state.error} />
          {state.data && <UserProfile user={state.data} stale />}
        </>
      )
  }
}
```

**When to use**:
- Use discriminated unions for any state with multiple exclusive variants
- Add a `status` or `type` field as the discriminator
- Let TypeScript exhaustively check all cases
- Common use cases: API states, form states, UI modes

---

## Use Interface for Object Shapes, Type for Unions and Mapped Types

**What it looks like**:
```typescript
// Instead of: Using type for simple object shapes
type User = {
  id: string
  name: string
}

// Then trying to extend it (awkward intersection)
type AdminUser = User & {
  permissions: string[]
}

// Trying to use interface for unions (syntax error!)
interface Status = 'active' | 'inactive'  // ❌ Error!

// Inconsistent mixing
interface Config {
  theme: Theme  // type
  user: User    // type
  settings: Settings  // interface
}
```

**Why it matters**:
- Interfaces give better error messages for objects
- Interfaces can be augmented/extended more easily
- Types are needed for unions, intersections, mapped types
- Mixing them inconsistently hurts readability
- IDE autocomplete differs between types and interfaces

**✅ Correct approach**:
```typescript
// Use: Interface for object shapes
interface User {
  id: string
  name: string
  email: string
}

// Interfaces extend cleanly (better errors than intersection)
interface AdminUser extends User {
  permissions: string[]
  role: 'admin'
}

// Interface for React props
interface ButtonProps {
  children: React.ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary'
  disabled?: boolean
}

// Type for unions, intersections, and complex types
type Status = 'active' | 'inactive' | 'pending'
type UserId = string & { readonly brand: unique symbol }
type Optional<T> = T | null | undefined

// Type for mapped types and transformations
type Readonly<T> = {
  readonly [P in keyof T]: T[P]
}

// Type for function signatures (when not part of interface)
type EventHandler = (event: Event) => void
type AsyncFunction<T> = () => Promise<T>

// General rule:
// - Interfaces: Objects, React props, class contracts
// - Types: Unions, intersections, primitives, tuples, mapped types
```

**When to use**:
- **Use interface** for: Object shapes, React component props, class implementations
- **Use type** for: Unions, intersections, tuples, mapped types, primitive aliases
- Be consistent within a file/module

---

## Use React 19 Patterns: ref as Prop, Direct Context, useActionState

**What it looks like**:
```typescript
// Instead of: Using forwardRef in React 19 (deprecated)
const MyInput = forwardRef<HTMLInputElement, Props>((props, ref) => (
  <input ref={ref} {...props} />
))

// Instead of: Using Context.Provider when Context works directly
<ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>

// Instead of: Using useFormState (renamed)
import { useFormState } from 'react-dom'
const [state, formAction] = useFormState(action, initialState)

// Instead of: Implicit ref callback returns (TypeScript error in React 19)
<div ref={el => (myRef = el)} />

// Instead of: Using ReactDOM.render (removed)
ReactDOM.render(<App />, container)
```

**Why it matters**:
- `forwardRef` is deprecated and adds unnecessary complexity
- `Context.Provider` is verbose when Context works directly
- `useFormState` was renamed to `useActionState`
- Implicit ref returns conflict with new cleanup function support
- Old APIs removed or deprecated in React 19

**✅ Correct approach**:
```typescript
// Use: ref as a prop (React 19)
interface Props {
  placeholder?: string
  disabled?: boolean
  ref?: React.Ref<HTMLInputElement>
}

function MyInput({ placeholder, disabled, ref }: Props) {
  return <input ref={ref} placeholder={placeholder} disabled={disabled} />
}

// Use: Context directly (no .Provider)
<ThemeContext value={theme}>{children}</ThemeContext>

// Use: useActionState (React 19)
import { useActionState } from 'react'
const [state, formAction, isPending] = useActionState(action, initialState)

// Use: Explicit ref callback (no implicit return)
<div ref={el => { myRef = el }} />

// Or with cleanup:
<div ref={el => {
  myRef = el
  return () => { myRef = null }  // Cleanup on unmount
}} />

// Use: createRoot (React 18+)
import { createRoot } from 'react-dom/client'
const root = createRoot(container)
root.render(<App />)

// Use new React 19 hooks
import { useOptimistic, use } from 'react'

function ChatMessages({ messages }: { messages: Message[] }) {
  const [optimisticMessages, addOptimistic] = useOptimistic(
    messages,
    (state, newMessage: string) => [
      ...state,
      { id: crypto.randomUUID(), text: newMessage, sending: true }
    ]
  )

  return optimisticMessages.map(msg => <Message key={msg.id} {...msg} />)
}

// use() hook can read promises conditionally
function Comments({ commentsPromise }: { commentsPromise: Promise<Comment[]> }) {
  const comments = use(commentsPromise)  // Suspends until resolved
  return comments.map(c => <Comment key={c.id} {...c} />)
}
```

**When to use**:
- Migrate to React 19 patterns when upgrading
- Use `ref` as a prop instead of `forwardRef`
- Use `useActionState` for form state management
- Use explicit ref callbacks
- Leverage new hooks (`useOptimistic`, `use`) for better UX

---

## Stabilize References with useCallback and useMemo

**What it looks like**:
```typescript
// Instead of: Creating new functions/objects every render
function Parent() {
  return (
    <>
      <Child onClick={() => console.log('click')} />
      <Child config={{ theme: 'dark' }} />
      <Child items={data.map(d => ({ ...d, formatted: true }))} />
    </>
  )
}

// All children re-render on every Parent render!
const Child = memo(({ onClick, config, items }) => {
  // Expensive component
})
```

**Why it matters**:
- Creates new references every render
- Breaks `React.memo` optimization
- Child components re-render unnecessarily
- Performance degrades with component tree depth
- Especially bad for lists and expensive components

**✅ Correct approach**:
```typescript
// Use: Use useCallback and useMemo

function Parent() {
  const handleClick = useCallback(() => {
    console.log('click')
  }, [])

  const config = useMemo(() => ({ theme: 'dark' }), [])

  const items = useMemo(
    () => data.map(d => ({ ...d, formatted: true })),
    [data]
  )

  return (
    <>
      <Child onClick={handleClick} />
      <Child config={config} />
      <Child items={items} />
    </>
  )
}

// Even better: Move static data outside component
const CONFIG = { theme: 'dark' }

function Parent() {
  const handleClick = useCallback(() => {
    console.log('click')
  }, [])

  const items = useMemo(
    () => data.map(d => ({ ...d, formatted: true })),
    [data]
  )

  return (
    <>
      <Child onClick={handleClick} />
      <Child config={CONFIG} />
      <Child items={items} />
    </>
  )
}
```

**When to use**:
- Use `useCallback` for event handlers passed to memo'd children
- Use `useMemo` for computed values or object props
- Move static data outside components
- Profile with React DevTools before optimizing

---

## Handle Async Errors Explicitly with User-Facing State

**What it looks like**:
```typescript
// Instead of: Not handling errors
async function loadUser() {
  const user = await fetchUser()  // What if this fails?
  setUser(user)
}

// Instead of: Catching but not handling
async function loadUser() {
  try {
    const user = await fetchUser()
    setUser(user)
  } catch (error) {
    console.log(error)  // Logged but not shown to user!
  }
}

// Instead of: Silent failures
async function loadUser() {
  try {
    const user = await fetchUser()
    setUser(user)
  } catch {
    // Error swallowed completely
  }
}
```

**Why it matters**:
- Unhandled promise rejections crash apps
- Users don't see error messages
- Hard to debug in production
- Error states not reflected in UI

**✅ Correct approach**:
```typescript
// Use: Proper error handling with user feedback
async function loadUser() {
  setLoading(true)
  setError(null)

  try {
    const user = await fetchUser()
    setUser(user)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to load user'
    setError(message)

    // Optional: Log to error tracking service
    if (error instanceof ApiError && error.status >= 500) {
      errorTracker.capture(error)
    }
  } finally {
    setLoading(false)
  }
}

// Better: Use discriminated union state
type UserState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: string }

async function loadUser() {
  setState({ status: 'loading' })

  try {
    const user = await fetchUser()
    setState({ status: 'success', data: user })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    setState({ status: 'error', error: message })
  }
}

// Render based on state
function UserProfile() {
  switch (state.status) {
    case 'idle':
      return <button onClick={loadUser}>Load User</button>
    case 'loading':
      return <Spinner />
    case 'error':
      return <Error message={state.error} retry={loadUser} />
    case 'success':
      return <Profile user={state.data} />
  }
}
```

**When to use**:
- ALWAYS wrap async operations in try/catch
- Show error messages to users
- Use discriminated unions for async state
- Log critical errors to monitoring service
