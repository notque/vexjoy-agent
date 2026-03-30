---
name: go-anti-patterns
description: "Detect and remediate Go anti-patterns."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
agent: golang-general-engineer
command: /go-anti-patterns
routing:
  force_route: true
  triggers:
    - Go mistake
    - bad Go
    - Go smell
    - code smell
    - premature abstraction
    - over-engineering
    - unnecessary complexity
    - "Go anti-pattern"
    - "Go code smell"
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
    - go-code-review
---

# Go Anti-Patterns Skill

Detect and remediate the 7 core Go anti-patterns: premature interface abstraction, goroutine overkill, error wrapping without context, channel misuse, generic abuse, context soup, and unnecessary function extraction. Every detection is evidence-based with code location and concrete harm explanation, and every recommendation aligns with Go proverbs and standard library conventions.

## Instructions

### Phase 1: Prepare

Read and follow the repository's CLAUDE.md before reviewing any code. Identify which files are under review and restrict all analysis to those files -- do not flag patterns in files outside the review scope.

If the user requests a full codebase scan or historical git analysis, enable those modes explicitly. Otherwise, stay within the files presented.

### Phase 2: Scan for Anti-Patterns

Use the Quick Detection Guide to systematically check each file under review. Work through the table row by row against the code.

| Code Smell | Detection Question | If Yes |
|------------|-------------------|--------|
| Interface with one impl | Do you have 2+ implementations? | Remove interface |
| Goroutine + WaitGroup | Is work I/O bound or CPU heavy? | Use sequential loop |
| `fmt.Errorf("error: %w")` | Does wrap add context? | Add operation + ID |
| Channel for return value | Is there actual concurrency? | Use regular return |
| Generic with one type | Used with multiple types? | Use concrete type |
| Context in pure function | Does function do I/O? | Remove context param |
| Tiny extracted function | Called from 2+ places? | Inline it |

Flag complexity only when a simpler idiomatic Go alternative exists. Do not suggest adding complexity (interfaces, generics, channels, goroutines) without 2+ concrete use cases that justify it -- this is the YAGNI principle applied to Go abstractions.

### Phase 3: Classify and Report

For each detected anti-pattern, produce a structured report entry. Every flagged pattern must cite a specific code location and explain the concrete harm it causes -- never flag without evidence.

```
ANTI-PATTERN DETECTED:
- Pattern: [Name from AP catalog, e.g., AP-1: Premature Interface Abstraction]
- Location: [File:line]
- Issue: [What is wrong with current approach]
- Impact: [Complexity/performance/maintainability cost]
- Severity: [Low/Medium/High based on codebase context]
- Recommendation: [Simpler Go alternative]
```

Rate severity based on the actual codebase context: a single-implementation interface in a small CLI is Low; in a hot path of a shared library it may be High. Address anti-patterns one at a time rather than proposing bulk rewrites.

### Phase 4: Provide Remediation

For each flagged pattern, show the current code alongside the recommended alternative so the reader can compare directly. Explain WHY the current pattern is harmful, not just that it is -- root cause understanding prevents recurrence.

Reference `${CLAUDE_SKILL_DIR}/references/code-examples.md` for extended before/after examples covering all 7 anti-patterns.

Do not rewrite working code without an explicit request from the user. Flag patterns for awareness and let the user decide whether to act. When the user does request changes, apply them one pattern at a time to keep diffs reviewable.

If metrics collection is requested, count anti-pattern occurrences by type to identify systemic issues.

---

## Anti-Pattern Catalog

### AP-1: Premature Interface Abstraction

**Detection**: Interface exists with exactly one implementation.

**Why it harms Go code**:
- Interfaces should be discovered, not invented upfront
- Go philosophy: "Accept interfaces, return concrete types"
- Adds cognitive overhead without providing flexibility

**Fix**: Start with concrete types. Add interface ONLY when you need 2+ implementations (e.g., adding a mock for tests or a cache layer).

```go
// BAD: Interface before need
type UserRepository interface {
    GetUser(id string) (*User, error)
}
type PostgresUserRepository struct{ db *sql.DB }
// Only one implementation exists

// GOOD: Concrete type first
type UserRepository struct{ db *sql.DB }
func (r *UserRepository) GetUser(id string) (*User, error) { ... }
// Add interface when second implementation appears
```

### AP-2: Goroutine Overkill for Sequential Work

**Detection**: Goroutines + WaitGroup + channels for operations that are not I/O bound or CPU intensive.

**Why it harms Go code**:
- Concurrency overhead may exceed processing time
- Makes debugging harder (race conditions, unpredictable ordering)
- WaitGroup + channel + error handling adds significant complexity

**Fix**: Use a sequential loop. Add concurrency ONLY after profiling proves it helps for I/O-bound or CPU-intensive work.

```go
// BAD: Goroutines for simple iteration
errCh := make(chan error, len(items))
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)
    go func(item Item) { defer wg.Done(); ... }(item)
}

// GOOD: Sequential is clearer
for _, item := range items {
    if err := process(item); err != nil {
        return fmt.Errorf("process item %s: %w", item.ID, err)
    }
}
```

### AP-3: Error Wrapping Without Context

**Detection**: Error wraps that add "error", "failed", or no meaningful information.

