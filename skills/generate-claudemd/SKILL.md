---
name: generate-claudemd
description: "Generate project-specific CLAUDE.md from repo analysis."
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
    - go-patterns
    - codebase-overview
  complexity: Medium
  category: documentation
---

# Generate CLAUDE.md Skill

4-phase pipeline: SCAN repo facts, DETECT domain enrichment, GENERATE from template, VALIDATE output. Produces a CLAUDE.md that makes new Claude sessions immediately productive with verified, project-specific facts.

Generates new CLAUDE.md files only. Use `claude-md-improver` to improve existing ones. Cannot document private dependencies or encrypted configs it cannot read, infer runtime behavior from static files, or replace deep domain expertise.

Does not use `context: fork` — requires interactive user gates (confirmation when CLAUDE.md exists, review of output).

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `CLAUDEMD_TEMPLATE.md` | Loads detailed guidance from `CLAUDEMD_TEMPLATE.md`. |
| example-driven tasks, errors | `examples-and-errors.md` | Loads detailed guidance from `examples-and-errors.md`. |

## Instructions

Execute all phases sequentially. Verify each gate before advancing. Load `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md` before Phase 3.

Optional modes (on explicit request only):
- **Subdirectory CLAUDE.md**: Per-package files for monorepos.
- **Minimal Mode** ("minimal claude.md"): Only Overview, Commands, Architecture.

> See `references/examples-and-errors.md` for worked examples and the language indicator table.

### Phase 1: SCAN

**Goal**: Gather repo facts — language, build system, directory structure, test patterns, config approach.

**Step 1: Check for existing CLAUDE.md**

```bash
ls -la CLAUDE.md .claude/CLAUDE.md 2>/dev/null
```

If exists, write to `CLAUDE.md.generated` and show diff — overwriting a hand-tuned CLAUDE.md destroys work. Continue all phases.

**Step 2: Detect language and framework**

Check root for language indicators (see `references/examples-and-errors.md` for the full table). Read the detected config file to extract project name, dependencies, language version. Do not assume standard patterns — read actual source files.

For Go: `head -5 go.mod`
For Node.js: `cat package.json | head -30`

**Step 3: Parse build system**

Parse the Makefile (or equivalent) for actual targets — the Makefile IS the source of truth and may wrap tools with flags/coverage/race detection that raw invocations miss.

```bash
ls Makefile makefile GNUmakefile 2>/dev/null
grep -E '^[a-zA-Z_-]+:' Makefile 2>/dev/null | head -20
```

Also check: `package.json` scripts, `Taskfile.yml`, `justfile`, CI config (`.github/workflows/`, `.gitlab-ci.yml`).

Record: build, test, lint, and "check everything" commands. If no build system found, document the gap.

**Step 4: Map directory structure**

```bash
ls -d */ 2>/dev/null
ls internal/ cmd/ pkg/ 2>/dev/null  # Go projects
```

Categorize directories by role (source, test, config, docs, build, vendor).

**Step 5: Find test patterns**

```bash
ls *_test.go 2>/dev/null | head -5          # Go
ls *.test.ts *.test.js 2>/dev/null | head -5 # Node.js
ls test_*.py *_test.py 2>/dev/null | head -5 # Python
```

Read 1-2 representative test files for: framework, assertion library, mocking approach, naming conventions.

**Step 6: Detect configuration approach**

```bash
ls .env.example .env.sample 2>/dev/null
ls config.yaml config.json *.toml *.ini 2>/dev/null
grep -r 'os.Getenv\|flag\.\|viper\.\|envconfig' --include='*.go' -l 2>/dev/null | head -5
```

**Step 7: Detect code style tooling**

```bash
ls .golangci.yml .eslintrc* .prettierrc* .flake8 pyproject.toml .editorconfig 2>/dev/null
```

If a linter config exists, read it for key rules.

**Step 8: Check for license headers**

```bash
grep -r 'SPDX-License-Identifier' --include='*.go' --include='*.py' --include='*.ts' -l 2>/dev/null | head -3
```

If found, note license type and header convention.

**GATE**: Language detected. Build targets identified. Directory structure mapped. Test patterns found (or noted absent). Config approach documented.

---

### Phase 2: DETECT

**Goal**: Identify domain-specific enrichment sources.

**Step 1: Check for sapcc domain (Go repos)**

```bash
grep -i 'sapcc\|sap-' go.mod 2>/dev/null
grep -r 'github.com/sapcc' --include='*.go' -l 2>/dev/null | head -5
```

