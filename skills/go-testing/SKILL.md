---
name: go-testing
description: |
  Go testing patterns and methodology: table-driven tests, t.Run subtests,
  t.Helper helpers, mocking interfaces, benchmarks, race detection, and
  synctest. Use when writing new Go tests, modifying existing tests, adding
  coverage, fixing failing tests, writing benchmarks, or creating mocks.
  Triggered by "go test", "_test.go", "table-driven", "t.Run", "benchmark",
  "mock", "race detection", "test coverage". Do NOT use for non-Go testing
  (use test-driven-development instead), debugging test failures (use
  systematic-debugging), or general Go development without test focus (use
  golang-general-engineer directly).
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
agent: golang-general-engineer
command: /go-testing
routing:
  triggers:
    - go test
    - Go test
    - "*_test.go"
    - testing
    - table-driven
    - t.Run
    - t.Helper
    - benchmark
    - mock
    - test coverage
    - race detection
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
  force_routing: true
---

# Go Testing Skill

## Operator Context

This skill operates as an operator for Go testing workflows, configuring Claude's behavior for idiomatic, thorough Go test development. It implements the **Pattern Library** architectural pattern -- applying canonical Go testing patterns (table-driven, subtests, helpers, mocking) with **Domain Intelligence** from the Go standard library's testing conventions.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before writing tests
- **Over-Engineering Prevention**: Write only the tests needed. No speculative coverage, no "while I'm here" test additions
- **Table-Driven Tests Required**: Multiple related cases MUST use table-driven pattern with `t.Run`
- **t.Helper() Required**: Every test helper function MUST call `t.Helper()` as its first line
- **Show Test Output**: Always show actual `go test` output. Never summarize as "tests pass"
- **Race Detector**: Run `go test -race` when testing concurrent code
- **Black-Box Testing**: Prefer `package_test` (external test package) over `package` (internal)

### Default Behaviors (ON unless disabled)
- **Parallel Execution**: Use `t.Parallel()` for independent tests by default
- **t.Cleanup Over defer**: Prefer `t.Cleanup()` for resource management in test helpers
- **t.Context()**: Use `t.Context()` (Go 1.24+) for context-aware tests
- **b.Loop()**: Use `b.Loop()` (Go 1.24+) instead of `for i := 0; i < b.N; i++` for benchmarks
- **gopls Diagnostics**: After editing test files, use `go_diagnostics` to catch errors before running tests
- **Error Path Testing**: Test error conditions, not just happy paths
- **Coverage Check**: Run `-coverprofile` and verify critical paths have >80% coverage
- **Cleanup Verification**: Each test must clean up after itself (no test pollution)

### Optional Behaviors (OFF unless enabled)
- **synctest Usage**: Use `testing/synctest` (Go 1.25+) for deterministic concurrency testing
- **Benchmark Comparison**: Use `benchstat` for before/after performance comparisons
- **Coverage HTML Report**: Generate and open HTML coverage visualization
- **Interface Deduplication**: Test multiple interface implementations with shared test functions

## Available Scripts

- **`scripts/gen-table-test.sh`** — Scaffold a table-driven test file for a Go function. Run `bash scripts/gen-table-test.sh --help` for options.
- **`scripts/bench-compare.sh`** — Run Go benchmarks with optional benchstat comparison. Run `bash scripts/bench-compare.sh --help` for options.

## What This Skill CAN Do
- Write idiomatic table-driven tests with `t.Run` subtests
- Create test helpers with proper `t.Helper()` marking
- Build manual mock implementations for interfaces
- Write benchmarks using modern `b.Loop()` pattern
- Set up parallel tests with proper variable capture
- Guide race detection and concurrent test patterns

## What This Skill CANNOT Do
- Debug failing tests (use `systematic-debugging` instead)
- Write non-Go tests (use `test-driven-development` instead)
- Perform general Go development (use `golang-general-engineer` directly)
- Generate code from mocking frameworks (manual mocks preferred in Go)
- Optimize performance without test focus (use performance profiling tools)

---

## Instructions

### Phase 1: UNDERSTAND Test Requirements

**Goal**: Determine what needs testing and the appropriate test strategy.

**Step 1: Identify test scope**
- What function/method/package is being tested?
- Is this a new test, modification, or coverage gap?
- Are there existing tests to follow as patterns?

