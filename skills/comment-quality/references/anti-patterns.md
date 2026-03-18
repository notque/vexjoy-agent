# Comment Quality Anti-Patterns

This document catalogs common problematic patterns found in code comments and documentation, with explanations of why they're problematic and how to fix them.

## High Priority Anti-Patterns

### Anti-Pattern 1: "X now does Y"
**Problem**: The word "now" implies a temporal change - something used to work differently
**Why it's bad**: Future readers don't care what it used to do, only what it does currently
**Examples**:
```go
// Bad: validateInput now checks for SQL injection
// Good: validateInput checks for SQL injection patterns

// Bad: The API now returns JSON instead of XML
// Good: The API returns JSON responses

// Bad: Errors now include stack traces
// Good: Errors include stack traces for debugging
```

### Anti-Pattern 2: "Improved/Better/Enhanced X"
**Problem**: Comparative adjectives imply comparison to a past state
**Why it's bad**: "Better" is meaningless without knowing what came before; focus on current behavior
**Examples**:
```go
// Bad: Uses improved caching mechanism
// Good: Uses LRU cache with 1000-entry limit

// Bad: Provides better error messages
// Good: Provides error messages with error codes and context

// Bad: Enhanced performance through parallel processing
// Good: Processes requests in parallel (up to 10 concurrent)
```

### Anti-Pattern 3: "Fixed bug where..."
**Problem**: References a bug that existed in the past
**Why it's bad**: Code should explain current behavior, not past problems
**Examples**:
```go
// Bad: Fixed bug where nil caused panic
// Good: Guards against nil to prevent panic

// Bad: Fixed race condition in counter
// Good: Mutex protects counter from concurrent modification

// Bad: Fixed memory leak by closing connections
// Good: Closes connections to prevent resource exhaustion
```

### Anti-Pattern 4: "Added/Removed/Changed X"
**Problem**: Development activity language describes history, not current state
**Why it's bad**: Focuses on what changed rather than what exists
**Examples**:
```go
// Bad: Added validation for email format
// Good: Validates email format using RFC 5322 regex

// Bad: Removed deprecated authentication method
// Good: Authenticates using JWT tokens

// Bad: Changed database from MySQL to PostgreSQL
// Good: Uses PostgreSQL with connection pooling
```

### Anti-Pattern 5: "New/Old system/approach/method"
**Problem**: Temporal designation of current vs previous implementation
**Why it's bad**: Everything is "new" until it's "old" - these labels are time-dependent
**Examples**:
```go
// Bad: The new authentication system uses OAuth
// Good: Authenticates using OAuth 2.0 with PKCE

// Bad: Replaced old caching with new Redis-based cache
// Good: Caches frequently accessed data in Redis

// Bad: New error handling approach
// Good: Error handling with structured logging and context
```

## Medium Priority Anti-Patterns

### Anti-Pattern 6: "Updated/Refactored/Optimized X"
**Problem**: Past tense development activity
**Why it's bad**: Tells you something changed, not what it does now
**Examples**:
```go
// Bad: Updated to use goroutines
// Good: Processes tasks concurrently using goroutines

// Bad: Refactored for better maintainability
// Good: Separates concerns: validation, processing, storage

// Bad: Optimized database queries
// Good: Uses indexed columns for O(log n) lookups
```

### Anti-Pattern 7: "This allows us to..." / "We can now..."
**Problem**: Focuses on capability gained rather than current functionality
**Why it's bad**: "Allows us to" implies past limitation; describe what it does
**Examples**:
```go
// Bad: This allows us to handle larger datasets
// Good: Handles datasets up to 1GB using streaming

// Bad: We can now process requests in parallel
// Good: Processes up to 10 requests concurrently

// Bad: This allows for better error reporting
// Good: Reports errors with file/line context
```

### Anti-Pattern 8: "Instead of X" / "Rather than X"
**Problem**: Comparison to previous approach
**Why it's bad**: Describes what it replaced, not what it does
**Examples**:
```go
// Bad: Uses map instead of array for lookups
// Good: Uses map for O(1) lookups by ID

// Bad: Returns error rather than panicking
// Good: Returns error to allow caller to handle failures

// Bad: Logs to file instead of stdout
// Good: Logs to rotated files in /var/log/app/
```

### Anti-Pattern 9: "Temporary/Interim/Stopgap X"
**Problem**: Indicates non-permanent solution without context
**Why it's bad**: If it's truly temporary, fix it properly or explain the constraint
**Examples**:
```go
// Bad: Temporary workaround for database limitation
// Good: Performs aggregation in-memory because database lacks GROUP BY support

// Bad: Interim solution until API v2
// Good: Uses v1 API endpoint /users (v2 migration pending - requires server upgrade)

// Bad: Stopgap until proper caching is implemented
// Good: In-memory cache (no persistence) for session data
```

