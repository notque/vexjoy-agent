# React 19 + TypeScript Patterns

Modern patterns for React 19 with full TypeScript support.

## React 19 Breaking Changes and Migrations

### forwardRef Deprecation

**Old Pattern (React 18)**:
```typescript
import { forwardRef } from 'react'

interface InputProps {
  placeholder?: string
  disabled?: boolean
}

const MyInput = forwardRef<HTMLInputElement, InputProps>(
  ({ placeholder, disabled }, ref) => {
    return <input ref={ref} placeholder={placeholder} disabled={disabled} />
  }
)

MyInput.displayName = 'MyInput'
```

**New Pattern (React 19)**:
```typescript
interface InputProps {
  placeholder?: string
  disabled?: boolean
  ref?: React.Ref<HTMLInputElement>
}

function MyInput({ placeholder, disabled, ref }: InputProps) {
  return <input ref={ref} placeholder={placeholder} disabled={disabled} />
}

// For generic/polymorphic components
interface ButtonProps<T extends React.ElementType = 'button'> {
  as?: T
  children: React.ReactNode
  ref?: React.Ref<HTMLElement>
}

function Button<T extends React.ElementType = 'button'>({
  as,
  children,
  ref,
  ...props
}: ButtonProps<T> & Omit<React.ComponentPropsWithoutRef<T>, keyof ButtonProps<T>>) {
  const Component = as || 'button'
  return <Component ref={ref} {...props}>{children}</Component>
}

// Usage
<Button ref={buttonRef}>Click</Button>
<Button as="a" href="/home" ref={linkRef}>Link</Button>
```

---

### Context.Provider Simplification

**Old Pattern (React 18)**:
```typescript
const ThemeContext = createContext<'light' | 'dark'>('light')

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  return (
    <ThemeContext.Provider value={theme}>
      <Header />
      <Main />
    </ThemeContext.Provider>
  )
}
```

**New Pattern (React 19)**:
```typescript
const ThemeContext = createContext<'light' | 'dark'>('light')

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  return (
    <ThemeContext value={theme}>
      <Header />
      <Main />
    </ThemeContext>
  )
}

// TypeScript properly infers the type
function Header() {
  const theme = useContext(ThemeContext)  // type: 'light' | 'dark'
  return <header className={theme === 'dark' ? 'dark' : 'light'} />
}
```

---

### useFormState → useActionState

**Old Pattern (React 18)**:
```typescript
import { useFormState } from 'react-dom'

interface FormState {
  message: string
  errors?: Record<string, string[]>
}

async function submitForm(
  prevState: FormState,
  formData: FormData
): Promise<FormState> {
  // Server action
  const result = await saveData(formData)
  return {
    message: result.success ? 'Saved!' : 'Failed',
    errors: result.errors
  }
}

function MyForm() {
  const [state, formAction] = useFormState(submitForm, { message: '' })

  return (
    <form action={formAction}>
      <button type="submit">Save</button>
      <p>{state.message}</p>
    </form>
  )
}
```

**New Pattern (React 19)**:
```typescript
import { useActionState } from 'react'

interface FormState {
  message: string
  errors?: Record<string, string[]>
}

async function submitForm(
  prevState: FormState,
  formData: FormData
): Promise<FormState> {
  'use server'  // Next.js server action

  const data = Object.fromEntries(formData)

  // Validate with Zod
  const result = FormSchema.safeParse(data)
  if (!result.success) {
    return {
      message: 'Validation failed',
      errors: result.error.flatten().fieldErrors
    }
  }

  // Process data
  await saveData(result.data)
  return { message: 'Saved successfully!' }
}

function MyForm() {
  const [state, formAction, isPending] = useActionState(
    submitForm,
    { message: '' }
  )

  return (
    <form action={formAction}>
      <input name="email" type="email" required />
      {state.errors?.email && (
        <span className="error">{state.errors.email[0]}</span>
      )}

      <button type="submit" disabled={isPending}>
        {isPending ? 'Saving...' : 'Save'}
      </button>

      {state.message && <p>{state.message}</p>}
    </form>
  )
}
```