**Step 2: Choose test type**

| Need | Test Type | Pattern |
|------|-----------|---------|
| Multiple input/output cases | Table-driven unit test | `[]struct` + `t.Run` |
| Single specific behavior | Focused unit test | Standard `TestXxx` |
| Cross-component interaction | Integration test | Setup/teardown helpers |
| Performance measurement | Benchmark | `b.Loop()` with `b.ReportAllocs()` |
| API usage documentation | Example test | `ExampleXxx` functions |

**Step 3: Verify test file structure**

```go
package mypackage_test  // Black-box testing (preferred)

import (
    "testing"
    "mymodule/mypackage"
)

// Order: Unit tests, Integration tests, Benchmarks, Examples
```

**Gate**: Test scope, type, and file location identified. Proceed only when gate passes.

### Phase 2: WRITE Tests

**Goal**: Implement tests following Go idioms.

**Step 1: Table-driven tests for multiple cases**

Every function with more than one test case MUST use table-driven pattern:

```go
func TestParseConfig(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    Config
        wantErr bool
    }{
        {
            name:  "valid YAML",
            input: `key: value`,
            want:  Config{Key: "value"},
        },
        {
            name:    "invalid syntax",
            input:   `{{{`,
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseConfig(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("ParseConfig() error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if !tt.wantErr && got != tt.want {
                t.Errorf("ParseConfig() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

**Step 2: Test helpers with t.Helper()**

```go
func assertEqual[T comparable](t *testing.T, got, want T) {
    t.Helper()  // MUST be first line
    if got != want {
        t.Errorf("got %v, want %v", got, want)
    }
}
```

**Step 3: Mocking interfaces**

Use manual mocks with function fields for flexible per-test behavior:

```go
type MockStore struct {
    GetFunc func(key string) ([]byte, error)
}

func (m *MockStore) Get(key string) ([]byte, error) {
    if m.GetFunc != nil {
        return m.GetFunc(key)
    }
    return nil, nil
}
```

See `references/go-test-patterns.md` for complete mock patterns with call tracking.

**Step 4: Parallel tests**

```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel()
        // test body (use tt directly in Go 1.22+)
    })
}
```

**Gate**: Tests follow table-driven pattern, helpers use `t.Helper()`, mocks use function fields. Proceed only when gate passes.

### Phase 3: RUN and Verify

**Goal**: Execute tests and confirm correctness.

**Step 1: Run tests**

```bash
# Standard run with verbose output
go test -v ./path/to/package/...

# With race detector (REQUIRED for concurrent code)
go test -race -v ./path/to/package/...

