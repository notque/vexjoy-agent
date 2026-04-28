# Comment Quality Signals and Fixes

<!-- no-pair-required: document introduction, not an individual anti-pattern block -->

This document catalogs common problematic patterns found in code comments and documentation, with explanations of why they're problematic and how to fix them.

For language-specific (Go, Python, JavaScript/TypeScript) and documentation-targeted (README, API docs) anti-patterns, see `anti-patterns-language-specific.md`.

## High Priority Signals to Detect and Fix

<!-- no-pair-required: section heading organizing multiple anti-pattern blocks -->

### Signal 1: "X now does Y"
**Signal**: The word "now" implies a temporal change - something used to work differently
**Why It Matters**: Future readers need the current behavior, not a history lesson

**Do instead**: Remove the temporal word and describe the current behavior directly.

**Examples**:
```go
// Bad: validateInput now checks for SQL injection
// Good: validateInput checks for SQL injection patterns

// Bad: The API now returns JSON instead of XML
// Good: The API returns JSON responses

// Bad: Errors now include stack traces
// Good: Errors include stack traces for debugging
```

### Signal 2: "Improved/Better/Enhanced X"
**Signal**: Comparative adjectives imply comparison to a past state
**Why It Matters**: "Better" is only useful when the current behavior is stated directly

**Do instead**: Replace vague comparative adjectives with specific, measurable descriptions.

**Examples**:
```go
// Bad: Uses improved caching mechanism
// Good: Uses LRU cache with 1000-entry limit

// Bad: Provides better error messages
// Good: Provides error messages with error codes and context

// Bad: Enhanced performance through parallel processing
// Good: Processes requests in parallel (up to 10 concurrent)
```

### Signal 3: "Fixed bug where..."
**Signal**: References a bug that existed in the past
**Why It Matters**: Comments should explain the present behavior, not the old failure mode

**Do instead**: Describe what the guard or check does and why it exists, not the bug it replaced.

**Examples**:
```go
// Bad: Fixed bug where nil caused panic
// Good: Guards against nil to prevent panic

// Bad: Fixed race condition in counter
// Good: Mutex protects counter from concurrent modification

// Bad: Fixed memory leak by closing connections
// Good: Closes connections to prevent resource exhaustion
```

### Signal 4: "Added/Removed/Changed X"
**Signal**: Development activity language describes history, not current state
**Why It Matters**: Readers need to know what the code does now

**Do instead**: State what exists now, using present tense and the actual mechanism.

**Examples**:
```go
// Bad: Added validation for email format
// Good: Validates email format using RFC 5322 regex

// Bad: Removed deprecated authentication method
// Good: Authenticates using JWT tokens

// Bad: Changed database from MySQL to PostgreSQL
// Good: Uses PostgreSQL with connection pooling
```

### Signal 5: "New/Old system/approach/method"
**Signal**: Temporal designation of current vs previous implementation
**Why It Matters**: Time-dependent labels age out quickly and stop helping readers

**Do instead**: Name the actual mechanism, protocol, or algorithm rather than labeling it by age.

**Examples**:
```go
// Bad: The new authentication system uses OAuth
// Good: Authenticates using OAuth 2.0 with PKCE

// Bad: Replaced old caching with new Redis-based cache
// Good: Caches frequently accessed data in Redis

// Bad: New error handling approach
// Good: Error handling with structured logging and context
```

## Medium Priority Signals to Detect and Fix

<!-- no-pair-required: section heading organizing multiple anti-pattern blocks -->

### Signal 6: "Updated/Refactored/Optimized X"
**Signal**: Past tense development activity
**Why It Matters**: The comment should describe the current behavior, not the work history

**Do instead**: Describe the current structure or behavior, not the transformation that produced it.

**Examples**:
```go
// Bad: Updated to use goroutines
// Good: Processes tasks concurrently using goroutines

// Bad: Refactored for better maintainability
// Good: Separates concerns: validation, processing, storage

// Bad: Optimized database queries
// Good: Uses indexed columns for O(log n) lookups
```

### Signal 7: "This allows us to..." / "We can now..."
**Signal**: Focuses on capability gained rather than current functionality
**Why It Matters**: Describe the behavior directly so future readers do not have to infer it

**Do instead**: State what the code does as a fact, not as a newly acquired capability.

**Examples**:
```go
// Bad: This allows us to handle larger datasets
// Good: Handles datasets up to 1GB using streaming

// Bad: We can now process requests in parallel
// Good: Processes up to 10 requests concurrently

// Bad: This allows for better error reporting
// Good: Reports errors with file/line context
```

