# Go Dead Code Analysis

Tool and decision guidance for dead code detection. Load for unused function cleanup or refactoring prep.

## deadcode — Primary Tool

`golang.org/x/tools/cmd/deadcode` uses SSA whole-program analysis with Rapid Type Analysis to resolve interface dispatch, method values, and reflection — none of which syntax-level tools handle.

### Install and Run

```bash
go install golang.org/x/tools/cmd/deadcode@latest

deadcode ./...                    # Text output
deadcode -json ./...              # Structured JSON
deadcode ./internal/processor/... # Filter to package
```

### What It Catches

- **Unexported unreachable functions**: not reachable from any `main` entry point
- **Exported functions with no callers**: no `main` entry reaches them — candidates for removal/unexport

### Why SSA Beats Syntax Analysis

Syntax tools (grep, tree-sitter, gopls references) cannot resolve:
- **Interface dispatch**: `handler.Process(x)` — target depends on runtime types
- **Method values**: `f := obj.Method; f()` — call through variable
- **Reflection**: `reflect.ValueOf(x).MethodByName("Foo").Call(...)` — invisible to text search

### Known False Positives

**Test helpers**: Functions called only from `_test.go` are flagged because deadcode analyzes `main` entry points, not test binaries. Verify before removing:

```bash
grep -rn "setupTestDB" --include="*_test.go"
deadcode -test ./...  # Include test binary entry points
```

**Exported API surface**: Libraries expose functions for external consumers deadcode cannot see. Focus on unexported functions.

### Integration with VERIFY Phase

Run after `go vet` during Phase 4 when the task involves dead code audits, cleanup, code review, refactoring prep, or post-migration cleanup. Not mandatory for every task.

```bash
go vet ./...
deadcode ./...
go test ./...
```

## Why Not Tree-Sitter for Go?

A/B tested across 5 tests on 2 repos: tree-sitter call graph added no measurable value over grep + file reading for dead code detection, code audits, or PR reviews. `deadcode` + `gopls` + grep cover all Go use cases.

For impact analysis ("what calls this function?"), use gopls `go_symbol_references` or grep.
