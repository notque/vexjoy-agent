# Advanced Isolation Techniques

This reference provides systematic approaches to narrowing down bug locations efficiently.

## Table of Contents
1. [Binary Search (Bisection)](#binary-search-bisection)
2. [Component Isolation](#component-isolation)
3. [Delta Debugging](#delta-debugging)
4. [Git Bisect](#git-bisect)
5. [Input Minimization](#input-minimization)
6. [Dependency Elimination](#dependency-elimination)
7. [Environment Isolation](#environment-isolation)

---

## Binary Search (Bisection)

### Concept
Divide the search space in half repeatedly to locate the bug efficiently. This is one of the most powerful debugging techniques.

### When to Use
- Large codebase with unclear failure point
- Long input causing failure
- Many commits between working and broken states
- Large dataset triggering bug

### Algorithm
```
1. Identify boundaries: working (good) and failing (bad) states
2. Test the midpoint between good and bad
3. If midpoint fails → new bad state (search lower half)
4. If midpoint passes → new good state (search upper half)
5. Repeat until narrowed to single point
```

### Example: Code Path Bisection

**Scenario**: Function fails with large input, works with small input

```python
def buggy_function(items):
    """Function that fails somewhere in processing."""
    # Step 1: Process first half
    for i in range(len(items) // 2):
        process(items[i])

    # Step 2: Process second half
    for i in range(len(items) // 2, len(items)):
        process(items[i])
```

**Bisection Process**:
```python
# Test 1: Only first half
def test_first_half(items):
    for i in range(len(items) // 2):
        process(items[i])
# Result: PASS → Bug not in first half

# Test 2: Only second half
def test_second_half(items):
    for i in range(len(items) // 2, len(items)):
        process(items[i])
# Result: FAIL → Bug is in second half

# Test 3: Only third quarter (first half of second half)
def test_third_quarter(items):
    start = len(items) // 2
    end = start + (len(items) - start) // 2
    for i in range(start, end):
        process(items[i])
# Result: FAIL → Bug is in third quarter

# Continue narrowing...
```

### Example: Loop Iteration Bisection

```bash
# Find which iteration causes failure
# Total iterations: 1000
# Binary search iterations: ~10 (log2(1000))

# Test iteration 500
# If FAIL: search 0-500
# If PASS: search 500-1000

# Test iteration 250 (if 500 failed)
# If FAIL: search 0-250
# If PASS: search 250-500

# Continue until single iteration identified
```

---

## Component Isolation

### Concept
Test components individually to determine which one contains the bug.

### Isolation Strategies

#### 1. Bottom-Up Isolation
Start with smallest components, work up to full system.

```python
# Full system (fails)
def full_system():
    data = fetch_data()        # Component A
    processed = process(data)  # Component B
    result = save(processed)   # Component C
    return result

# Test Component A alone
def test_component_a():
    data = fetch_data()
    assert data is not None
    assert isinstance(data, dict)
    print(f"Component A output: {data}")
    # Result: PASS

# Test Component B alone with mock data
def test_component_b():
    mock_data = {'key': 'value'}
    processed = process(mock_data)
    assert processed is not None
    print(f"Component B output: {processed}")
    # Result: FAIL → Bug is in Component B
```

#### 2. Top-Down Isolation
Start with full system, remove components until bug disappears.

```javascript
// Full system (fails)
async function fullSystem() {
    const data = await fetchFromAPI();     // Component 1
    const validated = validate(data);      // Component 2
    const transformed = transform(validated); // Component 3
    return await save(transformed);        // Component 4
}

// Remove Component 4 (save)
async function testWithoutSave() {
    const data = await fetchFromAPI();
    const validated = validate(data);
    const transformed = transform(validated);
    console.log(transformed); // Just log instead of save
    return transformed;
}
// Result: STILL FAILS → Bug not in Component 4

// Remove Component 3 (transform)
async function testWithoutTransform() {
    const data = await fetchFromAPI();
    const validated = validate(data);
    console.log(validated);
    return validated;
}
// Result: PASSES → Bug is in Component 3
```

#### 3. Substitution Isolation
Replace suspect component with known-good version or mock.

```go
// Original (fails)
func ProcessOrder(order Order) error {
    validated, err := ValidateOrder(order)  // Suspect
    if err != nil {
        return err
    }
    return SaveOrder(validated)
}

// Test with mock validator
func ProcessOrderWithMock(order Order) error {
    // Mock always returns order unchanged
    mockValidated := order
    return SaveOrder(mockValidated)
}
// Result: PASSES → Bug is in ValidateOrder

// Test with different validator implementation
func ProcessOrderWithAltValidator(order Order) error {
    validated := simpleValidate(order)  // Alternative implementation
    return SaveOrder(validated)
}
// Result: PASSES → Confirms bug in ValidateOrder
```

---

## Delta Debugging

### Concept
Systematically minimize the difference between passing and failing inputs to find the minimal change that triggers the bug.

### Algorithm
```
1. Start with failing input (F) and passing input (P)
2. Create input that is halfway between F and P
3. Test hybrid input
4. If fails: replace F with hybrid (smaller delta)
5. If passes: replace P with hybrid (smaller delta)
6. Repeat until minimal difference found
```

### Example: Configuration Delta

**Scenario**: Application works with config A, fails with config B

```json
// Config A (works)
{
    "timeout": 30,
    "retries": 3,
    "cache": true,
    "debug": false
}

// Config B (fails)
{
    "timeout": 60,
    "retries": 5,
    "cache": false,
    "debug": true
}
```

**Delta Debugging Process**:
```json
// Test 1: Half of changes
{
    "timeout": 60,    // From B
    "retries": 5,     // From B
    "cache": true,    // From A
    "debug": false    // From A
}
// Result: PASSES

// Test 2: Other half
{
    "timeout": 30,    // From A
    "retries": 3,     // From A
    "cache": false,   // From B
    "debug": true     // From B
}
// Result: FAILS → Bug is in cache or debug

// Test 3: Isolate cache change
{
    "timeout": 30,
    "retries": 3,
    "cache": false,   // From B
    "debug": false    // From A
}
// Result: FAILS → Bug triggered by cache=false
```

### Example: Code Delta

**Scenario**: Function works in v1, fails in v2

```python
# Version 1 (works)
def process_data_v1(data):
    result = []
    for item in data:
        result.append(item.upper())
    return result

# Version 2 (fails)
def process_data_v2(data):
    result = []
    for item in data:
        cleaned = item.strip()
        result.append(cleaned.upper())
    return result
```

**Delta Test**:
```python
# Test: Just the strip() addition
def delta_test(data):
    result = []
    for item in data:
        cleaned = item.strip()  # Only new code
        result.append(cleaned.upper())
    return result
# Result: FAILS → Bug is in strip() addition

# Further investigation reveals:
# Some items in data are None, and None.strip() crashes
```

---

## Git Bisect

### Concept
Use git's binary search to find the commit that introduced a bug.

### When to Use
- Bug appeared recently but exact commit unknown
- Many commits between working and broken states
- Automated test can verify bug presence

### Basic Usage

```bash
# Start bisect
git bisect start

# Mark current commit as bad
git bisect bad HEAD

# Mark last known good commit
git bisect good v1.2.0  # or commit hash

# Git checks out middle commit
# Test for bug
npm test  # or any test command

# If bug present
git bisect bad

# If bug absent
git bisect good

# Git automatically checks out next commit to test
# Repeat until git identifies first bad commit

# When done
git bisect reset
```

### Automated Bisect

```bash
# Create test script that returns 0 for good, 1 for bad
cat > test_bug.sh << 'EOF'
#!/bin/bash
npm test 2>&1 | grep -q "Expected error"
exit $?
EOF

chmod +x test_bug.sh

# Run automated bisect
git bisect start HEAD v1.2.0
git bisect run ./test_bug.sh

# Git will test each commit automatically
# and identify first bad commit
```

### Skip Commits

```bash
# If current commit can't be tested (won't compile, etc.)
git bisect skip

# Skip range of commits
git bisect skip v1.0..v1.1
```

### Bisect with Build Steps

```bash
# Test script that includes build
cat > test_with_build.sh << 'EOF'
#!/bin/bash
make clean
if ! make; then
    exit 125  # Special code: skip this commit
fi

./run_tests
exit $?
EOF

git bisect start HEAD v1.0.0
git bisect run ./test_with_build.sh
```

---

## Input Minimization

### Concept
Reduce input to smallest size that still triggers the bug.

### Why Minimize
- Easier to understand what's causing failure
- Faster test execution
- Clearer debugging focus
- Better test case for regression

### Text Input Minimization

**Original Input (100 lines, fails)**:
```
Line 1: Some data
Line 2: More data
...
Line 100: Final data
```

**Binary Search Approach**:
```bash
# Test first 50 lines
head -50 input.txt > test_input.txt
./program test_input.txt
# Result: FAILS → Bug in first 50 lines

# Test first 25 lines
head -25 input.txt > test_input.txt
./program test_input.txt
# Result: PASSES → Bug in lines 26-50

# Test lines 26-37
sed -n '26,37p' input.txt > test_input.txt
./program test_input.txt
# Result: FAILS → Bug in lines 26-37

# Continue until minimal input found
# Final: Line 32 triggers bug
```

### JSON Input Minimization

```python
# Original (large JSON, fails)
original = {
    "users": [...],  # 100 users
    "settings": {...},  # 50 settings
    "metadata": {...}  # 20 fields
}

# Test 1: Remove users
test1 = {
    "settings": {...},
    "metadata": {...}
}
# Result: FAILS → Bug not in users

# Test 2: Remove settings
test2 = {
    "users": [...],
    "metadata": {...}
}
# Result: PASSES → Bug is in settings

# Test 3: Reduce settings to half
test3 = {
    "users": [...],
    "settings": {
        # First 25 settings only
    },
    "metadata": {...}
}
# Result: FAILS → Bug in first 25 settings

# Continue until minimal settings found
```

### Array Input Minimization

```python
def minimize_array(array, test_function):
    """
    Minimize array while maintaining failure.

    Args:
        array: Original failing input
        test_function: Function that returns True if bug present

    Returns:
        Minimal array that still triggers bug
    """
    # Start with full array
    current = array.copy()

    # Try removing each element
    i = 0
    while i < len(current):
        # Try array without element i
        test = current[:i] + current[i+1:]

        if test_function(test):
            # Bug still present without this element
            current = test
            # Don't increment i, test same position again
        else:
            # Bug disappeared, keep this element
            i += 1

    return current

# Usage
failing_input = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def has_bug(arr):
    try:
        buggy_function(arr)
        return False
    except Exception:
        return True

minimal = minimize_array(failing_input, has_bug)
print(f"Minimal input: {minimal}")
# Output: Minimal input: [3, 7]  # Only these two elements needed
```

---

## Dependency Elimination

### Concept
Remove or mock external dependencies to isolate the bug to your code.

### Common Dependencies to Eliminate

#### 1. Database
```python
# Original (depends on database)
def get_user_score(user_id):
    user = database.query("SELECT * FROM users WHERE id = ?", user_id)
    return calculate_score(user)

# Isolated (no database)
def get_user_score_isolated(user_id):
    # Mock user data
    mock_user = {
        'id': user_id,
        'name': 'Test User',
        'points': 100
    }
    return calculate_score(mock_user)

# Test both
print(get_user_score(123))  # Fails
print(get_user_score_isolated(123))  # Passes → Bug is in database query
```

#### 2. Network/API
```javascript
// Original (depends on API)
async function processUserData(userId) {
    const userData = await fetch(`/api/users/${userId}`);
    const json = await userData.json();
    return transformData(json);
}

// Isolated (no network)
async function processUserDataIsolated(userId) {
    // Mock API response
    const mockData = {
        id: userId,
        name: "Test User",
        email: "test@example.com"
    };
    return transformData(mockData);
}

// Test
processUserData(123);  // Fails
processUserDataIsolated(123);  // Passes → Bug is in API interaction
```

#### 3. File System
```go
// Original (depends on filesystem)
func ProcessConfig(path string) error {
    data, err := os.ReadFile(path)
    if err != nil {
        return err
    }
    return parseConfig(data)
}

// Isolated (no filesystem)
func ProcessConfigIsolated() error {
    // Mock file contents
    mockData := []byte(`{"setting": "value"}`)
    return parseConfig(mockData)
}

// Test
ProcessConfig("config.json")  // Fails
ProcessConfigIsolated()       // Passes → Bug is in file reading
```

#### 4. Time/Clock
```python
# Original (depends on current time)
def is_expired(created_at):
    now = datetime.now()  # Non-deterministic
    age = now - created_at
    return age.days > 30

# Isolated (no time dependency)
def is_expired_isolated(created_at):
    # Mock current time
    mock_now = datetime(2025, 1, 1)
    age = mock_now - created_at
    return age.days > 30

# Test with consistent time
created = datetime(2024, 11, 1)
print(is_expired(created))  # Result depends on when you run it
print(is_expired_isolated(created))  # Always same result
```

---

## Environment Isolation

### Concept
Reproduce bug in controlled environment to eliminate environmental factors.

### Techniques

#### 1. Docker Container (Clean Environment)
```dockerfile
# Dockerfile for isolated testing
FROM python:3.11-slim

# Install exact dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy only necessary code
COPY app/ /app/
WORKDIR /app

# Run test
CMD ["python", "test_bug.py"]
```

```bash
# Build and run in isolated environment
docker build -t bug-test .
docker run --rm bug-test

# If bug still occurs → Not an environment issue
# If bug disappears → Environment-specific
```

#### 2. Virtual Environment (Python)
```bash
# Create fresh virtual environment
python -m venv test_env
source test_env/bin/activate

# Install minimal dependencies
pip install package==1.2.3  # Exact versions

# Test
python test_bug.py

# If bug occurs → Not dependency related
# If bug disappears → Check dependency versions
```

#### 3. Environment Variable Isolation
```bash
# Run with clean environment
env -i python test_bug.py

# Run with specific variables only
env -i PATH=/usr/bin PYTHONPATH=/app python test_bug.py

# Compare with full environment
python test_bug.py

# If results differ → Environment variable issue
```

#### 4. OS/Platform Isolation
```bash
# Test on different platforms
# Linux
docker run --rm -it ubuntu:22.04 bash -c "apt-get update && apt-get install -y python3 && python3 test_bug.py"

# macOS
# (run natively or in VM)

# Windows
# (run natively or in VM)

# If bug only on specific platform → Platform-specific issue
```

---

## Isolation Workflow Decision Tree

```
Bug Detected
│
├─ Known code location? ─── YES ──→ Component Isolation
│                                    └─ Bottom-up or Top-down
│
├─ Recent regression? ───── YES ──→ Git Bisect
│                                    └─ Find breaking commit
│
├─ Large input causing failure? ── YES ──→ Input Minimization
│                                          └─ Binary search on input
│
├─ External dependency involved? ─ YES ──→ Dependency Elimination
│                                          └─ Mock or remove dependencies
│
├─ Intermittent/environment? ───── YES ──→ Environment Isolation
│                                          └─ Clean environment test
│
└─ Unknown location in codebase? ─ YES ──→ Binary Search (Bisection)
                                           └─ Divide codebase in half
```

## Isolation Best Practices

1. **Always isolate before identifying**: Don't guess at the root cause
2. **Document isolation steps**: Record what you tested and results
3. **Use automated tests**: Speed up isolation with scripts
4. **Minimize changes**: Change one variable at a time
5. **Verify isolation**: Confirm bug appears/disappears consistently
6. **Combine techniques**: Use multiple isolation methods together
7. **Keep original reproduction**: Don't lose the original failing case

## Common Isolation Mistakes

1. **Changing multiple variables at once**: Can't determine which change mattered
2. **Insufficient testing**: Only testing once per isolation step
3. **Ignoring environmental factors**: Assuming environment doesn't matter
4. **Skipping documentation**: Forgetting what was already tested
5. **Stopping too early**: Not narrowing down to minimal case
6. **Not verifying assumptions**: Assuming component is irrelevant without testing

---

This reference provides systematic approaches to efficiently narrow down bug locations. Use these techniques in Phase 2 (ISOLATE) of the debugging workflow to reduce search space before attempting to identify root cause in Phase 3.
