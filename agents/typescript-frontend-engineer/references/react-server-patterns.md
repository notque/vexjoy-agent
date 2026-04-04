# React Server Patterns Reference
<!-- Loaded by typescript-frontend-engineer when task involves RSC, server components, data fetching, server actions, or caching -->

## Parallel Data Fetching with Component Composition
**Impact:** CRITICAL — eliminates server-side waterfalls

Component composition parallelizes RSC data fetching — each async component fetches independently rather than waiting for its parent to finish.

**Instead of:**
```tsx
// Sidebar waits for Page's fetch to complete
export default async function Page() {
  const header = await fetchHeader()
  return (
    <div>
      <div>{header}</div>
      <Sidebar />
    </div>
  )
}

async function Sidebar() {
  const items = await fetchSidebarItems()
  return <nav>{items.map(renderItem)}</nav>
}
```

**Use:**
```tsx
// Both fetch simultaneously
async function Header() {
  const data = await fetchHeader()
  return <div>{data}</div>
}

async function Sidebar() {
  const items = await fetchSidebarItems()
  return <nav>{items.map(renderItem)}</nav>
}

export default function Page() {
  return (
    <div>
      <Header />
      <Sidebar />
    </div>
  )
}
```

Children composition also works — `Layout` renders `Header` alongside whatever children the page passes in, both fetching in parallel:

```tsx
function Layout({ children }: { children: ReactNode }) {
  return (
    <div>
      <Header />
      {children}
    </div>
  )
}

export default function Page() {
  return (
    <Layout>
      <Sidebar />
    </Layout>
  )
}
```

---

## Per-Request Deduplication with React.cache()
**Impact:** MEDIUM — eliminates duplicate queries within a single request

`React.cache()` ensures each request gets its own isolated data — multiple components calling the same cached function within one render share the result without re-fetching.

**Instead of:**
```typescript
// Each component call hits the database separately
export async function getUser(uid: number) {
  return await db.user.findUnique({ where: { id: uid } })
}
```

**Use:**
```typescript
import { cache } from 'react'

export const getCurrentUser = cache(async () => {
  const session = await auth()
  if (!session?.user?.id) return null
  return await db.user.findUnique({ where: { id: session.user.id } })
})

// Multiple components calling getCurrentUser() within one request
// execute the query exactly once
```

**Argument equality uses `Object.is` — use primitives, not objects:**
```typescript
// Always cache miss — inline objects create new references each call
const getUser = cache(async (params: { uid: number }) => { /* ... */ })
getUser({ uid: 1 })  // runs query
getUser({ uid: 1 })  // runs query again

// Cache hit — primitives use value equality
const getUser = cache(async (uid: number) => {
  return await db.user.findUnique({ where: { id: uid } })
})
getUser(1)  // runs query
getUser(1)  // cache hit
```

Use `React.cache()` for: database queries, authentication checks, heavy computations, file system operations, and any async work that may be called from multiple components in one request.

---

## Request-Scoped State — No Shared Module Variables
**Impact:** HIGH — prevents cross-request data leakage in concurrent rendering

Keep request data local to the render tree. Module-level mutable variables are process-wide shared memory — concurrent renders can overwrite each other's data, causing one user's data to appear in another's response.

**Instead of:**
```tsx
// Race condition: request B can overwrite currentUser before request A finishes
let currentUser: User | null = null

export default async function Page() {
  currentUser = await auth()
  return <Dashboard />
}

async function Dashboard() {
  return <div>{currentUser?.name}</div>
}
```

**Use:**
```tsx
// Each render carries its own user reference through the component tree
export default async function Page() {
  const user = await auth()
  return <Dashboard user={user} />
}

function Dashboard({ user }: { user: User | null }) {
  return <div>{user?.name}</div>
}
```

Safe at module level: immutable static config loaded once at startup, caches intentionally shared across requests and keyed correctly, process-wide singletons that hold no user-specific mutable state.

---

## Minimize Serialization at RSC Boundaries
**Impact:** HIGH — reduces page weight and load time

Only pass fields the client component actually uses across the server/client boundary. Every prop is serialized into the HTML response — unused fields add wire weight with no benefit.

**Instead of:**
```tsx
// Serializes all 50 fields from the user object
async function Page() {
  const user = await fetchUser()
  return <Profile user={user} />
}

'use client'
function Profile({ user }: { user: User }) {
  return <div>{user.name}</div>  // uses 1 field
}
```

**Use:**
```tsx
// Serializes only what the client needs
async function Page() {
  const user = await fetchUser()
  return <Profile name={user.name} />
}

'use client'
function Profile({ name }: { name: string }) {
  return <div>{name}</div>
}
```

---

## Cross-Request LRU Caching
**Impact:** HIGH — serves repeated queries from memory across sequential requests

`React.cache()` only deduplicates within one request. For data that multiple sequential requests need (a user navigating through several pages), an LRU cache avoids repeated database hits.

**Use:**
```typescript
import { LRUCache } from 'lru-cache'

const cache = new LRUCache<string, unknown>({
  max: 1000,
  ttl: 5 * 60 * 1000  // 5 minutes
})

export async function getUser(id: string) {
  const cached = cache.get(id)
  if (cached) return cached

  const user = await db.user.findUnique({ where: { id } })
  cache.set(id, user)
  return user
}
// Request 1: DB query, result cached
// Request 2 (same user): cache hit, no DB query
```

