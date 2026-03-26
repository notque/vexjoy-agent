---
name: generate-claudemd
description: |
  Generate a project-specific CLAUDE.md by analyzing the current repository's
  code, build system, and architecture. 4-phase pipeline: SCAN, DETECT,
  GENERATE, VALIDATE. Auto-detects language/framework and enriches output with
  domain-specific conventions (e.g., go-sapcc-conventions for sapcc Go repos).
  Use for "generate claude.md", "create claude.md", "init claude.md",
  "bootstrap claude.md", "make claude.md". Do NOT use for improving an existing
  CLAUDE.md (use claude-md-improver instead).
version: 1.0.0
user-invocable: false
command: /generate-claudemd
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Skill
routing:
  triggers:
    - generate claude.md
    - create claude.md
    - init claude.md
    - bootstrap claude.md
    - make claude.md
  pairs_with:
    - go-sapcc-conventions
    - codebase-overview
  complexity: Medium
  category: documentation
---

# Generate CLAUDE.md Skill

## Operator Context

This skill operates as an operator for CLAUDE.md generation, configuring Claude's behavior for systematic repository analysis and project-specific documentation creation. It implements a **4-phase pipeline** -- SCAN repo facts, DETECT domain enrichment, GENERATE from template, VALIDATE output -- producing a CLAUDE.md that makes new Claude sessions immediately productive.

### Hardcoded Behaviors (Always Apply)
- **Analyze Before Writing**: Every section MUST be derived from actual repo analysis (reading files, parsing configs, checking paths). Why: guessed content wastes the context window and teaches Claude wrong patterns for the project. Never fill a section from assumptions.
- **Template Conformance**: Output follows `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md` structure. Why: consistent structure means Claude sessions can parse CLAUDE.md predictably across projects.
- **Path Verification**: Every path mentioned in the output MUST exist. Every command MUST be runnable. Why: a CLAUDE.md with broken paths is worse than no CLAUDE.md -- it teaches Claude to trust wrong information.
- **No Generic Advice**: Phrases like "use meaningful variable names", "write clean code", or "follow best practices" are banned. Why: generic advice wastes tokens and provides zero signal. Only project-specific facts belong in CLAUDE.md.
- **No Overwrite Without Confirmation**: If CLAUDE.md already exists, write to `CLAUDE.md.generated` and show a diff. Why: overwriting an existing, potentially hand-tuned CLAUDE.md destroys work.

### Default Behaviors (ON unless disabled)
- **Domain Enrichment**: Auto-detect repo domain in Phase 2 and load domain-specific patterns (sapcc Go conventions, OpenStack patterns, etc.)
- **Makefile Analysis**: Parse Makefile targets for build commands rather than guessing. Why: the Makefile IS the source of truth for build commands in most repos.
- **License Header Detection**: Note SPDX conventions if present in source files

### Why No `context: fork`
This skill requires interactive user gates (confirmation when CLAUDE.md already exists, review of generated output). Running in a forked context would bypass these safety checks.

### Optional Behaviors (OFF unless enabled)
- **Subdirectory CLAUDE.md**: Generate per-package CLAUDE.md files for monorepos (on explicit request)
- **Minimal Mode**: Only 3 sections -- Overview, Commands, Architecture (on explicit request: "minimal claude.md")

## What This Skill CAN Do
- Analyze a repository and produce a complete, project-specific CLAUDE.md
- Detect language, framework, build system, and test infrastructure from config files
- Load domain-specific enrichment (sapcc Go conventions, OpenStack patterns, etc.)
- Verify every path and command in the generated output
- Safely handle repos that already have a CLAUDE.md

## What This Skill CANNOT Do
- Improve an existing CLAUDE.md (use `claude-md-improver` for that)
- Generate documentation for code it cannot read (private dependencies, encrypted configs)
- Understand runtime behavior (it reads static files, does not execute the project)
- Replace domain expertise (enrichment patterns are templates, not deep knowledge)

---

## Instructions

Execute all phases sequentially. Verify each gate before advancing. Load the template from `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md` before Phase 3.

### Phase 1: SCAN

**Goal**: Gather facts about the repository -- language, build system, directory structure, test patterns, config approach.

**Step 1: Check for existing CLAUDE.md**

```bash
ls -la CLAUDE.md .claude/CLAUDE.md 2>/dev/null
```