### Anti-Pattern 10: "As of version X" / "Since version X"
**Problem**: Ties comment to specific version timeline
**Why it's bad**: Future readers don't care when it was introduced, only what it does
**Examples**:
```go
// Bad: As of v2.0, supports WebSocket connections
// Good: Supports WebSocket connections for real-time updates

// Bad: Since version 1.5, validates input data
// Good: Validates input data against schema

// Bad: Available from v3.0 onwards
// Good: Available in current version (requires feature flag ENABLE_X)
```

## Subtle Anti-Patterns

### Anti-Pattern 11: "More/Less efficient/effective"
**Problem**: Relative comparison without baseline
**Why it's bad**: "More efficient" compared to what? Be specific.
**Examples**:
```go
// Bad: More efficient algorithm for sorting
// Good: QuickSort provides O(n log n) average case

// Bad: Less memory intensive approach
// Good: Streams data in 1KB chunks to limit memory to 10MB

// Bad: More effective error handling
// Good: Error handling with retry logic (3 attempts, exponential backoff)
```

### Anti-Pattern 12: "Unlike X" / "Compared to X"
**Problem**: Defines behavior by what it's not
**Why it's bad**: Focuses on difference rather than actual behavior
**Examples**:
```go
// Bad: Unlike the previous version, this doesn't cache
// Good: Fetches fresh data on every request (no caching)

// Bad: Compared to the old system, this is faster
// Good: Responds within 100ms (p95 latency)

// Bad: Unlike other methods, this is thread-safe
// Good: Thread-safe: uses mutex for concurrent access
```

### Anti-Pattern 13: "Will/Going to/Eventually X"
**Problem**: Future tense for current code
**Why it's bad**: Code should describe current state, not future plans
**Examples**:
```go
// Bad: Will support pagination in future
// Good: TODO: Add pagination support for result sets > 1000 items

// Bad: Going to be replaced with GraphQL API
// Good: REST API (GraphQL migration planned - see ROADMAP.md)

// Bad: Eventually will use Redis for caching
// Good: In-memory cache (Redis integration tracked in issue #123)
```

### Anti-Pattern 14: "Used to X but now Y"
**Problem**: Explicit before/after comparison
**Why it's bad**: Historical context doesn't help understand current code
**Examples**:
```go
// Bad: Used to return nil but now returns empty slice
// Good: Returns empty slice (never nil) when no results found

// Bad: Used to block but now times out after 5 seconds
// Good: Times out after 5 seconds to prevent indefinite blocking

// Bad: Used to be synchronous but now async
// Good: Processes asynchronously and returns immediately
```

### Anti-Pattern 15: "Originally X"
**Problem**: References original implementation
**Why it's bad**: Original design is irrelevant to current functionality
**Examples**:
```go
// Bad: Originally designed for single-threaded use
// Good: Not thread-safe - use separate instance per goroutine

// Bad: Originally returned XML, now JSON
// Good: Returns JSON response with content-type application/json

// Bad: Originally limited to 100 items
// Good: Returns up to 1000 items (configurable via MAX_ITEMS env var)
```

## Context-Dependent Patterns

### Pattern 1: Deprecation Notices (ALLOWED)
**When allowed**: Official deprecation warnings
**Format**: `@deprecated` annotation with replacement
```go
// ALLOWED: @deprecated Use ProcessV2() instead. Removed in v3.0.
// Why: Deprecation notices serve a specific warning purpose
```

### Pattern 2: Migration Guidance (ALLOWED in specific contexts)
**When allowed**: CHANGELOG.md, MIGRATION.md, release notes
**When NOT allowed**: Code comments
```markdown
# ALLOWED in CHANGELOG.md:
## v2.0.0
- Changed: API now returns JSON instead of XML
- Migration: Update clients to parse JSON responses

# NOT ALLOWED in code:
// Changed to return JSON instead of XML (v2.0.0)
```

### Pattern 3: Historical Context (ALLOWED in specific files)
**When allowed**: HISTORY.md, ARCHITECTURE.md (decision context)
**When NOT allowed**: Code comments, inline documentation
```markdown
# ALLOWED in ARCHITECTURE.md:
## Authentication Decision
We chose JWT over sessions because our architecture is stateless
and requires horizontal scaling across multiple servers.

# NOT ALLOWED in code:
// Changed from sessions to JWT for better scalability
```

### Pattern 4: TODO Comments (CONDITIONAL)
**Allowed format**: Describe future work without temporal language
**Not allowed**: Reference past changes or current state as "temporary"
```go
// GOOD TODO:
// TODO: Add rate limiting (track in-flight requests, reject when > 100)

// BAD TODO:
// TODO: Remove this temporary fix when we upgrade database
// Better: TODO: Remove when database supports JSON queries (requires v5.0+)
```

## Language-Specific Patterns

### Go-Specific Anti-Patterns

#### Anti-Pattern: "Fixed panic"
```go
// Bad: Fixed panic when receiver is nil
// Good: Returns error when receiver is nil to prevent panic
```

