# TypeScript Frontend Error Catalog

Comprehensive error patterns and solutions for TypeScript frontend development.

## Category: Build and Compilation Errors

### Error: Type checking is too slow

**Symptoms**:
- `tsc` takes minutes to complete
- IDE becomes sluggish with large codebases
- Incremental builds don't help
- Memory usage spikes during compilation

**Cause**:
Overly complex types, circular references, or poor TypeScript configuration causing the compiler to perform expensive type computations.

**Solution**:
```bash
# 1. Enable incremental compilation
# tsconfig.json
{
  "compilerOptions": {
    "incremental": true,
    "tsBuildInfoFile": ".tsbuildinfo"
  }
}

# 2. Use project references for monorepos
# Root tsconfig.json
{
  "references": [
    { "path": "./packages/app" },
    { "path": "./packages/shared" }
  ]
}

# 3. Skip lib checking for dependencies
{
  "compilerOptions": {
    "skipLibCheck": true  // Skip type checking of declaration files
  }
}

# 4. Check for expensive type computations
# Look for deeply nested conditional types, recursive types
```

**Prevention**:
- Keep type complexity reasonable - avoid deeply nested mapped types
- Use simpler types for large objects
- Profile compilation with `tsc --diagnostics`
- Consider `isolatedModules: true` for faster builds

---

### Error: Module resolution failures

**Symptoms**:
```
Cannot find module '@/components/Button' or its corresponding type declarations.
```

**Cause**:
Path mapping in `tsconfig.json` doesn't match actual file structure, or bundler isn't configured to understand path aliases.

**Solution**:
```json
// tsconfig.json - Define path mappings
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@/components/*": ["./src/components/*"],
      "@/lib/*": ["./src/lib/*"]
    }
  }
}
```

```javascript
// vite.config.ts - Configure bundler to match
import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/lib': path.resolve(__dirname, './src/lib')
    }
  }
})
```

**Prevention**:
- Keep path mappings consistent between tsconfig and bundler config
- Use relative imports for closely related files
- Test imports after adding new path aliases

---

## Category: Type System Errors

### Error: Object is possibly 'null' or 'undefined'

**Symptoms**:
```typescript
const user = users.find(u => u.id === userId)
console.log(user.name)  // Error: Object is possibly 'undefined'
```

**Cause**:
Strict null checking enabled (which is good!) but code doesn't handle potential null/undefined values.

**Solution**:
```typescript
// Option 1: Optional chaining
console.log(user?.name)

// Option 2: Nullish coalescing
const name = user?.name ?? 'Unknown'

// Option 3: Type guard
if (user) {
  console.log(user.name)  // TypeScript knows user is defined
}

// Option 4: Non-null assertion (use sparingly!)
console.log(user!.name)  // Only if you KNOW it exists
```

**Prevention**:
- Always handle null/undefined cases
- Use optional chaining by default
- Prefer type guards over non-null assertions
- Validate external data with Zod before use

---

### Error: Type 'X' is not assignable to type 'Y'

**Symptoms**:
```typescript
interface User {
  id: string
  name: string
  email: string
}

const userData = { id: '1', name: 'John' }
const user: User = userData  // Error: Property 'email' is missing
```

**Cause**:
Object doesn't match the required type shape - missing required properties or wrong types.

**Solution**:
```typescript
// Option 1: Add missing properties
const user: User = {
  id: '1',
  name: 'John',
  email: 'john@example.com'
}

// Option 2: Make properties optional
interface User {
  id: string
  name: string
  email?: string  // Optional
}

// Option 3: Use Partial for incomplete objects
const partialUser: Partial<User> = { id: '1', name: 'John' }

// Option 4: Validate and handle missing data
const UserSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email().optional()
})

const result = UserSchema.safeParse(userData)
if (result.success) {
  const user: User = result.data
}
```

**Prevention**:
- Define interfaces that match actual data structures
- Use Zod schemas for runtime validation
- Make optional fields explicit with `?`
- Use utility types (Partial, Required, Pick, Omit) appropriately

