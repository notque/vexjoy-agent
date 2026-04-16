# Performance Comment Anti-Patterns

> **Scope**: Temporal and relative-comparison comment anti-patterns in performance-sensitive
> code: caching, batching, concurrency limits, and algorithmic complexity notes.
> **Version range**: All languages; Go goroutine pool patterns, Python asyncio, JS Promise.all
> **Generated**: 2026-04-16

---

## Overview

Performance code attracts the worst temporal comments. "Optimized for speed", "now uses
caching", "faster than the old approach" — all describe a past comparison that no longer
exists. The pattern appears across caching layers, batch processors, query optimizers, and
concurrency machinery. The skill must recognize vague performance praise and replace it with
measurable, specific descriptions of what the optimization does.

---

## Anti-Pattern Catalog

### ❌ "Optimized/improved for performance" — Vague praise

**Detection**:
```bash
grep -rn '//.*optimized.*\(for\|performance\|speed\|efficiency\)\|//.*improved.*performance' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(optimized|improved|enhanced|tuned) (for )?(performance|speed|efficiency|throughput)' -i
```

**What it looks like**:
```go
// Optimized for performance using goroutine pool
func processQueue(items []Item) {
    sem := make(chan struct{}, 10)
    for _, item := range items {
        sem <- struct{}{}
        go func(it Item) {
            defer func() { <-sem }()
            process(it)
        }(item)
    }
}

// Improved performance by caching database results
cache := sync.Map{}
```

**Why wrong**: "Optimized for performance" says nothing the reader can act on. What was the
bottleneck? What does the optimization constrain? What happens if the limit changes?

**Fix**:
```go
// Limits concurrent processing to 10 goroutines to cap memory and CPU usage.
// Increase cap if CPU is underutilized; decrease if memory pressure is high.
func processQueue(items []Item) {
    sem := make(chan struct{}, 10)
    for _, item := range items {
        sem <- struct{}{}
        go func(it Item) {
            defer func() { <-sem }()
            process(it)
        }(item)
    }
}

// In-process cache avoids repeated DB roundtrips for the same key within a request.
cache := sync.Map{}
```

---

### ❌ "Faster than X" / "More efficient than X" — Comparative without baseline

**Detection**:
```bash
grep -rn '//.*faster than\|//.*more efficient than\|//.*quicker than\|//.*slower than' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(faster|more efficient|quicker|better) than' -i
```

**What it looks like**:
```python
# Faster than sequential processing
results = await asyncio.gather(*[process(item) for item in items])

# More efficient than loading all records at once
def get_users_paginated(page_size=100):
    offset = 0
    while True:
        batch = db.query(User).limit(page_size).offset(offset).all()
        if not batch:
            break
        yield batch
        offset += page_size
```

**Why wrong**: "Faster than sequential" is historical context. How much faster? Under what
conditions? The reader needs to know what the parallelism model is and its trade-offs.

**Fix**:
```python
# Runs all process() calls concurrently; total time bounded by the slowest item.
# Do not use if process() has side effects that must not interleave.
results = await asyncio.gather(*[process(item) for item in items])

# Streams users in batches of 100 to avoid loading the full table into memory.
# Caller iterates yielded batches; do not materialize with list() on large tables.
def get_users_paginated(page_size=100):
    offset = 0
    while True:
        batch = db.query(User).limit(page_size).offset(offset).all()
        if not batch:
            break
        yield batch
        offset += page_size
```

---

### ❌ "Now uses cache" / "Added caching" — Cache capability addition

**Detection**:
```bash
grep -rn '//.*now.*cach\|//.*added.*cach\|//.*cach.*now\|//.*cach.*added' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(now uses|added|uses) (a |the )?(cache|caching|LRU|Redis)' -i
```

**What it looks like**:
```go
// Now uses Redis cache to avoid repeated database lookups
func getUser(id int) (*User, error) {
    if v, ok := cache.Get(id); ok {
        return v.(*User), nil
    }
    // ...fetch from DB and set cache
}

// Added LRU cache for improved response times
var lru = lrucache.New(1000)
```

**Why wrong**: "Now uses" describes migration history. The reader needs cache eviction policy,
TTL, capacity, and what happens on cache miss.

**Fix**:
```go
// Returns cached user within 5-minute TTL; fetches from DB on miss and repopulates cache.
func getUser(id int) (*User, error) {
    if v, ok := cache.Get(id); ok {
        return v.(*User), nil
    }
    // ...fetch from DB and set cache
}

// LRU cache capped at 1000 entries; evicts least-recently-used when full.
var lru = lrucache.New(1000)
```

---

### ❌ "Optimized database queries" / "Reduced N+1" — Query optimization narrative

**Detection**:
```bash
grep -rn '//.*optimized.*quer\|//.*quer.*optimized\|//.*N\+1\|//.*reduced.*quer' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(optimized|reduced|fixed) (query|queries|N\+1|database)' -i
```

