---
description: "Building MCP servers for local documentation access in TypeScript/Node.js and Go: JSON-RPC 2.0, Hugo front matter, indexing, caching, docs:// URIs."
type: reference
---

# MCP Local Docs Servers

Rules for protocol-compliant, efficient MCP servers that give local access to
documentation.

Not for: using existing MCP tools or servers (only building local-docs MCP
servers); web performance or LCP optimization (use the `frontend` skill);
writing the documentation content, API references, or runbooks (use the
`writing` skill).

## Expertise areas

- **MCP protocol:** JSON-RPC 2.0, resource management, tool schemas, server
  lifecycle.
- **Documentation parsing:** Hugo front matter (YAML/TOML), markdown
  processing, metadata normalization.
- **Server architecture:** TypeScript/Node.js and Go implementations,
  performance, error handling.
- **File system:** efficient traversal, change detection, concurrent access.

## Hard rules

- **Read the file before editing.** Never edit a file you have not read in this
  session.
- **Run build and tests before reporting completion:** `npm run build`
  (TypeScript) or `go build ./...` (Go). Show the actual output, not "build
  succeeds".
- **Feature branch, never main.** If on main, create a branch before committing.
- **Verify dependencies exist before importing them.** Check `package.json` for
  `@modelcontextprotocol/sdk` or `go.mod` for required modules.
- **JSON-RPC 2.0 compliance** for all protocol interactions, with proper
  request/response structures.
- **Standard MCP methods only** (`resources/list`, `resources/read`,
  `tools/call`); no custom extensions.
- **Indexing budget:** initial indexing of 1000+ files completes within 30
  seconds.
- **Validate Hugo front matter** (YAML/TOML) before parsing, so bad files cannot
  crash the server.

## Defaults (on unless disabled)

- In-memory cache of parsed docs, invalidated by file modification time.
- Incremental indexing: after the initial load, re-parse only files whose mtime
  changed.
- Graceful degradation: return partial results with error metadata when some
  files fail to parse.
- Strip Hugo shortcodes and internal links from returned content.

## Off unless requested

- Full-text search index (only when a `search_docs` tool is requested).
- Cross-reference resolution of internal doc links.
- Content summarization for long documents.
- Watch mode with hot reload (development mode only).

## Scope

In scope:

- TypeScript/Node.js MCP servers using `@modelcontextprotocol/sdk`.
- Go MCP servers with standard-library patterns.
- Hugo front matter parsing (YAML and TOML) with validation.
- Efficient indexing (1000+ files in under 30 s).
- MCP tools for search and filtering.
- Large documentation repositories with caching.
- Graceful error handling and partial results.

Out of scope (explain the limit and suggest an alternative):

- **Extending the MCP protocol:** standard methods only.
- **Real-time sync:** indexing is incremental by mtime, not instant file watch.
- **Non-Hugo content:** specialized for Hugo documentation structure.
- **Encrypted content:** plain-text markdown only.

## Output format (Implementation Schema)

```markdown
## Analysis
[What the current state is and what needs to be implemented]

## Implementation Plan
[Step-by-step approach]

## Changes Made
[Actual file modifications with paths and descriptions]

## Verification Steps
[How to test the implementation]

## Next Steps
[What remains or follow-up tasks]
```

## Implementation patterns

Server scaffolding for TypeScript/Node.js (`DocsServer` class with `Server`,
`StdioServerTransport`, handler setup, `run()`) and Go (`DocsServer` struct with
`sync.RWMutex`, `IndexDocs()` via `filepath.WalkDir`) is in
[server-templates.md](mcp-local-docs/server-templates.md).

Key patterns: async file I/O only (no `readFileSync`); index once at startup,
then serve from a `Map`; use the `docs://` URI scheme (never expose filesystem
paths); wrap front matter parsing in try-catch.

## Reference loading table

| Signal | Load |
|------|------|
| Scaffolding a new server, TypeScript DocsServer class, Go DocsServer struct | [server-templates.md](mcp-local-docs/server-templates.md) |
| MCP server development, tool registration, SDK patterns | [mcp-patterns.md](mcp-local-docs/mcp-patterns.md) |
| Front matter parsing failures, URI issues, shortcode bugs, detection commands | [mcp-preferred-patterns.md](mcp-local-docs/mcp-preferred-patterns.md) |
| Async file I/O, concurrency, EMFILE errors, slow indexing | [typescript-async-patterns.md](mcp-local-docs/typescript-async-patterns.md) |

## Errors

### Front matter parsing failure

**Cause:** invalid YAML/TOML in a markdown file.
**Fix:** wrap parsing in try-catch; log a warning with the file path; continue
indexing the rest; return a partial index with error metadata.

### Slow indexing on a large repository

**Cause:** too many files or inefficient parsing.
**Fix:** profile indexing; parse files in parallel with a concurrency limit; add
mtime-based caching; consider incremental indexing.

### MCP client connection timeout

**Cause:** initial indexing takes too long.
**Fix:** reduce indexing scope temporarily; index in the background; return
partial results while indexing continues; report indexing progress.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When
sure, decide, record the assumption in the report, and continue; ask Jev when
genuinely unsure. Ask only when these situations leave a material decision
uncovered. Rows marked **(owner)** guard production, destructive, credential,
public-exposure, or persistence actions: get explicit owner confirmation first.

| Situation | Why stop | Ask |
|-----------|----------|-----|
| Custom MCP methods requested | Protocol violation | "Standard MCP methods or a workaround using tools?" |
| Non-Hugo documentation format | Out of scope | "Is this Hugo-based docs? If not, a different parser is needed." |
| Authentication/encryption needed **(owner)** | Security scope | "What auth mechanism? MCP doesn't specify one." |
| Real-time sync required | Architecture change | "Real-time vs incremental indexing: what latency is tolerable?" |

Decide explicitly before acting on: authentication for doc access (owner
confirms), custom protocol extensions, performance requirements (indexing and
response time), and documentation structure assumptions (Hugo vs other).

## Rationalizations to reject

| Rationalization | Why it's wrong | Required action |
|-----------------|----------------|-----------------|
| "Custom MCP method is cleaner" | Breaks protocol compliance; clients won't support it | Standard methods + tools |
| "Sync file reading is fine for small docs" | Blocks the event loop; scales poorly | Always async |
| "Re-parsing is simpler than caching" | Destroys performance at scale | Cache from the start |
| "File paths in URIs are convenient" | Security risk; not portable | Custom URI scheme |

## Related skills

- `testing` for TDD, E2E, and verification.
