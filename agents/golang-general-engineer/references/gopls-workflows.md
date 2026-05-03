# gopls MCP Server Integration

The gopls MCP server provides workspace-aware Go intelligence. When working in a Go workspace, these tools give you capabilities beyond generic file operations. Loaded when working in a Go workspace with gopls configured.

## Available gopls MCP Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `go_workspace` | Learn workspace structure (module, workspace, GOPATH) | **Start of every Go session** — MUST use first |
| `go_vulncheck` | Identify security vulnerabilities | After `go_workspace` confirms Go workspace; after adding/updating dependencies |
| `go_search` | Fuzzy symbol search across workspace | Finding types, functions, variables by name |
| `go_file_context` | Show intra-package dependencies for a file | **After reading any Go file for the first time** — MUST use |
| `go_package_api` | Show a package's public API | Understanding third-party deps or other packages |
| `go_symbol_references` | Find all references to a symbol | **Before modifying any symbol definition** — MUST use |
| `go_diagnostics` | Report build/analysis errors for files | **After every code edit** — MUST use |

## gopls Read Workflow

Follow this when understanding Go code:

1. **Understand workspace layout**: Use `go_workspace` to learn the overall structure
2. **Find relevant symbols**: Use `go_search` for fuzzy symbol search
   ```
   go_search({"query": "Server"})
   ```
3. **Understand file dependencies**: After reading any Go file, use `go_file_context`
   ```
   go_file_context({"file": "/path/to/server.go"})
   ```
4. **Understand package APIs**: Use `go_package_api` for external package inspection
   ```
   go_package_api({"packagePaths": ["example.com/internal/storage"]})
   ```

## gopls Edit Workflow

Follow this iterative cycle when modifying Go code:

1. **Read first**: Follow the Read Workflow to understand the code
2. **Find references**: Before modifying ANY symbol, use `go_symbol_references`
   ```
   go_symbol_references({"file": "/path/to/server.go", "symbol": "Server.Run"})
   ```
3. **Make edits**: Apply all planned changes including reference updates
4. **Check diagnostics**: After EVERY edit, call `go_diagnostics`
   ```
   go_diagnostics({"files": ["/path/to/server.go"]})
   ```
5. **Fix errors**: Apply suggested quick fixes if correct, then re-run `go_diagnostics`
6. **Check vulnerabilities**: If go.mod changed, run `go_vulncheck({"pattern": "./..."})`
7. **Run tests**: Only after `go_diagnostics` reports no errors

## gopls Tool Availability

gopls MCP tools are only available when:
- The gopls MCP server is configured (`.mcp.json` with gopls entry)
- You are working in a Go workspace (has `go.mod`)

If gopls tools are not available, fall back to:
- `LSP` tool for goToDefinition, findReferences, hover, documentSymbol
- `Grep` for symbol searching
- `Bash` with `go build`, `go vet`, `go test` for diagnostics
