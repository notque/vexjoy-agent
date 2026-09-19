# TypeScript MCP Server Scaffold Template

Reference for Phase 3 GENERATE. Templates for generating TypeScript MCP servers.

## Assembly

Generate a complete MCP server project:

```bash
python3 skills/workflow/references/mcp-pipeline-builder/scripts/assemble-scaffold.py \
  --service github --entity issue --output-dir ./github-mcp-server
```

Or output a single file:

```bash
python3 scripts/assemble-scaffold.py --service github --entity issue --file package.json
```

Use `--list` to see all template files and key patterns.
Use `--help` for full parameter documentation.

## Template Files

| Output Path | Template | Purpose |
|-------------|----------|---------|
| `package.json` | `package.json.tmpl` | npm config with MCP SDK + Zod deps |
| `tsconfig.json` | `tsconfig.json.tmpl` | ES2022/Node16 TypeScript config |
| `src/index.ts` | `index.ts.tmpl` | McpServer init, transport, env var validation |
| `src/tools/*.ts` | `tools.ts.tmpl` | Tool registration with Zod schemas + annotations |
| `src/services/client.ts` | `client-http.ts.tmpl` | HTTP API client pattern |
| `src/services/client-cli.ts` | `client-cli.ts.tmpl` | Subprocess/CLI client pattern |
| `README.md` | `readme.md.tmpl` | Setup docs with Claude Code registration |

## Key Patterns

- **Tool annotations**: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- **Error handling**: Always return text content on error, never throw from tool handler
- **Auth**: Read credentials from env vars, throw at startup if missing
- **Logging**: Use `console.error()` (not `console.log`) with stdio transport
