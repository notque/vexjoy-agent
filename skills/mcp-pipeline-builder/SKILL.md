---
name: mcp-pipeline-builder
description: |
  Convert any repository into a registered MCP server: ANALYZE → DESIGN →
  GENERATE → VALIDATE → EVALUATE → REGISTER. Point at a repo URL or local
  path, get a working MCP server registered with Claude Code. Use for "mcp
  pipeline", "repo to mcp", "create mcp from repo", "generate mcp",
  "mcp builder", "mcp from repo". Do NOT use for modifying an existing MCP
  server or building against a known API specification (use mcp-builder instead).
version: 1.0.0
user-invocable: true
command: /mcp-pipeline
agent: mcp-local-docs-engineer
routing:
  triggers:
    - mcp pipeline
    - repo to mcp
    - create mcp from repo
    - generate mcp
    - mcp builder
    - mcp from repo
  pairs_with:
    - workflow-orchestrator
    - systematic-debugging
  complexity: Complex
  category: pipeline
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Edit
---

# MCP Pipeline Builder

## Purpose

Automate the path from "I have a repo" to "I have a working MCP server registered with Claude Code." The pipeline derives what to expose by analyzing the repository — no prior knowledge required from the user.

**Input**: A repository URL or local path (e.g., `https://github.com/org/repo` or `/home/user/my-tool`).
**Output**: A compiled, registered MCP server entry in `~/.claude.json` or `.claude/settings.json`.

---

## Operator Context

**Note on `context: fork`**: This pipeline intentionally does NOT declare `context: fork`, unlike other multi-phase pipeline skills. The Phase 2 human review gate requires interactive back-and-forth with the user; forked context would isolate that interaction from the parent session. The trade-off (larger parent context) is acceptable given the Phase 2 gate is the pipeline's most important safety mechanism.

### Hardcoded Behaviors (Always Apply)

- **Human Review Gate at Phase 2**: ALWAYS pause after producing `design.md` and show it to the user before generating any code. The user must explicitly say "yes", "proceed", or "y" before Phase 3 begins. This gate exists because Phase 1 analysis is imperfect — catching a wrong tool name costs seconds; fixing generated code costs minutes.
- **Read-Only Default**: Only read operations are mapped to tools unless the user passes `--allow-destructive`. Phase 1 must classify every operation as read or write. Phase 2 silently drops all write operations from the design unless `--allow-destructive` is set.
- **Append-Only Config Registration**: Phase 6 reads the existing config file before writing. It NEVER overwrites existing `mcpServers` entries. If the target server name already exists in the config, Phase 6 prints a warning and exits without modifying the file.
- **3-Iteration Fix Limit**: Phase 4 attempts to fix compilation errors automatically. After 3 failed iterations, the pipeline halts and surfaces all errors to the user. It does not retry a fourth time.
- **Artifact-First Execution**: Every phase produces a saved artifact before proceeding. If a phase artifact does not exist, the pipeline re-runs that phase rather than proceeding from stale state.

### Default Behaviors (ON unless disabled)

- **TypeScript Target Language**: Phase 3 generates TypeScript with `@modelcontextprotocol/sdk` + Zod unless `--python` is passed.
- **stdio Transport**: Default transport is stdio (local subprocess). Phase 1 may override this to HTTP if it detects the target is a running web service.
- **Workflow Tools Over API Wrappers**: Phase 2 enforces the 5–15 tool granularity target. Operations that would always be called together are merged.
- **Evaluation Gate**: Phase 5 requires accuracy ≥ 7/10 before proceeding to registration. One regeneration attempt is permitted below that threshold.

### Optional Behaviors (OFF unless enabled)

- **`--python`**: Generate Python FastMCP instead of TypeScript. Best when the target is a Python library with a clean importable API. Enable by passing `--python` on invocation.
- **`--allow-destructive`**: Include write, update, and delete operations in the design. Enable by passing `--allow-destructive`. Requires explicit user decision — prompt for confirmation even when flag is set.
- **`--dry-run`**: Phase 6 prints the config snippet without writing to disk. Enable by passing `--dry-run`.
- **`--import`**: For Python targets only. Import the target library directly rather than calling it via subprocess/HTTP. Enable by passing `--import`. Only valid with `--python`.

---

## Instructions

### Artifact Locations

All pipeline artifacts are written relative to the current working directory:

```
mcp-design/{repo-slug}/
  analysis.md             ← Phase 1 output
  design.md               ← Phase 2 output (human-reviewed)
  {server-name}/          ← Phase 3 output (full project tree)
    src/index.ts          (or src/main.py for Python)
    package.json          (or pyproject.toml)
    README.md
  evaluation-report.md    ← Phase 5 output
```

The `{repo-slug}` is derived from the repository name: lowercase, hyphens for separators, no special characters.

---