If a CLAUDE.md already exists:
- Inform the user: "CLAUDE.md already exists. Output will be written to CLAUDE.md.generated so you can compare."
- Set output path to `CLAUDE.md.generated`
- Continue with all phases (the generated file is still useful for comparison)

If no CLAUDE.md exists:
- Set output path to `CLAUDE.md`

**Step 2: Detect language and framework**

Check root directory for language indicators:

| File | Language/Framework |
|------|--------------------|
| `go.mod` | Go |
| `package.json` | Node.js / TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `Cargo.toml` | Rust |
| `pom.xml`, `build.gradle` | Java |
| `Gemfile` | Ruby |
| `mix.exs` | Elixir |

Read the detected config file to extract: project name, dependencies, language version.

For Go projects, also check:
```bash
# Read go.mod for module path and Go version
head -5 go.mod
```

For Node.js projects:
```bash
# Read package.json for name, scripts, and key dependencies
cat package.json | head -30
```

**Step 3: Parse build system**

Check for build tools and extract commands:

```bash
# Check for Makefile
ls Makefile makefile GNUmakefile 2>/dev/null

# If Makefile exists, extract targets
grep -E '^[a-zA-Z_-]+:' Makefile 2>/dev/null | head -20
```

Also check for:
- `package.json` scripts section
- `Taskfile.yml`
- `justfile`
- CI config (`.github/workflows/`, `.gitlab-ci.yml`)

Record: build command, test command, lint command, "check everything" command.

**Step 4: Map directory structure**

```bash
# Top-level directories with purpose indicators
ls -d */ 2>/dev/null
```

For Go projects, also examine:
```bash
# Internal packages
ls internal/ 2>/dev/null
ls cmd/ 2>/dev/null
ls pkg/ 2>/dev/null
```

Categorize directories by role (source, test, config, docs, build, vendor).

**Step 5: Find test patterns**

```bash
# Detect test framework and patterns
# Go
ls *_test.go 2>/dev/null | head -5
# Node.js
ls *.test.ts *.test.js *.spec.ts *.spec.js 2>/dev/null | head -5
# Python
ls test_*.py *_test.py 2>/dev/null | head -5
```

Read 1-2 representative test files to identify: test framework, assertion library, mocking approach, naming conventions.

**Step 6: Detect configuration approach**

```bash
# Environment-based config
ls .env.example .env.sample 2>/dev/null
# File-based config
ls config.yaml config.json *.toml *.ini 2>/dev/null
# Go flag-based or env-based
grep -r 'os.Getenv\|flag\.\|viper\.\|envconfig' --include='*.go' -l 2>/dev/null | head -5
```

**Step 7: Detect code style tooling**

```bash
# Linters and formatters
ls .golangci.yml .eslintrc* .prettierrc* .flake8 pyproject.toml .editorconfig 2>/dev/null
```

If a linter config exists, read it to extract key rules.

**Step 8: Check for license headers**

```bash
# Look for SPDX headers in source files
grep -r 'SPDX-License-Identifier' --include='*.go' --include='*.py' --include='*.ts' -l 2>/dev/null | head -3
```

If found, note the license type and header convention.

**GATE**: Language detected. Build targets identified. Directory structure mapped. Test patterns found (or noted as absent). Config approach documented. Proceed ONLY when gate passes.

---

### Phase 2: DETECT

**Goal**: Identify domain-specific enrichment sources based on repo characteristics.

**Step 1: Check for sapcc domain (Go repos)**

If Go project detected:

```bash
# Check go.mod for sapcc imports
grep -i 'sapcc\|sap-' go.mod 2>/dev/null
# Check for sapcc-specific packages
grep -r 'github.com/sapcc' --include='*.go' -l 2>/dev/null | head -5
```

If sapcc imports found, load enrichment from `go-sapcc-conventions` skill patterns:
- Anti-over-engineering principles
- Error wrapping conventions (`fmt.Errorf("...: %w", err)`)
- `must.Return` scope rules
- Testing patterns (table-driven tests, assertion libraries)
- Makefile management via `go-makefile-maker`

**Step 2: Check for OpenStack/Gophercloud**

```bash
grep -i 'gophercloud\|openstack' go.mod 2>/dev/null
grep -r 'gophercloud' --include='*.go' -l 2>/dev/null | head -5
```

If found, note OpenStack API patterns, Keystone auth, and endpoint catalog usage.

**Step 3: Detect database drivers**

