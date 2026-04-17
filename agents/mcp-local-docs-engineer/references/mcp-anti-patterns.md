---
name: MCP Server Anti-Patterns
description: Common MCP server mistakes with detection commands and fixes — front matter parsing, caching failures, protocol violations
---

# MCP Server Anti-Patterns

> **Scope**: Anti-patterns specific to MCP documentation servers in TypeScript/Node.js. Covers front matter parsing failures, indexing bugs, and protocol misuse.
> **Version range**: `@modelcontextprotocol/sdk` 0.5.0+, Node.js 18+
> **Generated**: 2026-04-08 — verify against current MCP spec

---

## Overview

MCP documentation servers fail in predictable ways. Front matter parsing crashes the entire server from a single bad file. Unvalidated Hugo shortcodes corrupt content sent to LLMs. Missing capability declarations cause clients to not discover tools. These failures often produce no visible errors during development but break under production load or unusual file content.

---

## Pattern Catalog

### ❌ Crashing on Single Malformed Front Matter File

**Detection**:
```bash
# Find YAML parse calls without try/catch
grep -rn 'yaml\.parse\|yaml\.load\|toml\.parse' --include="*.ts" src/
# Check if they're wrapped in try/catch
grep -B5 'yaml\.parse\|yaml\.load' --include="*.ts" -rn src/
```

**What it looks like**:
```typescript
function parseFrontMatter(content: string): DocMetadata {
  const parts = content.split('---');
  // Crashes if YAML is malformed — kills entire server
  const metadata = yaml.parse(parts[1]);
  return metadata as DocMetadata;
}
```

**Why wrong**: A single documentation file with a tab in YAML (invalid) or an unclosed quote crashes `yaml.parse()` and propagates to the indexing loop. The entire server process exits. All other 999 documents become inaccessible because of one bad file.

**Fix**:
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

**Version note**: `js-yaml` >= 4.0 uses `yaml.load()` not `yaml.safeLoad()`. The `safeLoad` method was removed in 4.0.

---

### ❌ Sending Raw Hugo Shortcodes to LLM Clients

**Detection**:
```bash
# Find files likely to have shortcodes
grep -rn '{{[<%]' --include="*.md" content/ | head -20
# Check if server strips them
grep -rn 'shortcode\|{{%\|{{<' --include="*.ts" src/
```

**What it looks like**:
```typescript
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const doc = this.docsIndex.get(request.params.uri);
  // Returns raw markdown with Hugo shortcodes intact
  return { contents: [{ uri: doc.uri, mimeType: 'text/markdown', text: doc.content }] };
});
```

**Why wrong**: Hugo shortcodes like `{{< youtube abc123 >}}` or `{{% notice warning %}}` are not markdown. LLMs see them as noise, may misinterpret them as code blocks, or produce hallucinated explanations of the shortcode syntax.

**Fix**:
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

---

### ❌ Missing Capabilities Declaration

**Detection**:
```bash
grep -rn 'capabilities' --include="*.ts" src/
# Must include capabilities matching registered handlers
```

**What it looks like**:
```typescript
this.server = new Server(
  { name: 'local-docs', version: '1.0.0' },
  { capabilities: {} }  // Empty — client won't discover tools or resources
);
```

**Why wrong**: MCP clients negotiate capabilities during the `initialize` handshake. If `capabilities.resources` is absent, clients skip the `resources/list` call entirely and never discover documents. If `capabilities.tools` is absent, the `search_docs` tool is invisible.

**Fix**:
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

**Version note**: SDK 0.6.0+ allows omitting empty `{}` for unimplemented capabilities — they default to absent.

---

### ❌ Path Traversal via URI Parameter

**Detection**:
```bash
# Find URI-to-path conversion without traversal check
grep -rn 'uriToPath\|path\.join.*params\.uri\|path\.resolve.*params' --include="*.ts" src/
```

**What it looks like**:
```typescript
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  // URI: docs://../../../etc/passwd — traverses out of docs root!
  const filePath = path.join(this.docsRoot, request.params.uri.slice('docs://'.length));
  const content = await fs.promises.readFile(filePath, 'utf-8');
  return { contents: [{ uri: request.params.uri, text: content }] };
});
```

**Why wrong**: `path.join` normalizes `..` segments but does NOT prevent traversal. `path.join('/docs', '../etc/passwd')` resolves to `/etc/passwd`. An MCP client (including a compromised LLM session) can read any file the server process has access to.

**Fix**:
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

---

### ❌ Draft Documents Exposed in Resource List

**Detection**:
```bash
# Check if draft filtering exists in list handler
grep -rn 'draft\|isDraft' --include="*.ts" src/
# Check Hugo content for draft: true documents
grep -rn '^draft: true\|^draft: "true"' --include="*.md" content/
```

**What it looks like**:
```typescript
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  const resources = Array.from(this.docsIndex.values()).map((doc) => ({
    uri: doc.uri,
    name: doc.metadata.title ?? 'Untitled',
  }));
  return { resources }; // Includes draft: true documents
});
```

**Why wrong**: Hugo draft documents are unpublished content — WIP, incomplete, or intentionally hidden. Exposing them to LLMs means Claude may cite unpublished information as authoritative.

**Fix**:
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
