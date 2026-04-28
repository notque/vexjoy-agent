# Comment Quality Examples

This document provides before/after examples of comment rewrites that remove temporal references and focus on timeless, meaningful documentation.

## Function/Method Documentation

### Example 1: General Function Comment
```go
// Bad: Updated this function to handle edge cases better
// Good: Handles edge cases including nil inputs and empty strings
// Why: Removes "updated" and "better", focuses on what it does
```

### Example 2: Validation Function
```go
// Bad: Fixed to properly validate user input
// Good: Validates user input against security policies X, Y, and Z
// Why: Removes "fixed" and "properly", explains specific validation
```

### Example 3: Algorithm Implementation
```go
// Bad: New implementation using improved algorithm
// Good: Uses QuickSort algorithm for O(n log n) average case performance
// Why: Removes "new" and "improved", specifies algorithm and complexity
```

### Example 4: Error Handling
```go
// Bad: Enhanced error handling to provide better messages
// Good: Returns structured error messages with error codes and troubleshooting hints
// Why: Removes "enhanced" and "better", describes actual error message structure
```

### Example 5: Data Processing
```go
// Bad: Refactored to process data more efficiently
// Good: Processes data in batches of 1000 to reduce memory usage
// Why: Removes "refactored" and "more efficiently", explains specific approach
```

## Inline Comments

### Example 1: Performance Optimization
```go
// Bad: Changed to use map for better performance
// Good: Map provides O(1) lookup compared to O(n) array search
// Why: Removes "changed" and "better", explains specific performance benefit
```

### Example 2: Nil Check
```go
// Bad: Added check to fix null pointer issue
// Good: Guards against nil receiver to prevent panic
// Why: Removes "added" and "fix", explains purpose of guard
```

### Example 3: Business Logic
```go
// Bad: Removed old validation logic
// Good: Validates only active users per business requirement BR-123
// Why: Removes "removed" and "old", explains current validation rule
```

### Example 4: Cache Implementation
```go
// Bad: Now using LRU cache instead of simple map
// Good: LRU cache limits memory usage to 100MB
// Why: Removes "now using" and "instead of", focuses on current behavior
```

### Example 5: Concurrency
```go
// Bad: Fixed race condition by adding mutex
// Good: Mutex protects concurrent access to shared state
// Why: Removes "fixed" and "adding", explains mutex purpose
```

## Documentation Headers

### Example 1: README Title
```markdown
# Bad: Updated API Documentation
# Good: API Documentation
# Why: Header should state what it is, not that it changed
```

### Example 2: User Guide
```markdown
# Bad: New User Guide (Revised March 2024)
# Good: User Guide
# Why: Remove "new", "revised", and date - user guides are living documents
```

### Example 3: Installation Guide
```markdown
# Bad: Improved Installation Instructions
# Good: Installation Instructions
# Why: "Improved" is relative to past state, not useful information
```

### Example 4: API Overview
```markdown
# Bad: Enhanced API with Better Error Handling
# Good: API Overview
# Why: "Enhanced" and "Better" are temporal comparisons
```

## Documentation Content

### Example 1: Error Handling Description
```markdown
# Bad: All storage-related errors now follow a consistent JSON structure
# Good: All storage-related errors follow a consistent JSON structure
# Why: Remove "now" - this is the current state
```

### Example 2: Feature Description
```markdown
# Bad: The improved error handling system now provides better messages
# Good: The error handling system provides structured error messages with context
# Why: Removes "improved", "now", "better" - focuses on what it provides
```

### Example 3: API Description
```markdown
# Bad: We have enhanced the API to now return detailed error codes
# Good: The API returns detailed error codes
# Why: Removes "enhanced", "now", focuses on current behavior
```

### Example 4: Functionality Explanation
```markdown
# Bad: Errors now include helpful hints for troubleshooting
# Good: Errors include troubleshooting hints based on error type
# Why: Removes "now", adds specific detail about hints
```

### Example 5: System Architecture
```markdown
# Bad: The new architecture uses microservices instead of monolith
# Good: The architecture uses microservices with REST APIs for inter-service communication
# Why: Removes "new" and "instead of", describes current architecture
```

## Package/Module Documentation

### Example 1: Package Overview
```go
// Bad: Package utils provides improved utility functions
// Good: Package utils provides string manipulation, data validation, and type conversion utilities
// Why: Removes "improved", lists specific utilities
```

### Example 2: Module Purpose
```python
# Bad: This module was refactored to better handle async operations
# Good: This module handles asynchronous operations with context cancellation and timeout support
# Why: Removes "refactored" and "better", explains specific capabilities
```

### Example 3: Library Description
```javascript
// Bad: Updated library that now supports TypeScript
// Good: Library with TypeScript definitions for type-safe API usage
// Why: Removes "updated" and "now", describes TypeScript support
```

## Complex Scenarios

### Example 1: Algorithm Choice Explanation
```go
// Bad: Changed from bubble sort to quicksort for better performance
// Good: Uses QuickSort for O(n log n) average case, acceptable because dataset is typically random
// Why: Removes "changed from" and "better", explains algorithm and rationale
```

### Example 2: Design Decision
```go
// Bad: Switched to event-driven architecture to improve scalability
// Good: Event-driven architecture decouples components and allows horizontal scaling
// Why: Removes "switched to" and "improve", explains benefits of current design
```

### Example 3: Error Handling Strategy
```go
// Bad: Now wraps all errors with context instead of returning raw errors
// Good: Wraps errors with context (file path, operation) to aid debugging
// Why: Removes "now" and "instead of", explains what context is added
```