### PHASE 1: ANALYZE

**Input**: Repository URL or local path (from user invocation).
**Output artifact**: `mcp-design/{repo-slug}/analysis.md`

#### Tasks

1. **Fetch the repository**: If a URL is given, clone or read via the web. If a local path is given, read directly.
2. **Identify stack**: Language(s), primary framework, package manager. See `references/analysis-checklist.md` → Stack Identification.
3. **Discover API surface**: REST endpoints, CLI commands, exported functions/classes. See `references/analysis-checklist.md` → API Surface Discovery.
4. **Identify auth mechanisms**: What credentials does this service require? (env vars, API key, OAuth, JWT). See `references/analysis-checklist.md` → Auth Pattern Recognition.
5. **Map data entities**: What "nouns" does this system manage? (users, issues, events, records)
6. **Classify operations as read or write**: Apply the explicit heuristic from `references/analysis-checklist.md` → Read/Write Classification. Every operation gets a classification.
7. **Detect transport signal**: Does the repo describe or expose a running HTTP server? If yes, note "HTTP transport candidate" in analysis.
8. **Estimate tool count**: Count meaningful read operations. If > 20, identify grouping opportunities.

#### Questions Phase 1 Must Answer

- What does this repo DO? (service purpose, one sentence)
- What are the primary entities (nouns)? → Candidate resources
- What are the primary operations (verbs)? → Candidate tools
- What requires auth? How is auth passed?
- Which operations are destructive or irreversible?
- What is the recommended transport? (stdio or HTTP)

#### Output Format

Write `mcp-design/{repo-slug}/analysis.md` with the schema from `references/analysis-checklist.md` → Output Format.

**GATE**: `analysis.md` must exist and contain all seven sections (`Service Purpose`, `Stack`, `Auth`, `Entities`, `Operations`, `Tool Count Signal`, `Notes`) before Phase 2 begins.

---

### PHASE 2: DESIGN

**Input**: `mcp-design/{repo-slug}/analysis.md`
**Output artifact**: `mcp-design/{repo-slug}/design.md`

#### Tasks

1. **Select target language**: TypeScript (default) or Python if `--python` is set. Record the decision and rationale in design.md.
2. **Select transport**: stdio (default) or HTTP if Phase 1 flagged the target as a service. Record decision.
3. **Assign operations to primitives**: Use the heuristic table from `references/design-rules.md` → Primitive Selection. In brief: tools for operations requiring parameters or having side effects; resources for stable, URI-addressable reference data; prompts only if clearly high-value.
4. **Filter destructive operations**: If `--allow-destructive` is NOT set, exclude all write/update/delete operations. Log each exclusion.
5. **Name each tool**: Follow `{service}_{verb}_{noun}` snake_case convention. See `references/design-rules.md` → Tool Naming.
6. **Apply workflow-tool heuristic**: If two tools would always be called in sequence, merge them. Target 5–15 tools total. See `references/design-rules.md` → Tool Granularity.
7. **Write tool descriptions and parameter schemas in prose**: Pre-code specification. Each tool entry must have: name, description (2–3 sentences), parameters (name, type, required/optional, description), expected response format, annotations (readOnlyHint, destructiveHint, idempotentHint).
8. **Write resource definitions** (if any): URI template, description, mime type.

#### Output Format

Write `mcp-design/{repo-slug}/design.md` with the schema from `references/design-rules.md` → Output Format.

#### MANDATORY GATE — Human Review

**PAUSE HERE. Do not proceed to Phase 3.**

Show the user:
1. The full contents of `design.md`
2. The tool count and names as a summary list
3. The question: **"Proceed with generation? (y/edit/abort)"**

- If "y" or "proceed": continue to Phase 3
- If "edit": apply the user's edits to `design.md`, then re-ask
- If "abort": stop pipeline; artifacts remain on disk for manual continuation

This gate exists because Phase 1 analysis may misidentify the relevant API surface or pick wrong primitive types. A wrong `design.md` produces hundreds of lines of wrong code. User review at this point costs seconds.

**Do NOT rationalize skipping this gate.** No time pressure, confidence level, or apparent obviousness of the design justifies proceeding without explicit user approval.

---

### PHASE 3: GENERATE

**Input**: `mcp-design/{repo-slug}/design.md` + access to target repo source code.
**Output artifact**: `mcp-design/{repo-slug}/{server-name}/` (full project tree)

The `{server-name}` comes from the design.md header (e.g., `github-mcp-server`).

#### TypeScript Project Structure (default)

```
{server-name}/
  package.json
  tsconfig.json
  src/
    index.ts          ← McpServer init, transport, tool registrations
    tools/            ← one file per tool or tool group
    services/
      client.ts       ← shared API client or subprocess wrapper
    schemas/          ← Zod schemas for request/response types
  README.md
```