**Why it harms Go code**:
- Error messages should form a narrative from top to bottom
- Missing context makes debugging require source code inspection
- Vague wraps like "error: %w" or "failed: %w" waste the wrap

**Fix**: Include the operation being performed and relevant identifiers.

```go
// BAD: No context
return nil, fmt.Errorf("error: %w", err)
return nil, fmt.Errorf("failed: %w", err)

// GOOD: Narrative context
return nil, fmt.Errorf("load config from %s: %w", path, err)
return nil, fmt.Errorf("parse config JSON from %s: %w", path, err)
```

### AP-4: Channel Misuse for Simple Communication

**Detection**: Channels used where a return value or direct function call suffices.

**Why it harms Go code**:
- Channels are for communication between goroutines
- Without actual concurrency, channels add ceremony without benefit
- Error handling becomes awkward (need separate error channel)

**Fix**: Use standard return values. Reserve channels for worker pools, fan-out/fan-in, and event streams.

```go
// BAD: Channel for simple return
func GetUserName(id string) <-chan string {
    ch := make(chan string, 1)
    go func() { ch <- fetchUser(id).Name }()
    return ch
}

// GOOD: Direct return
func GetUserName(id string) (string, error) {
    user, err := fetchUser(id)
    if err != nil { return "", err }
    return user.Name, nil
}
```

### AP-5: Generic Abuse for Single-Use Cases

**Detection**: Type parameters used with only one concrete type instantiation.

**Why it harms Go code**:
- Generics add complexity (type parameters, constraints)
- Only valuable when you actually need multiple concrete types
- Go prioritizes simplicity over premature generalization

**Fix**: Use concrete types. Add generics when you have 2+ type instantiations for data structures, algorithms, or shared behavior.

```go
// BAD: Generic with one type
type Container[T any] struct{ value T }
// Only ever used as Container[string]

// GOOD: Concrete type
type StringContainer struct{ value string }
```

### AP-6: Context Soup

**Detection**: `context.Context` parameter in functions that perform no I/O, cancellation, or deadline checks.

**Why it harms Go code**:
- Context is for cancellation, deadlines, and request-scoped values
- In pure computation, context adds noise to signatures
- Suggests the function might do I/O when it does not

**Fix**: Reserve context for functions that do I/O, should be cancellable, or carry request-scoped values.

```go
// BAD: Context in pure function
func CalculateTotal(ctx context.Context, prices []float64) float64 { ... }

// GOOD: No context needed
func CalculateTotal(prices []float64) float64 { ... }
```

### AP-7: Unnecessary Function Extraction

**Detection**: Tiny functions (1-5 lines) called from exactly one place, extracted to satisfy complexity metrics.

**Why it harms Go code**:
- Adds indirection without adding clarity
- Reader must jump between functions to understand a simple flow
- Satisfying cyclomatic complexity tools is not a valid reason

**When TO extract**: Reused in 2+ places, complex enough to warrant its own name, needs independent testing, or represents a distinct logical operation.

**When NOT to extract**: To satisfy metrics tools, for trivial operations called once, or when the function name just describes what the code obviously does.

```go
// BAD: Extracted for metrics
func (opts AuditorOpts) parsePort() (int, error) {
    if opts.Port == "" { return 5672, nil }
    return strconv.Atoi(opts.Port)
}
// Called exactly once from buildConnectionURL

// GOOD: Inline when called once
func (opts AuditorOpts) buildConnectionURL() (string, error) {
    port := 5672
    if opts.Port != "" {
        var err error
        port, err = strconv.Atoi(opts.Port)
        if err != nil { return "", fmt.Errorf("parse port %q: %w", opts.Port, err) }
    }
    return fmt.Sprintf("amqp://%s:%d", opts.Host, port), nil
}
```

---

## Error Handling

### Error: "False Positive -- Pattern Is Intentional"
**Cause**: Detected anti-pattern is actually justified by context (e.g., interface for testing boundary, generic for library API).
**Solution**: Check for 2+ implementations or concrete future need. If justified, note as acceptable trade-off and move on.

### Error: "Refactoring Breaks Tests"
**Cause**: Tests depended on the anti-pattern structure (e.g., mocking an interface that gets removed).
**Solution**: Update tests to use the concrete type. If removal would require major test rewrite, flag as tech debt rather than fixing immediately.

### Error: "Team Disagrees on Pattern"
**Cause**: Different Go style preferences or legacy conventions in the codebase.
**Solution**: Defer to existing codebase conventions. Flag in review comments rather than changing unilaterally. Cite Go proverbs or standard library examples as evidence.

---

## Examples

### Example 1: Code Review Detection
User says: "Review this Go service for anti-patterns"
Actions:
1. Scan using Quick Detection Guide table
2. Flag each detected pattern with location and severity
3. Provide before/after for highest-severity items
4. Document findings in structured report format
Result: Prioritized list of anti-patterns with remediation guidance

### Example 2: Specific Pattern Question
User says: "Should I add an interface for this repository?"
Actions:
1. Check how many implementations exist or are planned
2. If only one: recommend concrete type (AP-1)
3. If testing boundary: suggest consumer-side interface
4. Explain Go's "accept interfaces, return structs" philosophy
Result: Evidence-based recommendation with Go idiom context

---

## References

- `${CLAUDE_SKILL_DIR}/references/code-examples.md`: Extended before/after examples for all 7 anti-patterns
