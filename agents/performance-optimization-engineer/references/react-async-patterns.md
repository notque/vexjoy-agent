# React Async Patterns Reference
<!-- Loaded by performance-optimization-engineer when task involves async data fetching, waterfalls, or parallelization -->

## Promise.all for Independent Operations
**Impact:** CRITICAL — 2-10x improvement

Independent async operations complete in the time of the slowest, not the sum of all. `Promise.all` enables parallel fetching for any operations with no interdependencies.

**Instead of:**
```typescript
const user = await fetchUser()
const posts = await fetchPosts()
const comments = await fetchComments()
// Total time: fetchUser + fetchPosts + fetchComments
```

**Use:**
```typescript
const [user, posts, comments] = await Promise.all([
  fetchUser(),
  fetchPosts(),
  fetchComments()
])
// Total time: max(fetchUser, fetchPosts, fetchComments)
```

---

## Cheap Condition Before Await
**Impact:** HIGH — avoids unnecessary async work when a synchronous guard already fails

When a branch uses `await` for a flag or remote value and also requires a cheap synchronous condition (local props, already-loaded state), evaluate the cheap condition first. Otherwise you pay for the async call even when the compound condition can never be true.

**Instead of:**
```typescript
const someFlag = await getFlag()

if (someFlag && someCondition) {
  // ...
}
```

**Use:**
```typescript
if (someCondition) {
  const someFlag = await getFlag()
  if (someFlag) {
    // ...
  }
}
```

This matters when `getFlag` hits the network, a feature-flag service, or a cache: skipping it when `someCondition` is false removes that cost on the cold path.

Keep the original order if `someCondition` is expensive, depends on the flag, or side effects must run in fixed order.

---

## Defer Await to Maximize Parallelism
**Impact:** HIGH — avoids blocking unused code paths

Move `await` into the branches where the result is actually used. Starting a fetch does not require awaiting it immediately — and returning early before an await means the fetch never happens at all.

**Instead of:**
```typescript
async function handleRequest(userId: string, skipProcessing: boolean) {
  const userData = await fetchUserData(userId)

  if (skipProcessing) {
    return { skipped: true } // still waited for userData
  }

  return processUserData(userData)
}
```

**Use:**
```typescript
async function handleRequest(userId: string, skipProcessing: boolean) {
  if (skipProcessing) {
    return { skipped: true } // no fetch at all
  }

  const userData = await fetchUserData(userId)
  return processUserData(userData)
}
```

Another example — ordering awaits by dependency rather than by declaration:

```typescript
// fetch only what each step actually needs, in the order needed
async function updateResource(resourceId: string, userId: string) {
  const resource = await getResource(resourceId)
  if (!resource) return { error: 'Not found' }

  const permissions = await fetchPermissions(userId)
  if (!permissions.canEdit) return { error: 'Forbidden' }

  return updateResourceData(resource, permissions)
}
```

This optimization is especially valuable when the skipped branch is frequently taken or when the deferred operation is expensive.

---

## Dependency-Based Parallelization
**Impact:** CRITICAL — 2-10x improvement

When operations have partial dependencies (B needs A, but C is independent of both), naive `Promise.all` groups them incorrectly and serializes what could be parallel. Starting each operation as early as possible — by chaining off the promise rather than the resolved value — maximizes concurrency.

**Instead of:**
```typescript
const [user, config] = await Promise.all([fetchUser(), fetchConfig()])
const profile = await fetchProfile(user.id) // profile forced to wait for config
```

**Use:**
```typescript
const userPromise = fetchUser()
const profilePromise = userPromise.then(user => fetchProfile(user.id))

const [user, config, profile] = await Promise.all([
  userPromise,
  fetchConfig(), // runs in parallel with user and profile chain
  profilePromise
])
```

For complex dependency graphs, the `better-all` library provides a declarative API that automatically starts each task at the earliest possible moment:

```typescript
import { all } from 'better-all'

const { user, config, profile } = await all({
  async user() { return fetchUser() },
  async config() { return fetchConfig() },
  async profile() {
    return fetchProfile((await this.$.user).id)
  }
})
```

Reference: [better-all](https://github.com/shuding/better-all)

---

## Suspense Boundaries for Streaming
**Impact:** HIGH — faster initial paint

Instead of awaiting all data before returning JSX, use Suspense boundaries to show wrapper UI immediately while data streams in. Only the component that needs the data blocks — the rest of the page renders without waiting.

**Instead of:**
```tsx
async function Page() {
  const data = await fetchData() // blocks entire page

  return (
    <div>
      <Sidebar />
      <Header />
      <DataDisplay data={data} />
      <Footer />
    </div>
  )
}
```

**Use:**
```tsx
function Page() {
  return (
    <div>
      <Sidebar />
      <Header />
      <Suspense fallback={<Skeleton />}>
        <DataDisplay />
      </Suspense>
      <Footer />
    </div>
  )
}

async function DataDisplay() {
  const data = await fetchData() // only blocks this component
  return <div>{data.content}</div>
}
```

When multiple components share the same data, pass the promise down rather than fetching separately — one network request, shared across both:

```tsx
function Page() {
  const dataPromise = fetchData() // start fetch, don't await

  return (
    <Suspense fallback={<Skeleton />}>
      <DataDisplay dataPromise={dataPromise} />
      <DataSummary dataPromise={dataPromise} />
    </Suspense>
  )
}

function DataDisplay({ dataPromise }: { dataPromise: Promise<Data> }) {
  const data = use(dataPromise)
  return <div>{data.content}</div>
}
```

When not to apply: SEO-critical above-fold content, data needed for layout decisions, or small fast queries where the fallback causes more layout shift than it saves.

---

## API Route Waterfall Prevention
**Impact:** CRITICAL — 2-10x improvement

In API route handlers and server actions, start independent operations immediately rather than awaiting sequentially. The pattern: fire all promises, then await only what each subsequent step depends on.

**Instead of:**
```typescript
export async function GET(request: Request) {
  const session = await auth()
  const config = await fetchConfig() // waits for auth unnecessarily
  const data = await fetchData(session.user.id)
  return Response.json({ data, config })
}
```

**Use:**
```typescript
export async function GET(request: Request) {
  const sessionPromise = auth()
  const configPromise = fetchConfig() // starts immediately, no dependency on auth

  const session = await sessionPromise
  const [config, data] = await Promise.all([
    configPromise,
    fetchData(session.user.id)
  ])

  return Response.json({ data, config })
}
```

Auth and config fetch in parallel. `fetchData` starts as soon as auth resolves, and config is guaranteed ready by the time both complete.

---