---

## New React 19 Hooks

### useOptimistic - Optimistic UI Updates

```typescript
interface Message {
  id: string
  text: string
  sending?: boolean
}

function Chat({ messages }: { messages: Message[] }) {
  const [optimisticMessages, addOptimistic] = useOptimistic(
    messages,
    (state: Message[], newMessage: string) => [
      ...state,
      {
        id: crypto.randomUUID(),
        text: newMessage,
        sending: true
      }
    ]
  )

  async function sendMessage(formData: FormData) {
    const text = formData.get('message') as string

    // Immediately show message (optimistically)
    addOptimistic(text)

    // Send to server
    await submitMessage(text)
  }

  return (
    <div>
      <ul>
        {optimisticMessages.map(msg => (
          <li key={msg.id} className={msg.sending ? 'opacity-50' : ''}>
            {msg.text}
          </li>
        ))}
      </ul>

      <form action={sendMessage}>
        <input name="message" type="text" required />
        <button type="submit">Send</button>
      </form>
    </div>
  )
}
```

**Advanced Pattern - Optimistic with Error Handling**:
```typescript
interface TodoItem {
  id: string
  text: string
  completed: boolean
  optimistic?: boolean
}

function TodoList({ initialTodos }: { initialTodos: TodoItem[] }) {
  const [todos, setTodos] = useState(initialTodos)
  const [optimisticTodos, setOptimisticTodos] = useOptimistic(
    todos,
    (state: TodoItem[], action: { type: 'add' | 'toggle' | 'delete'; payload: any }) => {
      switch (action.type) {
        case 'add':
          return [...state, { ...action.payload, optimistic: true }]
        case 'toggle':
          return state.map(todo =>
            todo.id === action.payload.id
              ? { ...todo, completed: !todo.completed, optimistic: true }
              : todo
          )
        case 'delete':
          return state.filter(todo => todo.id !== action.payload.id)
        default:
          return state
      }
    }
  )

  async function addTodo(formData: FormData) {
    const text = formData.get('text') as string
    const tempId = crypto.randomUUID()

    // Optimistic update
    setOptimisticTodos({
      type: 'add',
      payload: { id: tempId, text, completed: false }
    })

    try {
      // Server request
      const newTodo = await createTodo(text)
      setTodos(prev => [...prev, newTodo])
    } catch (error) {
      // Rollback on error
      setTodos(prev => prev.filter(t => t.id !== tempId))
      alert('Failed to add todo')
    }
  }

  async function toggleTodo(id: string) {
    setOptimisticTodos({ type: 'toggle', payload: { id } })

    try {
      await updateTodo(id)
      setTodos(prev => prev.map(t => (t.id === id ? { ...t, completed: !t.completed } : t)))
    } catch (error) {
      // Rollback
      setTodos(prev => prev.map(t => (t.id === id ? { ...t, completed: !t.completed } : t)))
      alert('Failed to update todo')
    }
  }

  return (
    <div>
      <ul>
        {optimisticTodos.map(todo => (
          <li key={todo.id}>
            <input
              type="checkbox"
              checked={todo.completed}
              onChange={() => toggleTodo(todo.id)}
              disabled={todo.optimistic}
            />
            <span className={todo.optimistic ? 'opacity-50' : ''}>{todo.text}</span>
          </li>
        ))}
      </ul>

      <form action={addTodo}>
        <input name="text" type="text" required />
        <button type="submit">Add Todo</button>
      </form>
    </div>
  )
}
```

---

### use() - Read Promises and Context