```bash
# Go
grep -E 'database/sql|pgx|gorm|sqlx|ent' go.mod 2>/dev/null
# Node.js
grep -E '"pg"|"mysql"|"prisma"|"typeorm"|"knex"|"drizzle"' package.json 2>/dev/null
# Python
grep -E 'sqlalchemy|django|psycopg|asyncpg' pyproject.toml requirements.txt 2>/dev/null
```

If found, plan to include Database Patterns section.

**Step 4: Detect API frameworks**

```bash
# Go
grep -E 'gorilla/mux|gin-gonic|chi|echo|fiber|go-swagger' go.mod 2>/dev/null
# Node.js
grep -E '"express"|"fastify"|"koa"|"hono"|"next"' package.json 2>/dev/null
# Python
grep -E 'fastapi|flask|django|starlette' pyproject.toml requirements.txt 2>/dev/null
```

If found, plan to include API Patterns section.

**Step 5: Build enrichment plan**

Compile a list of which optional CLAUDE.md sections to include and which domain-specific patterns to apply:

```
Enrichment Plan:
- [ ] sapcc Go conventions (if sapcc imports detected)
- [ ] OpenStack/Gophercloud patterns (if gophercloud detected)
- [ ] Error Handling section (if Go, Rust, or explicit error patterns)
- [ ] Database Patterns section (if DB driver detected)
- [ ] API Patterns section (if API framework detected)
- [ ] Configuration section (if non-trivial config detected)
```

**GATE**: Enrichment sources identified. Domain-specific patterns loaded (or explicitly noted as not applicable). Enrichment plan documented. Proceed ONLY when gate passes.

---

### Phase 3: GENERATE

**Goal**: Load template, fill sections from scan results and enrichment, write CLAUDE.md.

**Step 1: Load template**

Read `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md` for the output structure.

**Step 2: Fill required sections**

Fill all 6 required sections from Phase 1 scan results:

**Section 1 -- Project Overview**: Use project name from config file and a description derived from README.md (first paragraph), go.mod module path, or package.json description. List 3-5 key concepts extracted from directory names and core module names.

**Section 2 -- Build and Test Commands**: Use ONLY commands found in Makefile, package.json scripts, or equivalent. Format as table. Include "check everything" command prominently. Include single-test and package-test commands.

**Section 3 -- Architecture**: Map directory structure from Phase 1 Step 4. Identify key components by reading entry points and core modules. Use absolute directory descriptions, not guesses.

**Section 4 -- Code Style**: Document linter config findings, import ordering (from reading actual source files), naming conventions (from actual code patterns), and tooling that enforces style.

**Section 5 -- Testing Conventions**: Document test framework, assertion library, mocking approach, file naming pattern, and integration test requirements from Phase 1 Step 5.

**Section 6 -- Common Pitfalls**: Derive from actual codebase analysis. Examples of real pitfalls:
- Build tool quirks (e.g., "Makefile is managed by go-makefile-maker -- do not edit directly")
- Dependency gotchas (e.g., "gophercloud v2 migration incomplete -- some packages still use v1")
- Test requirements (e.g., "integration tests require PostgreSQL running locally")
- Config requirements (e.g., "OS_AUTH_URL must be set for any OpenStack operation")

Do NOT invent pitfalls. If nothing notable was found, include 1-2 based on the build system (e.g., "run make check before committing").

**Step 3: Fill optional sections**

Based on the Phase 2 enrichment plan, fill applicable optional sections:

- **Error Handling**: For Go repos, document wrapping conventions found in source. For sapcc repos, include `fmt.Errorf("...: %w", err)` pattern and note error checking tools from linter config.
- **Database Patterns**: Document the driver/ORM, migration tool, and key query patterns found in source.
- **API Patterns**: Document the framework, auth mechanism, and response format found in source.
- **Configuration**: Document config source (env vars, files, flags), key variables from `.env.example`, and override precedence.

**Step 4: Apply domain enrichment**

For sapcc Go repos (detected in Phase 2 Step 1), integrate these patterns into the relevant sections:

In Code Style, add:
- Anti-over-engineering: prefer simple, readable solutions over clever abstractions
- Scope `must.Return` to init functions and test helpers only
- Error wrapping: always add context with `fmt.Errorf("during X: %w", err)`

In Testing Conventions, add:
- Table-driven tests as the default pattern
- Relevant assertion libraries detected in go.mod

In Common Pitfalls, add:
- go-makefile-maker manages the Makefile (if detected)
- Any sapcc-specific patterns found in the codebase

