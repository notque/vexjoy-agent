# Pattern Categorization Guide

## Standard Categories for Coding Rules

When generating coding rules documents from mined data, organize patterns into these standard categories:

### 1. Error Handling
Patterns related to error creation, checking, wrapping, and propagation.

**Common Patterns**:
- Use `errors.Is()` for error comparison (not string comparison)
- Use `errors.As()` for error type checking
- Wrap errors with context using `fmt.Errorf("context: %w", err)`
- Check errors immediately after function calls
- Don't ignore errors (no `_ = func()` without comment)

**Example Pattern**:
```markdown
### Use errors.Is() for error comparison (HIGH confidence)

**Pattern**: Prefer errors.Is() over string comparison

**Good**:
```go
if errors.Is(err, ErrNotFound) {
```

**Bad**:
```go
if err.Error() == "not found" {
```

**Rationale**: From PR #123 review by senior-reviewer:
"Use errors.Is() instead of comparing error strings"
```

### 2. Testing Standards
Patterns for test structure, assertions, test data, and coverage.

**Common Patterns**:
- Use `assert.Equal()` not `assert.True(a == b)`
- Prefer `==` over `DeepEqual` for comparable types
- Use table-driven tests for multiple cases
- Test error paths explicitly
- Use meaningful test names

### 3. API Design
Patterns for function signatures, parameters, return values, and interfaces.

**Common Patterns**:
- Verbose parameter names for IDE autocomplete
- Return errors as last parameter
- Use context.Context as first parameter for cancellation
- Prefer interfaces for dependencies (dependency injection)
- Keep interfaces small (1-3 methods)

### 4. Type System & Reflection
Patterns for type assertions, type switches, reflection usage.

**Common Patterns**:
- Use reflection for type introspection when needed
- Defense in depth for type switch nil handling
- Prefer type assertions with ok check: `val, ok := x.(Type)`
- Avoid reflection in hot paths (performance)

### 5. Performance Optimization
Patterns for efficiency, resource usage, and bottlenecks.

**Common Patterns**:
- Preallocate slices when size is known
- Use `strings.Builder` for string concatenation in loops
- Avoid unnecessary allocations
- Profile before optimizing
- Document performance-critical sections

### 6. Documentation Standards
Patterns for comments, godoc, and code documentation.

**Common Patterns**:
- Godoc comments start with function/type name
- Explain why, not what (code shows what)
- Document exported functions and types
- Add examples for complex APIs
- Keep comments up to date with code

### 7. Code Organization
Patterns for file structure, package organization, imports.

**Common Patterns**:
- Group imports (stdlib, external, internal)
- One concept per file
- Keep files under 500 lines
- Use meaningful package names (not "util" or "common")
- Organize by domain, not layer

### 8. Concurrency
Patterns for goroutines, channels, mutexes, and synchronization.

**Common Patterns**:
- Always handle goroutine cleanup
- Use context for cancellation
- Protect shared state with mutexes
- Prefer channels for communication
- Document synchronization requirements

### 9. Resource Management
Patterns for cleanup, deferred operations, lifecycle management.

**Common Patterns**:
- Use defer for cleanup (close files, unlock mutexes)
- Check close errors where important
- Use context for timeouts
- Clean up resources in reverse order of acquisition

### 10. Code Style & Conventions
Patterns for naming, formatting, and readability.

**Common Patterns**:
- Use gofmt (enforced by CI)
- Follow effective Go guidelines
- Use consistent naming conventions
- Keep functions focused (single responsibility)
- Avoid deep nesting (early returns)

## Confidence Scoring Within Categories

### HIGH Confidence (5+ occurrences)
Place these patterns first in each category section. They represent well-established team standards.

Example heading: `### Use errors.Is() for error comparison (HIGH confidence)`

### MEDIUM Confidence (2-4 occurrences)
Place these after HIGH confidence patterns. They may represent emerging standards or context-specific practices.

Example heading: `### Preallocate slices for known sizes (MEDIUM confidence)`

### LOW Confidence (1 occurrence)
Place these in an "Additional Observations" subsection at the end of each category. They may be one-off suggestions or experimental patterns.

Example heading: `### Consider using sync.Pool for frequent allocations (LOW confidence)`

## Markdown Template Structure

```markdown
# {Repo Name} Coding Rules

Generated from {N} interactions across {M} PRs on {date}
Source: {mined_data_file}

## Error Handling

### {Pattern Name} ({CONFIDENCE} confidence)

**Pattern**: {Brief description}

**Good**:
```go
{good_example_code}
```

**Bad**:
```go
{bad_example_code}
```

**Rationale**: From PR #{pr_number} review by {reviewer}:
"{comment_text}"

---

## Testing Standards

{...similar structure...}

---

## Additional Observations

### Category: Error Handling
- {LOW confidence pattern 1}
- {LOW confidence pattern 2}

### Category: Testing
- {LOW confidence pattern 3}
```

## Cross-Category Patterns

Some patterns span multiple categories. Choose the primary category:

- **"Use context for cancellation"** → Concurrency (primary) + API Design (secondary)
- **"Document exported functions"** → Documentation Standards (primary) + Code Style (secondary)
- **"Defer cleanup operations"** → Resource Management (primary) + Error Handling (secondary)

If a pattern truly belongs in multiple categories, include it in the primary category with a reference note:

```markdown
## Concurrency

### Use context for cancellation (HIGH confidence)

{full pattern documentation}

*Note: This pattern also affects API design - see API Design section for parameter ordering.*
```

## Evolving Categories

As you mine more data, you may discover new category needs:

1. Add new category to this document
2. Update all generated rules to use consistent categories
3. Document rationale for new category
4. Provide examples of patterns that belong in new category

Example new categories discovered:
- **Observability** (logging, metrics, tracing)
- **Security** (input validation, secrets handling)
- **Database** (query patterns, transaction handling)
