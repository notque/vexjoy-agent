# Phase 2 Design Rules

Rules for converting `analysis.md` into `design.md`. Follow these in order.

---

## Primitive Selection

Use this heuristic table for every operation in the analysis. When in doubt, use a Tool — Tools are always acceptable; Resources and Prompts are optional specializations.

| If the operation... | Expose as... | Reason |
|--------------------|-------------|--------|
| Requires parameters to identify what to fetch | **Tool** | Parameters need schema validation and error handling |
| Has side effects (creates, updates, deletes) | **Tool** (or excluded) | Side effects require explicit invocation |
| Has complex validation or business logic | **Tool** | Tools handle validation; resources don't |
| Is a CLI command | **Tool** | Commands have flags/args that map to parameters |
| Is a REST endpoint | **Tool** | Endpoints map cleanly to tool call/response |
| Is stable, URI-addressable reference data | **Resource** | Schema files, config templates, docs pages |
| Is a canned workflow prompt | **Prompt** | Only expose if clearly high-value and reusable |
| Is authentication configuration | Neither (env var in README) | Not an operation; handled at server startup |

**Practical rule**: When in doubt, use a Tool. Resources are for genuinely static or template-URI-addressable data (e.g., `schema://users`, `docs://authentication`). Prompts are rarely needed.

---

## Tool Naming Convention

Format: `{service}_{verb}_{noun}` — all lowercase, underscores as separators.

| Component | Rules |
|-----------|-------|
| `{service}` | Short name of the target service (1–2 words max). Examples: `github`, `jira`, `kubectl`, `pg` |
| `{verb}` | Action word. Prefer: `get`, `list`, `search`, `create`, `update`, `delete`. Avoid: `fetch`, `retrieve`, `obtain` |
| `{noun}` | Primary entity being operated on. Use singular for single-entity ops, plural for list ops |

**Examples**:
- `github_get_issue` — get a single issue by number
- `github_list_issues` — list issues with filters
- `github_get_issue_with_comments` — merged tool (issue + its comments together)
- `jira_search_issues` — JQL search
- `kubectl_get_pod_logs` — get logs for a specific pod
- `pg_execute_query` — execute a read-only SQL query

**Anti-examples**:
- `fetchIssue` — wrong case, wrong separator
- `get_github_data` — too vague, doesn't name the entity
- `github_retrieve_an_issue_by_its_number` — verbose, not idiomatic

---

## Workflow-Tool vs API-Wrapper Rule

**The most important design decision in Phase 2.**

An MCP server with 30 narrow tools is worse than one with 10 workflow tools. When a model uses the server, it must select the right tool. Many similar tools create decision paralysis and waste tool-call turns.

### The Test

Ask for each pair of operations: "Would a user ever call operation A without also wanting the result of operation B?"

- If **usually no** → merge into one tool
- If **sometimes no** → consider merging; add the secondary data as an optional field

### Common Merges

| Separate (wrong) | Merged (right) | Reasoning |
|-----------------|----------------|-----------|
| `github_get_issue` + `github_get_issue_comments` | `github_get_issue_with_context` | Reading an issue without its comments rarely serves a purpose |
| `kubectl_get_pod` + `kubectl_get_pod_logs` | `kubectl_get_pod_status` (returns pod + recent logs) | Debugging pods always needs both |
| `jira_get_issue` + `jira_get_issue_transitions` | `jira_get_issue_with_workflow` | Workflow state is always relevant when viewing an issue |

### Granularity Target

| Tool count | Assessment |
|------------|-----------|
| 3–5 | Acceptable for narrow services; check you haven't over-merged |
| 5–15 | Ideal range. Tools are specific but not overlapping |
| 15–20 | Warning zone. Review for merging opportunities |
| > 20 | Stop. Group before proceeding. Return to grouping step |

---

## Destructive Tool Handling

By default (no `--allow-destructive` flag):
1. Read every write operation from `analysis.md` → Write Operations section
2. Do NOT include any of them in `design.md`
3. Add a single `design.md` section: "Excluded Operations" listing what was dropped and why

If `--allow-destructive` is set:
1. Include write operations as tools
2. Mark each with `annotations: { destructiveHint: true, idempotentHint: false }`
3. Write an explicit warning in `design.md`: "These tools modify data. Review carefully."
4. Still ask for user confirmation at the Phase 2 gate about the destructive tools specifically

---

## Transport Selection Rules

| If... | Then transport = |
|-------|----------------|
| Target is a local CLI tool or library | stdio |
| Target's README describes a base URL to call | HTTP |
| Target repo has an Express/FastAPI/Django server as its main component | HTTP |
| Target repo IS the server you're calling | HTTP |
| Uncertain | stdio (safer default; can always add HTTP later) |

Record the transport decision and its reason in `design.md`.

---

## Parameter Schema Guidance

For each tool, specify parameters with this precision:

```
name: {param_name}
  type: string | number | boolean | array | object
  required: yes | no
  description: {what this controls, in plain language}
  example: {a realistic example value}
```

**Required vs optional**:
- Required: parameters needed to identify the target resource (e.g., `owner`, `repo`, `issue_number`)
- Optional: filters, pagination, format preferences (e.g., `state: "open"`, `limit: 20`)

**Type choices**:
- Prefer `string` for identifiers, even numeric-looking ones (e.g., issue numbers → string for flexibility)
- Use `number` for quantities and numeric comparisons
- Use `boolean` for flags (e.g., `include_comments: true`)
- Avoid `object` for top-level parameters — flatten into individual fields

**Description format**:
- One sentence, plain language
- Include valid values if constrained: `"Filter by state. One of: open, closed, all"`
- Include units for numeric params: `"Maximum number of results to return. Default: 20, max: 100"`

---

## Output Format for `design.md`

```markdown
# MCP Server Design: {Server Name}

## Target Service
{service name and one-line description from analysis.md}

## Configuration
- Target language: TypeScript | Python
- Transport: stdio | HTTP
- Server name (slug): {service}-mcp-server
- Auth: {how the server will read credentials}

## Tools

### {tool_name}
**Description**: {2–3 sentences: what this does, for what use case, what it returns}

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| {param} | {type} | yes/no | {description} |

**Response**: {describe the structure of the successful response}

**Annotations**:
- readOnlyHint: true | false
- destructiveHint: true | false
- idempotentHint: true | false

---

{repeat for each tool}

## Resources (if any)

### {resource_uri_template}
**Description**: {what this resource contains}
**MIME type**: {text/plain | application/json | text/markdown}

## Excluded Operations
{List of write operations excluded because --allow-destructive was not set}

## Notes
{Any design decisions, trade-offs, or warnings for the user to review}
```
