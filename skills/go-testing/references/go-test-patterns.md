# Go Test Patterns Reference

Detailed examples for the go-testing skill. See SKILL.md for methodology and workflow.

---

## Table-Driven Test Patterns

### Basic Table-Driven Test

```go
func TestParseTime(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    time.Time
        wantErr bool
    }{
        {
            name:  "valid RFC3339",
            input: "2023-01-01T00:00:00Z",
            want:  time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC),
        },
        {
            name:    "invalid format",
            input:   "not a time",
            wantErr: true,
        },
        {
            name:  "valid with timezone",
            input: "2023-01-01T00:00:00+01:00",
            want:  time.Date(2023, 1, 1, 0, 0, 0, 0, time.FixedZone("", 3600)),
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseTime(tt.input)

            if (err != nil) != tt.wantErr {
                t.Errorf("ParseTime() error = %v, wantErr %v", err, tt.wantErr)
                return
            }

            if !tt.wantErr && !got.Equal(tt.want) {
                t.Errorf("ParseTime() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

### Parallel Table-Driven Tests

```go
func TestConcurrentOperations(t *testing.T) {
    tests := []struct {
        name  string
        input string
        want  string
    }{
        {"case1", "input1", "output1"},
        {"case2", "input2", "output2"},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            got := Transform(tt.input)
            if got != tt.want {
                t.Errorf("got %v, want %v", got, tt.want)
            }
        })
    }
}
```

Note: In Go 1.22+, the loop variable capture (`tt := tt`) is no longer needed.

### Named Type vs Anonymous Struct

```go
// PREFER: Anonymous struct for simple tests
tests := []struct {
    name    string
    input   string
    want    int
    wantErr bool
}{ ... }

// USE named type only when:
// 1. Struct is reused across multiple test functions
// 2. Complex setup requires methods on the test case
type parseTestCase struct {
    name    string
    input   string
    setup   func(t *testing.T) *Parser
    verify  func(t *testing.T, result *Result)
}
```

---

## Test Helper Patterns

### Assertion Helpers

```go
func assertNoError(t *testing.T, err error) {
    t.Helper()
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
}

func assertEqual[T comparable](t *testing.T, got, want T) {
    t.Helper()
    if got != want {
        t.Errorf("got %v, want %v", got, want)
    }
}

func assertContains(t *testing.T, haystack, needle string) {
    t.Helper()
    if !strings.Contains(haystack, needle) {
        t.Errorf("expected %q to contain %q", haystack, needle)
    }
}
```

### must.SucceedT Pattern

```go
func SucceedT[T any](t *testing.T, val T, err error) T {
    t.Helper()
    if err != nil {
        t.Fatalf("expected success but got error: %v", err)
    }
    return val
}

// Usage
func TestSomething(t *testing.T) {
    user := must.SucceedT(t, repo.GetUser(ctx, userID))
}
```

### must vs assert: When to Use Which

In Go test code, `must` (fatal) and `assert` (non-fatal) serve different roles:

| Context | Use | Why |
|---------|-----|-----|
| `mustXxx` helper function | `must.SucceedT` / `must.ReturnT` | Fatal — function name says "must" |
| Setup/precondition in test body | `must.SucceedT` / `must.ReturnT` | Fatal — next lines depend on this |
| Checking the tested operation's outcome | `assert.ErrEqual(t, err, nil)` | Non-fatal — reports ALL failures |
| Need return value from fallible call | `must.ReturnT` | Fatal — no assert equivalent |

**Decision tree:**
1. Inside a `mustXxx` helper? → `must.SucceedT` / `must.ReturnT`
2. Next line needs this result? → `must.SucceedT` / `must.ReturnT`
3. Checking the outcome of the tested operation? → `assert.ErrEqual(t, err, nil)`
4. Need a return value? → `must.ReturnT`

```go
// Setup (fatal) — next lines depend on this
must.SucceedT(t, store.UpdateMetrics())
families := must.ReturnT(registry.Gather())(t)

// Assertion (non-fatal) — checking expected outcome
assert.ErrEqual(t, err, nil)
assert.Equal(t, len(families), 3)
```

**The rule: helper = must, assertion = assert.**

Note: For projects using shared test assertion libraries, `must` and `assert` may come from the organization's shared library. The same principle applies to any fatal vs non-fatal test helper pattern.

**Equal vs DeepEqual:**
- `Equal(t, actual, expected)` — for comparable types (int, string, bool), uses `==`
- `DeepEqual(t, "label", actual, expected)` — for slices/maps/structs, uses `reflect.DeepEqual`
- If type supports `==` → `Equal`. If not → `DeepEqual`. Reviewers flag `DeepEqual` used on comparable types.

### Setup/Teardown with t.Cleanup

```go
func setupTestDB(t *testing.T) *sql.DB {
    t.Helper()

    db, err := sql.Open("sqlite3", ":memory:")
    assertNoError(t, err)

    err = runMigrations(db)
    assertNoError(t, err)

    t.Cleanup(func() {
        db.Close()
    })

    return db
}