---

## Category: React + TypeScript Errors

### Error: JSX element type 'X' does not have any construct or call signatures

**Symptoms**:
```typescript
const Button = (props: ButtonProps) => <button {...props} />
<Button />  // Error with capitalization or component definition
```

**Cause**:
Component isn't properly typed or isn't a valid React component.

**Solution**:
```typescript
// Option 1: Explicit React.FC (not recommended in React 19)
const Button: React.FC<ButtonProps> = (props) => <button {...props} />

// Option 2: Function component (recommended)
function Button(props: ButtonProps) {
  return <button {...props} />
}

// Option 3: Arrow function with proper return type
const Button = (props: ButtonProps): JSX.Element => {
  return <button {...props} />
}

// React 19: ref as prop
interface ButtonProps {
  children: React.ReactNode
  onClick?: () => void
  ref?: React.Ref<HTMLButtonElement>
}

function Button({ children, onClick, ref }: ButtonProps) {
  return <button ref={ref} onClick={onClick}>{children}</button>
}
```

**Prevention**:
- Use function declarations for components
- Type props interfaces clearly
- In React 19, use `ref` as a regular prop instead of `forwardRef`

---

### Error: Property 'ref' does not exist on type 'IntrinsicAttributes'

**Symptoms**:
```typescript
// React 18 pattern causing error in React 19
const MyComponent = forwardRef<HTMLDivElement, Props>((props, ref) => {
  return <div ref={ref}>{props.children}</div>
})
```

**Cause**:
Using deprecated `forwardRef` pattern in React 19 or not including ref in props type.

**Solution**:
```typescript
// React 19: ref as regular prop
interface Props {
  children: React.ReactNode
  className?: string
  ref?: React.Ref<HTMLDivElement>
}

function MyComponent({ children, className, ref }: Props) {
  return <div ref={ref} className={className}>{children}</div>
}

// For generic components
interface PolymorphicProps<T extends React.ElementType = 'div'> {
  as?: T
  children: React.ReactNode
  ref?: React.Ref<HTMLElement>
}

function Polymorphic<T extends React.ElementType = 'div'>({
  as,
  children,
  ref,
  ...props
}: PolymorphicProps<T> & Omit<React.ComponentPropsWithoutRef<T>, keyof PolymorphicProps<T>>) {
  const Component = as || 'div'
  return <Component ref={ref} {...props}>{children}</Component>
}
```

**Prevention**:
- Use ref as a prop in React 19
- Avoid `forwardRef` in new code
- Update existing components gradually

---

### Error: Ref callback return type mismatch (React 19)

**Symptoms**:
```typescript
// TypeScript error in React 19
<div ref={el => (myRef = el)} />  // Implicit return not allowed
```

**Cause**:
React 19 supports cleanup functions from ref callbacks, so TypeScript rejects implicit returns.

**Solution**:
```typescript
// Option 1: Explicit no-return (no cleanup)
<div ref={el => { myRef = el }} />

// Option 2: With cleanup function
<div ref={el => {
  myRef = el
  return () => { myRef = null }  // Cleanup on unmount
}} />

// Option 3: useRef hook instead
const myRef = useRef<HTMLDivElement>(null)
<div ref={myRef} />
```

**Prevention**:
- Use explicit function bodies for ref callbacks
- Prefer `useRef` hook for simple cases
- Add cleanup functions when needed (e.g., removing event listeners)

---

## Category: Form and Validation Errors

### Error: Zod validation fails at runtime

**Symptoms**:
```typescript
const schema = z.object({ email: z.string().email() })
const data = { email: 'invalid' }
schema.parse(data)  // Throws ZodError
```

**Cause**:
Data doesn't match schema definition, causing runtime validation failure.

