# Generate CLAUDE.md — Examples and Error Handling

## Examples

### Example 1: Go sapcc Repository

User says: "generate claude.md"

Actions:
1. SCAN: Detect go.mod, parse Makefile targets (`make build`, `make check`, `make lint`), map `cmd/`, `internal/`, `pkg/` directories, find `_test.go` files with `testify` assertions
2. DETECT: Find `github.com/sapcc` imports in go.mod, load sapcc conventions (anti-over-engineering, error wrapping, go-makefile-maker)
3. GENERATE: Fill template with Go-specific content, add sapcc enrichment to Code Style and Testing sections, include error handling section
4. VALIDATE: Verify all `internal/` paths exist, confirm `make check` target exists in Makefile, no placeholders

Result: CLAUDE.md with sapcc-aware conventions, real Makefile commands, verified paths

---

### Example 2: Node.js/TypeScript Project

User says: "create a claude.md for this repo"

Actions:
1. SCAN: Detect `package.json`, extract npm scripts (`npm test`, `npm run build`, `npm run lint`), map `src/`, `tests/` directories, find `.test.ts` files with vitest
2. DETECT: Find express in dependencies, plan API Patterns section, no domain enrichment
3. GENERATE: Fill template with TypeScript content, include API patterns (Express routes, middleware), testing conventions (vitest, co-located tests)
4. VALIDATE: Verify all paths, confirm npm scripts exist, no generic filler

Result: CLAUDE.md with actual npm commands, Express API patterns, vitest testing conventions

---

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

**Solution**: Generate a minimal CLAUDE.md documenting only what can be verified (directory structure, language, test patterns). Note prominently in the Build and Test Commands section: "No build system detected — add build commands manually." Continue with all other phases.

---

### Error: CLAUDE.md Already Exists

**Cause**: Repository already has a CLAUDE.md (root or `.claude/` directory).

**Solution**: Write output to `CLAUDE.md.generated`. Show diff between existing and generated files. Suggest using `claude-md-improver` to merge improvements. Never overwrite without explicit user confirmation.

---

### Error: Unknown Language

**Cause**: No recognized language indicator files in the repository root.

**Solution**: Produce a language-agnostic CLAUDE.md focusing on directory structure, Makefile targets (if present), and any README content. Note the gap: "Language could not be auto-detected — add language-specific sections manually."

---

## Phase 3: Section Descriptions and Sapcc Enrichment

### Required Section Details

**Section 1 — Project Overview**: Use project name from config file and a description derived from README.md (first paragraph), go.mod module path, or package.json description. List 3-5 key concepts extracted from directory names and core module names. Extract relevant facts from README (project purpose, key concepts) but reframe for Claude's needs — README is for GitHub visitors, CLAUDE.md is for Claude sessions, so skip installation guides, badges, and user-facing documentation.

**Section 2 — Build and Test Commands**: Use ONLY commands found in Makefile, package.json scripts, or equivalent. Format as table. Include "check everything" command prominently. Include single-test and package-test commands. Never write `go test ./...` without checking the Makefile first because the project's canonical command may include flags, coverage, or race detection.

**Section 3 — Architecture**: Map directory structure from Phase 1 Step 4. Identify key components by reading entry points and core modules. Use absolute directory descriptions, not guesses.

**Section 4 — Code Style**: Document linter config findings, import ordering, naming conventions, and tooling that enforces style. Document CLI commands for linting and formatting — do not include IDE/editor setup because CLAUDE.md is read by Claude, not by editors.

**Section 5 — Testing Conventions**: Document test framework, assertion library, mocking approach, file naming pattern, and integration test requirements from Phase 1 Step 5.

**Section 6 — Common Pitfalls**: Derive from actual codebase analysis. Keep the pitfalls grounded in observed repository behavior because fabricated warnings erode trust. If nothing notable was found, include 1-2 based on the build system (e.g., "run make check before committing").

### Optional Section Details

- **Error Handling**: For Go repos, document wrapping conventions found in source. For sapcc repos, include `fmt.Errorf("...: %w", err)` pattern and note error checking tools from linter config.
- **Database Patterns**: Document the driver/ORM, migration tool, and key query patterns found in source.
- **API Patterns**: Document the framework, auth mechanism, and response format found in source.
- **Configuration**: Document config source (env vars, files, flags), key variables from `.env.example`, and override precedence.

### Sapcc Go Enrichment (apply when sapcc imports detected in Phase 2 Step 1)

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

---

## Phase 4 Validation Report Template

Display this summary after completing all validation steps:

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

---

## Detection Patterns

### Language Indicator Files

| File | Language/Framework |
|------|--------------------|
| `go.mod` | Go |
| `package.json` | Node.js / TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `Cargo.toml` | Rust |
| `pom.xml`, `build.gradle` | Java |
| `Gemfile` | Ruby |
| `mix.exs` | Elixir |

### Banned Generic Phrases (Phase 3 and Phase 4)

If any of the following appear in the generated output, replace with project-specific content or remove the section entirely:

- "use meaningful variable names"
- "write clean code"
- "follow best practices"
- "ensure code quality"
- "maintain consistency"
- "keep it simple"
- "write tests"
- "handle errors properly"

### Phase 4 Placeholder Patterns (grep target)

```bash
grep -E '\{[^}]+\}|TODO|FIXME|TBD|PLACEHOLDER' <output_file>
```
