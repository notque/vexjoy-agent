# JavaScript Algorithm Optimizations Reference
<!-- Loaded by performance-optimization-engineer when task involves Set, Map, array, loop, sort, flatMap, early return, or index maps -->

Apply these patterns in hot paths: render loops, event handlers called frequently, data processing pipelines. Skip them for code that runs once or rarely — the gains are real but small in isolation, and they compound when applied to high-frequency code.

---

## Set and Map for O(1) Lookups
**Impact:** LOW-MEDIUM — O(n) to O(1) per membership check

Array `.includes()` scans every element. Converting to a `Set` or `Map` makes repeated lookups constant time — the larger the collection and the more checks you perform, the more this compounds.

**Instead of:**
```typescript
const allowedIds = ['a', 'b', 'c', ...]
items.filter(item => allowedIds.includes(item.id)) // O(n) per item
```

**Use:**
```typescript
const allowedIds = new Set(['a', 'b', 'c', ...])
items.filter(item => allowedIds.has(item.id)) // O(1) per item
```

Build the Set once outside the loop; pay the O(n) construction cost once rather than O(n) per lookup.

---

## Index Maps for Repeated Lookups
**Impact:** LOW-MEDIUM — O(n) to O(1) per lookup; 1M ops to 2K ops for 1000×1000 case

Multiple `.find()` calls over the same array perform O(n) work each time. Building a Map once pays O(n) upfront and makes every subsequent lookup O(1).

**Instead of:**
```typescript
function processOrders(orders: Order[], users: User[]) {
  return orders.map(order => ({
    ...order,
    user: users.find(u => u.id === order.userId) // O(n) per order
  }))
}
```

**Use:**
```typescript
function processOrders(orders: Order[], users: User[]) {
  const userById = new Map(users.map(u => [u.id, u])) // O(n) once

  return orders.map(order => ({
    ...order,
    user: userById.get(order.userId) // O(1) per order
  }))
}
```

For 1000 orders × 1000 users: 1,000,000 comparisons reduced to ~2,000.

---

## Cache Function Results
**Impact:** MEDIUM — avoids redundant computation for repeated calls with same inputs

When the same function is called repeatedly with the same inputs — especially in render loops — a module-level Map eliminates recomputation. This differs from `useMemo` in that it works anywhere (utilities, event handlers), not just inside React components.

**Instead of:**
```typescript
function ProjectList({ projects }: { projects: Project[] }) {
  return (
    <div>
      {projects.map(project => {
        const slug = slugify(project.name) // recomputed on every render
        return <ProjectCard key={project.id} slug={slug} />
      })}
    </div>
  )
}
```

**Use:**
```typescript
const slugifyCache = new Map<string, string>()

function cachedSlugify(text: string): string {
  if (slugifyCache.has(text)) return slugifyCache.get(text)!
  const result = slugify(text)
  slugifyCache.set(text, result)
  return result
}
```

For single-value functions, a simple variable cache works:
```typescript
let isLoggedInCache: boolean | null = null

function isLoggedIn(): boolean {
  if (isLoggedInCache !== null) return isLoggedInCache
  isLoggedInCache = document.cookie.includes('auth=')
  return isLoggedInCache
}

function onAuthChange() {
  isLoggedInCache = null // invalidate on change
}
```

---

## Cache Property Access in Loops
**Impact:** LOW-MEDIUM — reduces object traversal in hot loops

Deep property chains (`obj.config.settings.value`) re-traverse the object graph on every iteration. Caching the resolved value before the loop eliminates that overhead for the duration of the loop.

**Instead of:**
```typescript
for (let i = 0; i < arr.length; i++) {
  process(obj.config.settings.value) // 3 property lookups × N iterations
}
```

**Use:**
```typescript
const value = obj.config.settings.value // 3 lookups once
const len = arr.length                  // 1 lookup once
for (let i = 0; i < len; i++) {
  process(value)
}
```

---

## Combine Array Iterations
**Impact:** LOW-MEDIUM — reduces iterations over large arrays

Multiple chained `.filter()` calls each traverse the full array. A single `for...of` loop with multiple conditionals does the same work in one pass.

**Instead of:**
```typescript
const admins = users.filter(u => u.isAdmin)    // pass 1
const testers = users.filter(u => u.isTester)  // pass 2
const inactive = users.filter(u => !u.isActive) // pass 3
```

**Use:**
```typescript
const admins: User[] = []
const testers: User[] = []
const inactive: User[] = []

for (const user of users) {
  if (user.isAdmin) admins.push(user)
  if (user.isTester) testers.push(user)
  if (!user.isActive) inactive.push(user)
}
```

---

## Early Returns
**Impact:** LOW-MEDIUM — avoids unnecessary computation when result is already determined

Returning as soon as an answer is known skips all remaining iterations and branches. Most valuable when the early-exit condition is frequently true or when the remaining computation is expensive.