```typescript
import { use, Suspense } from 'react'

// use() with promises
interface Comment {
  id: number
  text: string
  author: string
}

async function fetchComments(): Promise<Comment[]> {
  const response = await fetch('/api/comments')
  return response.json()
}

function Comments({ commentsPromise }: { commentsPromise: Promise<Comment[]> }) {
  // use() suspends until promise resolves
  const comments = use(commentsPromise)

  return (
    <ul>
      {comments.map(comment => (
        <li key={comment.id}>
          <strong>{comment.author}:</strong> {comment.text}
        </li>
      ))}
    </ul>
  )
}

function App() {
  const commentsPromise = fetchComments()

  return (
    <Suspense fallback={<div>Loading comments...</div>}>
      <Comments commentsPromise={commentsPromise} />
    </Suspense>
  )
}
```

**Conditional Promise Reading (use() advantage over await)**:
```typescript
function UserProfile({ userId, includeComments }: { userId: string; includeComments: boolean }) {
  const userPromise = fetchUser(userId)
  const user = use(userPromise)

  // use() can be called conditionally (unlike hooks!)
  const comments = includeComments ? use(fetchComments(userId)) : []

  return (
    <div>
      <h1>{user.name}</h1>
      {comments.length > 0 && (
        <ul>
          {comments.map(c => <li key={c.id}>{c.text}</li>)}
        </ul>
      )}
    </div>
  )
}
```

**use() with Context**:
```typescript
const ThemeContext = createContext<'light' | 'dark'>('light')

function Button() {
  // use() can read context (alternative to useContext)
  const theme = use(ThemeContext)

  return <button className={theme === 'dark' ? 'dark' : 'light'}>Click</button>
}
```

---

## Ref Callback Cleanup Functions

React 19 supports cleanup functions from ref callbacks. TypeScript enforces explicit returns.

```typescript
// Old: Implicit return (ERROR in React 19)
<div ref={el => (myRef = el)} />  // TypeScript error!

// New: Explicit return (no cleanup)
<div ref={el => { myRef = el }} />

// With cleanup function
function VideoPlayer() {
  const videoRef = useRef<HTMLVideoElement>(null)

  return (
    <video
      ref={el => {
        if (el) {
          // Setup
          videoRef.current = el
          el.play()

          // Cleanup function (called on unmount or when element changes)
          return () => {
            el.pause()
            videoRef.current = null
          }
        }
      }}
      src="/video.mp4"
    />
  )
}

// Advanced: Event listener cleanup
function InteractiveDiv() {
  return (
    <div
      ref={el => {
        if (!el) return

        const handleClick = () => console.log('clicked')
        el.addEventListener('click', handleClick)

        // Cleanup: Remove event listener
        return () => {
          el.removeEventListener('click', handleClick)
        }
      }}
    >
      Click me
    </div>
  )
}
```

---

## Document Metadata (Built-in)

React 19 automatically hoists metadata tags to `<head>`.

```typescript
function BlogPost({ post }: { post: Post }) {
  return (
    <article>
      {/* These get hoisted to <head> automatically */}
      <title>{post.title} - My Site</title>
      <meta name="description" content={post.excerpt} />
      <meta property="og:title" content={post.title} />
      <meta property="og:description" content={post.excerpt} />
      <meta property="og:image" content={post.coverImage} />
      <link rel="canonical" href={`https://example.com/posts/${post.slug}`} />

      {/* Regular content */}
      <h1>{post.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: post.content }} />
    </article>
  )
}

// Multiple components can add metadata
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Default metadata */}
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>{children}</body>
    </html>
  )
}

// Child components override with more specific metadata
function ProductPage({ product }: { product: Product }) {
  return (
    <div>
      <title>{product.name} - Shop</title>
      <meta name="description" content={product.description} />
      <meta property="og:type" content="product" />
      <meta property="product:price:amount" content={product.price.toString()} />

      <h1>{product.name}</h1>
      <p>{product.description}</p>
    </div>
  )
}
```

**Note**: For complex SEO requirements, still use `react-helmet-async` or Next.js `<Head>`. Built-in metadata is for simple cases.

---

## Native Form Actions

React 19 supports `action` prop on forms for progressive enhancement.

```typescript
interface ActionResult {
  success: boolean
  message: string
  errors?: Record<string, string[]>
}