**What it looks like**:
```python
# Optimized to avoid N+1 query problem
users = User.objects.prefetch_related('orders').filter(active=True)

# Reduced database queries by batching inserts
def bulk_insert(records):
    db.bulk_create(records, batch_size=500)
```

**Why wrong**: "Optimized to avoid" is history. The current behavior — eager loading, batch
size, indexed column — is what matters.

**Fix**:
```python
# Eager-loads orders in a single query to prevent one query per user in downstream loops.
users = User.objects.prefetch_related('orders').filter(active=True)

# Inserts in batches of 500 to stay within DB parameter limits and reduce roundtrips.
def bulk_insert(records):
    db.bulk_create(records, batch_size=500)
```

---

### ❌ "Replaced X with Y for better performance" — Replacement narrative

**Detection**:
```bash
grep -rn '//.*replaced.*\(better\|improve\|faster\|performance\)\|//.*\(better\|improve\|faster\|performance\).*replaced' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*replaced .* (for|with) better (performance|speed|efficiency)' -i
```

**What it looks like**:
```typescript
// Replaced array.find() with Map for better performance on large collections
const userIndex = new Map(users.map(u => [u.id, u]));

// Replaced polling with WebSocket for improved real-time performance
const ws = new WebSocket(endpoint);
```

**Why wrong**: Describes what was replaced instead of what the current structure provides.

**Fix**:
```typescript
// Map provides O(1) lookup by ID; array.find() is O(n) and slow for collections > 1000.
const userIndex = new Map(users.map(u => [u.id, u]));

// WebSocket pushes updates from server; avoids 1-second polling latency for real-time feeds.
const ws = new WebSocket(endpoint);
```

---

### ❌ "Reduced memory usage" / "Less memory" — Vague memory claim

**Detection**:
```bash
grep -rn '//.*reduced.*memory\|//.*less.*memory\|//.*memory.*reduced\|//.*lower.*memory' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
rg '//\s*(reduced|lower|less|minimal) memory' -i
```

**What it looks like**:
```go
// Reduced memory usage by streaming instead of loading all data
func exportCSV(w io.Writer, db *DB) error {
    rows, _ := db.Query("SELECT * FROM users")
    defer rows.Close()
    enc := csv.NewWriter(w)
    for rows.Next() {
        // write row
    }
    return rows.Err()
}
```

**Why wrong**: "Reduced memory usage" compared to what? State the bound, not the reduction.

**Fix**:
```go
// Streams rows directly to w; memory usage is O(1) per row, not O(total rows).
// Callers should buffer w if writing to a slow sink (network, disk).
func exportCSV(w io.Writer, db *DB) error {
    rows, _ := db.Query("SELECT * FROM users")
    defer rows.Close()
    enc := csv.NewWriter(w)
    for rows.Next() {
        // write row
    }
    return rows.Err()
}
```

---

## Error-Fix Mappings

| Pattern Found | Root Cause | Rewrite Strategy |
|---------------|------------|------------------|
| `// Optimized for performance` | Vague praise | State the specific mechanism (pool size, batch size, cache TTL) |
| `// Faster than X` | Relative comparison | State complexity class or measured bound |
| `// Now uses cache` | Capability addition | State eviction policy, TTL, capacity, miss behavior |
| `// Reduced N+1` | Query fix narrative | Describe current loading strategy (eager, batch size) |
| `// Replaced X with Y for speed` | Replacement narrative | State why current structure is better (O(1) vs O(n)) |
| `// Reduced memory usage` | Vague claim | State memory bound (O(1), O(n), capped at Xmb) |

---

## Pattern Table

| Pattern | When to Rewrite | Replacement Focus |
|---------|----------------|-------------------|
| `faster / slower` | Always | State complexity class or measured latency |
| `more efficient` | Always | Specify what resource (CPU, memory, I/O) and how much |
| `cache / caching` | When describing addition | State TTL, capacity, eviction, miss behavior |
| `batch` | When describing improvement | State batch size and why it was chosen |
| `goroutine pool / semaphore` | When describing optimization | State concurrency limit and tuning guidance |
| `streaming` | When comparing to bulk load | State memory bound (O(1) per item vs O(n) total) |

---

## Detection Commands Reference

```bash
# Vague performance praise
grep -rn '//.*\b(optimized|improved|enhanced)\b.*\b(performance|speed|efficiency)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Relative comparisons
grep -rn '//.*\b(faster|slower|quicker|more efficient|less efficient)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Cache addition language
grep -rn '//.*\b(now uses|added|use)\b.*\b(cache|caching|LRU|Redis|Memcached)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Memory vagueness
grep -rn '//.*\b(reduced|less|lower|minimal)\b.*\bmemory\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i
```

---

## See Also

- `anti-patterns.md` — complete temporal anti-pattern catalog across all languages
- `error-handling-patterns.md` — temporal patterns in error handling code
- `go-comment-patterns.md` — Go-specific temporal patterns (goroutines, context, generics)