#### Anti-Pattern: "Now uses context"
```go
// Bad: Updated to use context for cancellation
// Good: Accepts context for cancellation and timeout control
```

#### Anti-Pattern: "Improved error handling"
```go
// Bad: Improved error handling with wrapping
// Good: Wraps errors with operation context using fmt.Errorf
```

### Python-Specific Anti-Patterns

#### Anti-Pattern: "Changed to use type hints"
```python
# Bad: Added type hints for better IDE support
# Good: Type hints specify expected types for validation
```

#### Anti-Pattern: "Refactored to use dataclass"
```python
# Bad: Refactored to use dataclass instead of dict
# Good: Uses dataclass for automatic __init__ and __repr__
```

### JavaScript/TypeScript Anti-Patterns

#### Anti-Pattern: "Migrated to async/await"
```javascript
// Bad: Migrated from promises to async/await
// Good: Uses async/await for sequential asynchronous operations
```

#### Anti-Pattern: "Updated to ES6 syntax"
```javascript
// Bad: Updated to use arrow functions
// Good: Arrow function preserves outer 'this' context
```

## Documentation-Specific Anti-Patterns

### README Files

#### Anti-Pattern: Version-specific feature lists
```markdown
# Bad:
## New in v2.0
- Added authentication
- Improved performance

# Good:
## Features
- JWT-based authentication
- Response time < 100ms (p95)
```

#### Anti-Pattern: Historical installation instructions
```markdown
# Bad:
Installation has been simplified. Previously you needed to...
Now you just run: npm install

# Good:
## Installation
```bash
npm install mypackage
```
```

### API Documentation

#### Anti-Pattern: Endpoint evolution
```markdown
# Bad:
This endpoint was updated to return pagination metadata

# Good:
## Response Format
Returns paginated results with:
- `items`: Array of results
- `total`: Total count
- `next_page`: Token for next page
```

#### Anti-Pattern: Parameter history
```markdown
# Bad:
The `filter` parameter was added in v1.5 to allow...

# Good:
### Parameters
- `filter` (optional): JSON query using RFC 6902 syntax
```

## Detection Strategies

### High-Confidence Detection
These patterns almost always indicate temporal language:
- "now" (when not part of time.Now() or datetime.now())
- "new" + system/method/approach/implementation
- "old" + any noun
- "fixed"
- "added" + feature/check/validation
- "improved" + noun
- "enhanced" + noun
- "updated" + noun

### Context-Dependent Detection
These patterns MAY be temporal (require context analysis):
- "allows" - could be temporal ("allows us to") or functional ("allows customization")
- "using" - could be temporal ("now using") or current ("using Redis")
- "better" - almost always comparative (temporal)
- "more/less" - usually comparative unless followed by absolute ("more than 100")

### False Positives to Ignore
These patterns are NOT temporal:
- "new" in variable names (newValue, newConfig)
- "old" in variable names (oldValue, oldConfig)
- "now" in time functions (time.Now(), datetime.now())
- "current" in variable names (currentUser, currentState)
- "update" as present tense ("updates the counter")

## Automated Detection Regular Expressions

### High Priority Patterns (Regex)
```regex
\b(now|new|old|fixed|added|removed|updated|changed|improved|enhanced)\s+
\b(better|worse|faster|slower)\s+(than|error|performance)
\b(instead\s+of|rather\s+than|unlike|compared\s+to)
\b(as\s+of|since\s+version|from\s+version|in\s+v\d+)
\b(temporary|interim|stopgap|workaround)
\b(originally|previously|formerly|used\s+to)
```

### Medium Priority Patterns (Regex)
```regex
\b(refactored|optimized|migrated|upgraded|deprecated)
\b(more|less)\s+(efficient|effective|accurate)
\b(allows\s+us\s+to|we\s+can\s+now)
\b(will|going\s+to|eventually|soon|later)
```

### Context Required (Manual Review)
```regex
\bcurrent\b  # May be variable name or temporal reference
\busing\b    # May be "now using" (bad) or "using X" (good)
\ballow\b    # May be "allows us" (bad) or "allows" (good)
```

## Quick Reference Checklist

Use this checklist to validate comments:

- [ ] No words: new, old, now, recently, latest, modern
- [ ] No words: added, removed, updated, changed, fixed, improved, enhanced
- [ ] No words: better, worse, faster, slower (without measurements)
- [ ] No phrases: instead of, rather than, unlike, compared to
- [ ] No references: as of, since version, from version
- [ ] No development activity: implementing, addition of, fix for
- [ ] Focuses on WHAT the code does
- [ ] Explains WHY when not obvious
- [ ] Would make sense in 10 years
- [ ] Doesn't require knowing code history
- [ ] Self-contained and complete

If ALL checkboxes pass: Comment is timeless ✓
If ANY checkbox fails: Comment needs rewrite ✗