Follow patterns from `references/ts-scaffold-template.md`:
- Tool annotations: set `readOnlyHint: true` on all read tools
- Error handling: always return text content on error; do not throw
- Auth pattern: read from `process.env.SERVICE_API_KEY`; throw if missing
- Import style: use named imports from `@modelcontextprotocol/sdk/server/mcp.js`

#### Python Project Structure (`--python`)

```
{server-name}/
  pyproject.toml
  src/
    main.py           ← @mcp.tool decorators, mcp.run()
    client.py         ← shared client class
  README.md
```

Follow patterns from `references/python-scaffold-template.md`:
- Tool decorator: `@mcp.tool` with Pydantic v2 model for parameters
- Error handling: raise with clear message; FastMCP converts to MCP error
- Startup: `mcp.run(transport="stdio")`

#### Generation Approach

Generate tools one at a time from the design.md tool list. For each tool:
1. Read the target repo source code for the relevant operation
2. Implement the tool using the client approach (call target API/CLI), not import approach
3. Apply the auth pattern from analysis.md

**GATE**: All tools listed in design.md must be implemented. No stubs, no TODO comments in the generated code. Every file must be complete.

---

### PHASE 4: VALIDATE

**Input**: Generated project directory `mcp-design/{repo-slug}/{server-name}/`
**Output**: Build success confirmation or complete error list

#### Build Commands

- TypeScript: `cd {server-name} && npm install && npm run build`
- Python: `cd {server-name} && python -m py_compile src/main.py`

#### Fix Loop (Max 3 Iterations)

1. Run the build command. If it succeeds, proceed to Phase 5.
2. If it fails: parse the error output, identify the root cause, apply a fix.
3. Re-run the build.
4. Repeat up to 3 total attempts.

After 3 failures:
- Surface the full error output
- Explain the probable root cause
- Halt the pipeline
- Tell the user: "Manual intervention required. Fix the errors above and re-run from Phase 4."

Do not attempt a 4th iteration. Three failed iterations means the design has a structural problem that automated fixing cannot resolve.

**GATE**: Build must succeed before Phase 5 begins.

---

### PHASE 5: EVALUATE

**Input**: Compiled server + `mcp-design/{repo-slug}/analysis.md`
**Output artifact**: `mcp-design/{repo-slug}/evaluation-report.md`

#### Generate Q&A Pairs

Produce 10 evaluation question-answer pairs using the rules from `references/evaluation-guide.md`. Requirements:
- Read-only (do not modify state)
- Independently verifiable (answers exist in the repo data)
- Stable (answers do not change between runs)
- Format: `{"question": "...", "expected_answer_contains": "...", "tool_hints": ["tool_name"], "category": "get_single|list_filtered|search|metadata", "entity_type": "..."}` — see `references/evaluation-guide.md` → Q&A Pair Format for full field definitions

Use the heuristic: 2 Q&A pairs per major entity type from analysis.md.

#### Run Evaluation

1. Launch the compiled server as a stdio subprocess
2. For each Q&A pair: send the question via the MCP protocol, capture the response
3. Score each response: exact match = 1.0, partial = 0.5, wrong/missing = 0
4. Record tool call counts and timing per question

See `references/evaluation-guide.md` for the evaluation harness design and subprocess launch pattern.

#### Write Report

Write `mcp-design/{repo-slug}/evaluation-report.md` with:
- Overall accuracy score (X/10)
- Per-question results table
- Tool call counts per question
- Total evaluation time
- Any questions that errored or timed out

#### Accuracy Gate

- **Accuracy ≥ 7/10**: Proceed to Phase 6.
- **Accuracy < 7/10**: Attempt one Phase 3 regeneration (re-run GENERATE with additional guidance derived from which questions failed). Then re-run Phase 4 and Phase 5.
- **If accuracy still < 7/10 after regeneration**: Surface the evaluation report, explain which tools are failing, halt the pipeline. Do not attempt a third generation pass.

**GATE**: Accuracy ≥ 7/10 required to proceed to Phase 6.

---

### PHASE 6: REGISTER

**Input**: Compiled server path + transport type from Phase 3.
**Output**: MCP server entry written to config; confirmation printed.

#### Config Target Selection

Pass `--project` to write to `.claude/settings.json` in the current directory (project-level config). Omit `--project` to write to `~/.claude.json` (global config, the default). The script does not auto-detect which config to use — the flag is required to select project scope. If `~/.claude.json` does not exist, it is created.

#### Registration

Run the registration script:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/register_mcp.py \
  --name {server-slug} \
  --command node \
  --args {absolute-path-to-dist/index.js} \
  [--env SERVICE_API_KEY=...] \
  [--dry-run] \
  [--project]
