# Go Benchmarks and Concurrency Testing Reference

Detailed examples for benchmarks, synctest, and race detection. See SKILL.md for methodology.

---

## Benchmarks with b.Loop() (Go 1.24+)

### Why b.Loop() Over b.N

The old `for i := 0; i < b.N; i++` pattern is deprecated. Use `b.Loop()` because:

1. **Prevents Dead Code Elimination**: Compiler detects `b.Loop()` and prevents inlining
2. **Automatic Timer Management**: Integrated `b.ResetTimer()` at start, `b.StopTimer()` at end
3. **More Accurate Results**: Prevents compiler optimizations that make benchmarks artificially fast
4. **Faster Execution**: Single-pass ramp-up instead of multiple function calls with ramping b.N

### Complete Benchmark Example

```go
func BenchmarkStringBuilder(b *testing.B) {
    words := []string{"hello", "world", "from", "go", "benchmark"}

    b.Run("strings.Builder", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() {
            var sb strings.Builder
            for _, word := range words {
                sb.WriteString(word)
                sb.WriteString(" ")
            }
            _ = sb.String()
        }
    })

    b.Run("bytes.Buffer", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() {
            var buf bytes.Buffer
            for _, word := range words {
                buf.WriteString(word)
                buf.WriteString(" ")
            }
            _ = buf.String()
        }
    })

    b.Run("string concatenation", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() {
            result := ""
            for _, word := range words {
                result += word + " "
            }
            _ = result
        }
    })
}
```

### Benchstat Comparison Workflow

```bash
# Install benchstat
go install golang.org/x/perf/cmd/benchstat@latest

# Baseline measurements (run 10 times for statistical significance)
go test -bench=. -count=10 ./... > old.txt

# Make changes...

# New measurements
go test -bench=. -count=10 ./... > new.txt

# Compare
benchstat old.txt new.txt
```

### Running Benchmarks

```bash
go test -bench=. -benchmem ./...                    # All benchmarks with memory
go test -bench=BenchmarkStringBuilder -benchmem ./...  # Specific benchmark
go test -cpuprofile=cpu.prof -memprofile=mem.prof -bench=. ./...  # With profiling
```

---

## synctest: Deterministic Concurrency Testing (Go 1.25+)

The `testing/synctest` package provides deterministic testing for concurrent code with virtual time.

### Core Concepts

**Bubble**: An isolated execution context with its own virtualized clock.
- All goroutines started within the bubble are part of it
- The clock only advances when all goroutines are "durably blocked"
- Initial time: midnight UTC 2000-01-01

**Durably Blocked**: A goroutine is durably blocked when:
- It is blocked (channel receive, `time.Sleep`, etc.)
- Can only be unblocked by another goroutine in the same bubble
- Cannot be unblocked by external events

### Key API

```go
import "testing/synctest"

// Execute function in bubble with virtual time
synctest.Test(t, func(t *testing.T) {
    // Test code with virtual time
})

// Wait for all goroutines to be durably blocked
synctest.Wait()
```

### Example: Testing Timeouts

```go
func TestTimeout(t *testing.T) {
    synctest.Test(t, func(t *testing.T) {
        done := make(chan bool)
        go func() {
            time.Sleep(5 * time.Second)  // Instant with virtual time
            done <- true
        }()

        ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
        defer cancel()

        select {
        case <-done:
            // Completed in "5 seconds" (instant in test)
        case <-ctx.Done():
            t.Fatal("timeout waiting for goroutine")
        }
    })
}
```

### Benefits
1. **Fast**: Virtual time means no waiting for real delays
2. **Reliable**: Deterministic execution eliminates flaky tests
3. **Safe**: Automatic deadlock detection
4. **Simple**: No manual synchronization for time-based code

### Limitations
- Cannot recognize goroutines blocked on network or I/O
- Network testing requires fake implementations (e.g., `net.Pipe()`)
- Generally provide mock implementations of network clients/servers

---

## Race Detection Patterns

### Always Run With Race Detector

```bash
go test -race -count=1 -v ./...           # Full suite
go test -race -run TestConcurrentOp ./...  # Specific test
```

### Common Race Condition Fix

```go
// BAD: Race condition
func TestConcurrent(t *testing.T) {
    var count int
    for i := 0; i < 100; i++ {
        go func() {
            count++  // RACE!
        }()
    }
}

// GOOD: Use atomic operations
func TestConcurrent(t *testing.T) {
    var count atomic.Int64
    var wg sync.WaitGroup

    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            count.Add(1)
        }()
    }

    wg.Wait()
    assertEqual(t, count.Load(), int64(100))
}
```

### Mock Thread Safety

When mocks are used in concurrent tests, protect shared state:

```go
type MockStore struct {
    mu    sync.Mutex
    calls []string
}

func (m *MockStore) Get(key string) ([]byte, error) {
    m.mu.Lock()
    m.calls = append(m.calls, key)
    m.mu.Unlock()
    return nil, nil
}

func (m *MockStore) GetCalls() []string {
    m.mu.Lock()
    defer m.mu.Unlock()
    return append([]string{}, m.calls...)
}
```
