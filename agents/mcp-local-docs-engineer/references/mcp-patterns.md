---
description: Core MCP SDK patterns for TypeScript/Node.js server implementation, tool registration, and resource handling
---

# MCP Server Development Patterns

> **Scope**: TypeScript/Node.js MCP via `@modelcontextprotocol/sdk` 0.5.0+.

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `StdioServerTransport` | 0.5.0+ | Claude Desktop integration | HTTP API needed |
| `SSEServerTransport` | 0.5.0+ | Web-based clients, multiple connections | Single-process use |
| `server.setRequestHandler()` | 0.5.0+ | All request handling | Direct protocol manipulation |
| `ListResourcesRequestSchema` | 0.5.0+ | Exposing documents/files | Structured data with tools |
| `CallToolRequestSchema` | 0.5.0+ | Search, filtering, actions | Read-only resource access |

---

## Correct Patterns

### Tool Registration with Input Schema

Explicit JSON Schema for client-side validation and LLM parameter guidance.

```typescript
import { CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';

const SearchSchema = z.object({
  query: z.string().min(1).describe('Search terms'),
  limit: z.number().int().min(1).max(100).default(10).describe('Max results'),
  tags: z.array(z.string()).optional().describe('Filter by tags'),
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name !== 'search_docs') {
    throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
  }

  // Validate with Zod before processing
  const args = SearchSchema.parse(request.params.arguments ?? {});
  const results = await searchIndex(args.query, args.limit, args.tags);

  return {
    content: [{ type: 'text', text: JSON.stringify(results, null, 2) }],
  };
});
```

**Why**: Without schema, malformed arguments cause cryptic errors instead of `InvalidParams`.

---

### Resource URI Design with Custom Scheme

`docs://` scheme — never expose filesystem paths.

```typescript
function pathToUri(docsRoot: string, filePath: string): string {
  const relative = path.relative(docsRoot, filePath);
  // docs://guides/api-reference.md — portable, no host path leakage
  return `docs://${relative.replace(path.sep, '/')}`;
}

function uriToPath(docsRoot: string, uri: string): string {
  if (!uri.startsWith('docs://')) {
    throw new McpError(ErrorCode.InvalidParams, `Invalid URI scheme: ${uri}`);
  }
  const relative = uri.slice('docs://'.length);
  // Prevent path traversal
  const resolved = path.resolve(docsRoot, relative);
  if (!resolved.startsWith(docsRoot)) {
    throw new McpError(ErrorCode.InvalidParams, 'Path traversal not allowed');
  }
  return resolved;
}
```

**Why**: `file:///` exposes filesystem layout. `docs://` is portable.

---

### Startup Indexing with Background Continuation

Serve partial results for large corpora while indexing continues.

```typescript
class DocsServer {
  private indexReady = false;
  private indexingPromise: Promise<void> | null = null;

  async start(): Promise<void> {
    // Begin indexing, but don't await completion — serve partial results
    this.indexingPromise = this.indexDocs();

    // Wait up to 10s for initial batch, then proceed
    await Promise.race([
      this.indexingPromise,
      new Promise<void>((resolve) => setTimeout(resolve, 10_000)),
    ]);
    this.indexReady = true;

    const transport = new StdioServerTransport();
    await this.server.connect(transport);
  }

  private async indexDocs(): Promise<void> {
    const files = await glob('**/*.md', { cwd: this.docsPath });
    // Process in batches of 50 to avoid memory spikes
    for (let i = 0; i < files.length; i += 50) {
      const batch = files.slice(i, i + 50);
      await Promise.all(batch.map((f) => this.parseAndCache(f)));
    }
  }
}
```

**Why**: Full indexing before connect causes client timeouts. Batch processing prevents heap exhaustion.

---

## Pattern Catalog

### Use Async File I/O in Request Handlers
**Detection**:
```bash
grep -rn 'readFileSync\|existsSync\|readdirSync' --include="*.ts" src/
rg 'Sync\(' --type ts src/
```

**Signal**:
```typescript
server.setRequestHandler(ReadResourceRequestSchema, (request) => {
  // NOT async — blocks the entire Node.js event loop
  const content = fs.readFileSync(uriToPath(request.params.uri), 'utf-8');
  return { contents: [{ uri: request.params.uri, text: content }] };
});
```

**Why this matters**: `readFileSync` blocks the event loop. While one client is reading a large file, all other clients are frozen. Under concurrent load this causes cascading timeouts — the MCP client kills the connection thinking the server hung.

**Preferred action**:
```typescript
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const filePath = uriToPath(this.docsRoot, request.params.uri);
  const content = await fs.promises.readFile(filePath, 'utf-8');
  return { contents: [{ uri: request.params.uri, text: content }] };
});
```

---

