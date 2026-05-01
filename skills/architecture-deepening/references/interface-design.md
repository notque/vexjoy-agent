# Interface Design Patterns

> **Scope**: Patterns for exploring alternative interfaces when deepening a module. Loaded during Phase 2 (PRESENT CANDIDATES) when designing interface alternatives.

---

## Generating Alternatives

For each shallow module, generate 2-3 interface alternatives. Each alternative
makes a different trade-off between simplicity and flexibility. The goal is not
to find the "right" answer immediately but to explore the design space so the
user can make an informed choice.

### Alternative Generation Checklist

For each candidate module, ask:

1. **What are callers actually trying to do?** Not "what function do they
   call" but "what outcome do they need." The answer reveals whether the
   current interface matches caller intent or forces callers to think in the
   module's terms.

2. **What do all callers have in common?** If 8 of 10 callers pass the same
   configuration, that configuration should be a default, not a parameter.

3. **What varies between callers?** The things that genuinely differ across
   callers are the parameters the interface needs. Everything else is
   implementation detail that belongs behind the interface.

4. **What would the caller code look like?** Write the caller code first,
   then derive the interface from it. This prevents designing interfaces that
   are elegant in isolation but awkward to use.

---

## Common Deepening Patterns

### Absorb Configuration

**Before** (shallow): Callers must construct and pass configuration objects
that mirror internal structure.

```
// Caller must know about internal retry, timeout, and pool settings
client := NewClient(Config{
    RetryCount: 3,
    RetryBackoff: time.Second,
    Timeout: 30 * time.Second,
    PoolSize: 10,
    PoolIdleTimeout: 5 * time.Minute,
})
```

**After** (deep): Module provides sensible defaults. Callers override only
what they need.

```
// Module absorbs configuration decisions
client := NewClient(endpoint)

// Callers with unusual needs use options
client := NewClient(endpoint, WithTimeout(60*time.Second))
```

**When to apply**: When most callers pass the same or similar configuration.
The functional options pattern (WithX) provides an escape hatch for callers
with unusual requirements without burdening the common path.

**Deletion test**: Count configuration construction code in callers. If most
callers build the same config object, all of that code is deletable.

---

### Absorb Sequencing

**Before** (shallow): Callers must call functions in a specific order and
manage state transitions.

```
db := OpenDatabase(path)
db.Migrate()
db.WaitForReady()
defer db.Close()
// now safe to use db
```

**After** (deep): Module manages its own lifecycle. Callers get a ready-to-use
instance.

```
db := OpenDatabase(path)  // migrates, waits, ready to use
defer db.Close()
```

**When to apply**: When callers must follow a multi-step initialization
sequence and getting the order wrong causes subtle bugs. The sequencing
knowledge belongs in the module, not distributed across callers.

**Deletion test**: Count lifecycle management lines in callers. Setup,
initialization, and state-checking code is deletable.

---

### Absorb Error Translation

**Before** (shallow): Callers must handle implementation-specific errors and
translate them into meaningful actions.

```
result, err := service.Process(input)
if errors.Is(err, sql.ErrNoRows) {
    // caller must know this is backed by SQL
    return nil, ErrNotFound
} else if errors.Is(err, redis.ErrCacheMiss) {
    // caller must know this uses Redis
    return service.ProcessWithoutCache(input)
}
```

**After** (deep): Module translates errors into caller-meaningful categories.

```
result, err := service.Process(input)
if errors.Is(err, service.ErrNotFound) {
    return nil, ErrNotFound
}
// cache misses handled internally with fallback
```

**When to apply**: When callers import error types from the module's
dependencies rather than from the module itself. Dependency-specific errors in
caller code are a direct measure of interface leakage.

**Deletion test**: Count error handling blocks that reference the module's
internal dependencies. Each such block is deletable after error translation.

---

### Absorb Coordination

**Before** (shallow): Callers must coordinate between multiple modules to
accomplish a single logical operation.

```
token := auth.GetToken()
if auth.IsExpired(token) {
    token = auth.Refresh(token)
}
resp := api.Call(endpoint, token)
```

**After** (deep): One module owns the coordinated operation.

```
resp := api.Call(endpoint)  // auth handled internally
```

**When to apply**: When the same multi-module coordination pattern appears in
3+ callers. The coordination logic is duplicated knowledge that belongs behind
a single interface.

**Deletion test**: Count coordination code that appears in multiple callers.
The total across all callers is the deletable line count.

---

### Extract Common Default

**Before** (shallow): Every caller makes the same decision because the module
does not have an opinion.

```
// All 8 callers do this:
logger := NewLogger(os.Stdout, LevelInfo, JSONFormat)
```

**After** (deep): Module provides an opinionated default. Unusual callers
can override.

```
logger := NewLogger()  // stdout, info, JSON by default
// Override when needed:
logger := NewLogger(WithLevel(LevelDebug))
```

**When to apply**: When sampling callers reveals that most pass identical
arguments. The "right" default is whatever most callers already choose.

**Deletion test**: Count argument-construction code in callers that matches
the new default. All of it is deletable.

---

## Documenting Alternatives

For each alternative, fill this template:

```markdown
### Alternative {N}: {short name}

**New interface**:
{function signatures, types, key behaviors}

**What moves behind the interface**:
{implementation details callers no longer manage}

**Deletion test**:
- Caller A: {N} lines deletable ({which lines})
- Caller B: {N} lines deletable ({which lines})
- Total: {N} lines across {M} callers

**Trade-offs**:
- Gains: {what callers no longer need to know}
- Loses: {what flexibility callers give up}
- Escape hatch: {how unusual callers retain needed flexibility}
```

---

## Red Flags in Interface Design

Watch for these signals that a proposed interface is not actually deeper:

1. **Renamed but not absorbed**: The new interface has the same number of
   parameters with different names. This is a rename, not a deepening.

2. **Hidden complexity, not absorbed complexity**: The module now does the
   same thing callers did, but callers must still understand what happens
   internally to handle edge cases. The complexity moved but did not shrink.

3. **Lost escape hatch**: The new interface cannot handle the one caller with
   unusual requirements. That caller now works around the interface, creating
   a worse situation than before.

4. **Increased coupling**: The deepened module now depends on things it did
   not before, creating a tighter coupling web. Good deepening reduces total
   coupling by consolidating coordination.

5. **Zero deletion test**: If no caller code can be deleted after the
   change, the interface may not be meaningfully deeper. Question whether
   the change is worth the migration cost.
