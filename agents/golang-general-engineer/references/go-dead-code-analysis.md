# Go Dead Code Analysis

Tools and decision guidance for dead code detection and call-graph navigation in Go codebases. Load when the task involves finding unused functions, cleanup, refactoring prep, or understanding call chains.

## deadcode — Primary Tool for Dead Code Detection

`golang.org/x/tools/cmd/deadcode` is the official Go team tool for finding unreachable functions. It uses SSA (Static Single Assignment) whole-program analysis with Rapid Type Analysis to resolve interface dispatch, method values, and reflection — none of which syntax-level tools can handle.

### Install and Run

```bash
go install golang.org/x/tools/cmd/deadcode@latest

# Text output — one line per unreachable function
deadcode ./...

# Structured output — machine-parseable JSON
deadcode -json ./...

# Filter to a specific package
deadcode ./internal/processor/...
```

### What It Catches

- **Unexported unreachable functions**: functions not reachable from any `main` package entry point through the whole-program call graph.
- **Exported functions with no callers**: exported functions that no `main` package entry point reaches. These are candidates for removal or unexport.

### Why SSA Beats Syntax Analysis

Syntax-level tools (grep, tree-sitter, gopls references) find textual call sites. They cannot resolve:

- **Interface dispatch**: `handler.Process(x)` calls whichever concrete type implements `Handler` — the actual target depends on runtime types, not source text.
- **Method values**: `f := obj.Method; f()` — the call to `Method` happens through the variable `f`, invisible to syntax search.
- **Reflection**: `reflect.ValueOf(x).MethodByName("Foo").Call(...)` — no syntax tool can resolve this.

deadcode's SSA analysis builds the complete call graph including these edges. A function that appears unused by grep may be reachable through an interface. A function that appears used by grep may actually be dead — the call site itself is unreachable.

### Known False Positives

**Test helpers**: deadcode analyzes reachability from `main` package entry points. Functions called only from `_test.go` files are not reachable from `main` — they are reachable from test binaries, which deadcode does not analyze. This is expected behavior, not a bug. When deadcode flags a function that is clearly a test helper (e.g., `setupTestDB`, `assertResponse`), verify by checking test file usage before removing:

```bash
# Confirm the function is used in tests before dismissing the finding
grep -rn "setupTestDB" --include="*_test.go"
```

**Exported API surface**: Libraries expose exported functions for external consumers. deadcode cannot see callers outside the module. For library code, focus deadcode findings on unexported functions.

### Integration with VERIFY Phase

Run deadcode after `go vet` during Phase 4 (VERIFY) when the task involves:

- Dead code audits or cleanup tasks
- Code review where unused functions are a concern
- Refactoring prep — identifying what is safe to remove
- Post-migration cleanup after removing a feature or dependency

deadcode is not mandatory for every task. It adds value when the question is "what can I safely delete?" — not when the question is "does this build and pass tests?"

```bash
# VERIFY phase sequence for cleanup tasks
go vet ./...
deadcode ./...
go test -v -race ./...
```

## Why Not Tree-Sitter for Go?

Tree-sitter parses syntax, not semantics. It cannot resolve interface dispatch, method values, or reflection. In Go codebases that use interfaces (which is most of them), syntax-level call graph tools produce false positives: functions called through interfaces appear to have zero callers because the call site references the interface method, not the concrete implementation.

A/B tested across 5 tests on 2 repos (hermes, log-router): tree-sitter call graph added no measurable value over grep + file reading for dead code detection, code audits, PR reviews, or impact analysis. `deadcode` + `gopls` + grep cover all Go use cases with equal or better results.

For **impact analysis** ("what calls this function?"), use `gopls` MCP's `go_symbol_references` tool or grep. Both outperformed tree-sitter call graphs in blind testing.
