# gopls MCP Server Integration

Workspace-aware Go intelligence. Use when gopls MCP is configured (`.mcp.json` with gopls entry, project has `go.mod`).

## Available Tools

| Tool | Purpose | When |
|------|---------|------|
| `go_workspace` | Workspace structure | **Session start** — MUST use first |
| `go_vulncheck` | Security vulnerabilities | After `go_workspace`; after dependency changes |
| `go_search` | Fuzzy symbol search | Finding types, functions, variables |
| `go_file_context` | Intra-package dependencies | **After reading any .go file** — MUST use |
| `go_package_api` | Package public API | Understanding deps or other packages |
| `go_symbol_references` | All symbol references | **Before modifying any symbol** — MUST use |
| `go_diagnostics` | Build/analysis errors | **After every code edit** — MUST use |

## Read Workflow

1. `go_workspace` — understand structure
2. `go_search({"query": "Server"})` — find symbols
3. `go_file_context({"file": "/path/to/server.go"})` — after reading any file
4. `go_package_api({"packagePaths": ["example.com/internal/storage"]})` — inspect APIs

## Edit Workflow

1. Follow Read Workflow to understand code
2. `go_symbol_references` before modifying any symbol
3. Make edits including reference updates
4. `go_diagnostics({"files": ["/path/to/server.go"]})` after every edit
5. Fix errors, re-run diagnostics
6. `go_vulncheck` if go.mod changed
7. Run tests only after diagnostics clean

## Fallback (no gopls MCP)

- `LSP` tool for goToDefinition, findReferences, hover, documentSymbol
- `Grep` for symbol searching
- `Bash` with `go build`, `go vet`, `go test` for diagnostics