**Solution**:
```typescript
// Option 1: safeParse for graceful handling
const result = schema.safeParse(data)
if (!result.success) {
  console.error(result.error.errors)  // Array of validation errors
  // Display errors to user
  result.error.errors.forEach(err => {
    console.log(`${err.path}: ${err.message}`)
  })
} else {
  // result.data is properly typed and validated
  console.log(result.data.email)
}

// Option 2: Custom error handling
try {
  const validated = schema.parse(data)
} catch (error) {
  if (error instanceof z.ZodError) {
    const fieldErrors = error.flatten().fieldErrors
    // { email: ["Invalid email"] }
  }
}

// Option 3: Transform errors for forms
const FormSchema = z.object({
  email: z.string().email('Please enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters')
})

const result = FormSchema.safeParse(formData)
if (!result.success) {
  const errors = result.error.formErrors.fieldErrors
  setFormErrors(errors)  // Set React state
}
```

**Prevention**:
- Always use `safeParse` for user input
- Provide helpful error messages in schemas
- Transform Zod errors to match form library format
- Test validation logic with edge cases

---

### Error: React Hook Form + TypeScript type mismatch

**Symptoms**:
```typescript
const { register } = useForm<FormData>()
<input {...register('nonExistentField')} />  // No type error!
```

**Cause**:
Field name isn't type-checked by default with React Hook Form.

**Solution**:
```typescript
import { useForm, UseFormReturn, Path } from 'react-hook-form'

interface FormData {
  email: string
  password: string
  age: number
}

// Type-safe field component
interface FieldProps {
  name: Path<FormData>  // Only allows valid field names
  label: string
  form: UseFormReturn<FormData>
}

function Field({ name, label, form }: FieldProps) {
  return (
    <div>
      <label>{label}</label>
      <input {...form.register(name)} />  // Type-safe!
      {form.formState.errors[name] && (
        <span>{form.formState.errors[name]?.message}</span>
      )}
    </div>
  )
}

// Usage
function MyForm() {
  const form = useForm<FormData>()
  return (
    <form>
      <Field name="email" label="Email" form={form} />
      <Field name="nonExistent" label="Error" form={form} />  {/* TypeScript error! */}
    </form>
  )
}
```

**Prevention**:
- Use `Path<T>` type for field names
- Create type-safe wrapper components
- Integrate Zod with React Hook Form via `zodResolver`

---

## Category: API and Data Fetching Errors

### Error: Unhandled promise rejection in fetch

**Symptoms**:
```typescript
async function fetchUser() {
  const response = await fetch('/api/user')
  const data = await response.json()
  return data  // No error handling!
}
```

**Cause**:
Missing error handling for network failures, API errors, or malformed responses.

**Solution**:
```typescript
// Complete error handling
async function fetchUser(): Promise<User> {
  try {
    const response = await fetch('/api/user')

    if (!response.ok) {
      throw new ApiError(
        `HTTP ${response.status}: ${response.statusText}`,
        response.status
      )
    }

    const data = await response.json()

    // Validate response with Zod
    const validated = UserSchema.parse(data)
    return validated

  } catch (error) {
    if (error instanceof ApiError) {
      throw error  // Re-throw API errors
    }
    if (error instanceof z.ZodError) {
      throw new Error(`Invalid response: ${error.message}`)
    }
    throw new Error(`Network error: ${error}`)
  }
}

// Usage with error handling
async function loadUser() {
  try {
    const user = await fetchUser()
    setUser(user)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirectToLogin()
    } else {
      setError(error.message)
    }
  }
}
```

**Prevention**:
- Always check `response.ok` before parsing
- Validate response data with Zod
- Create custom error classes for API errors
- Handle network errors separately from API errors

---

## Category: State Management Errors

### Error: Zustand state not updating in component

**Symptoms**:
```typescript
const useStore = create((set) => ({
  count: 0,
  increment: () => set({ count: count + 1 })  // Stale closure!
}))
```

**Cause**:
Closure captures stale state value instead of using current state.