### Index Once at Startup and Serve from Cache
**Detection**:
```bash
grep -rn 'indexDocs\|parseDoc\|WalkDir' --include="*.ts" src/
# Flag if found inside a setRequestHandler callback
```

**Signal**:
```typescript
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  // Re-parses all markdown files on every list call — seconds of delay
  const docs = await this.indexDocs();
  return { resources: docs.map((d) => ({ uri: d.uri, name: d.metadata.title })) };
});
```

**Why this matters**: Claude calls `resources/list` repeatedly during a session. Re-parsing 1000 files takes 3-10 seconds each time. The LLM context window fills with timeout errors before any content arrives.

**Preferred action**: Index once at startup, serve from in-memory Map, use mtime-based cache invalidation:
```typescript
private docsIndex = new Map<string, ParsedDoc>();

// Called once at startup
async indexDocs(): Promise<void> {
  const files = await glob('**/*.md', { cwd: this.docsPath });
  await Promise.all(files.map((f) => this.parseAndCache(f)));
}

async parseAndCache(relativePath: string): Promise<void> {
  const fullPath = path.join(this.docsPath, relativePath);
  const stat = await fs.promises.stat(fullPath);
  const existing = this.docsIndex.get(relativePath);
  // Skip if unchanged
  if (existing && existing.mtime === stat.mtimeMs) return;
  const doc = await this.parseDoc(fullPath);
  this.docsIndex.set(relativePath, { ...doc, mtime: stat.mtimeMs });
}
```

---

### Use McpError with Proper Error Codes
**Detection**:
```bash
grep -rn 'throw new Error(' --include="*.ts" src/
# Should be McpError for protocol failures
```

**Signal**:
```typescript
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const doc = this.docsIndex.get(request.params.uri);
  if (!doc) {
    throw new Error(`Not found: ${request.params.uri}`); // Generic JS error
  }
  return { contents: [{ uri: doc.uri, text: doc.content }] };
});
```

**Why this matters**: Generic `Error` objects get wrapped in an internal error JSON-RPC response with code `-32603`. MCP clients cannot distinguish "resource not found" from "server crashed." Proper `McpError` with `ErrorCode.InvalidParams` or `ErrorCode.InternalError` lets clients handle the failure gracefully.

**Preferred action**:
```typescript
import { McpError, ErrorCode } from '@modelcontextprotocol/sdk/types.js';

if (!doc) {
  throw new McpError(
    ErrorCode.InvalidParams,
    `Resource not found: ${request.params.uri}`
  );
}
```

**Version note**: `McpError` and `ErrorCode` available since `@modelcontextprotocol/sdk` 0.4.0.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `MCP error -32601: Method not found` | Handler not registered for method | Add `server.setRequestHandler(MethodSchema, ...)` |
| `MCP error -32602: Invalid params` | Arguments fail schema validation | Check Zod schema matches tool's `inputSchema` definition |
| `connect ENOENT /tmp/...` (stdio) | Server process died before connecting | Check server startup logs; ensure `indexDocs()` doesn't throw |
| `YAML Exception: ...` on startup | Malformed front matter in a markdown file | Wrap YAML parse in try/catch, log warning, continue |
| `Cannot read properties of undefined (reading 'uri')` | `request.params` not validated | Add `if (!request.params?.uri)` guard or use schema validation |
| `RangeError: Maximum call stack size exceeded` | Circular reference in docs index structure | Avoid nested document objects; store flat metadata |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| SDK 0.5.0 | `SSEServerTransport` added | HTTP+SSE transport available alongside stdio |
| SDK 0.6.0 | `server.tool()` helper added | Simpler tool registration without manual `setRequestHandler` |
| MCP spec 2024-11 | `resources/subscribe` added | Clients can subscribe to resource change notifications |
| Node.js 18+ | `fs.promises` stable | Use `await fs.promises.readFile()` without `.promises` polyfill |

---

## Detection Commands Reference

```bash
# Blocking I/O in handlers
grep -rn 'readFileSync\|existsSync\|readdirSync' --include="*.ts" src/

# Generic errors instead of McpError
grep -rn 'throw new Error(' --include="*.ts" src/

# Re-indexing inside request handlers
grep -A5 'setRequestHandler' src/ --include="*.ts" -rn | grep -E 'indexDocs|parseDoc|WalkDir'

# Filesystem path leakage in URIs
grep -rn 'file:///' --include="*.ts" src/

# Missing async on handlers
grep -rn 'setRequestHandler.*request.*=>' --include="*.ts" src/ | grep -v 'async'
```

---

## See Also

- `mcp-preferred-patterns.md` — Front matter, caching, and URI anti-patterns catalog
- MCP Specification: https://spec.modelcontextprotocol.io/
- SDK source: https://github.com/modelcontextprotocol/typescript-sdk
