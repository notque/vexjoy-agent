# Cobalt Core — Concurrency Patterns

> **Scope**: Goroutine management, synchronization primitives, and scrape-safe concurrency as used in kvm-exporter. Does not cover general Go concurrency theory.
> **Version range**: Go 1.21+ (uses `sync.Mutex.TryLock`, generics-ready patterns)
> **Generated**: 2026-04-16 — verify against `internal/libvirt/` source

---

## Overview

kvm-exporter collects metrics from 50–500+ KVM domains per scrape, each requiring libvirt RPC calls, /proc reads, and cgroup stat lookups. The concurrency model is built around: (1) goroutine-per-domain with a semaphore cap to prevent socket exhaustion, (2) `TryLock` to serialize overlapping Prometheus scrapes, and (3) tiered caching with `sync.Map` for cross-scrape state. Violating these patterns causes libvirt socket exhaustion, metric duplication, or stale data.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `sync.Mutex.TryLock()` | Go 1.18+ | Scrape serialization — skip if already collecting | Long-held business locks |
| Buffered channel semaphore | All | Cap goroutines to protect shared resource (libvirt socket) | Global rate limits (use `golang.org/x/sync/semaphore`) |
| `sync.Map` | Go 1.9+ | Per-domain delta state that survives scrapes | Simple per-request scratch space (use plain map + mutex) |
| `atomic.Value` | All | Single-value timestamp for readiness probe | Multi-field structs (use mutex instead) |
| `context.WithTimeout` | All | Bound collection to 40s scrape deadline | Calling `context.Background()` directly in collection |

---

## Correct Patterns

### Semaphore-Limited Goroutines (the kvm-exporter pattern)

Cap concurrent domain collections to prevent libvirt socket exhaustion. The semaphore is a buffered channel of empty structs.

```go
sem := make(chan struct{}, 50) // max 50 concurrent domain goroutines

var wg sync.WaitGroup
for _, domain := range domains {
    wg.Add(1) // Add BEFORE go func to avoid race with wg.Wait()
    go func(d libvirt.Domain) {
        defer wg.Done()
        sem <- struct{}{}         // acquire slot
        defer func() { <-sem }() // release slot
        collectDomain(ctx, d, ch)
    }(domain)
}
wg.Wait()
```

**Why**: libvirt's Unix socket is a single RPC endpoint. Sending 500 simultaneous calls causes libvirt to drop connections. The semaphore keeps in-flight calls bounded without serializing all collection.

---

### TryLock for Scrape Serialization

Use `TryLock` to skip a scrape when the previous one is still running, rather than blocking Prometheus.

```go
type ServiceImpl struct {
    mu sync.Mutex
}

func (s *ServiceImpl) Collect(ch chan<- prometheus.Metric) {
    if !s.mu.TryLock() {
        // Previous scrape still running — emit nothing, Prometheus retries
        return
    }
    defer s.mu.Unlock()
    s.retrieveMetrics(ctx, ch)
}
```

**Why**: If collection takes 35s and Prometheus scrapes every 30s, blocking stacks goroutines until OOM. `TryLock` sacrifices one scrape rather than accumulating blocked callers.

**Version note**: `sync.Mutex.TryLock()` added in Go 1.18.

---

### sync.Map for Cross-Scrape Delta State

Steal time requires comparing current CPU time to the previous scrape's value. `sync.Map` provides concurrent-safe access without a mutex wrapping the domain loop.

```go
// Key: "domainName-PID"
var stealTimeHistory sync.Map

func calculateStealTime(domain, pid string, current uint64) float64 {
    key := domain + "-" + pid
    if prev, ok := stealTimeHistory.Load(key); ok {
        delta := current - prev.(uint64)
        stealTimeHistory.Store(key, current)
        return float64(delta)
    }
    stealTimeHistory.Store(key, current)
    return 0 // first scrape — no delta available
}
```

