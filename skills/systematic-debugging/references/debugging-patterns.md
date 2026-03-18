# Common Bug Patterns and Solutions

This reference provides a catalog of frequently encountered bug patterns, their characteristics, and systematic debugging approaches.

## Table of Contents
1. [Off-by-One Errors](#off-by-one-errors)
2. [Null/None Pointer Errors](#nullnone-pointer-errors)
3. [Race Conditions](#race-conditions)
4. [Resource Leaks](#resource-leaks)
5. [Incorrect Error Handling](#incorrect-error-handling)
6. [Type Coercion Issues](#type-coercion-issues)
7. [Scope and Closure Problems](#scope-and-closure-problems)
8. [Encoding and Unicode Issues](#encoding-and-unicode-issues)
9. [Timezone and Date Problems](#timezone-and-date-problems)
10. [Cache Invalidation Issues](#cache-invalidation-issues)

---

## Off-by-One Errors

### Characteristics
- Array index out of bounds
- Loop executes one too many/few times
- Fence post errors (off by one in boundary calculations)

### Common Manifestations
```python
# Python - Classic off-by-one
items = [1, 2, 3, 4, 5]
for i in range(len(items)):
    print(items[i+1])  # BUG: IndexError on last iteration

# Fixed version
for i in range(len(items) - 1):
    print(items[i+1])
```

```javascript
// JavaScript - Array slicing
const arr = [1, 2, 3, 4, 5];
const subset = arr.slice(0, 3);  // Gets [1, 2, 3] - correct
const buggy = arr.slice(1, 3);   // Gets [2, 3] - might be off-by-one if you expected [1, 2, 3]
```

```go
// Go - Slice boundaries
items := []int{1, 2, 3, 4, 5}
for i := 0; i <= len(items); i++ {  // BUG: <= should be <
    fmt.Println(items[i])  // panic on last iteration
}
```

### Debugging Strategy
1. **Reproduce**: Test with different array sizes (0, 1, 2, 10 elements)
2. **Isolate**: Add logging at loop entry, each iteration, and exit
3. **Identify**: Check loop conditions and index calculations
4. **Verify**: Test boundary cases (empty, single element, full array)

### Prevention
- Use language iterators when possible (`for item in items`)
- Explicitly test with empty collections and single-element collections
- Add assertions for array bounds: `assert 0 <= index < len(array)`

---

## Null/None Pointer Errors

### Characteristics
- Dereferencing null/None/nil values
- Missing null checks before access
- Returning null when caller expects valid object

### Common Manifestations
```python
# Python - NoneType error
def get_user(user_id):
    user = database.find(user_id)
    return user  # May return None

result = get_user(123)
print(result.name)  # BUG: AttributeError if user not found
```

```javascript
// JavaScript - Cannot read property of undefined
function getConfig(key) {
    const config = loadConfig();  // May return null
    return config[key];  // BUG: TypeError if config is null
}
```

```go
// Go - nil pointer dereference
func GetUser(id int) *User {
    user, err := db.Find(id)
    if err != nil {
        return nil  // Returning nil without clear indication
    }
    return user
}

user := GetUser(123)
fmt.Println(user.Name)  // BUG: panic if user is nil
```

### Debugging Strategy
1. **Reproduce**: Test with IDs/keys that don't exist
2. **Isolate**: Add logging before dereference to check for null
3. **Identify**: Trace back to find where null is introduced
4. **Verify**: Test with both valid and invalid inputs

### Prevention
```python
# Python - Explicit null handling
def get_user(user_id):
    user = database.find(user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return user

# Or use default values
result = get_user(123) or default_user
```

```go
// Go - Always check for nil
user := GetUser(123)
if user == nil {
    log.Printf("User not found: %d", 123)
    return
}
fmt.Println(user.Name)
```

---

## Race Conditions

### Characteristics
- Intermittent failures (bug appears/disappears randomly)
- Behavior changes with timing (adding logging "fixes" the bug)
- Different results with same inputs
- Failures more common under load

### Common Manifestations
```python
# Python - Race condition in shared state
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        # BUG: Read-modify-write is not atomic
        temp = self.count
        temp += 1
        self.count = temp

# Two threads calling increment() can both read 0, both write 1
```

```javascript
// JavaScript - Race in async operations
let balance = 100;

async function withdraw(amount) {
    // BUG: Race between check and update
    if (balance >= amount) {
        await delay(100);  // Simulate network delay
        balance -= amount;
        return true;
    }
    return false;
}

// Two concurrent withdrawals of 60 can both succeed, leaving balance at -20
```

```go
// Go - Concurrent map access
var cache = make(map[string]string)

func getValue(key string) string {
    // BUG: Concurrent read/write to map causes panic
    if val, ok := cache[key]; ok {
        return val
    }
    val := fetchFromDB(key)
    cache[key] = val  // Multiple goroutines can write simultaneously
    return val
}
```

### Debugging Strategy
1. **Reproduce**: Run with concurrency testing tools, add delays to expose race
2. **Isolate**: Use race detectors (`go test -race`, Python thread sanitizer)
3. **Identify**: Look for shared mutable state without synchronization
4. **Verify**: Run concurrent tests many times (1000+ iterations)

### Prevention
```python
# Python - Use locks for shared state
import threading

class Counter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.count += 1
```

```go
// Go - Use mutex or channels
var (
    cache = make(map[string]string)
    mu    sync.RWMutex
)

func getValue(key string) string {
    mu.RLock()
    if val, ok := cache[key]; ok {
        mu.RUnlock()
        return val
    }
    mu.RUnlock()

    val := fetchFromDB(key)

    mu.Lock()
    cache[key] = val
    mu.Unlock()

    return val
}
```

---

## Resource Leaks

### Characteristics
- Memory usage grows over time
- File descriptor exhaustion
- Database connection pool exhaustion
- Goroutine/thread leaks

### Common Manifestations
```python
# Python - File handle leak
def process_file(filename):
    f = open(filename)  # BUG: File never closed
    data = f.read()
    return process(data)

# After many calls, OS runs out of file descriptors
```

```go
// Go - Goroutine leak
func processMessages() {
    for msg := range messages {
        go func(m Message) {
            // BUG: Goroutine may block forever if process() hangs
            process(m)
        }(msg)
    }
}
// Goroutines accumulate, consuming memory
```

```javascript
// JavaScript - Event listener leak
function attachHandler(element) {
    // BUG: Event listener not removed when element removed from DOM
    element.addEventListener('click', handleClick);
}
// Memory leak as elements accumulate
```

### Debugging Strategy
1. **Reproduce**: Monitor resource usage over time (memory, file descriptors)
2. **Isolate**: Use profiling tools to identify resource allocation sites
3. **Identify**: Check for missing cleanup (close, free, remove listeners)
4. **Verify**: Monitor resources after fix, ensure they're released

### Prevention
```python
# Python - Use context managers
def process_file(filename):
    with open(filename) as f:
        data = f.read()
    return process(data)  # File automatically closed
```

```go
// Go - Use defer for cleanup
func processFile(filename string) error {
    f, err := os.Open(filename)
    if err != nil {
        return err
    }
    defer f.Close()  // Guaranteed cleanup

    data, err := io.ReadAll(f)
    return processData(data)
}

// Go - Use context for goroutine cancellation
func processMessages(ctx context.Context) {
    for msg := range messages {
        go func(m Message) {
            select {
            case <-ctx.Done():
                return  // Cancel goroutine
            default:
                process(m)
            }
        }(msg)
    }
}
```

---

## Incorrect Error Handling

### Characteristics
- Errors silently swallowed
- Wrong error returned to caller
- Error handling changes control flow unexpectedly
- Errors logged but not propagated

### Common Manifestations
```python
# Python - Silently swallowing errors
try:
    result = risky_operation()
except Exception:
    pass  # BUG: Error hidden, caller thinks operation succeeded

# Using result that was never assigned
print(result)  # NameError or uses stale value
```

```go
// Go - Ignoring errors
func processData() {
    data, _ := fetchData()  // BUG: Error ignored
    save(data)              // May save nil/invalid data
}
```

```javascript
// JavaScript - Wrong error handling in promises
fetch(url)
    .then(response => response.json())
    .then(data => process(data))
    .catch(err => {
        console.log(err);  // BUG: Error logged but not handled
        // Code continues as if successful
    });
```

### Debugging Strategy
1. **Reproduce**: Test with inputs that cause errors
2. **Isolate**: Add logging for all error paths
3. **Identify**: Trace error handling from source to caller
4. **Verify**: Ensure errors propagate correctly and are handled appropriately

### Prevention
```python
# Python - Explicit error handling
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    return default_value  # Or raise, depending on context
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise  # Propagate unexpected errors
```

```go
// Go - Always check errors
func processData() error {
    data, err := fetchData()
    if err != nil {
        return fmt.Errorf("fetch failed: %w", err)  // Wrap and propagate
    }

    if err := save(data); err != nil {
        return fmt.Errorf("save failed: %w", err)
    }

    return nil
}
```

---

## Type Coercion Issues

### Characteristics
- Unexpected type conversions
- Comparison bugs due to type differences
- Arithmetic errors from mixed types
- JSON serialization/deserialization bugs

### Common Manifestations
```javascript
// JavaScript - Type coercion surprises
"5" + 3      // "53" (string concatenation)
"5" - 3      // 2 (numeric subtraction)
"" == false  // true (type coercion)
[] == false  // true (type coercion)

// BUG: Comparison behaves unexpectedly
if (userInput == 0) {  // "" also matches!
    // Code executes for empty string
}
```

```python
# Python - String vs bytes
def process_data(data):
    # BUG: Assumes data is string, might be bytes
    return data.upper()

process_data(b"hello")  # AttributeError: bytes has no upper()
```

```go
// Go - Integer overflow
var x int8 = 127
x += 1  // Wraps to -128 (overflow)
```

### Debugging Strategy
1. **Reproduce**: Test with different input types
2. **Isolate**: Add type checking/logging before operations
3. **Identify**: Find where type assumptions break
4. **Verify**: Test with all expected input types

### Prevention
```javascript
// JavaScript - Use strict equality
if (userInput === 0) {  // Only matches numeric 0
    // Safe code
}

// TypeScript - Static type checking
function process(data: string): string {
    return data.toUpperCase();
}
```

```python
# Python - Type hints and validation
def process_data(data: str) -> str:
    if not isinstance(data, str):
        raise TypeError(f"Expected str, got {type(data)}")
    return data.upper()
```

---

## Scope and Closure Problems

### Characteristics
- Variables have unexpected values
- Loop variables captured incorrectly
- Functions close over wrong variables
- Unexpected shared state

### Common Manifestations
```javascript
// JavaScript - Classic closure bug
const functions = [];
for (var i = 0; i < 3; i++) {
    functions.push(function() {
        console.log(i);  // BUG: All functions print 3
    });
}

functions[0]();  // Prints 3, not 0
functions[1]();  // Prints 3, not 1
```

```python
# Python - Late binding in closures
functions = []
for i in range(3):
    functions.append(lambda: print(i))  # BUG: All print 2

functions[0]()  # Prints 2, not 0
```

### Debugging Strategy
1. **Reproduce**: Call function and check variable values
2. **Isolate**: Add logging inside closure to see captured values
3. **Identify**: Check scope of captured variables
4. **Verify**: Test each closure independently

### Prevention
```javascript
// JavaScript - Use let (block scope) or IIFE
const functions = [];
for (let i = 0; i < 3; i++) {  // let creates new binding per iteration
    functions.push(function() {
        console.log(i);  // Correct: each closure has own i
    });
}

// Or use IIFE with var
for (var i = 0; i < 3; i++) {
    functions.push((function(j) {
        return function() { console.log(j); };
    })(i));
}
```

```python
# Python - Use default argument to capture value
functions = []
for i in range(3):
    functions.append(lambda i=i: print(i))  # Captures value, not reference

functions[0]()  # Prints 0 correctly
```

---

## Encoding and Unicode Issues

### Characteristics
- Mojibake (garbled characters)
- UnicodeDecodeError / UnicodeEncodeError
- Data corruption when round-tripping through files
- Different behavior on different systems

### Common Manifestations
```python
# Python - Encoding mismatch
with open("file.txt", "r") as f:  # BUG: Assumes UTF-8, might be Latin-1
    text = f.read()

# Writing with wrong encoding
with open("output.txt", "w") as f:
    f.write("café")  # BUG: Uses system default encoding
```

```javascript
// Node.js - Buffer encoding issues
const data = Buffer.from("café", "utf8");
const decoded = data.toString("latin1");  // BUG: Wrong encoding
console.log(decoded);  // Garbled output
```

### Debugging Strategy
1. **Reproduce**: Test with non-ASCII characters (é, ñ, 中文, emoji)
2. **Isolate**: Check encoding at each I/O boundary
3. **Identify**: Find where encoding is lost or changed
4. **Verify**: Round-trip data and check for corruption

### Prevention
```python
# Python - Explicit encoding
with open("file.txt", "r", encoding="utf-8") as f:
    text = f.read()

with open("output.txt", "w", encoding="utf-8") as f:
    f.write("café")

# Always decode bytes to str as early as possible
data = b"caf\xc3\xa9"
text = data.decode("utf-8")  # Explicit decoding
```

---

## Timezone and Date Problems

### Characteristics
- Off-by-one day errors
- Incorrect date calculations across DST boundaries
- Date comparisons fail unexpectedly
- Different results in different timezones

### Common Manifestations
```python
# Python - Naive datetime comparison
from datetime import datetime

dt1 = datetime.now()  # Local time, no timezone info
dt2 = datetime.utcnow()  # UTC time, no timezone info

# BUG: Comparing times from different timezones as if same
if dt1 > dt2:
    print("Local time is later")  # Misleading
```

```javascript
// JavaScript - Date parsing ambiguity
const date = new Date("2025-01-15");  // BUG: Interpreted as UTC midnight
const date2 = new Date("2025-01-15T00:00:00");  // Also UTC
const date3 = new Date("01/15/2025");  // Local timezone

// Different behaviors in different locales
```

### Debugging Strategy
1. **Reproduce**: Test with dates in different timezones and DST transitions
2. **Isolate**: Log dates with full timezone information
3. **Identify**: Check for naive vs aware datetimes
4. **Verify**: Test across timezone boundaries and DST changes

### Prevention
```python
# Python - Always use timezone-aware datetimes
from datetime import datetime, timezone
import zoneinfo

# Create timezone-aware datetime
dt = datetime.now(timezone.utc)

# Convert to specific timezone
pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
dt_pacific = dt.astimezone(pacific)

# Store in UTC, display in local timezone
```

```javascript
// JavaScript - Use ISO 8601 with timezone
const date = new Date("2025-01-15T00:00:00Z");  // Explicit UTC

// Or use date-fns/moment with timezone support
import { zonedTimeToUtc } from 'date-fns-tz';
const date = zonedTimeToUtc('2025-01-15 00:00:00', 'America/New_York');
```

---

## Cache Invalidation Issues

### Characteristics
- Stale data returned after updates
- Inconsistent data across cache and database
- Cache stampede under high load
- Memory exhaustion from unbounded cache

### Common Manifestations
```python
# Python - Cache never invalidated
cache = {}

def get_user(user_id):
    if user_id in cache:
        return cache[user_id]  # BUG: Returns stale data

    user = database.fetch(user_id)
    cache[user_id] = user
    return user

def update_user(user_id, new_data):
    database.update(user_id, new_data)
    # BUG: Forgot to invalidate cache
    # Next get_user() call returns old data
```

```go
// Go - Unbounded cache growth
var cache = make(map[string]interface{})

func getValue(key string) interface{} {
    if val, ok := cache[key]; ok {
        return val
    }

    val := fetchExpensiveData(key)
    cache[key] = val  // BUG: Cache grows without bounds
    return val
}
// Eventually runs out of memory
```

### Debugging Strategy
1. **Reproduce**: Update data and verify cache reflects changes
2. **Isolate**: Add logging for cache hits, misses, invalidations
3. **Identify**: Find all code paths that should invalidate cache
4. **Verify**: Test update operations and check cache consistency

### Prevention
```python
# Python - Explicit cache invalidation
cache = {}

def get_user(user_id):
    if user_id in cache:
        return cache[user_id]

    user = database.fetch(user_id)
    cache[user_id] = user
    return user

def update_user(user_id, new_data):
    database.update(user_id, new_data)
    # Invalidate cache after update
    cache.pop(user_id, None)

# Or use cache with TTL
from cachetools import TTLCache
cache = TTLCache(maxsize=1000, ttl=300)  # 5-minute TTL, max 1000 items
```

```go
// Go - Use LRU cache with size limits
import "github.com/hashicorp/golang-lru/v2"

cache, _ := lru.New[string, interface{}](1000)  // Max 1000 items

func getValue(key string) interface{} {
    if val, ok := cache.Get(key); ok {
        return val
    }

    val := fetchExpensiveData(key)
    cache.Add(key, val)  // Automatically evicts oldest if at capacity
    return val
}
```

---

## Pattern Recognition Checklist

When debugging, ask these questions to identify the pattern:

- **Off-by-One**: Does the bug occur at boundaries? (first/last element, zero/max value)
- **Null/None**: Does the bug occur when data is missing or invalid?
- **Race Condition**: Is the bug intermittent? Does adding delays change behavior?
- **Resource Leak**: Does the bug worsen over time? Does memory/handles increase?
- **Error Handling**: Are errors being suppressed or mishandled?
- **Type Coercion**: Does the bug involve comparisons or arithmetic with mixed types?
- **Scope/Closure**: Does the bug involve functions capturing variables?
- **Encoding**: Does the bug involve non-ASCII text or file I/O?
- **Timezone**: Does the bug involve date calculations or comparisons?
- **Cache**: Does the bug involve stale or inconsistent data?

Identifying the pattern early helps guide the isolation and identification phases of systematic debugging.