**Solution**:
```typescript
// Correct: Use function form of set
const useStore = create<CounterStore>((set) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
  decrement: () => set((state) => ({ count: state.count - 1 }))
}))

// For complex updates
const useStore = create<Store>((set, get) => ({
  users: [],
  addUser: (user: User) => set((state) => ({
    users: [...state.users, user]
  })),
  // Access current state with get()
  getUserById: (id: string) => {
    return get().users.find(u => u.id === id)
  }
}))
```

**Prevention**:
- Always use function form of `set` when updating based on current state
- Use `get()` to access current state in actions
- Test state updates with multiple rapid calls

---

## Category: CSS and Styling Errors

### Error: Undefined CSS module class

**Symptoms**:
```typescript
import styles from './Button.module.css'
<button className={styles.primaryButton} />  // Runtime: undefined
```

**Cause**:
Class name doesn't exist in CSS module file, or CSS file isn't loaded correctly.

**Solution**:
```bash
# 1. Install CSS modules linting
npm install --save-dev eslint-plugin-css-modules

# 2. Add to .eslintrc.js
{
  "plugins": ["css-modules"],
  "rules": {
    "css-modules/no-undef-class": "error",
    "css-modules/no-unused-class": "warn"
  }
}

# 3. Optional: Generate TypeScript types
npm install --save-dev typescript-plugin-css-modules

# tsconfig.json
{
  "compilerOptions": {
    "plugins": [{ "name": "typescript-plugin-css-modules" }]
  }
}
```

**Prevention**:
- Use CSS modules linting to catch undefined classes at build time
- Generate TypeScript definitions for CSS modules
- Use Tailwind CSS for utility-first approach with autocomplete

---

### Error: Tailwind classes not working

**Symptoms**:
```typescript
<div className="mt-4 bg-blue-500">  {/* Styles not applied */}
```

**Cause**:
Class names not detected by Tailwind's JIT compiler, or configuration is incorrect.

**Solution**:
```javascript
// tailwind.config.js - Ensure content paths are correct
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
    './app/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}'
  ],
  // ...
}

// Check for dynamic class names (won't work with JIT)
// ❌ Bad - Tailwind can't detect
const color = 'blue'
<div className={`bg-${color}-500`} />

// ✅ Good - Full class names
<div className={color === 'blue' ? 'bg-blue-500' : 'bg-red-500'} />

// Install Tailwind linting
npm install --save-dev eslint-plugin-tailwindcss

// .eslintrc.js
{
  "plugins": ["tailwindcss"],
  "rules": {
    "tailwindcss/no-custom-classname": "warn"
  }
}
```

**Prevention**:
- Always use complete class names (no string interpolation)
- Verify content paths in `tailwind.config.js`
- Use safelist for dynamic classes
- Install Tailwind ESLint plugin for warnings

---

## Category: Performance Issues

### Error: Excessive re-renders

**Symptoms**:
- Component renders multiple times per state change
- Console shows multiple "render" logs
- UI feels sluggish

**Cause**:
Creating new object/function references on every render, causing child components to re-render unnecessarily.

**Solution**:
```typescript
// ❌ Bad - Creates new function every render
function Parent() {
  return <Child onClick={() => console.log('click')} />
}

// ✅ Good - Use useCallback
function Parent() {
  const handleClick = useCallback(() => {
    console.log('click')
  }, [])

  return <Child onClick={handleClick} />
}

// ❌ Bad - Creates new object every render
function Parent() {
  return <Child config={{ theme: 'dark' }} />
}

// ✅ Good - Use useMemo
function Parent() {
  const config = useMemo(() => ({ theme: 'dark' }), [])
  return <Child config={config} />
}

// ✅ Better - Move static data outside component
const CONFIG = { theme: 'dark' }
function Parent() {
  return <Child config={CONFIG} />
}
```

**Prevention**:
- Move static data outside components
- Use `useCallback` for event handlers passed to children
- Use `useMemo` for computed values or object props
- Use React DevTools Profiler to identify re-render causes