**Why**: The domain loop runs concurrently. A plain `map[string]uint64` requires a global mutex serializing all delta lookups. `sync.Map` is optimized for read-heavy workloads with stable key sets (domain IDs don't churn rapidly).

---

### Context Cancellation in Collection Loops

Check `ctx.Err()` before queuing each domain to exit early when the scrape timeout fires.

```go
for _, domain := range domains {
    if ctx.Err() != nil {
        return // timeout fired before we could queue this domain
    }
    wg.Add(1)
    go func(d libvirt.Domain) {
        defer wg.Done()
        sem <- struct{}{}
        defer func() { <-sem }()
        if ctx.Err() != nil {
            return // re-check inside goroutine before doing any work
        }
        collectDomain(ctx, d, ch)
    }(domain)
}
```

**Why**: Without the pre-queue check, all 500 domains could be queued before the timeout fires, then all goroutines start and run over deadline together.

---

## Pattern Catalog

### ❌ Unbounded Goroutine-Per-Domain

**Detection**:
```bash
# Find goroutine launches — review each for semaphore acquire
rg 'go func\(' --type go internal/
grep -rn 'go func(' --include="*.go" internal/
```

**What it looks like**:
```go
for _, domain := range domains {
    go func(d libvirt.Domain) {
        collectDomain(ctx, d, ch) // no semaphore
    }(domain)
}
```

**Why wrong**: On a hypervisor with 500 VMs, this launches 500 goroutines simultaneously. Each goroutine makes libvirt RPC calls over the same Unix socket. libvirt queues drop, connections time out, and the exporter logs hundreds of "connection refused" per scrape.

**Fix**: Add buffered channel semaphore with cap ≤ 50 as shown in Correct Patterns above.

---

### ❌ Blocking Lock in Prometheus Collect Path

**Detection**:
```bash
rg '\.Lock\(\)' --type go internal/libvirt/
grep -n "\.Lock()" internal/libvirt/*.go
```
Review if `Lock()` appears in any `Collect()` or `Describe()` method.

**What it looks like**:
```go
func (s *ServiceImpl) Collect(ch chan<- prometheus.Metric) {
    s.mu.Lock()         // blocks if previous scrape running
    defer s.mu.Unlock()
    s.retrieveMetrics(ctx, ch)
}
```

**Why wrong**: Prometheus's default scrape timeout is 10s. If collection takes 35s and Prometheus fires every 30s, the second `Collect()` call blocks, then the third — goroutines stack until the scrape target appears hung and alerts fire.

**Fix**: Replace `s.mu.Lock()` with `if !s.mu.TryLock() { return }`.

**Version note**: `TryLock` added in Go 1.18. For earlier versions, use `sync/atomic` swap-based implementation.

---

### ❌ Skipping ClearScrapeCache() on Error Exit

**Detection**:
```bash
rg 'ClearScrapeCache' --type go
grep -rn 'ClearScrapeCache' --include="*.go" .
```
Confirm it is called in `defer` or in all exit paths of `retrieveMetrics`.

**What it looks like**:
```go
func (s *ServiceImpl) retrieveMetrics(ctx context.Context, ch chan<- prometheus.Metric) {
    if err := s.connectLibvirt(); err != nil {
        log.Errorf("connect: %v", err)
        return // scrape cache NOT cleared — stale data persists
    }
    // ...
    s.ch.ClearScrapeCache() // only reached on success
}
```

**Why wrong**: Per-scrape caches (PID lookup, VM counters) accumulate stale entries. On the next successful scrape, the exporter reads stale PIDs for domains restarted since last scrape, emitting metrics for dead processes.

**Fix**: `defer s.ch.ClearScrapeCache()` at the top of `retrieveMetrics`, before any error paths.

---

### ❌ Plain map for Concurrent Domain State

**Detection**:
```bash
rg 'map\[string\]' --type go internal/libvirt/
grep -n "map\[string\]" internal/libvirt/*.go
```
Any `map[string]` accessed from goroutines without a wrapping mutex is a data race.

**What it looks like**:
```go
var history = map[string]uint64{} // shared, no mutex

func updateHistory(key string, val uint64) uint64 {
    prev := history[key]  // concurrent read — data race
    history[key] = val    // concurrent write — data race
    return val - prev
}
```

**Why wrong**: Go's race detector (`go test -race`) catches this. In production without `-race`, it causes silent map corruption or `panic: concurrent map read and map write`.

**Fix**: Use `sync.Map` for stable read-heavy key sets (domain IDs), or a `sync.RWMutex`-protected map if you need `range` iteration.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `panic: concurrent map read and map write` | Goroutine-per-domain accessing plain `map` | Replace with `sync.Map` or add `sync.RWMutex` |
| `libvirt: connection refused` (mass, same scrape) | Too many concurrent goroutines saturating libvirt socket | Verify semaphore is applied; reduce cap if needed |
| `context deadline exceeded` every scrape | Collection regularly exceeds 40s timeout | Enable pprof (`ENABLE_PPROF=true`); common culprit is blocked libvirt RPC without per-call timeout |
| Metrics missing for some domains each scrape | `wg.Add(1)` called inside goroutine rather than before launch | Move `wg.Add(1)` to before `go func(...)` |

---

## Detection Commands Reference

```bash
# Find unbounded goroutine launches (check each for semaphore)
rg 'go func\(' --type go internal/

# Find blocking Lock() in Prometheus Collect path
rg '\.Lock\(\)' --type go internal/libvirt/

# Find plain map in concurrent code
rg 'map\[string\]' --type go internal/libvirt/

# Find missing or misplaced ClearScrapeCache calls
rg 'ClearScrapeCache' --type go

# Run race detector across all packages
go test -race ./internal/...
```

---

## See Also

- `references/kvm-exporter.md` — Concurrency Model and Cache Tiers sections for architecture overview
- `references/testing-patterns.md` — How to write race-detector-clean tests with moq
