---
name: TypeScript Async Patterns for MCP Servers
description: Async/await, concurrency control, and error propagation patterns for MCP documentation server performance
---

# TypeScript Async Patterns for MCP Servers

> **Scope**: Async patterns relevant to MCP documentation servers — file I/O concurrency, indexing performance, error propagation. Does not cover general TypeScript async (unrelated to server contexts).
> **Version range**: Node.js 18+, TypeScript 5.0+
> **Generated**: 2026-04-08

---

## Overview

MCP documentation servers are I/O-bound: they read hundreds or thousands of files at startup. The failure modes split into two categories: doing too little concurrency (sequential file reads take minutes) and doing too much (reading all files simultaneously exhausts file descriptors and memory). The correct approach is bounded concurrency via batching or a semaphore.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `Promise.all(batch)` | Node 18+ | Bounded concurrent I/O | Unbounded arrays (OOM risk) |
| `Promise.allSettled()` | Node 12.9+ | Must collect all results despite failures | Need fast-fail on first error |
| `Promise.race()` | Node 18+ | Startup timeout racing | Error handling (loses other results) |
| `async/await` in handlers | Always | All `setRequestHandler` callbacks | Sync callbacks (blocks event loop) |
| `AbortController` | Node 18+ | Cancellable indexing operations | Simple timeouts (use setTimeout) |

---

## Correct Patterns

### Bounded Concurrency for File Indexing

Process files in fixed-size batches to avoid exhausting file descriptors.

```typescript
async function indexFilesInBatches(
  files: string[],
  batchSize: number,
  processFile: (path: string) => Promise<void>
): Promise<{ processed: number; failed: number }> {
  let processed = 0;
  let failed = 0;

  for (let i = 0; i < files.length; i += batchSize) {
    const batch = files.slice(i, i + batchSize);
    const results = await Promise.allSettled(batch.map(processFile));

    for (const result of results) {
      if (result.status === 'fulfilled') {
        processed++;
      } else {
        failed++;
        console.warn(`[warn] indexing failed: ${result.reason}`);
      }
    }
  }

  return { processed, failed };
}

// Usage: process 50 files at a time
await indexFilesInBatches(allFiles, 50, (f) => this.parseAndCache(f));
```

**Why**: `Promise.all(files.map(...))` on 10,000 files opens 10,000 file handles simultaneously. Most OS defaults limit to 1024 open file descriptors. `EMFILE: too many open files` crashes the indexer.

---

### Startup Timeout with Partial Results

Start serving before indexing completes; return partial results with metadata.

```typescript
class DocsServer {
  private indexingComplete = false;

  async start(): Promise<void> {
    const STARTUP_TIMEOUT_MS = 15_000;

    const indexingDone = this.runIndexing();

    // Serve partial results after timeout — don't block connection
    const startupFence = Promise.race([
      indexingDone.then(() => { this.indexingComplete = true; }),
      new Promise<void>((resolve) => setTimeout(resolve, STARTUP_TIMEOUT_MS)),
    ]);

    await startupFence;

    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    // Indexing may still be running in background
    await indexingDone.then(() => { this.indexingComplete = true; }).catch(() => {});
  }

  // Add indexing status to list response metadata
  handleListResources() {
    return {
      resources: this.getIndexedResources(),
      _meta: this.indexingComplete ? undefined : { indexing: true },
    };
  }
}
```

**Why**: MCP clients (Claude Desktop) have a 30-second connection timeout. A 10,000-file corpus can take 60+ seconds to index sequentially. Without a startup fence, Claude never connects.

---

### Error Propagation with Context

Preserve error context through async chains for debuggable server logs.

```typescript
async function parseDocWithContext(filePath: string): Promise<ParsedDoc> {
  try {
    const content = await fs.promises.readFile(filePath, 'utf-8');
    return parseMarkdownDoc(filePath, content);
  } catch (err) {
    // Wrap with file context before re-throwing
    throw new Error(`Failed to parse ${filePath}: ${(err as Error).message}`, {
      cause: err, // Node 16.9+ / ES2022
    });
  }
}

// Caller can inspect cause:
try {
  await parseDocWithContext('/docs/broken.md');
} catch (err) {
  if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
    // File disappeared between glob and read — normal race condition
  }
  console.error(err.message); // "Failed to parse /docs/broken.md: ENOENT..."
  console.error('Caused by:', (err as Error).cause);
}
```

**Why**: `cause` option (ES2022, Node 16.9+) enables error chains without losing the original. Without it, wrapping with template strings loses the original stack trace.

---

## Anti-Pattern Catalog

### ❌ Unbounded Promise.all on File List