// Server action (Next.js)
async function handleSubmit(formData: FormData): Promise<ActionResult> {
  'use server'

  const data = {
    name: formData.get('name') as string,
    email: formData.get('email') as string
  }

  // Validate
  const result = FormSchema.safeParse(data)
  if (!result.success) {
    return {
      success: false,
      message: 'Validation failed',
      errors: result.error.flatten().fieldErrors
    }
  }

  // Process
  await saveUser(result.data)
  return { success: true, message: 'User saved!' }
}

function UserForm() {
  const [state, formAction, isPending] = useActionState(handleSubmit, {
    success: false,
    message: ''
  })

  return (
    <form action={formAction}>
      <input name="name" type="text" required />
      {state.errors?.name && <span className="error">{state.errors.name[0]}</span>}

      <input name="email" type="email" required />
      {state.errors?.email && <span className="error">{state.errors.email[0]}</span>}

      <button type="submit" disabled={isPending}>
        {isPending ? 'Saving...' : 'Submit'}
      </button>

      {state.message && (
        <p className={state.success ? 'success' : 'error'}>{state.message}</p>
      )}
    </form>
  )
}
```

**Client-side action**:
```typescript
function SearchForm() {
  async function handleSearch(formData: FormData) {
    const query = formData.get('query') as string

    // Client-side processing
    const results = await searchAPI(query)
    setResults(results)
  }

  return (
    <form action={handleSearch}>
      <input name="query" type="text" placeholder="Search..." />
      <button type="submit">Search</button>
    </form>
  )
}
```

---

## TypeScript 5+ Features for React

### Const Type Parameters

```typescript
function useState<T>(initialValue: T): [T, (value: T) => void] {
  // ...
}

// Before: Type widened to string
const [status, setStatus] = useState('active')  // type: string

// After: Type narrowed to literal
const [status, setStatus] = useState('active' as const)  // type: 'active'

// Better: Use satisfies for const inference
const [status, setStatus] = useState('active' satisfies Status)  // type: 'active'
```

### Satisfies Operator

```typescript
type Route = {
  path: string
  component: React.ComponentType
  exact?: boolean
}

// Before: Either lose type safety or lose autocomplete
const routes: Route[] = [
  { path: '/', component: Home, exact: true },
  { path: '/about', component: About }
]

// After: Get both type safety AND autocomplete
const routes = [
  { path: '/', component: Home, exact: true },
  { path: '/about', component: About }
] satisfies Route[]

// Type error if route is invalid, but inferred type preserves specifics
const route = routes[0]  // { path: '/', component: typeof Home, exact: true }
```

### Template Literal Types for Props

```typescript
type Size = 'sm' | 'md' | 'lg'
type Variant = 'primary' | 'secondary'

type ButtonClass = `btn-${Size}-${Variant}`
// "btn-sm-primary" | "btn-sm-secondary" | "btn-md-primary" | ...

interface ButtonProps {
  className?: ButtonClass
  children: React.ReactNode
}

function Button({ className, children }: ButtonProps) {
  return <button className={className}>{children}</button>
}

// TypeScript enforces valid combinations
<Button className="btn-md-primary">Valid</Button>
<Button className="btn-invalid">Error!</Button>
```

### NoInfer for Generic Constraints

```typescript
// Problem: TypeScript infers T from both parameters
function createStore<T>(initialState: T, validator: (state: T) => boolean) {
  // ...
}

// This incorrectly widens to { count: number } | boolean
createStore({ count: 0 }, (state) => state === true)

// Solution: Use NoInfer to prevent inference from validator
function createStore<T>(
  initialState: T,
  validator: (state: NoInfer<T>) => boolean
) {
  // ...
}

// Now T is inferred only from initialState
createStore({ count: 0 }, (state) => state === true)  // Error: boolean not assignable to { count: number }
```