### Example 4: Configuration Approach
```go
// Bad: Updated configuration system to use environment variables
// Good: Configuration loads from environment variables, falling back to config.yaml
// Why: Removes "updated", describes complete configuration behavior
```

## API Documentation

### Example 1: Endpoint Description
```markdown
# Bad: Enhanced endpoint that now returns pagination metadata
# Good: Returns paginated results with total count and next page token
# Why: Removes "enhanced" and "now", describes response structure
```

### Example 2: Parameter Documentation
```markdown
# Bad: Added optional filter parameter for better query flexibility
# Good: Optional filter parameter supports JSON query syntax (RFC 6902)
# Why: Removes "added" and "better", specifies filter syntax
```

### Example 3: Response Format
```markdown
# Bad: Improved error responses with more details
# Good: Error responses include error code, message, and field-level validation errors
# Why: Removes "improved" and "more", lists specific error response fields
```

## README Content

### Example 1: Features Section
```markdown
# Bad: New features in this release
# Good: Features

- Authentication with JWT tokens
- Rate limiting (100 requests/minute)
- Webhook support for real-time updates

# Why: Remove "new" and "in this release", list current features
```

### Example 2: Installation Section
```markdown
# Bad: Updated installation process now uses Docker
# Good: Installation

Requires Docker 20.10 or higher:
```bash
docker pull myapp:latest
docker run -p 8080:8080 myapp:latest
```

# Why: Remove "updated" and "now uses", provide current installation steps
```

### Example 3: Usage Examples
```markdown
# Bad: We improved the API to make it easier to use
# Good: Quick Start

```python
from mylib import Client
client = Client(api_key="your_key")
result = client.query(filters={"status": "active"})
```

# Why: Remove marketing language, show actual usage
```

## Common Pitfalls and Preferred Fixes

<!-- no-pair-required: section heading organizing pitfall examples; each pitfall subsection carries its own Good example -->

### Pitfall 1: Hidden Temporal Language in Adjectives
```go
// Bad: ProcessData runs faster validation
// Good: ProcessData validates in O(n) time using hash-based lookup
// Why: "faster" implies comparison to past - be specific instead
```

### Pitfall 2: Comparison Without Context
```go
// Bad: Uses more efficient caching
// Good: Uses LRU cache with 1000-item capacity and 5-minute TTL
// Why: "more efficient" is meaningless without baseline - describe actual behavior
```

### Pitfall 3: Development Process in Production Code
```go
// Bad: Temporary workaround until database supports JSON queries
// Good: Parses JSON in application code because database version 5.x lacks JSON query support
// Why: Remove "temporary" and "workaround", explain constraint and approach
```

### Pitfall 4: Future-Looking Statements
```go
// Bad: TODO: Remove this when we migrate to v2 API
// Good: TODO: Replace with v2 API endpoint when server supports it (requires server >= 2.0)
// Why: Remove temporal language from TODO, specify dependency
```

### Pitfall 5: Historical Context in Comments
```go
// Bad: This used to cause race conditions but is now safe
// Good: Mutex protects counter from concurrent modification
// Why: History doesn't help future maintainers - explain current safety mechanism
```

## Edge Cases

### Edge Case 1: Deprecation (Allowed)
```go
// Good: @deprecated Use ProcessDataV2() instead. This method will be removed in v3.0.
// Why: Deprecation notices are explicitly allowed - they serve a warning purpose
```

### Edge Case 2: Legal Notices (Allowed)
```go
// Good: Copyright 2024 Company Name. All rights reserved.
// Why: Legal requirements and copyright notices are unchanged
```

### Edge Case 3: Generated Code (Allowed)
```go
// Good: Generated by protoc-gen-go. DO NOT EDIT.
// Why: Code generation markers are tool-specific and required
```

### Edge Case 4: Version Tags in API Docs (Context-Dependent)
```go
// Context matters:
// Bad in code comment: "Added in v2.0"
// Good in API changelog: "Available since v2.0"
// Why: Changelogs track history, code comments explain current behavior
```

## Complete Rewrite Example

### Before (Multiple Issues)
```go
// ProcessUserData handles user data processing
// Updated in v2.0 to include better validation and error handling
// Fixed bug where nil users caused crashes
// Now supports concurrent processing for improved performance
// Returns enhanced error messages with more details
func ProcessUserData(users []User) error {
    // Added nil check to fix crash issue
    if users == nil {
        return errors.New("users cannot be nil")
    }

    // Changed to use goroutines for better performance
    var wg sync.WaitGroup
    // ... rest of implementation
}
```

### After (Timeless)
```go
// ProcessUserData validates and processes user records concurrently
// Returns an error if users is nil or if any user fails validation
// Validation rules: email format, age >= 18, non-empty name
// Processes up to 100 users concurrently to balance throughput and resource usage
func ProcessUserData(users []User) error {
    // Guards against nil slice to prevent panic in range iteration
    if users == nil {
        return errors.New("users cannot be nil")
    }

    // Process users concurrently with semaphore limiting to 100 goroutines
    var wg sync.WaitGroup
    // ... rest of implementation
}
```

### Why This Works
- Removed all temporal references: "Updated", "v2.0", "better", "Fixed", "now", "improved", "more", "added", "changed"
- Explains WHAT it does: validates, processes concurrently
- Explains WHY: specific validation rules, resource balance
- Explains HOW: nil guard prevents panic, semaphore limits goroutines
- Timeless: works equally well in 10 years
