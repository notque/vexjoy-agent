# Edge Case Tables

Systematic edge cases by data type for business logic review.

## Numeric Types

| Data Type | Edge Cases |
|-----------|-----------|
| Integers | 0, 1, -1, MAX_INT, MIN_INT, overflow, underflow |
| Floats | 0.0, -0.0, NaN, Infinity, -Infinity, precision loss, rounding |
| Decimals (money) | 0.00, negative, MAX_DECIMAL, rounding at 2 decimals |
| Percentages | 0%, 100%, >100%, negative, fractional |
| Counts | 0, 1, negative, fractional (if invalid) |

**Common Bugs**: Division by zero, integer truncation needing float, overflow unchecked, rounding compounding in loops, off-by-one in range checks.

## String Types

| Data Type | Edge Cases |
|-----------|-----------|
| Text | empty "", null, whitespace "   ", very long (>1MB), special chars, unicode |
| Names | empty, single char, unicode, trailing spaces, hyphens, apostrophes |
| Email | empty, invalid format, very long, unicode domains |
| URLs | empty, invalid scheme, localhost, very long, unicode |
| Passwords | empty, min/max length, special char requirements |

**Common Bugs**: Empty vs null conflation, whitespace not trimmed, length limits unenforced, unicode mishandled, SQL injection.

## Array/Collection Types

| Data Type | Edge Cases |
|-----------|-----------|
| Arrays | empty [], single [x], null elements, duplicates, very large (>10k) |
| Maps | empty, null keys, null values, key collisions |

**Common Bugs**: Index out of bounds on empty, null pointer on element access, loop assumes non-empty, O(n^2) on large sets, duplicate handling wrong.

## Date/Time Types

| Data Type | Edge Cases |
|-----------|-----------|
| Dates | null, epoch (1970-01-01), year 2038, leap years, Feb 29 |
| Times | midnight (00:00), null, DST transitions |
| Timestamps | null, epoch, future, past, timezone handling |
| Durations | 0 seconds, negative, overflow |
| Ranges | start = end, start > end, null start/end |

**Common Bugs**: DST 1-hour shifts, leap year logic wrong (2000 leap, 1900 not), timezone unspecified, date arithmetic wrong near boundaries, year 2038 overflow.

## Object/Struct Types

| Data Type | Edge Cases |
|-----------|-----------|
| Objects | null, empty {}, missing required fields, extra fields |
| Nested objects | null at any level, deeply nested (>10), circular references |
| Optional fields | null, undefined, missing entirely |
| Polymorphic types | all possible types, invalid type |

**Common Bugs**: Null pointer deref, missing field unhandled, extra fields failing validation, nested null unchecked, type assertion fails.

## File/Upload Types

| Data Type | Edge Cases |
|-----------|-----------|
| Files | missing, empty (0 bytes), very large (>100MB), wrong format, corrupt |
| Uploads | timeout mid-upload, duplicate filename, path traversal, malicious content |
| Paths | empty, null, relative, absolute, non-existent, symlinks |

**Common Bugs**: Missing file unchecked, large file not streamed, path traversal escape, permissions unchecked, temp files not cleaned.

## Boolean Types

| Data Type | Edge Cases |
|-----------|-----------|
| Booleans | true, false, null (tri-state), default value |
| Flags | unset (null) vs false, bitwise operations |

**Common Bugs**: Null treated as false (or true), default incorrect, bitwise logic inverted.

## State Machine Edge Cases

| State Type | Edge Cases |
|-----------|-----------|
| Status enum | all valid, invalid, null, case sensitivity |
| Transitions | all valid FROM->TO, invalid, concurrent changes |
| Terminal states | can't exit, proper cleanup |
| Error states | recovery path, retry, timeout |

**Common Bugs**: Invalid transition allowed, terminal escapable, concurrent race, error unrecoverable, state persisted before validation.

## Calculation Edge Cases

| Type | Edge Cases |
|------|-----------|
| Tax | 0%, 100%, fractional rates, compound, rounding |
| Discounts | 0%, 100%, >100% (invalid), stacking |
| Totals | sum of zeros, negatives, overflow, precision loss |
| Averages | divide by zero, all zeros, single value, rounding |

**Common Bugs**: Division by zero, wrong order of operations, rounding at wrong step, overflow unchecked, negative amounts unvalidated.

## Concurrent Access Edge Cases

| Pattern | Edge Cases |
|---------|-----------|
| Read-modify-write | race, lost update, stale read |
| Increment/decrement | race on counter, overflow |
| Check-then-act | state changed between check and act |
| Resource allocation | double-spend, over-allocation, deadlock |

**Common Bugs**: Check-then-act race, lost update, deadlock from lock ordering, double-spend, stale read after concurrent update.