In traditional serverless environments where each function invocation is isolated, consider Redis or another shared store for cross-process caching.

---

## Hoist Static I/O to Module Level
**Impact:** HIGH — eliminates repeated file/network I/O on every request

Module-level code runs once when the module is first imported. Hoisting static asset loading (fonts, images, config files) to module scope avoids re-reading them on every request.

**Instead of:**
```typescript
// Reads from disk on every request
export async function GET(request: Request) {
  const fontData = await fetch(new URL('./fonts/Inter.ttf', import.meta.url))
    .then(res => res.arrayBuffer())
  // ... use fontData
}
```

**Use:**
```typescript
// Starts fetching once at module init, awaited per-request
const fontData = fetch(new URL('./fonts/Inter.ttf', import.meta.url))
  .then(res => res.arrayBuffer())

const configPromise = fs.readFile('./config.json', 'utf-8').then(JSON.parse)

export async function GET(request: Request) {
  const [font, config] = await Promise.all([fontData, configPromise])
  // ... use font, config
}
```

Apply when: loading fonts for image generation, reading config files that are static at runtime, loading email or HTML templates, any asset identical across all requests.

Do not apply when: assets vary per request or user, files may change at runtime, large files would consume excessive memory.

---

## Authenticate Server Actions Like API Routes
**Impact:** CRITICAL — prevents unauthorized access to server mutations

Server Actions are public endpoints. Always verify authentication and authorization inside each action — middleware and layout guards can be bypassed by calling actions directly.

**Instead of:**
```typescript
'use server'

export async function deleteUser(userId: string) {
  // No auth — anyone can call this directly
  await db.user.delete({ where: { id: userId } })
  return { success: true }
}
```

**Use:**
```typescript
'use server'

import { z } from 'zod'

const updateProfileSchema = z.object({
  userId: z.string().uuid(),
  name: z.string().min(1).max(100),
  email: z.string().email(),
})

export async function updateProfile(data: unknown) {
  // 1. Validate input first
  const validated = updateProfileSchema.parse(data)

  // 2. Authenticate
  const session = await verifySession()
  if (!session) throw new Error('Unauthorized')

  // 3. Authorize
  if (session.user.id !== validated.userId) throw new Error('Forbidden')

  // 4. Perform mutation
  await db.user.update({
    where: { id: validated.userId },
    data: { name: validated.name, email: validated.email },
  })

  return { success: true }
}
```

Order matters: validate input first (avoids auth overhead on malformed data), then authenticate, then authorize, then mutate.

---

## Non-Blocking Post-Response Work
**Impact:** MEDIUM — faster response times for logging and side effects

Schedule logging, analytics, and notifications to run after the response is sent rather than blocking it. The user gets their response immediately; side effects happen in the background.

Available in Next.js via `after()` from `next/server`. Other frameworks provide similar mechanisms — the principle applies regardless of framework.

**Instead of:**
```tsx
export async function POST(request: Request) {
  await updateDatabase(request)
  await logUserAction({ userAgent: request.headers.get('user-agent') })  // blocks response
  return new Response(JSON.stringify({ status: 'success' }), { status: 200 })
}
```

**Use (Next.js):**
```tsx
import { after } from 'next/server'

export async function POST(request: Request) {
  await updateDatabase(request)

  after(async () => {
    await logUserAction({ userAgent: request.headers.get('user-agent') ?? 'unknown' })
  })

  return new Response(JSON.stringify({ status: 'success' }), { status: 200 })
}
```

Common use cases: analytics tracking, audit logging, notifications, cache invalidation, cleanup tasks.

---

## Parallel Nested Data Fetching
**Impact:** CRITICAL — prevents one slow item from blocking all nested fetches

Chain each item's dependent fetch within its own promise. A slow item's inner fetch starts as soon as its outer fetch resolves, without waiting for all outer fetches to complete.

**Instead of:**
```tsx
// A single slow getChat() blocks ALL author fetches from starting
const chats = await Promise.all(chatIds.map(id => getChat(id)))
const chatAuthors = await Promise.all(chats.map(chat => getUser(chat.author)))
```

**Use:**
```tsx
// Each item chains independently — a slow chat only delays its own author fetch
const chatAuthors = await Promise.all(
  chatIds.map(id => getChat(id).then(chat => getUser(chat.author)))
)
```

---

## Move Client Transformations to Client Components
**Impact:** LOW — reduces network payload for primitive arrays

RSC serialization deduplicates by object reference. Transforming an array on the server (`.toSorted()`, `.filter()`, `.map()`) creates a new reference and forces both arrays to serialize. Move transformations to the client component.

**Instead of:**
```tsx
// Sends 6 strings — both arrays fully serialized
<ClientList usernames={usernames} usernamesOrdered={usernames.toSorted()} />
```

**Use:**
```tsx
// Sends 3 strings — one array, transform in client
<ClientList usernames={usernames} />

'use client'
const sorted = useMemo(() => [...usernames].sort(), [usernames])
```

Operations that break deduplication: `.toSorted()`, `.filter()`, `.map()`, `.slice()`, spread syntax, `Object.assign()`, `structuredClone()`.

Exception: pass derived data when the transformation is computationally expensive and the client does not need the original.
