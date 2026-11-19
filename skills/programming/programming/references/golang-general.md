---
description: "General Go development: features, debugging, code review, performance. Modern Go 1.26+ (and 1.27 when go.mod allows) rules, gopls order, five-phase workflow."
type: reference
---

# General Go Development

Rules and workflow for idiomatic, production-ready Go (Go 1.26+, plus Go 1.27
idioms when `go.mod` allows them). Covers features, debugging, code review, and
performance. Task-specific depth lives in `go/` (testing, concurrency, errors,
review, SAPCC, quality gate, Google style).

Not for: "go" used as a verb ("go ahead", "go fix this"); Kotlin coroutine work
(load `kotlin-general.md`).

## Hard rules

- **Write modern Go.** Before you write or edit Go code, load
  [go-modern-code.md](golang-general/go-modern-code.md) and follow it. Code that
  builds and passes tests still fails review when it uses the old idioms listed
  there. The rules most often missed:
  - A `// Package x ...` comment in every package (including `main`) and a doc
    comment on every exported name, starting with the name.
  - `os.Exit` skips defers: `main` calls `os.Exit(run())` and `run` holds the defers.
  - Tests: `t.Context()`, never `context.Background()`; `synctest.Test` for
    anything with goroutines or time, never `time.Sleep` (import path in
    go-modern-code.md section 10).
  - `wg.Go(f)`, not `wg.Add(1)` + `go` + `defer wg.Done()`.
  - `errors.Is` for sentinels (never `==`), `errors.AsType[*T](err)` for types
    (never `errors.As` on 1.26+), typed driver errors (never string matching).
  - Standard `uuid` package on 1.27, never hand-rolled UUIDs; `slices.SortFunc`
    + `cmp.Or`, never `sort.Slice`; `slog.DiscardHandler`.
  - Let `http.ServeMux` answer 405 (it sets `Allow`); after a failed `Shutdown`,
    call `Close`.
- **Precedence over older examples.** Some `go/` deep-reference examples still
  show `wg.Add(1)` + `go`, `context.Background()` in tests, or `interface{}`.
  When `go.mod` allows the modern form, the rules above and
  go-modern-code.md win; those examples show the pattern, not the idiom.
- **Format with `gofmt -w`.** Non-negotiable: run it on every edited `.go` file.
- **After a clean `go build`, run `go vet`** to catch subtle issues.
- **Errors carry useful context.** Return an error unchanged when it is already
  clear. Add actionable context when it helps. Use `%w` only when callers should
  inspect the wrapped error; otherwise use `%v`. This Google-guide decision
  takes precedence over the blanket "always `%w`" wording in
  `go/error-handling.md`.
- **Use `any`, not `interface{}`** (Go 1.18+).
- **Pre-handoff checklist.** Before you report done, run the command sequence
  and tick the checklist in go-modern-code.md section 12. Without tools, check
  the code against each checklist line.
- **Show complete command output.** Paste actual `go test` output instead of
  "tests pass".
- **Table-driven tests** when many cases share similar test logic; keep
  distinct scenarios in separate tests when that is clearer.
- **Version-aware code.** Detect the Go version from `go.mod` and use only
  features available in that version or earlier.
- **Verify library behavior from source.** When a change depends on specific
  behavior of an imported library (commit semantics, retry logic, connection
  lifecycle, error types), read the library source in GOMODCACHE or use
  `go doc`, not protocol-level reasoning from training data. The question is not
  "how does Kafka work?" but "how does segmentio/kafka-go v0.4.47 implement this
  method?" Use `cat $(go env GOMODCACHE)/path/to/lib@version/file.go`.
- **gopls MCP first.** In a Go workspace with gopls MCP available, use its tools
  in this order, because they answer with type information grep cannot:
  1. `go_workspace` at session start, to detect the workspace
  2. `go_file_context` after the first read of any `.go` file
  3. `go_symbol_references` before modifying a symbol definition
  4. `go_diagnostics` after each edit to `.go` files
  5. `go_vulncheck` after any `go.mod` dependency change

  Fall back to the LSP tool or grep only when gopls MCP is not configured.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| go_workspace, go_diagnostics, go_symbol_references, GOMODCACHE, stale binary, stat, deadcode, render-time output, tree-sitter, cleanup, refactoring prep | [go-verification-workflow.md](golang-general/go-verification-workflow.md) | gopls MCP ordering, library-source verification, rebuilt-binary stat check, /tmp reproducer rule, deadcode false-positive fixes, hermes/log-router A/B result |
