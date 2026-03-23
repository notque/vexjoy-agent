# TypeScript MCP Server Scaffold Template

Reference for Phase 3 GENERATE. Use these patterns when generating TypeScript MCP servers.

---

## Directory Structure

```
{service}-mcp-server/
  package.json
  tsconfig.json
  src/
    index.ts          ← McpServer init, transport connect, registerTool calls
    tools/
      {tool_group}.ts ← Tool implementations (one file per logical group)
    services/
      client.ts       ← Shared API client or subprocess wrapper
    schemas/
      {entity}.ts     ← Zod schemas for request/response types
  dist/               ← Compiled output (gitignored)
  README.md
```

---

## `package.json` Template

```json
{
  "name": "{service}-mcp-server",
  "version": "0.1.0",
  "description": "MCP server for {Service Name}",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "tsc --watch"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.6.1",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "typescript": "^5.6.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

---

## `tsconfig.json` Template

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

---

## `src/index.ts` Template

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Import tool registration functions
import { registerIssueTools } from "./tools/issues.js";
// Add more imports as needed

// Validate required environment variables at startup
const API_KEY = process.env.SERVICE_API_KEY;
if (!API_KEY) {
  throw new Error(
    "SERVICE_API_KEY environment variable is required. " +
    "Set it before starting the server."
  );
}

// Initialize the MCP server
const server = new McpServer({
  name: "{service}-mcp-server",
  version: "0.1.0",
});

// Register all tools
registerIssueTools(server, { apiKey: API_KEY });
// Call additional registration functions here

// Connect transport and start
const transport = new StdioServerTransport();
await server.connect(transport);

// Note: do NOT log to stdout when using stdio transport.
// Use stderr for any debug output: console.error("debug message")
```

---

## Tool Registration Pattern

Each tool group lives in `src/tools/{group}.ts`:

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { ServiceClient } from "../services/client.js";

interface ToolConfig {
  apiKey: string;
}