**Instead of:**
```typescript
function validateUsers(users: User[]) {
  let hasError = false
  let errorMessage = ''

  for (const user of users) {
    if (!user.email) { hasError = true; errorMessage = 'Email required' }
    if (!user.name) { hasError = true; errorMessage = 'Name required' }
    // Continues scanning even after first error found
  }

  return hasError ? { valid: false, error: errorMessage } : { valid: true }
}
```

**Use:**
```typescript
function validateUsers(users: User[]) {
  for (const user of users) {
    if (!user.email) return { valid: false, error: 'Email required' }
    if (!user.name) return { valid: false, error: 'Name required' }
  }
  return { valid: true }
}
```

---

## flatMap Over filter + map
**Impact:** LOW-MEDIUM — eliminates intermediate array and reduces iterations

`.map().filter(Boolean)` creates an intermediate array and iterates twice. `.flatMap()` transforms and filters in a single pass with no intermediate allocation.

**Instead of:**
```typescript
const userNames = users
  .map(user => user.isActive ? user.name : null) // intermediate array
  .filter(Boolean) // second pass
```

**Use:**
```typescript
const userNames = users.flatMap(user =>
  user.isActive ? [user.name] : []
)
```

More examples:
```typescript
// Extract valid emails
const emails = responses.flatMap(r =>
  r.success ? [r.data.email] : []
)

// Parse and filter valid numbers
const numbers = strings.flatMap(s => {
  const n = parseInt(s, 10)
  return isNaN(n) ? [] : [n]
})
```

---

## Loop for Min/Max Instead of Sort
**Impact:** LOW — O(n) instead of O(n log n)

Sorting an array just to read the first or last element does O(n log n) work when O(n) is sufficient. A single loop finds the minimum or maximum in one pass without allocating a new array.

**Instead of:**
```typescript
function getLatestProject(projects: Project[]) {
  return [...projects].sort((a, b) => b.updatedAt - a.updatedAt)[0]
}
```

**Use:**
```typescript
function getLatestProject(projects: Project[]) {
  if (projects.length === 0) return null
  let latest = projects[0]
  for (let i = 1; i < projects.length; i++) {
    if (projects[i].updatedAt > latest.updatedAt) latest = projects[i]
  }
  return latest
}
```

Finding both min and max in one pass:
```typescript
function getOldestAndNewest(projects: Project[]) {
  if (projects.length === 0) return { oldest: null, newest: null }
  let oldest = projects[0], newest = projects[0]
  for (let i = 1; i < projects.length; i++) {
    if (projects[i].updatedAt < oldest.updatedAt) oldest = projects[i]
    if (projects[i].updatedAt > newest.updatedAt) newest = projects[i]
  }
  return { oldest, newest }
}
```

`Math.min(...arr)` works for small arrays but can throw or produce incorrect results for very large arrays (spread operator argument count limits). The loop approach is reliable at any size.

---

## toSorted for Immutable Sorting
**Impact:** MEDIUM-HIGH — prevents mutation bugs in React state and props

`.sort()` mutates the array in place. Sorting a prop array or state array directly breaks React's immutability model and causes stale closure bugs. `.toSorted()` returns a new sorted array, leaving the original untouched.

**Instead of:**
```typescript
function UserList({ users }: { users: User[] }) {
  const sorted = useMemo(
    () => users.sort((a, b) => a.name.localeCompare(b.name)), // mutates prop!
    [users]
  )
  return <div>{sorted.map(renderUser)}</div>
}
```

**Use:**
```typescript
function UserList({ users }: { users: User[] }) {
  const sorted = useMemo(
    () => users.toSorted((a, b) => a.name.localeCompare(b.name)),
    [users]
  )
  return <div>{sorted.map(renderUser)}</div>
}
```

Browser support: Chrome 110+, Safari 16+, Firefox 115+, Node.js 20+. Fallback:
```typescript
const sorted = [...items].sort((a, b) => a.value - b.value)
```

Related immutable array methods: `.toReversed()`, `.toSpliced()`, `.with()`.

---

## Length Check Before Expensive Comparison
**Impact:** MEDIUM-HIGH — avoids expensive operations when lengths differ

When comparing arrays with expensive operations (sorting, deep equality, serialization), arrays of different lengths cannot be equal. An O(1) length check eliminates the expensive path for that case.

**Instead of:**
```typescript
function hasChanges(current: string[], original: string[]) {
  return current.sort().join() !== original.sort().join() // always sorts both
}
```

**Use:**
```typescript
function hasChanges(current: string[], original: string[]) {
  if (current.length !== original.length) return true // O(1) early exit

  const currentSorted = current.toSorted()
  const originalSorted = original.toSorted()
  for (let i = 0; i < currentSorted.length; i++) {
    if (currentSorted[i] !== originalSorted[i]) return true
  }
  return false
}
```

Uses `.toSorted()` to avoid mutating the input arrays as a bonus.