If found, load enrichment from `go-patterns` skill: error wrapping, `must.Return` scope, table-driven tests, `go-makefile-maker`.

**Step 2: Check for OpenStack/Gophercloud**

```bash
grep -i 'gophercloud\|openstack' go.mod 2>/dev/null
grep -r 'gophercloud' --include='*.go' -l 2>/dev/null | head -5
```

If found, note OpenStack API patterns, Keystone auth, endpoint catalog usage.

**Step 3: Detect database drivers**

```bash
grep -E 'database/sql|pgx|gorm|sqlx|ent' go.mod 2>/dev/null
grep -E '"pg"|"mysql"|"prisma"|"typeorm"|"knex"|"drizzle"' package.json 2>/dev/null
grep -E 'sqlalchemy|django|psycopg|asyncpg' pyproject.toml requirements.txt 2>/dev/null
```

**Step 4: Detect API frameworks**

```bash
grep -E 'gorilla/mux|gin-gonic|chi|echo|fiber|go-swagger' go.mod 2>/dev/null
grep -E '"express"|"fastify"|"koa"|"hono"|"next"' package.json 2>/dev/null
grep -E 'fastapi|flask|django|starlette' pyproject.toml requirements.txt 2>/dev/null
```

**Step 5: Build enrichment plan**

```
Enrichment Plan:
- [ ] sapcc Go conventions (if sapcc imports detected)
- [ ] OpenStack/Gophercloud patterns (if gophercloud detected)
- [ ] Error Handling section (if Go, Rust, or explicit error patterns)
- [ ] Database Patterns section (if DB driver detected)
- [ ] API Patterns section (if API framework detected)
- [ ] Configuration section (if non-trivial config detected)
```

**GATE**: Enrichment sources identified. Domain-specific patterns loaded or noted as N/A. Enrichment plan documented.

---

### Phase 3: GENERATE

**Goal**: Load template, fill sections from scan results and enrichment, write CLAUDE.md. Every section must derive from actual repo analysis — guessed content wastes context and teaches wrong patterns.

**Step 1: Load template**

Read `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md`. Follow its structure exactly.

**Step 2: Fill required sections**

Fill all 6 required sections from Phase 1 results. No guesses, no fabrication.

> See `references/examples-and-errors.md` (Phase 3: Section Descriptions) for per-section rules, optional section guidelines, and banned generic phrases.

**Step 3: Fill optional sections** from Phase 2 enrichment plan. Omit sections without evidence.

**Step 4: Apply domain enrichment**

> See `references/examples-and-errors.md` (Sapcc Go Enrichment) for patterns to integrate when sapcc imports were detected.

**Step 5: Write output**

Write to the path from Phase 1 Step 1. Verify every path exists and every command is runnable before writing — a CLAUDE.md with broken paths is worse than none.

If writing to `CLAUDE.md.generated`:
```bash
diff CLAUDE.md CLAUDE.md.generated 2>/dev/null || echo "New file created"
```

**GATE**: CLAUDE.md written. All required sections populated with project-specific content. No placeholders. Optional sections filled per enrichment plan.

---

### Phase 4: VALIDATE

**Goal**: Verify accuracy, completeness, no generic filler.

**Step 1: Verify all paths exist**

```bash
test -e "<path>" && echo "OK: <path>" || echo "MISSING: <path>"
```

Fix or remove any missing references.

**Step 2: Verify all commands parse**

```bash
which <tool> 2>/dev/null || echo "MISSING: <tool>"
grep -q '^<target>:' Makefile 2>/dev/null || echo "MISSING TARGET: <target>"
```

**Step 3: Check for placeholders**

```bash
grep -E '\{[^}]+\}|TODO|FIXME|TBD|PLACEHOLDER' <output_file>
```

Fill from repo analysis or remove the containing section.

**Step 4: Check for generic filler**

> See `references/examples-and-errors.md` for banned phrases. Search for each; remove or replace any found.

**Step 5: Report summary** — display validation report from `references/examples-and-errors.md`.

**GATE**: All paths resolve. All commands verified. No placeholders. No generic filler. Validation report displayed.

---

## References

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/CLAUDEMD_TEMPLATE.md`: Template structure with required and optional sections
- `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`: Worked examples, error handling, language indicators, banned phrases
- Official Anthropic `claude-md-management:claude-md-improver`: Companion skill for improving existing files

### Companion Skills

- `go-patterns`: Domain-specific patterns for sapcc Go repos (Phase 2 enrichment)
- `codebase-overview`: Deeper exploration when generation needs more architectural context
