# React Client Data Fetching Reference
<!-- Loaded by typescript-frontend-engineer when task involves SWR, fetch, data loading, event listeners, or localStorage -->

## SWR for Automatic Request Deduplication
**Impact:** MEDIUM-HIGH — multiple component instances share one in-flight request

SWR enables deduplication, caching, and revalidation across component instances sharing the same key — multiple mounts of the same component result in one network request, not N.

**Instead of:**
```tsx
// Each instance fetches independently
function UserList() {
  const [users, setUsers] = useState([])
  useEffect(() => {
    fetch('/api/users').then(r => r.json()).then(setUsers)
  }, [])
}
```

**Use:**
```tsx
import useSWR from 'swr'

function UserList() {
  const { data: users } = useSWR('/api/users', fetcher)
  // All mounted UserList instances share one request
}

// For data that never changes server-side:
import { useImmutableSWR } from '@/lib/swr'
function StaticContent() {
  const { data } = useImmutableSWR('/api/config', fetcher)
}

// For mutations:
import { useSWRMutation } from 'swr/mutation'
function UpdateButton() {
  const { trigger } = useSWRMutation('/api/user', updateUser)
  return <button onClick={() => trigger()}>Update</button>
}
```

---

## Deduplicate Global Event Listeners
**Impact:** LOW — single listener regardless of how many components subscribe

When multiple component instances need the same global event, registering N listeners is wasteful. Use a module-level dispatch map so one listener serves all subscribers.

**Instead of:**
```tsx
// N instances = N window listeners
function useKeyboardShortcut(key: string, callback: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey && e.key === key) callback()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [key, callback])
}
```

**Use:**
```tsx
import useSWRSubscription from 'swr/subscription'

const keyCallbacks = new Map<string, Set<() => void>>()

function useKeyboardShortcut(key: string, callback: () => void) {
  useEffect(() => {
    if (!keyCallbacks.has(key)) keyCallbacks.set(key, new Set())
    keyCallbacks.get(key)!.add(callback)
    return () => {
      const set = keyCallbacks.get(key)
      if (set) {
        set.delete(callback)
        if (set.size === 0) keyCallbacks.delete(key)
      }
    }
  }, [key, callback])

  // One shared listener for all key combinations
  useSWRSubscription('global-keydown', () => {
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey && keyCallbacks.has(e.key)) {
        keyCallbacks.get(e.key)!.forEach(cb => cb())
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  })
}
```

---

## Passive Event Listeners for Scroll Performance
**Impact:** MEDIUM — eliminates scroll delay caused by synchronous listener checks

Browsers wait for touch and wheel listeners to complete before scrolling, in case they call `preventDefault()`. Marking listeners passive signals that scrolling can proceed immediately.

**Instead of:**
```typescript
useEffect(() => {
  const handleTouch = (e: TouchEvent) => console.log(e.touches[0].clientX)
  const handleWheel = (e: WheelEvent) => console.log(e.deltaY)
  document.addEventListener('touchstart', handleTouch)
  document.addEventListener('wheel', handleWheel)
  return () => {
    document.removeEventListener('touchstart', handleTouch)
    document.removeEventListener('wheel', handleWheel)
  }
}, [])
```

**Use:**
```typescript
useEffect(() => {
  const handleTouch = (e: TouchEvent) => console.log(e.touches[0].clientX)
  const handleWheel = (e: WheelEvent) => console.log(e.deltaY)
  document.addEventListener('touchstart', handleTouch, { passive: true })
  document.addEventListener('wheel', handleWheel, { passive: true })
  return () => {
    document.removeEventListener('touchstart', handleTouch)
    document.removeEventListener('wheel', handleWheel)
  }
}, [])
```

Use `passive: true` when: tracking, analytics, logging, any listener that never calls `preventDefault()`.

Do not use `passive: true` when: implementing custom swipe gestures, custom zoom controls, or any listener that needs to cancel the default browser behavior.

---

## Version and Minimize localStorage Data
**Impact:** MEDIUM — prevents schema conflicts across deployments, reduces storage size

Versioned keys let you migrate stale data on read. Storing only the fields the UI needs prevents accidentally persisting sensitive data or large server payloads.

**Instead of:**
```typescript
// No version, stores everything, no error handling
localStorage.setItem('userConfig', JSON.stringify(fullUserObject))
const data = localStorage.getItem('userConfig')
```

**Use:**
```typescript
const VERSION = 'v2'

function saveConfig(config: { theme: string; language: string }): void {
  try {
    localStorage.setItem(`userConfig:${VERSION}`, JSON.stringify(config))
  } catch {
    // Throws in incognito/private browsing, quota exceeded, or when storage is disabled
  }
}

function loadConfig(): { theme: string; language: string } | null {
  try {
    const data = localStorage.getItem(`userConfig:${VERSION}`)
    return data ? JSON.parse(data) : null
  } catch {
    return null
  }
}

// Migration from v1 to v2 — run on app init
function migrate(): void {
  try {
    const v1 = localStorage.getItem('userConfig:v1')
    if (v1) {
      const old = JSON.parse(v1)
      saveConfig({ theme: old.darkMode ? 'dark' : 'light', language: old.lang })
      localStorage.removeItem('userConfig:v1')
    }
  } catch {}
}

// Store minimal fields from server responses
function cachePrefs(user: FullUser): void {
  try {
    localStorage.setItem('prefs:v1', JSON.stringify({
      theme: user.preferences.theme,
      notifications: user.preferences.notifications,
    }))
  } catch {}
}
```

Always wrap in `try-catch` — `getItem()` and `setItem()` throw in incognito/private browsing (Safari, Firefox), when quota is exceeded, or when storage is disabled by policy.
