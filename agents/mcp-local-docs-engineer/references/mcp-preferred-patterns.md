---
description: Common MCP server mistakes with detection commands and fixes — front matter parsing, caching failures, protocol violations
---

# MCP Server Patterns Guide

> **Scope**: Correct patterns for MCP documentation servers in TypeScript/Node.js. Covers front matter resilience, content sanitization, capability declaration, path safety, and draft filtering.
> **Version range**: `@modelcontextprotocol/sdk` 0.5.0+, Node.js 18+
> **Generated**: 2026-04-08 — verify against current MCP spec

---

## Overview

MCP documentation servers fail in predictable ways when they lack defensive patterns. A single malformed front matter file crashes the entire server. Unvalidated Hugo shortcodes corrupt content sent to LLMs. Missing capability declarations make tools invisible to clients. The patterns below prevent each failure mode.

---

## Pattern Catalog

### Wrap Front Matter Parsing in Try/Catch

Parse YAML front matter defensively: catch parse errors, log a warning, and continue indexing remaining files. A single malformed file must never crash the entire server.

```typescript
function parseFrontMatter(content: string): { metadata: Partial<DocMetadata>; error?: string } {
  const parts = content.split('---');
  if (parts.length < 3) {
    return { metadata: {}, error: 'No front matter delimiters found' };
  }
  try {
    const metadata = yaml.parse(parts[1]) as DocMetadata;
    return { metadata: metadata ?? {} };
  } catch (err) {
    // Log warning, return empty metadata — do not crash
    return { metadata: {}, error: `YAML parse failed: ${(err as Error).message}` };
  }
}

// In indexing loop:
const { metadata, error } = parseFrontMatter(content);
if (error) {
  console.warn(`[warn] front matter: ${filePath}: ${error}`);
  // Continue indexing remaining files
}
```

**Why this matters**: A tab in YAML (invalid) or an unclosed quote crashes `yaml.parse()` and propagates to the indexing loop. The entire server process exits, making all 999 other documents inaccessible because of one bad file.

**Detection**:
```bash
# Find YAML parse calls without try/catch
grep -rn 'yaml\.parse\|yaml\.load\|toml\.parse' --include="*.ts" src/
# Check if they're wrapped in try/catch
grep -B5 'yaml\.parse\|yaml\.load' --include="*.ts" -rn src/
```

**Version note**: `js-yaml` >= 4.0 uses `yaml.load()` not `yaml.safeLoad()`. The `safeLoad` method was removed in 4.0.

---

### Strip Hugo Shortcodes Before Sending Content

Remove Hugo shortcodes (`{{< >}}` and `{{% %}}`) from markdown content before returning it to MCP clients. LLMs interpret shortcodes as noise or produce hallucinated explanations of the syntax.

```typescript
function stripHugoShortcodes(content: string): string {
  return content
    // Remove block shortcodes: {{< name >}}...{{< /name >}}
    .replace(/\{\{<\s*\/?\s*\w+[^>]*>\}\}/g, '')
    // Remove percent shortcodes: {{% name %}}
    .replace(/\{\{%[^%]*%\}\}/g, '')
    // Remove inline shortcodes with content
    .replace(/\{\{<\s*\w+[^>]*>\}\}[\s\S]*?\{\{<\s*\/\w+\s*>\}\}/g, '')
    // Clean up empty lines left by removal
    .replace(/\n{3,}/g, '\n\n');
}
```

**Why this matters**: Hugo shortcodes like `{{< youtube abc123 >}}` or `{{% notice warning %}}` are not markdown. When sent raw to LLMs, they appear as noise, may be misinterpreted as code blocks, or produce hallucinated explanations.

**Detection**:
```bash
# Find files likely to have shortcodes
grep -rn '{{[<%]' --include="*.md" content/ | head -20
# Check if server strips them
grep -rn 'shortcode\|{{%\|{{<' --include="*.ts" src/
```

---

### Declare All Implemented Capabilities

Register `resources` and `tools` in the server capabilities object during initialization. Only add capability keys for features you implement — omit `prompts` and `logging` if unused.

```typescript
this.server = new Server(
  { name: 'local-docs', version: '1.0.0' },
  {
    capabilities: {
      resources: {},        // Enables resources/list and resources/read
      tools: {},            // Enables tools/list and tools/call
      // Only add these if you implement them:
      // prompts: {},
      // logging: {},
    },
  }
);
```