**Detection**:
```bash
# Find Promise.all with .map() on potentially large arrays
grep -rn 'Promise\.all.*\.map' --include="*.ts" src/
rg 'Promise\.all\(' --type ts src/ -A2 | grep '\.map'
```

**What it looks like**:
```typescript
// Reads ALL files simultaneously — EMFILE on large repos
const docs = await Promise.all(
  allFiles.map((f) => fs.promises.readFile(f, 'utf-8'))
);
```

**Why wrong**: `EMFILE: too many open files` at runtime. Default ulimit is 1024 file descriptors on Linux. A repo with 2000 markdown files triggers this. The error appears non-deterministically depending on OS load, making it hard to reproduce locally.

**Fix**:
```typescript
// Process in batches of 50
for (let i = 0; i < allFiles.length; i += 50) {
  await Promise.all(allFiles.slice(i, i + 50).map((f) => this.parseAndCache(f)));
}
```

**Version note**: Node.js 18+ raises default file descriptor limit on Linux but OS limits still apply. Don't rely on this.

---

### ❌ Floating Promise in Request Handler

**Detection**:
```bash
grep -rn 'setRequestHandler' --include="*.ts" src/ -A10 | grep -v 'async\|await\|return'
# More specifically: promises not awaited inside handlers
rg 'setRequestHandler.*\{' --type ts src/ -A5 | grep '^\s*[a-zA-Z].*\(\)' | grep -v 'await'
```

**What it looks like**:
```typescript
server.setRequestHandler(CallToolRequestSchema, (request) => {
  // Not async, not returning promise properly
  this.searchIndex(request.params.arguments?.query).then((results) => {
    return { content: [{ type: 'text', text: JSON.stringify(results) }] };
  });
  // Returns undefined! Handler completes before search finishes.
});
```

**Why wrong**: The handler returns `undefined` immediately. The MCP framework sends an empty/null response to the client. The `.then()` callback runs later and its return value is discarded. The client receives a malformed response and may log it as a server error.

**Fix**:
```typescript
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const results = await this.searchIndex(request.params.arguments?.query as string);
  return { content: [{ type: 'text', text: JSON.stringify(results) }] };
});
```

---

### ❌ Swallowing Errors in indexDocs

**Detection**:
```bash
grep -rn 'catch.*{}' --include="*.ts" src/
grep -rn 'catch.*return\s*$\|catch.*return;\s*$' --include="*.ts" src/
```

**What it looks like**:
```typescript
async indexDocs(): Promise<void> {
  const files = await glob('**/*.md', { cwd: this.docsPath });
  await Promise.all(files.map(async (f) => {
    try {
      await this.parseAndCache(f);
    } catch {
      // Silently swallow — no log, no counter
    }
  }));
}
```

**Why wrong**: Silent failures make debugging impossible. If 50% of files fail to index, the server starts with half the documentation. No error appears in logs. Users get incomplete results with no indication of why.

**Fix**:
```typescript
let failCount = 0;
await Promise.allSettled(files.map(async (f) => {
  try {
    await this.parseAndCache(f);
  } catch (err) {
    failCount++;
    console.warn(`[warn] skip ${f}: ${(err as Error).message}`);
  }
}));
if (failCount > 0) {
  console.error(`[error] indexing: ${failCount}/${files.length} files failed`);
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `EMFILE: too many open files` | Unbounded `Promise.all` opening all files | Use batched processing (50 files/batch) |
| `UnhandledPromiseRejection` | Floating promise in handler | Make handler `async`, add `await` |
| Handler returns `undefined` | Sync handler with `.then()` instead of `await` | Convert to `async`/`await` |
| `Cannot read properties of undefined` in `.then()` | Race between indexing and handler registration | Use `await this.indexDocs()` before `server.connect()` |
| `Error [ERR_UNHANDLED_REJECTION]: ...` | Promise chain without terminal `.catch()` | Add `.catch(console.error)` to background promises |

---

## Detection Commands Reference

```bash
# Unbounded Promise.all (potential EMFILE)
grep -rn 'Promise\.all.*\.map' --include="*.ts" src/

# Non-async request handlers
grep -rn 'setRequestHandler(' --include="*.ts" src/ -A3 | grep -v async

# Empty catch blocks
grep -rn 'catch.*{' --include="*.ts" src/ -A1 | grep '^\s*}$'

# Missing await on async calls
grep -rn 'this\.\w\+(' --include="*.ts" src/ | grep -v await | grep -v '//'

# Floating promises (then without return/await)
grep -rn '\.then(' --include="*.ts" src/ | grep -v 'return\|await\|const\|let\|var'
```

---

## See Also

- `mcp-patterns.md` — Core MCP server patterns including startup indexing
- Node.js fs.promises docs: https://nodejs.org/api/fs.html#promises-api