// Usage - no defer needed
func TestUserRepository(t *testing.T) {
    db := setupTestDB(t)
    repo := NewUserRepository(db)
    // test repo methods
}
```

---

## Mocking Patterns

### Manual Mock with Function Fields and Call Tracking

```go
type EmailSender interface {
    SendEmail(ctx context.Context, to, subject, body string) error
}

type MockEmailSender struct {
    SendEmailFunc func(ctx context.Context, to, subject, body string) error
    calls         []EmailCall
    mu            sync.Mutex
}

type EmailCall struct {
    To      string
    Subject string
    Body    string
}

func (m *MockEmailSender) SendEmail(ctx context.Context, to, subject, body string) error {
    m.mu.Lock()
    m.calls = append(m.calls, EmailCall{To: to, Subject: subject, Body: body})
    m.mu.Unlock()

    if m.SendEmailFunc != nil {
        return m.SendEmailFunc(ctx, to, subject, body)
    }
    return nil
}

func (m *MockEmailSender) GetCalls() []EmailCall {
    m.mu.Lock()
    defer m.mu.Unlock()
    return append([]EmailCall{}, m.calls...)
}

// Usage
func TestNotificationService(t *testing.T) {
    mockSender := &MockEmailSender{
        SendEmailFunc: func(ctx context.Context, to, subject, body string) error {
            if to == "invalid@example.com" {
                return errors.New("invalid email")
            }
            return nil
        },
    }

    service := NewNotificationService(mockSender)
    err := service.NotifyUser(context.Background(), "user@example.com", "Test")
    assertNoError(t, err)

    calls := mockSender.GetCalls()
    if len(calls) != 1 {
        t.Fatalf("expected 1 call, got %d", len(calls))
    }
    assertEqual(t, calls[0].To, "user@example.com")
}
```

### Mock with Expectation Assertions

```go
type MockStorage struct {
    events   []Event
    getCalls []EventFilter
}

func (m *MockStorage) StoreEvent(e Event) error {
    m.events = append(m.events, e)
    return nil
}

func (m *MockStorage) ExpectEvents(t *testing.T, expected ...Event) {
    t.Helper()
    if !reflect.DeepEqual(m.events, expected) {
        t.Errorf("events mismatch:\ngot:  %+v\nwant: %+v", m.events, expected)
    }
}
```

---

## Interface Test Deduplication

When testing multiple implementations of the same interface:

```go
type BackingStore interface {
    Get(key string) ([]byte, error)
    Set(key string, value []byte) error
}

// Shared test logic for any implementation
func testBackingStoreOperations(t *testing.T, store BackingStore) {
    t.Helper()

    err := store.Set("key1", []byte("value1"))
    assertNoError(t, err)

    val, err := store.Get("key1")
    assertNoError(t, err)
    assertEqual(t, string(val), "value1")
}

// Run against all implementations
func testWithEachBackingStore(t *testing.T, action func(*testing.T, BackingStore)) {
    t.Run("with file store", func(t *testing.T) {
        action(t, newTestFileBackingStore(t))
    })
    t.Run("with memory store", func(t *testing.T) {
        action(t, newTestMemoryBackingStore(t))
    })
}

// Usage
func TestBackingStore(t *testing.T) {
    testWithEachBackingStore(t, testBackingStoreOperations)
}
```

---

## Context in Tests

```go
// Go 1.24+: Use t.Context() for automatic cancellation when test ends
func TestWithContext(t *testing.T) {
    ctx := t.Context()
    result, err := longRunningOperation(ctx)
    assertNoError(t, err)
}

// Pre-1.24: Manual context with timeout
func TestEventProcessing(t *testing.T) {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    result, err := processEvent(ctx, testEvent)
    assertNoError(t, err)
    assertEqual(t, result.Status, "processed")
}
```

---

## Coverage Guidelines

1. **Critical paths**: >80% coverage required
2. **Error paths**: Must be tested, not just happy paths
3. **Edge cases**: Empty inputs, nil values, boundary values
4. **Do not chase 100%**: Simple getters and generated code rarely need tests