export function registerIssueTools(server: McpServer, config: ToolConfig): void {
  const client = new ServiceClient(config.apiKey);

  // Read-only tool example
  server.tool(
    "service_get_issue",
    "Get a single issue by its identifier. Returns the issue title, description, state, labels, and assignees.",
    {
      // Zod schema for parameters
      owner: z.string().describe("Repository owner or organization name"),
      repo: z.string().describe("Repository name"),
      issue_number: z.string().describe("Issue number as a string (e.g., '42')"),
    },
    {
      // Tool annotations — set these accurately
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    async ({ owner, repo, issue_number }) => {
      // Always wrap in try/catch; always return text content on error
      try {
        const issue = await client.getIssue(owner, repo, parseInt(issue_number));
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(issue, null, 2),
            },
          ],
        };
      } catch (error) {
        // Return error as text content — do NOT throw
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: "text",
              text: `Error fetching issue: ${message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );

  // List tool example with optional parameters
  server.tool(
    "service_list_issues",
    "List issues with optional filters. Returns a JSON array of issues matching the criteria.",
    {
      owner: z.string().describe("Repository owner or organization name"),
      repo: z.string().describe("Repository name"),
      state: z.enum(["open", "closed", "all"]).optional().describe("Filter by state. Default: open"),
      limit: z.number().min(1).max(100).optional().describe("Maximum results to return. Default: 20"),
    },
    {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    async ({ owner, repo, state = "open", limit = 20 }) => {
      try {
        const issues = await client.listIssues(owner, repo, { state, limit });
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(issues, null, 2),
            },
          ],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Error listing issues: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
```

---

## `src/services/client.ts` Template

The shared API client. Adapt to the target service's protocol (HTTP, subprocess, etc.).

### HTTP Client Pattern

```typescript
export interface IssueData {
  number: number;
  title: string;
  state: string;
  body: string;
  labels: string[];
}

export class ServiceClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor(apiKey: string, baseUrl = "https://api.example.com") {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }
    const response = await fetch(url.toString(), {
      headers: {
        "Authorization": `Bearer ${this.apiKey}`,
        "Accept": "application/json",
      },
    });
    if (!response.ok) {
      throw new Error(`API error ${response.status}: ${await response.text()}`);
    }
    return response.json() as Promise<T>;
  }

  async getIssue(owner: string, repo: string, number: number): Promise<IssueData> {
    return this.request<IssueData>(`/repos/${owner}/${repo}/issues/${number}`);
  }

  async listIssues(owner: string, repo: string, opts: { state: string; limit: number }): Promise<IssueData[]> {
    return this.request<IssueData[]>(`/repos/${owner}/${repo}/issues`, {
      state: opts.state,
      per_page: String(opts.limit),
    });
  }
}
```

### Subprocess/CLI Client Pattern

Use this when the target exposes a CLI rather than an HTTP API:

```typescript
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export class CliClient {
  private readonly executable: string;
  private readonly env: Record<string, string>;

  constructor(executable: string, env: Record<string, string> = {}) {
    this.executable = executable;
    this.env = env;
  }

  async run(args: string[]): Promise<string> {
    const { stdout, stderr } = await execFileAsync(this.executable, args, {
      env: { ...process.env, ...this.env },
      maxBuffer: 10 * 1024 * 1024, // 10MB
    });
    if (stderr && !stdout) {
      throw new Error(stderr);
    }
    return stdout;
  }
}
```

---

## Key Patterns

### Tool Annotation Hints

Set these accurately for every tool — they're hints to clients, not security guarantees:

| Annotation | Type | Set to `true` when... |
|------------|------|----------------------|
| `readOnlyHint` | boolean | Tool does not modify any state |
| `destructiveHint` | boolean | Tool may delete or irreversibly modify data |
| `idempotentHint` | boolean | Calling tool twice with same params has same effect |
| `openWorldHint` | boolean | Tool interacts with external services (the internet) |

### Error Handling Pattern

**Always return text content on error. Never throw from a tool handler.**

```typescript
async (params) => {
  try {
    const result = await client.doSomething(params);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: `Error: ${message}` }],
      isError: true,
    };
  }
}
```

### Auth Pattern

Always read credentials from environment variables. Throw at startup if missing — do not silently use undefined values.

```typescript
const API_KEY = process.env.SERVICE_API_KEY;
if (!API_KEY) {
  // Note: this throws at startup, not at first tool call.
  // This produces a clear error immediately rather than a confusing "undefined" later.
  throw new Error("SERVICE_API_KEY is required. Export it before starting the server.");
}
```

### stdout vs stderr

When using stdio transport, stdout is the MCP protocol stream. Never write to stdout directly.
Use `console.error()` for any debug logging.

```typescript
// Wrong — breaks stdio transport
console.log("Server started");

// Correct
console.error("Server started");
```

---

## `README.md` Template

```markdown
# {Service Name} MCP Server

MCP server for {Service Name}. Provides Claude Code with tools to {one-line purpose}.

## Tools

| Tool | Description |
|------|-------------|
| `service_get_thing` | Get a single thing by ID |
| `service_list_things` | List things with optional filters |

## Setup

### Prerequisites
- Node.js >= 18
- {Service Name} API key

### Install

\`\`\`bash
npm install
npm run build
\`\`\`

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERVICE_API_KEY` | Yes | {Service Name} API key from {where to get it} |

### Register with Claude Code

\`\`\`bash
python3 pipelines/mcp-pipeline-builder/scripts/register_mcp.py \
  --name {service}-mcp-server \
  --command node \
  --args $(pwd)/dist/index.js \
  --env SERVICE_API_KEY=your_key_here
\`\`\`

Or add manually to `~/.claude.json`:

\`\`\`json
{
  "mcpServers": {
    "{service}-mcp-server": {
      "command": "node",
      "args": ["/absolute/path/to/dist/index.js"],
      "env": {
        "SERVICE_API_KEY": "your_key_here"
      }
    }
  }
}
\`\`\`
```