# With coverage
go test -coverprofile=coverage.out ./path/to/package/...
go tool cover -func=coverage.out
```

**Step 2: Verify results**
- All tests pass (show actual output)
- No race conditions detected
- Critical paths have >80% coverage
- Error paths are exercised

**Step 3: Run full suite**

```bash
go test ./...
```

Verify no regressions in other packages.

**Gate**: All tests pass, race detector clean, coverage adequate. Proceed only when gate passes.

### Phase 4: REVIEW Test Quality

**Goal**: Ensure tests are maintainable and complete.

**Checklist**:
- [ ] Table-driven tests for multiple cases?
- [ ] Test helpers marked with `t.Helper()`?
- [ ] Parallel execution where safe?
- [ ] Error conditions tested?
- [ ] Edge cases covered (empty, nil, boundary)?
- [ ] Cleanup performed (`t.Cleanup` or `defer`)?
- [ ] No test interdependencies?
- [ ] Race detector passes?

**Gate**: All checklist items satisfied. Tests are complete.

---

## Benchmark Guide

**Use `b.Loop()` (Go 1.24+) for all new benchmarks.** It prevents dead code elimination, manages timers automatically, and produces more accurate results.

```go
func BenchmarkProcess(b *testing.B) {
    b.ReportAllocs()
    for b.Loop() {
        _ = Process(input)
    }
}
```

Sub-benchmarks for comparison:

```go
func BenchmarkBuilder(b *testing.B) {
    b.Run("strings.Builder", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() { /* ... */ }
    })
    b.Run("bytes.Buffer", func(b *testing.B) {
        b.ReportAllocs()
        for b.Loop() { /* ... */ }
    })
}
```

Run: `go test -bench=. -benchmem ./...`

See `references/go-benchmark-and-concurrency.md` for benchstat comparison workflow and synctest patterns.

---

## Commands Reference

```bash
go test ./...                              # Run all tests
go test -v ./...                           # Verbose output
go test -race ./...                        # Race detector
go test -run TestMyFunc ./...              # Specific test
go test -run TestMyFunc/subtest ./...      # Specific subtest
go test -coverprofile=coverage.out ./...   # Coverage profile
go tool cover -func=coverage.out           # Coverage summary
go tool cover -html=coverage.out           # Coverage HTML
go test -bench=. -benchmem ./...           # Benchmarks
go test -short ./...                       # Skip long tests
go test -timeout 30s ./...                 # With timeout
go test -count=10 ./...                    # Detect flaky tests
```

---

## Error Handling

### Error: "test passes but shouldn't"
Cause: Test assertion is wrong or testing the wrong thing (tautological test)
Solution:
1. Verify test actually exercises the code under test
2. Temporarily break the implementation and confirm test fails
3. Check assertion compares meaningful values, not self-referential ones

### Error: "race detected during test"
Cause: Shared mutable state accessed from goroutines without synchronization
Solution:
1. Use `sync.Mutex` or `atomic` operations for shared state
2. Use channels for goroutine communication
3. Ensure mock call tracking uses mutex protection
4. See `references/go-benchmark-and-concurrency.md` for patterns

### Error: "test passes locally but fails in CI"
Cause: Environment dependency, timing assumption, or file path difference
Solution:
1. Use `t.TempDir()` instead of hardcoded paths
2. Use `t.Setenv()` for environment variables (auto-restored)
3. Replace `time.Sleep` with `synctest.Test` for timing-dependent tests
4. Check for platform-specific assumptions

---

## Anti-Patterns

### Anti-Pattern 1: Separate Functions for Related Cases
**What it looks like**: `TestParseValid`, `TestParseInvalid`, `TestParseEmpty` as separate functions
**Why wrong**: Duplicates setup, obscures the input-output relationship, harder to add cases
**Do instead**: One `TestParse` with table-driven cases and `t.Run` subtests

### Anti-Pattern 2: Missing t.Helper()
**What it looks like**: Test helper reports errors at the helper's line, not the caller's
**Why wrong**: Makes debugging test failures slow because error location is misleading
**Do instead**: Add `t.Helper()` as the first line of every test helper function

### Anti-Pattern 3: Testing Implementation Instead of Behavior
**What it looks like**: Asserting internal method calls, field values, or execution order
**Why wrong**: Breaks on every refactor even when behavior is unchanged
**Do instead**: Test observable behavior (return values, side effects, state changes)

### Anti-Pattern 4: Test Pollution via Shared State
**What it looks like**: Package-level variables modified by tests, test order matters
**Why wrong**: Tests become flaky, pass individually but fail together
**Do instead**: Create fresh state in each test. Use `t.Cleanup()` for teardown.

### Anti-Pattern 5: Hardcoded File Paths
**What it looks like**: `os.ReadFile("testdata/input.json")` without considering working directory
**Why wrong**: Breaks when test runs from different directory or in CI
**Do instead**: Use `t.TempDir()` for generated files, `os.Getwd()` + relative path for testdata

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization Core](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Anti-Rationalization Testing](../shared-patterns/anti-rationalization-testing.md) - Testing-specific rationalization prevention
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "One test case, no need for table-driven" | Will grow to multiple cases | Set up table-driven from the start |
| "t.Helper() is just cosmetic" | Wrong error location wastes debug time | Always add t.Helper() |
| "Tests pass, no need for -race" | Race conditions are silent until production | Run with -race for concurrent code |
| "Coverage is 80%, good enough" | What's in the uncovered 20%? | Check that critical paths are covered |
| "Mock is too complex to build" | Complex ≠ optional | Build the mock, track calls |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/go-test-patterns.md`: Full examples for table-driven tests, helpers, mocking, interface deduplication
- `${CLAUDE_SKILL_DIR}/references/go-benchmark-and-concurrency.md`: b.Loop() benchmarks, benchstat, synctest, race detection patterns