```

For Python servers:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/register_mcp.py \
  --name {server-slug} \
  --command python3 \
  --args {absolute-path-to-src/main.py} \
  [--env SERVICE_API_KEY=...] \
  [--dry-run] \
  [--project]
```

With `--dry-run`: print the config snippet only; do not write.

#### Post-Registration Output

After successful registration, the script prints:

```
MCP server registered: {server-name}
Config location: {path}

Config snippet written:
{full JSON snippet}

Restart Claude Code to activate the new MCP server.
```

The pipeline agent should additionally inform the user: "Test with `/mcp` or the Claude Code MCP menu after restarting."

**GATE**: If `--dry-run` is set, stop here. Do not write config.

---

## Error Handling

### Phase 1: Analysis Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| Cannot clone/read repo | Invalid URL, auth required, network issue | Ask user for local path or credentials |
| No API surface found | Repo is data-only, no operations | Inform user: this repo may not produce a useful MCP server |
| Too many operations (>40) | Large API surface | Phase 2 will enforce grouping; warn user that design may simplify significantly |

### Phase 2: Design Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| Zero tools after filtering | All operations are write-only | Inform user; suggest `--allow-destructive` if appropriate |
| User aborts at gate | User doesn't like the design | Artifacts remain; user can edit `design.md` manually and re-run from Phase 3 |

### Phase 4: Validation Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| npm not found | Node.js not installed | Inform user; suggest `brew install node` or `nvm install` |
| Type errors in generated code | Zod/TypeScript mismatch | 3-iteration fix loop handles these automatically |
| Import errors | Wrong module path | Fix loop resolves; if not after 3 passes, surface and halt |
| Still failing after 3 passes | Structural design problem | Halt; show errors; ask user to review design.md |

### Phase 5: Evaluation Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| Server fails to start | Build artifact missing or wrong path | Re-run Phase 4 |
| All Q&A fail | Tools return wrong format or error | Regeneration pass triggered automatically |
| Evaluation times out | Server hangs | Kill subprocess; report timeout; check tool implementations |

### Phase 6: Registration Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| Server name already exists | Previous run registered same server | Print warning; do not overwrite; suggest `--name {new-name}` |
| Config file unwritable | Permission error | Report path; suggest `chmod` or manual edit |

---

## Anti-Patterns

### Skipping the Phase 2 Gate

Rationalizing: "The design is obviously correct, no need to pause."
Why wrong: Phase 1 analysis is probabilistic. The user knows their target repo; the model does not. A 30-second review catches a wrong tool scope that would take 10 minutes to debug in generated code.

### Generating API Wrappers

Rationalizing: "I'll expose every endpoint as a tool — comprehensive coverage."
Why wrong: 30 tools with vague descriptions is worse than 8 tools with clear workflow semantics. The model wastes turns selecting between near-identical options. Phase 2 must enforce the 5–15 tool target.

### Continuing Past 3 Fix Iterations

Rationalizing: "Just one more iteration — this error looks simple."
Why wrong: If three targeted fix passes haven't resolved it, the design has a structural problem. More iterations produce increasingly speculative fixes. Surface the error and halt.

### Writing Config Without Read-First

Rationalizing: "I'll just write the new entry — the config is probably empty."
Why wrong: The config may contain other MCP server entries the user depends on. Always read before write. `register_mcp.py` enforces this.

### Exposing Destructive Operations by Default

Rationalizing: "The user probably wants full CRUD coverage."
Why wrong: A model cannot reliably determine which write operations are safe to expose. Wrong assumptions here delete production data. Read-only is the safe default.

---

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "User seems impatient, I'll skip the design gate" | Impatience doesn't reduce the cost of wrong code generation | Show design.md; ask the question |
| "The analysis found obvious tools, design is clearly right" | Obvious to the model ≠ correct for the user's use case | Still show; still ask |
| "The build almost passes, 4th iteration will fix it" | Structural errors don't yield to more iterations | Surface errors; halt |
| "Accuracy is 6/10, close enough" | The gate exists because 6/10 means 40% of questions are wrong | Trigger regeneration pass |
| "Config file looks empty, safe to write directly" | Look ≠ verify; other entries may be present | read-before-write enforced by register_mcp.py |
| "I'll expose write tools too, it's more useful" | Usefulness judgment without user input is dangerous for destructive ops | Only expose write tools if `--allow-destructive` is set |

---

## References

- `references/analysis-checklist.md` — Phase 1 discovery checklist and output schema
- `references/design-rules.md` — Phase 2 primitive selection, naming, and granularity rules
- `references/ts-scaffold-template.md` — TypeScript project scaffold patterns for Phase 3
- `references/python-scaffold-template.md` — Python FastMCP scaffold patterns for Phase 3
- `references/evaluation-guide.md` — Phase 5 Q&A pair rules and evaluation harness design
- `scripts/register_mcp.py` — Phase 6 append-only config registration script