**Why this matters**: MCP clients negotiate capabilities during the `initialize` handshake. If `capabilities.resources` is absent, clients skip `resources/list` entirely and never discover documents. If `capabilities.tools` is absent, the `search_docs` tool is invisible. An empty `capabilities: {}` object makes the server appear to have no features.

**Detection**:
```bash
grep -rn 'capabilities' --include="*.ts" src/
grep -rn 'new Server(' --include="*.ts" src/ -A5 | grep -v 'capabilities'
```

**Version note**: SDK 0.6.0+ allows omitting empty `{}` for unimplemented capabilities — they default to absent.

---

### Validate URI Paths Against Traversal

When converting URIs to file paths, resolve the path and verify it stays within the docs root directory. `path.join` normalizes `..` segments but does NOT prevent traversal.

```typescript
function safeUriToPath(docsRoot: string, uri: string): string {
  if (!uri.startsWith('docs://')) {
    throw new McpError(ErrorCode.InvalidParams, `Invalid URI scheme: ${uri}`);
  }
  const relative = uri.slice('docs://'.length);
  const resolved = path.resolve(docsRoot, relative);
  // Enforce that resolved path stays within docsRoot
  if (!resolved.startsWith(path.resolve(docsRoot) + path.sep) &&
      resolved !== path.resolve(docsRoot)) {
    throw new McpError(ErrorCode.InvalidParams, 'Path traversal not allowed');
  }
  return resolved;
}
```

**Why this matters**: `path.join('/docs', '../etc/passwd')` resolves to `/etc/passwd`. An MCP client (including a compromised LLM session) can read any file the server process has access to without traversal validation.

**Detection**:
```bash
grep -rn 'uriToPath\|path\.join.*params\.uri\|path\.resolve.*params' --include="*.ts" src/
```

---

### Filter Draft Documents From Resource Lists

Exclude documents with `draft: true` front matter from the resource list handler. Only published content should be discoverable by MCP clients.

```typescript
const resources = Array.from(this.docsIndex.values())
  .filter((doc) => !doc.metadata.draft)
  .map((doc) => ({
    uri: doc.uri,
    name: doc.metadata.title ?? path.basename(doc.path, '.md'),
    description: doc.metadata.description,
    mimeType: 'text/markdown',
  }));
```

**Why this matters**: Hugo draft documents are unpublished content — WIP, incomplete, or intentionally hidden. Exposing them to LLMs means Claude may cite unpublished information as authoritative.

**Detection**:
```bash
# Check if draft filtering exists in list handler
grep -rn 'draft\|isDraft' --include="*.ts" src/
# Check Hugo content for draft: true documents
grep -rn '^draft: true\|^draft: "true"' --include="*.md" content/
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `YAMLException: unexpected end of the stream` | Unclosed YAML string in front matter | Wrap in try/catch, skip file with warning |
| `TypeError: Cannot read properties of null (reading 'title')` | `yaml.parse()` returned null for empty front matter | Check `metadata ?? {}` after parse |
| `McpError: Resource not found` at client | URI uses backslash on Windows (`docs://foo\bar`) | Normalize with `replace(/\\/g, '/')` in `pathToUri` |
| Server exits with code 1 immediately | Uncaught promise rejection in `indexDocs()` | Add `.catch()` to indexing promise or wrap in try/catch |
| Client sees 0 resources | `capabilities.resources` not declared | Add `resources: {}` to server capabilities |
| `tools/list` returns empty array | `capabilities.tools` not declared | Add `tools: {}` to server capabilities |
| `EACCES: permission denied` | Server process lacks read permission | Check file ownership; run with appropriate user |

---

## Detection Commands Reference

```bash
# All YAML/TOML parse calls (verify each has try/catch)
grep -rn 'yaml\.parse\|yaml\.load\|toml\.parse' --include="*.ts" src/

# Hugo shortcodes not stripped
grep -rn '{{[<%]' --include="*.md" content/ | wc -l

# Missing capability declaration
grep -rn 'new Server(' --include="*.ts" src/ -A5 | grep -v 'capabilities'

# Path traversal risk
grep -rn 'path\.join.*params\.' --include="*.ts" src/

# Draft documents in index
grep -rn 'draft' --include="*.ts" src/ | grep -v filter

# Generic Error instead of McpError
grep -rn 'throw new Error(' --include="*.ts" src/
```

---

## See Also

- `mcp-patterns.md` — Correct MCP server development patterns
- Hugo front matter docs: https://gohugo.io/content-management/front-matter/
- MCP error codes: https://spec.modelcontextprotocol.io/specification/server/utilities/logging/
