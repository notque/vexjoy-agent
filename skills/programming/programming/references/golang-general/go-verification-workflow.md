# Go Verification Workflow

Toolkit-specific verification: gopls MCP ordering, library-source checks, rebuilt-binary and render-time verification, dead-code analysis. Loaded for any Go edit, review, or cleanup task.

## gopls MCP Tool Order

Available when `.mcp.json` has a gopls entry and the project has `go.mod`.

| Tool | When (mandatory ordering) |
|------|---------------------------|
| `go_workspace` | First call of every Go session |
| `go_vulncheck` | After `go_workspace` confirms a Go workspace; again after dependency changes |
| `go_file_context` | After reading any Go file for the first time |
| `go_symbol_references` | Before modifying any symbol definition |
| `go_diagnostics` | After every code edit; re-run after applying fixes |
| `go_search` / `go_package_api` | Fuzzy symbol search / third-party package API inspection, as needed |

```
go_symbol_references({"file": "/path/to/server.go", "symbol": "Server.Run"})
go_diagnostics({"files": ["/path/to/server.go"]})
```

Fallback without gopls: `LSP` tool (goToDefinition, findReferences), `Grep` for symbols, `go build` / `go vet` / `go test` for diagnostics. gopls understands types and references where grep sees text — use `go_symbol_references` before renaming.

## Verify the Library, Not the Protocol

**What it looks like**: "Kafka consumer groups will rebalance after a member leaves, so this is safe."
**Why wrong**: Protocol-level behavior and library-level behavior are not the same. LLMs reason from training data about protocols, not from reading the specific library version in go.mod.
**Do instead**: Read the library source in GOMODCACHE. The question is not "how does the protocol work?" but "how does THIS library version implement THIS method?"

```bash
cat $(go env GOMODCACHE)/path/to/lib@version/file.go
```

## Rebuilt Binary Check

When testing a fix to a CLI binary, confirm the binary you're running matches the fix. Check `stat -f %m ./bin/foo` (BSD stat; `stat -c %Y` on Linux) vs the fix commit time, or compare the embedded version SHA against `git rev-parse HEAD`. A stale binary silently passes tests against the old (broken) code path.

## Render-Time Fixes Need Render-Time Verification

Bugs that manifest at output-render time (table layout, template output, log formatting) slip past compile + `go test`. Build a small standalone reproducer under `/tmp` with realistic fake data, run it, and compare before/after output byte-for-byte. Use the module cache rather than vendoring; backend creds stay unneeded.

## Pre-Handoff Command Sequence

Run in this order on every Go change; each must be clean before you report done. Paste the real output.

```bash
gofmt -l .                                               # prints nothing when formatted; fix with gofmt -w
go vet ./...
go fix -diff ./...                                       # Go 1.26+ modernizers; apply with go fix ./...
go run honnef.co/go/tools/cmd/staticcheck@latest ./...   # no global install
go test -race -count=1 ./...                             # -count=1 defeats the test cache
```

A `golangci-lint` binary built with an older Go refuses newer modules: `the Go language version (go1.26) used to build golangci-lint is lower than the targeted Go version (1.27)`. Use `go run` of staticcheck instead, or rebuild golangci-lint with the current toolchain, and say which you ran.

## Dead Code Analysis with deadcode

`golang.org/x/tools/cmd/deadcode` (SSA whole-program analysis) resolves interface dispatch, method values, and reflection — edges syntax tools miss. Run it during VERIFY for cleanup, review, or refactoring-prep tasks; skip it when the question is only "does this build and pass tests?"

```bash
# no install needed; runs the pinned tool from the module cache
go run golang.org/x/tools/cmd/deadcode@latest ./...          # one line per unreachable function
go run golang.org/x/tools/cmd/deadcode@latest -json ./...    # machine-parseable
go run golang.org/x/tools/cmd/deadcode@latest -test ./...    # include test binary entry points

# VERIFY sequence for cleanup tasks
go vet ./... && go run golang.org/x/tools/cmd/deadcode@latest ./... && go test ./...
```

Known false positives, with fixes:

| Finding | Cause | Fix |
|---------|-------|-----|
| Test helpers flagged (`setupTestDB`, `assertResponse`) | Reachability is computed from `main` entry points; test binaries are excluded by default | `grep -rn "<name>" --include="*_test.go"` to confirm usage, or run `deadcode -test ./...` |
| Exported library API flagged | deadcode cannot see callers outside the module | For library code, act only on unexported findings |

**Tooling decision (measured)**: A/B tested across 5 tests on 2 repos (hermes, log-router): tree-sitter call graph added no measurable value over grep + file reading for dead code detection, code audits, PR reviews, or impact analysis. `deadcode` + `gopls` + grep cover all Go use cases with equal or better results. For impact analysis ("what calls this function?"), use `go_symbol_references` or grep — both outperformed tree-sitter call graphs in blind testing.