**Step 5: Write output**

Write the completed CLAUDE.md (or CLAUDE.md.generated) to the output path determined in Phase 1 Step 1.

If writing to `CLAUDE.md.generated`, also show the user a summary diff:
```bash
diff CLAUDE.md CLAUDE.md.generated 2>/dev/null || echo "New file created"
```

**GATE**: CLAUDE.md written. All required sections populated with project-specific content (no placeholders). Optional sections populated based on enrichment plan. Output path is correct. Proceed ONLY when gate passes.

---

### Phase 4: VALIDATE

**Goal**: Verify the generated CLAUDE.md is accurate, complete, and free of generic filler.

**Step 1: Verify all paths exist**

Extract every file path and directory path mentioned in the generated CLAUDE.md. Check each one:

```bash
# For each path mentioned in the output
test -e "<path>" && echo "OK: <path>" || echo "MISSING: <path>"
```

If any path is missing, fix or remove the reference.

**Step 2: Verify all commands parse**

Extract every command mentioned in the generated CLAUDE.md. Check each one exists:

```bash
# For each command mentioned (e.g., "make lint")
# Verify the tool exists
which <tool> 2>/dev/null || echo "MISSING: <tool>"
# For Makefile targets, verify the target exists
grep -q '^<target>:' Makefile 2>/dev/null || echo "MISSING TARGET: <target>"
```

If a command references a missing tool or target, fix or remove it.

**Step 3: Check for remaining placeholders**

Search the output for placeholder patterns:

```bash
grep -E '\{[^}]+\}|TODO|FIXME|TBD|PLACEHOLDER' <output_file>
```

If any placeholders remain, fill them from repo analysis or remove the containing section.

**Step 4: Check for generic filler**

Search the output for banned generic phrases:

```
- "use meaningful variable names"
- "write clean code"
- "follow best practices"
- "ensure code quality"
- "maintain consistency"
- "keep it simple"
- "write tests"
- "handle errors properly"
```

If any generic filler is found, replace with project-specific content or remove.

**Step 5: Report summary**

Display a validation report:

```
CLAUDE.md Generation Complete
==============================
Output: <path>
Sections: <count> required + <count> optional
Paths verified: <count> OK, <count> fixed
Commands verified: <count> OK, <count> fixed
Placeholders: <count> (should be 0)
Generic filler: <count> (should be 0)

Domain enrichment applied:
- <enrichment 1>
- <enrichment 2>

Next steps:
- Review the generated file
- If CLAUDE.md.generated: compare with existing CLAUDE.md and merge manually
- Use /claude-md-improver to refine further
```

**GATE**: All paths resolve. All commands verified. No placeholders remain. No generic filler detected. Validation report displayed.

---

## Examples

### Example 1: Go sapcc Repository
User says: "generate claude.md"
Actions:
1. SCAN: Detect go.mod, parse Makefile targets (`make build`, `make check`, `make lint`), map `cmd/`, `internal/`, `pkg/` directories, find `_test.go` files with `testify` assertions
2. DETECT: Find `github.com/sapcc` imports in go.mod, load sapcc conventions (anti-over-engineering, error wrapping, go-makefile-maker)
3. GENERATE: Fill template with Go-specific content, add sapcc enrichment to Code Style and Testing sections, include error handling section
4. VALIDATE: Verify all `internal/` paths exist, confirm `make check` target exists in Makefile, no placeholders
Result: CLAUDE.md with sapcc-aware conventions, real Makefile commands, verified paths

### Example 2: Node.js/TypeScript Project
User says: "create a claude.md for this repo"
Actions:
1. SCAN: Detect `package.json`, extract npm scripts (`npm test`, `npm run build`, `npm run lint`), map `src/`, `tests/` directories, find `.test.ts` files with vitest
2. DETECT: Find express in dependencies, plan API Patterns section, no domain enrichment
3. GENERATE: Fill template with TypeScript content, include API patterns (Express routes, middleware), testing conventions (vitest, co-located tests)
4. VALIDATE: Verify all paths, confirm npm scripts exist, no generic filler
Result: CLAUDE.md with actual npm commands, Express API patterns, vitest testing conventions

