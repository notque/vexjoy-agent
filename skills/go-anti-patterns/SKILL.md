---
name: go-anti-patterns
description: |
  Detect and remediate Go anti-patterns: premature interface abstraction,
  goroutine overkill, context soup, error wrapping mistakes, generic abuse,
  channel misuse, unnecessary function extraction, and interface pollution.
  Use when reviewing Go code for quality, detecting over-engineering, or when
  user mentions "anti-pattern", "code smell", "Go mistake", or "bad Go".
  Do NOT use for feature implementation, performance optimization without a
  code smell, or non-Go languages.
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
  force_routing: true
---

# Go Anti-Patterns Skill

## Operator Context

This skill operates as an operator for Go anti-pattern detection and remediation, configuring Claude's behavior to identify over-engineering, premature abstraction, and idiomatic violations in Go code. It implements the **Pattern Recognition** architectural approach -- scan, detect, explain, remediate -- with **Domain Intelligence** embedded in Go-specific heuristics.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before reviewing
- **Over-Engineering Prevention**: Flag complexity only when simpler Go exists; never add complexity while removing it
- **Evidence-Based Detection**: Every flagged anti-pattern must cite specific code location and explain concrete harm
- **YAGNI Enforcement**: Do not suggest abstractions (interfaces, generics, channels) without 2+ concrete use cases
- **Preserve Working Code**: Flag patterns for awareness; do not rewrite working code without explicit request
- **Idiomatic Go Priority**: Recommendations must align with Go proverbs and standard library conventions

### Default Behaviors (ON unless disabled)
- **Quick Detection Table**: Use the detection guide to scan code systematically
- **One Pattern at a Time**: Address anti-patterns individually, not in bulk rewrites
- **Context-Aware Severity**: Rate impact as low/medium/high based on codebase context
- **Show Both Versions**: Present current code alongside recommended alternative
- **Root Cause Explanation**: Explain WHY the pattern is harmful, not just that it is
- **Scope Limitation**: Only flag patterns within the files under review

### Optional Behaviors (OFF unless enabled)
- **Full Codebase Scan**: Scan entire repository for anti-pattern instances
- **Metrics Collection**: Count anti-pattern occurrences by type
- **Auto-Refactor**: Apply fixes directly instead of only flagging them
- **Historical Analysis**: Check git history for when anti-patterns were introduced

## What This Skill CAN Do
- Detect the 7 core Go anti-patterns with code-level evidence
- Provide idiomatic Go alternatives with before/after examples
- Explain the concrete harm each pattern causes (complexity, bugs, maintenance)
- Distinguish between genuine anti-patterns and acceptable trade-offs
- Guide incremental cleanup without destabilizing working code

## What This Skill CANNOT Do
- Rewrite entire codebases (use systematic-refactoring instead)
- Detect non-Go anti-patterns (use language-specific skills)
- Optimize performance (use performance profiling tools)
- Replace code review (use go-code-review for comprehensive review)
- Judge patterns without seeing the surrounding context

---

## Instructions

### Step 1: Scan for Anti-Patterns

Use the Quick Detection Guide to systematically check code under review.

| Code Smell | Detection Question | If Yes |
|------------|-------------------|--------|
| Interface with one impl | Do you have 2+ implementations? | Remove interface |
| Goroutine + WaitGroup | Is work I/O bound or CPU heavy? | Use sequential loop |
| `fmt.Errorf("error: %w")` | Does wrap add context? | Add operation + ID |
| Channel for return value | Is there actual concurrency? | Use regular return |
| Generic with one type | Used with multiple types? | Use concrete type |
| Context in pure function | Does function do I/O? | Remove context param |
| Tiny extracted function | Called from 2+ places? | Inline it |

### Step 2: Classify and Report

For each detected anti-pattern, produce a structured report:

```
ANTI-PATTERN DETECTED:
- Pattern: [Name from catalog below]
- Location: [File:line]
- Issue: [What is wrong with current approach]
- Impact: [Complexity/performance/maintainability cost]
- Severity: [Low/Medium/High]
- Recommendation: [Simpler Go alternative]
```

### Step 3: Provide Remediation

Show before/after code. Reference the detailed examples in `references/code-examples.md` for full patterns.

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

## Go-Specific Phantom Problem Indicators

Watch for solutions looking for problems:

- Adding interfaces when concrete types suffice
- Implementing channels when simple function calls work
- Creating goroutines for inherently sequential operations
- Over-abstracting with generics for single-use cases
- Adding middleware layers for simple HTTP handlers
- Creating worker pools for low-throughput scenarios

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

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It Is Wrong | Required Action |
|-----------------|-----------------|-----------------|
| "This interface might be needed later" | YAGNI; future is unknown | Start concrete, extract when needed |
| "Goroutines make it faster" | Concurrency has overhead; profile first | Prove bottleneck exists before adding goroutines |
| "Context should be everywhere" | Context is for I/O and cancellation only | Remove from pure functions |
| "Generics make it more flexible" | Flexibility without use cases is complexity | Use concrete types until 2+ instantiations |
| "Small functions are always better" | Indirection has cognitive cost | Inline single-use trivial functions |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/code-examples.md`: Extended before/after examples for all 7 anti-patterns