### Signal 8: "Instead of X" / "Rather than X"
**Signal**: Comparison to previous approach
**Why It Matters**: Lead with the current behavior and only mention replacement context when it clarifies intent
**Examples**:
```go
// Bad: Uses map instead of array for lookups
// Good: Uses map for O(1) lookups by ID

// Bad: Returns error rather than panicking
// Good: Returns error to allow caller to handle failures

// Bad: Logs to file instead of stdout
// Good: Logs to rotated files in /var/log/app/
```

### Signal 9: "Temporary/Interim/Stopgap X"
**Signal**: Indicates non-permanent solution without context
**Why It Matters**: Time-bound work needs either a concrete constraint or a tracked follow-up

**Do instead**: Explain the actual constraint that prevents a permanent solution, not just that it is temporary.

**Examples**:
```go
// Bad: Temporary workaround for database limitation
// Good: Performs aggregation in-memory because database lacks GROUP BY support

// Bad: Interim solution until API v2
// Good: Uses v1 API endpoint /users (v2 migration pending - requires server upgrade)

// Bad: Stopgap until proper caching is implemented
// Good: In-memory cache (no persistence) for session data
```

### Signal 10: "As of version X" / "Since version X"
**Signal**: Ties comment to a specific version timeline
**Why It Matters**: Version history belongs in changelogs or release notes, not in behavior comments

**Do instead**: Drop the version reference and describe what the code does, or note a runtime requirement if relevant.

**Examples**:
```go
// Bad: As of v2.0, supports WebSocket connections
// Good: Supports WebSocket connections for real-time updates

// Bad: Since version 1.5, validates input data
// Good: Validates input data against schema

// Bad: Available from v3.0 onwards
// Good: Available in current version (requires feature flag ENABLE_X)
```

## Subtle Signals to Detect and Fix

<!-- no-pair-required: section heading organizing multiple anti-pattern blocks -->

### Signal 11: "More/Less efficient/effective"
**Signal**: Relative comparison without a baseline
**Why It Matters**: Specific costs, timings, or resource usage make the comment verifiable

**Do instead**: Replace the relative claim with a concrete bound, complexity class, or measured value.

**Examples**:
```go
// Bad: More efficient algorithm for sorting
// Good: QuickSort provides O(n log n) average case

// Bad: Less memory intensive approach
// Good: Streams data in 1KB chunks to limit memory to 10MB

// Bad: More effective error handling
// Good: Error handling with retry logic (3 attempts, exponential backoff)
```

### Signal 12: "Unlike X" / "Compared to X"
**Signal**: Defines behavior by contrast instead of direct description
**Why It Matters**: Direct behavior is easier to verify and easier to maintain

**Do instead**: Define the behavior directly, using positive statements about what the code does.

**Examples**:
```go
// Bad: Unlike the previous version, this doesn't cache
// Good: Fetches fresh data on every request (no caching)

// Bad: Compared to the old system, this is faster
// Good: Responds within 100ms (p95 latency)

// Bad: Unlike other methods, this is thread-safe
// Good: Thread-safe: uses mutex for concurrent access
```

### Signal 13: "Will/Going to/Eventually X"
**Signal**: Future tense for current code
**Why It Matters**: Current code should describe the behavior that exists today

**Do instead**: Convert to a concrete TODO with a specific dependency, or describe current state if the feature already exists.

**Examples**:
```go
// Bad: Will support pagination in future
// Good: TODO: Add pagination support for result sets > 1000 items

// Bad: Going to be replaced with GraphQL API
// Good: REST API (GraphQL migration planned - see ROADMAP.md)

// Bad: Eventually will use Redis for caching
// Good: In-memory cache (Redis integration tracked in issue #123)
```

### Signal 14: "Used to X but now Y"
**Signal**: Explicit before/after comparison
**Why It Matters**: Current behavior is the useful detail; historical contrast can move to changelogs

**Do instead**: Keep only the "now Y" part, stated as a present fact without the historical contrast.

**Examples**:
```go
// Bad: Used to return nil but now returns empty slice
// Good: Returns empty slice (never nil) when no results found

// Bad: Used to block but now times out after 5 seconds
// Good: Times out after 5 seconds to prevent indefinite blocking

// Bad: Used to be synchronous but now async
// Good: Processes asynchronously and returns immediately
```

### Signal 15: "Originally X"
**Signal**: References the original implementation
**Why It Matters**: Readers need the present contract, not the original design story

**Do instead**: State the current invariant or constraint directly, without referencing the origin.

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