### Example 3: Existing CLAUDE.md
User says: "generate claude.md"
Actions:
1. SCAN: Find existing CLAUDE.md, set output to `CLAUDE.md.generated`, continue analysis
2. DETECT: Standard detection, no special domain
3. GENERATE: Write to `CLAUDE.md.generated`
4. VALIDATE: Show diff between existing and generated, suggest using claude-md-improver to merge
Result: CLAUDE.md.generated alongside existing file, with diff for comparison

---

## Error Handling

### Error: No Build System Detected
**Cause**: No Makefile, package.json scripts, Taskfile, or other build configuration found.
**Solution**: Generate a minimal CLAUDE.md documenting only what can be verified (directory structure, language, test patterns). Note prominently in the Build and Test Commands section: "No build system detected -- add build commands manually." Continue with all other phases.

### Error: CLAUDE.md Already Exists
**Cause**: Repository already has a CLAUDE.md (root or `.claude/` directory).
**Solution**: Write output to `CLAUDE.md.generated`. Show diff between existing and generated files. Suggest using `claude-md-improver` to merge improvements. Never overwrite without explicit user confirmation.

### Error: Unknown Language
**Cause**: No recognized language indicator files in the repository root.
**Solution**: Produce a language-agnostic CLAUDE.md focusing on directory structure, Makefile targets (if present), and any README content. Note the gap: "Language could not be auto-detected -- add language-specific sections manually."

---

## Anti-Patterns

### Anti-Pattern 1: Generic Filler Content
**What it looks like**: "Write clean, maintainable code" or "Follow best practices for error handling" in the generated CLAUDE.md.
**Why wrong**: Generic advice wastes context tokens and provides zero project-specific signal. Claude already knows generic best practices.
**Do instead**: Only include facts derived from actual repo analysis. "Error wrapping uses `fmt.Errorf('during %s: %w', action, err)` pattern (see `internal/api/handler.go`)" is useful. "Handle errors properly" is not.

### Anti-Pattern 2: Guessing Commands
**What it looks like**: Writing `go test ./...` without checking the Makefile, or `npm test` without reading package.json scripts.
**Why wrong**: The Makefile may wrap `go test` with flags, coverage, or race detection. Using the wrong command teaches Claude to skip project-specific tooling.
**Do instead**: Read the Makefile (or equivalent) first. Use the project's canonical commands. If `make check` exists, document `make check`, not the raw tool invocations.

### Anti-Pattern 3: Copying README Verbatim
**What it looks like**: Pasting the README's project description, installation steps, or usage examples into CLAUDE.md.
**Why wrong**: README is for GitHub visitors (humans browsing the repo). CLAUDE.md is for Claude sessions (AI working in the codebase). Different audiences need different information. README covers "what is this and how to install it." CLAUDE.md covers "how to work effectively in this codebase."
**Do instead**: Extract relevant facts from README (project purpose, key concepts) but reframe for Claude's needs. Skip installation guides, badges, and user-facing documentation.

### Anti-Pattern 4: Including IDE Setup
**What it looks like**: Adding VS Code extensions, editor config, or debugging launch configurations to CLAUDE.md.
**Why wrong**: CLAUDE.md is read by Claude, not by editors. IDE setup belongs in README or CONTRIBUTING.md.
**Do instead**: Document CLI commands for linting, formatting, and testing. These are what Claude actually uses.

---

## Anti-Rationalization

### Domain-Specific Rationalizations

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I know this is a Go project, I can fill in standard Go patterns" | Standard patterns may not match this project's conventions | Read actual source files before writing any section |
| "The README has a good description, I'll use that" | README is for humans, CLAUDE.md is for Claude sessions | Extract facts, reframe for Claude's context |
| "No Makefile, but `go build` is obvious" | The project may use a custom build script or task runner | Document the gap, don't guess commands |
| "This section is optional, I'll skip the analysis" | Optional sections still require evidence if included | Either analyze properly or omit the section entirely |
| "The paths probably exist, no need to check each one" | Probably != verified. One broken path undermines trust | Check every path with `test -e` |
| "Generic advice is better than nothing" | Generic advice is worse than nothing -- it wastes tokens | Leave section out rather than fill with filler |

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md`: Template structure for generated CLAUDE.md files with required and optional sections
- Official Anthropic `claude-md-management:claude-md-improver`: Companion skill for improving existing CLAUDE.md files (use after generation for refinement)

### Companion Skills
- `go-sapcc-conventions`: Domain-specific patterns for sapcc Go repositories (loaded during Phase 2 enrichment)
- `codebase-overview`: Deeper codebase exploration when CLAUDE.md generation needs more architectural context
