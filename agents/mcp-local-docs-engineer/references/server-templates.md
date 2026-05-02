# MCP Server Templates Reference

## TypeScript/Node.js Core Structure

```typescript
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

interface DocMetadata {
  title: string;
  description?: string;
  scope?: string;
  service?: string;
  tags?: string[];
  draft?: boolean;
  lastModified: Date;
}

interface ParsedDoc {
  uri: string;
  metadata: DocMetadata;
  content: string;
  path: string;
}

class DocsServer {
  private server: Server;
  private docsIndex: Map<string, ParsedDoc> = new Map();
  private docsPath: string;

  constructor(docsPath: string) {
    this.docsPath = docsPath;
    this.server = new Server(
      { name: 'local-docs', version: '1.0.0' },
      { capabilities: { resources: {}, tools: {} } }
    );
    this.setupHandlers();
  }

  private setupHandlers(): void {
    // List all documentation resources
    this.server.setRequestHandler(ListResourcesRequestSchema, async () => {
      const resources = Array.from(this.docsIndex.values()).map((doc) => ({
        uri: doc.uri,
        name: doc.metadata.title,
        description: doc.metadata.description,
        mimeType: 'text/markdown',
      }));
      return { resources };
    });

    // Read specific documentation resource
    this.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
      const doc = this.docsIndex.get(request.params.uri);
      if (!doc) {
        throw new Error(`Resource not found: ${request.params.uri}`);
      }
      return {
        contents: [{
          uri: doc.uri,
          mimeType: 'text/markdown',
          text: doc.content,
        }],
      };
    });

    // Search documentation tool
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name === 'search_docs') {
        return this.handleSearchDocs(request.params.arguments);
      }
      throw new Error(`Unknown tool: ${request.params.name}`);
    });
  }

  async run(): Promise<void> {
    await this.indexDocs();
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
  }
}
```

## Go Implementation Core Structure

```go
package main

import (
    "bufio"
    "encoding/json"
    "fmt"
    "io/fs"
    "os"
    "path/filepath"
    "strings"
    "sync"

    "gopkg.in/yaml.v3"
)

type DocMetadata struct {
    Title       string   `yaml:"title" json:"title"`
    Description string   `yaml:"description" json:"description,omitempty"`
    Scope       string   `yaml:"scope" json:"scope,omitempty"`
    Service     string   `yaml:"service" json:"service,omitempty"`
    Tags        []string `yaml:"tags" json:"tags,omitempty"`
    Draft       bool     `yaml:"draft" json:"draft,omitempty"`
}

type ParsedDoc struct {
    URI      string      `json:"uri"`
    Metadata DocMetadata `json:"metadata"`
    Content  string      `json:"content"`
    Path     string      `json:"path"`
    ModTime  int64       `json:"modTime"`
}

type DocsServer struct {
    docsPath string
    index    map[string]*ParsedDoc
    mu       sync.RWMutex
}

func (s *DocsServer) IndexDocs() error {
    return filepath.WalkDir(s.docsPath, func(path string, d fs.DirEntry, err error) error {
        if err != nil || d.IsDir() || !strings.HasSuffix(path, ".md") {
            return err
        }

        doc, err := s.parseDoc(path)
        if err != nil {
            fmt.Fprintf(os.Stderr, "Warning: failed to parse %s: %v\n", path, err)
            return nil // Continue indexing
        }

        s.mu.Lock()
        s.index[doc.URI] = doc
        s.mu.Unlock()

        return nil
    })
}
```

## Preferred Patterns

- **Async I/O**: Cache in memory, serve from cache, index once at startup. See `mcp-patterns.md`.
- **Custom URI scheme**: `docs://` with relative paths. Never expose filesystem paths. See `mcp-patterns.md`.
- **Front matter error handling**: Try-catch, partial results, continue indexing.

```typescript
function parseFrontMatter(content: string): DocMetadata {
  try {
    const parts = content.split('---');
    if (parts.length < 3) return { title: 'Untitled', lastModified: new Date() };
    return { ...yaml.parse(parts[1]), lastModified: new Date() };
  } catch (e) {
    console.error(`Front matter parse error: ${e}`);
    return { title: 'Untitled', lastModified: new Date() };
  }
}
```
