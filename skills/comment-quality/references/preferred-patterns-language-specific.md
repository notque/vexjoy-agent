# Language-Specific and Documentation Comment Patterns

<!-- no-pair-required: document introduction, not an individual anti-pattern block -->

Companion file to `preferred-patterns.md`. Covers language-specific and documentation-targeted comment anti-patterns. Load alongside `preferred-patterns.md` when reviewing code or documentation in Go, Python, JavaScript/TypeScript, or when auditing README/API documentation for temporal references.

## Language-Specific Patterns

### Go-Specific Patterns

<!-- no-pair-required: subsection heading grouping language-specific examples -->

#### Preferred Pattern: "Fixed panic"

**Do instead**: Describe the guard and what it prevents.

```go
// Bad: Fixed panic when receiver is nil
// Good: Returns error when receiver is nil to prevent panic
```

#### Preferred Pattern: "Now uses context"

**Do instead**: State what the context controls and what happens when it expires.

```go
// Bad: Updated to use context for cancellation
// Good: Accepts context for cancellation and timeout control
```

#### Preferred Pattern: "Improved error handling"

**Do instead**: Name the wrapping mechanism and what context it adds.

```go
// Bad: Improved error handling with wrapping
// Good: Wraps errors with operation context using fmt.Errorf
```

### Python-Specific Patterns

<!-- no-pair-required: subsection heading grouping language-specific examples -->

#### Preferred Pattern: "Changed to use type hints"

**Do instead**: Explain what the type hints constrain or enable.

```python
# Bad: Added type hints for better IDE support
# Good: Type hints specify expected types for validation
```

#### Preferred Pattern: "Refactored to use dataclass"

**Do instead**: Name the specific behavior the dataclass provides.

```python
# Bad: Refactored to use dataclass instead of dict
# Good: Uses dataclass for automatic __init__ and __repr__
```

### JavaScript/TypeScript Patterns

<!-- no-pair-required: subsection heading grouping language-specific examples -->

#### Preferred Pattern: "Migrated to async/await"

**Do instead**: Describe the execution model the pattern provides.

```javascript
// Bad: Migrated from promises to async/await
// Good: Uses async/await for sequential asynchronous operations
```

#### Preferred Pattern: "Updated to ES6 syntax"

**Do instead**: Name the concrete behavior the syntax change enables.

```javascript
// Bad: Updated to use arrow functions
// Good: Arrow function preserves outer 'this' context
```

## Documentation-Specific Patterns

<!-- no-pair-required: subsection heading grouping documentation anti-patterns -->

### README Files

#### Preferred Pattern: Version-specific feature lists

**Do instead**: List features by name and behavior, without tying them to a release version.

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

#### Preferred Pattern: Historical installation instructions

**Do instead**: Show the current installation steps with no reference to how they changed.

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

#### Preferred Pattern: Endpoint evolution

**Do instead**: Document the current response schema directly, without mentioning past changes.

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

#### Preferred Pattern: Parameter history

**Do instead**: Document the parameter's type and usage, not when or why it was introduced.

```markdown
# Bad:
The `filter` parameter was added in v1.5 to allow...

# Good:
### Parameters
- `filter` (optional): JSON query using RFC 6902 syntax
```
