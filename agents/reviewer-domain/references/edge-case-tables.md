# Edge Case Tables

Systematic edge cases to check for each data type during business logic review.

## Numeric Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Integers | 0, 1, -1, MAX_INT, MIN_INT, overflow, underflow |
| Floats | 0.0, -0.0, NaN, Infinity, -Infinity, precision loss, rounding |
| Decimals (money) | 0.00, negative amounts, MAX_DECIMAL, rounding at 2 decimals |
| Percentages | 0%, 100%, >100%, negative, fractional |
| Counts/Quantities | 0, 1, negative, fractional (if invalid) |

**Common Bugs**:
- Division by zero not handled
- Integer division truncating when float needed
- Overflow/underflow not checked
- Rounding errors compounding in loops
- Off-by-one in range checks (`>` vs `>=`)

## String Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Text | empty "", null, whitespace only "   ", very long (>1MB), special chars, unicode |
| Names | empty, single char, unicode names, trailing spaces, hyphens, apostrophes |
| Email | empty, invalid format, very long, unicode domains |
| URLs | empty, invalid scheme, localhost, very long, unicode |
| Passwords | empty, min length, max length, special char requirements |

**Common Bugs**:
- Empty string not handled differently from null
- Whitespace not trimmed before validation
- Length limits not enforced
- Unicode/UTF-8 not handled correctly
- SQL injection via unsanitized strings

## Array/Collection Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Arrays | empty [], single element [x], null elements, duplicates, very large (>10k items) |
| Lists | empty, null, single item, all identical items |
| Sets | empty, single item, duplicate handling |
| Maps | empty, null keys, null values, key collisions |

**Common Bugs**:
- Index out of bounds on empty array
- Null pointer on null element access
- Loop assumes non-empty array
- O(n²) performance on large collections
- Duplicate handling incorrect

## Date/Time Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Dates | null, epoch (1970-01-01), year 2038 problem, leap years, Feb 29 |
| Times | midnight (00:00), null, daylight saving transitions |
| Timestamps | null, epoch, future, past, timezone handling |
| Durations | 0 seconds, negative, overflow (>MAX_INT seconds) |
| Ranges | start = end, start > end, null start, null end |

**Common Bugs**:
- DST transitions causing 1-hour shifts
- Leap year logic incorrect (2000 is leap, 1900 is not)
- Timezone not specified (assumes local vs UTC)
- Date arithmetic wrong near boundaries
- Year 2038 overflow on 32-bit Unix timestamps

## Object/Struct Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Objects | null, empty {}, missing required fields, extra unexpected fields |
| Nested objects | null at any level, deeply nested (>10 levels), circular references |
| Optional fields | null, undefined, missing entirely |
| Polymorphic types | all possible types, invalid type |

**Common Bugs**:
- Null pointer dereferencing
- Missing field not handled
- Extra fields causing validation failure
- Nested null not checked
- Type assertion fails on unexpected type

## File/Upload Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Files | missing, empty (0 bytes), very large (>100MB), wrong format, corrupt, no read perms |
| Uploads | timeout mid-upload, duplicate filename, path traversal attack, malicious content |
| Paths | empty, null, relative paths, absolute paths, non-existent, symlinks |

**Common Bugs**:
- Missing file not checked before open
- Large file not chunked/streamed
- Path traversal allows directory escape
- File permissions not checked
- Temp files not cleaned up

## Boolean Types

| Data Type | Edge Cases to Check |
|-----------|---------------------|
| Booleans | true, false, null (tri-state), default value |
| Flags | unset (null) vs false, bitwise operations |

**Common Bugs**:
- Null treated as false (or true)
- Default value incorrect
- Bitwise AND/OR logic inverted

## State Machine Edge Cases

| State Type | Edge Cases to Check |
|-----------|---------------------|
| Status enum | all valid values, invalid value, null, case sensitivity |
| Transitions | all valid FROM→TO, invalid transitions, concurrent changes |
| Terminal states | can't transition out, proper cleanup |
| Error states | recovery path exists, retry logic, timeout handling |

**Common Bugs**:
- Invalid transition allowed
- Terminal state escapable
- Concurrent transition race condition
- Error state unrecoverable
- State persisted before validation

## Calculation Edge Cases

| Calculation Type | Edge Cases to Check |
|------------------|---------------------|
| Tax calculations | 0% tax, 100% tax, fractional rates, compound tax, rounding |
| Discounts | 0% discount, 100% discount, >100% (invalid), stacking discounts |
| Totals | sum of zeros, negative numbers, overflow, precision loss |
| Averages | divide by zero, all zeros, single value, rounding |
| Percentages | 0 denominator, negative, >100%, fractional |

**Common Bugs**:
- Division by zero
- Order of operations incorrect
- Rounding at wrong step
- Overflow not checked
- Negative amounts not validated

## Concurrent Access Edge Cases

| Access Pattern | Edge Cases to Check |
|----------------|---------------------|
| Read-modify-write | race condition, lost update, stale read |
| Increment/decrement | race on counter, overflow |
| Check-then-act | state changed between check and act |
| Resource allocation | double-spend, over-allocation, deadlock |

**Common Bugs**:
- Check-then-act race condition
- Lost update (concurrent writes)
- Deadlock (lock ordering)
- Double-spend/double-allocation
- Stale read after concurrent update