| Any task that writes or edits Go code: new package, handler, CLI, worker pool, iterator, repository, tests | [go-modern-code.md](golang-general/go-modern-code.md) | Measured failure patterns with before/after code: doc comments, errors, context, `wg.Go`, bounded pools, HTTP serve/shutdown, `uuid`, CLI flags, iterators, synctest, database/sql, pre-handoff checklist |
| interface{}, any, omitzero, omitempty, wg.Go, b.Loop, t.Context, errors.AsType, new(val), SplitSeq, uuid, CutLast, generic methods, json/v2, go.mod version, undefined:, requires go1.N | [go-version-idioms.md](golang-general/go-version-idioms.md) | Go 1.18–1.27 idiom replacement table, hard gates with fixes, error-message-to-version map |
| Testing, concurrency, error handling, review, SAPCC, `make check`, Google style | `go/*.md` (see the Go table in `SKILL.md`) | Task-specific deep references |
| Hard-gate framework | [forbidden-patterns-template.md](../../../shared-patterns/forbidden-patterns-template.md) | Shared gate format |

## Workflow

Follow these phases for every Go task. Skipping phases is the dominant cause of
regressions and death-loop debugging.

### Phase 1: Discover

Call `go_workspace` first, because gopls must index the project before any other
MCP call returns meaningful data. Then call `go_file_context` on every `.go` file
before reading it, because a stale model of package dependencies leads to the
wrong edit location.

**Gate:** `go_workspace` returned workspace metadata, and `go_file_context`
results exist for all read files.

### Phase 2: Plan

Check `go.mod` for the Go version: `for range n` on a project pinned to Go 1.21
breaks the build, and `uuid.New` on a project pinned to 1.26 fails with
`requires go1.27 or later`. Identify the failing test or compilation error,
because jumping to implementation before reproducing the failure almost always
fixes the wrong thing.

**Gate:** Go version identified; reproduction steps or failing test captured.

### Phase 3: Implement

Apply minimum-viable edits; over-engineering beyond the request is the most
common Go review rejection. Follow the Google guide's error decision: add useful
context, avoid empty wrappers such as `fmt.Errorf("failed: %w", err)`, and
expose an error chain with `%w` only when that is part of the API.

**Gate:** `go_diagnostics` returns zero errors for edited files.

### Phase 4: Verify

- Run `gofmt -w` on every edited file; unformatted Go fails CI before any logic
  review runs.
- Run `go fix -diff ./...` (Go 1.26+) and apply what it reports; modernizer
  findings mean an outdated idiom shipped.
- Run `go test -race ./...` and paste the actual output. Summarizing "tests
  pass" without evidence is the dominant rationalization that ships broken code.
- For cleanup, review, or refactoring tasks, run `deadcode ./...` after
  `go vet` to find unreachable functions. See
  [go-verification-workflow.md](golang-general/go-verification-workflow.md) for
  usage and false-positive guidance.

**Render-time fixes need render-time verification.** Bugs that show at output
render time (table layout, template output, log formatting) are not caught by
compile + `go test`. Build a small standalone reproducer under `/tmp` with
realistic fake data, run it, and compare before/after output byte for byte. Use
the module cache, not vendor pollution. No backend credentials needed.

**Rebuilt binary check.** When testing a fix to a CLI binary, confirm the binary
you run matches the fix. Compare `stat -f %m ./bin/foo` (BSD; `stat -c %Y` on
Linux) against the fix commit time, or compare the embedded version SHA against
`git rev-parse HEAD`. A stale binary silently passes tests against the old,
broken code path.

**Gate:** `go test ./...` output shown in full, `go vet ./...` clean. For
render-time fixes: reproducer output shown with a before/after diff.

### Phase 5: Report

Report exit status with real command output. No "should work": either the gates
passed or they didn't.

**Gate:** the completion report includes command output, not summaries.

## Preferred patterns

See [go-version-idioms.md](golang-general/go-version-idioms.md) for the modern
idiom replacement table, hard gates with fixes, and the error-message-to-version
map.

## Error handling

Standard Go failure modes (goroutine leaks, races, nil pointers, context
deadlines) are base-model knowledge: diagnose with `go vet`, `-race`, and
`go_diagnostics`. Verification workflows and gopls fallback guidance live in
[go-verification-workflow.md](golang-general/go-verification-workflow.md).
