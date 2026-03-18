---
name: codebase-overview
description: |
  Systematic 4-phase codebase exploration: Detect, Explore, Map, Summarize.
  Use when starting work on an unfamiliar codebase, onboarding to a new project,
  reviewing a repository for the first time, or building context before debugging
  or code review. Use for "explore codebase", "what does this project do",
  "understand architecture", or "onboard me". Do NOT use for modifying files,
  running applications, performance optimization, or deep domain analysis.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
context: fork
---

# Codebase Overview Skill

## Operator Context

This skill operates as an operator for systematic codebase exploration, configuring Claude's behavior for rigorous, evidence-based discovery. It implements the **Phased Discovery** architectural pattern -- Detect project type, Explore key files, Map architecture, Summarize findings -- with **Domain Intelligence** embedded in language-specific exploration strategies.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before exploration
- **Over-Engineering Prevention**: Explore only what's needed for the overview. No speculative deep-dives, no "while I'm here" tangents
- **Read-Only Operations**: NEVER modify, create, or delete project files
- **Evidence Required**: Every architectural claim MUST cite an examined file and path
- **Systematic Phases**: Follow DETECT -> EXPLORE -> MAP -> SUMMARIZE in order
- **Project Agnostic**: Work across any language, framework, or build system
- **Absolute Paths**: All file references in output MUST use absolute paths

### Default Behaviors (ON unless disabled)
- Report facts without self-congratulation; show evidence, not descriptions
- Start from current working directory
- Examine up to 20 key files per category
- Include recent commit themes (last 10 commits)
- Generate structured markdown report to stdout
- Exclude noise directories: `node_modules/`, `venv/`, `vendor/`, `dist/`, `build/`, `__pycache__/`
- Remove any temporary files created during exploration at completion
- Show absolute file paths in all output

### Optional Behaviors (OFF unless enabled)
- Deep dive into specific subsystems (on explicit request)
- Generate architecture diagrams (requires explicit request)
- Include full file contents in report (vs summaries)
- Export findings to separate file (vs stdout)
- Analyze dependency vulnerability status

## What This Skill CAN Do
- Systematically discover project type, tech stack, and architecture
- Identify entry points, core modules, data models, and API surfaces
- Map design patterns and key abstractions with file-level evidence
- Produce actionable onboarding documentation for new contributors
- Work across any language and framework without prior knowledge

## What This Skill CANNOT Do
- Modify, create, or delete any files in the target project
- Run the application or execute its test suite
- Provide deep domain expertise (use specialized agent instead)
- Replace reading the codebase (this accelerates, not replaces)
- Skip any of the 4 phases

---

## Instructions

Execute all phases autonomously. Verify each gate before advancing. Consult `references/exploration-strategies.md` for language-specific discovery commands.

### Phase 1: DETECT

**Goal**: Determine project type, language, framework, and tech stack.

**Step 1: Examine root directory**

```bash
ls -la
```

Identify configuration files that indicate project type:
- `package.json` -> Node.js/JavaScript/TypeScript
- `go.mod` -> Go
- `pyproject.toml`, `requirements.txt`, `setup.py` -> Python
- `pom.xml`, `build.gradle` -> Java
- `Cargo.toml` -> Rust
- See `references/exploration-strategies.md` for complete indicator table

**Step 2: Read primary configuration**

Based on detected type, read the main config file. Preference order:
- Python: `pyproject.toml` > `setup.py` > `requirements.txt`
- Node.js: `package.json`
- Go: `go.mod`

Extract: project name, dependencies, language version, build system, scripts/commands.

**Step 3: Identify frameworks and tooling**

Search for framework-specific files:

```bash
# Frameworks
ls -la manage.py next.config.js nuxt.config.js angular.json 2>/dev/null

# Build and infrastructure
ls -la Makefile Dockerfile docker-compose.yml 2>/dev/null
ls -la .github/workflows/ 2>/dev/null
```

**Step 4: Check for CLAUDE.md**

Read any `.claude/CLAUDE.md` or `CLAUDE.md` in the repository root. Follow its instructions throughout remaining phases.

**Step 5: Document findings**

```markdown
## DETECT Results
- Language: [detected language + version]
- Framework: [detected framework + version]
- Build system: [build tool]
- Key dependencies: [top 5-10]
- Run command: [from scripts/Makefile]
- Test command: [from scripts/Makefile]
```

**Gate**: Project type identified (language + framework). Tech stack documented. Build/run commands known. Proceed ONLY when gate passes.

### Phase 2: EXPLORE

**Goal**: Discover entry points, core modules, data models, API surfaces, configuration, and tests.

**Step 1: Find entry points**

Use language-specific patterns from `references/exploration-strategies.md`. Read each entry point file to understand application bootstrapping.

For any language, look for:
- `main` functions or `__main__` modules
- Server/app initialization files
- CLI entry points declared in config

**Step 2: Map directory structure**

```bash
find . -type d \
  -not -path '*/\.*' \
  -not -path '*/node_modules/*' \
  -not -path '*/venv/*' \
  -not -path '*/vendor/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  | head -50
```

Categorize directories by layer:

| Pattern | Layer |
|---------|-------|
| `models/`, `db/`, `schema/`, `entities/` | Data |
| `api/`, `routes/`, `handlers/`, `controllers/` | API |
| `services/`, `lib/`, `core/`, `domain/` | Business logic |
| `utils/`, `helpers/`, `common/` | Utilities |
| `tests/`, `test/`, `__tests__/` | Tests |
| `config/`, `settings/` | Configuration |
| `cmd/`, `cli/` | CLI |

**Step 3: Examine data layer**

Search for model, schema, and entity files. Read 3-5 representative files.

```markdown
## Data Layer Findings
- Database: [technology]
- ORM: [library, if any]
- Key models:
  - [ModelName] ([file path]): [primary fields, relationships]
  - [ModelName] ([file path]): [primary fields, relationships]
- Migrations: [tool and location]
```

Document: entity relationships (which models reference which), primary data structures and their fields, database technology, migration strategy.

**Step 4: Discover API surface**

Search for route, handler, and controller files. Read 3-5 key API files.

```markdown
## API Surface Findings
- Type: [REST/GraphQL/gRPC]
- Auth: [JWT/OAuth/API keys/none]
- Key endpoints:
  - [METHOD] /path - [purpose] ([handler file])
  - [METHOD] /path - [purpose] ([handler file])
- Versioning: [strategy, if any]
```

Document: endpoint structure and URL patterns, HTTP methods and request/response formats, authentication and authorization patterns, API versioning strategy.

**Step 5: Identify configuration**

Find `.env.example`, config files, and settings modules.

```bash
# Environment configs
ls -la .env .env.example config.yaml config.json settings.py 2>/dev/null

# Environment-specific configs
ls -la config/*.yaml config/*.json config/*.toml 2>/dev/null
```

Document: required environment variables and their purpose, external service dependencies (databases, APIs, caches, queues), feature flags or runtime options.

**Step 6: Examine test structure**

Find test files and test configuration. Read 2-3 representative tests.

```bash
# Find test files (language-agnostic)
find . -name "*_test.*" -o -name "*.test.*" -o -name "*Test.*" -o -path "*/tests/*" \
  2>/dev/null | head -20
```

Document: testing framework, test organization (co-located vs separate directory), common patterns (fixtures, factories, mocks), coverage tooling.

**Gate**: Entry points identified. Core modules mapped. Data layer understood. API surface discovered. Configuration examined. Test structure documented. Proceed ONLY when gate passes.

### Phase 3: MAP

**Goal**: Synthesize findings into architectural understanding.

**Step 1: Identify design patterns**

Based on examined files, identify and document with evidence:

```markdown
## Design Patterns
- Architecture: [MVC/layered/microservices/etc.] (evidence: [file paths])
- Organization: [by-feature/by-layer] (evidence: [directory structure])
- Error handling: [exceptions/error returns/result types] (evidence: [file paths])
- Async patterns: [promises/async-await/goroutines/callbacks] (evidence: [file paths])
- DI approach: [manual/framework/none] (evidence: [file paths])
```

**Step 2: Map key abstractions**

Identify the 5-10 most important types, classes, or modules:

```markdown
## Key Abstractions
1. [TypeName] ([file path]): [responsibility, what depends on it]
2. [TypeName] ([file path]): [responsibility, what depends on it]
...
```

Document: core domain concepts, primary interfaces/abstractions, component communication (direct calls, events, queues).

**Step 3: Document data flow**

Trace a typical request from entry point through the full stack:

```markdown
## Request Flow (typical)
1. [/abs/path/main.py] - Starts server, registers routes
2. [/abs/path/routes/api.py] - Maps URL to handler
3. [/abs/path/handlers/user.py] - Validates input, calls service
4. [/abs/path/services/user.py] - Applies business logic
5. [/abs/path/models/user.py] - Persists to database
6. Response flows back through handler
```

**Step 4: Analyze recent activity**

```bash
git log --oneline --no-decorate -10
```

Categorize commits into themes:
- Feature development (new capabilities)
- Bug fixes (corrections)
- Refactoring (structural changes)
- Infrastructure (CI/CD, deployment, dependencies)

If not a git repository, note this limitation and skip this step.

**Gate**: Design patterns identified with file evidence. Key abstractions mapped (5-10 concepts). Data flow documented with absolute paths. Recent activity analyzed. Proceed ONLY when gate passes.

### Phase 4: SUMMARIZE

**Goal**: Generate structured overview report.

**Step 1: Generate report**

Use the template in `references/report-template.md`. Fill every section with evidence from examined files. Requirements:
- All file paths MUST be absolute
- All architectural claims MUST cite source files
- All commands MUST come from actual config files (package.json, Makefile, etc.)
- Empty sections MUST note why information is unavailable

**Step 2: Quality check**

Before outputting, verify:
- [ ] All 13 template sections addressed
- [ ] No placeholder text remains
- [ ] Every claim backed by file evidence
- [ ] Paths are absolute, not relative
- [ ] Commands are real, not guessed

**Step 3: Output report**

Display complete markdown report to stdout. If export behavior is enabled, also write to file.

**Gate**: Report has all sections filled. All paths are absolute. All claims cite evidence. Report is actionable for onboarding. Quality check passes. Total files examined count is accurate.

---

## Examples

### Example 1: New Project Onboarding
User says: "Help me understand this codebase"
Actions:
1. Check root for config files, identify Python/FastAPI project (DETECT)
2. Read `main.py`, map `src/` structure, examine `models/`, `routes/` (EXPLORE)
3. Identify layered architecture, map User/Order/Payment models, trace request flow (MAP)
4. Generate report with all sections, absolute paths, evidence citations (SUMMARIZE)
Result: Structured overview enabling immediate productive contribution

### Example 2: Pre-Review Context Building
User says: "I need to review a PR in this repo but don't know the codebase"
Actions:
1. Detect Go project with `go.mod`, identify Gin framework (DETECT)
2. Find `cmd/server/main.go` entry point, map `internal/` packages (EXPLORE)
3. Map handler -> service -> repository pattern, document gRPC + REST dual API (MAP)
4. Generate report focused on architecture and conventions (SUMMARIZE)
Result: Reviewer has architectural context for informed code review

### Example 3: Pre-Debug Context
User says: "I need to fix a bug but don't know this codebase yet"
Actions:
1. Detect Node.js/Express project from `package.json` (DETECT)
2. Find `src/index.ts` entry, map middleware chain, locate error handlers (EXPLORE)
3. Map request lifecycle through middleware -> router -> controller -> service (MAP)
4. Generate report emphasizing error handling patterns and test structure (SUMMARIZE)
Result: Debugger has structural context to apply systematic-debugging skill effectively

---

## Error Handling

### Error: "Cannot Determine Project Type"
Cause: No recognized configuration files in root directory
Solution:
1. Check if in a subdirectory (`pwd`)
2. Look for README that might indicate project type
3. Examine file extensions to infer dominant language
4. Document as "Unknown project type" and proceed with generic exploration

### Error: "Not a Git Repository"
Cause: Directory lacks `.git/` or git is not initialized
Solution: Skip git-related steps (recent commits, development activity). Note in report that version control info is unavailable. Continue with all other phases.

### Error: "Too Many Files to Examine"
Cause: Large monorepo, generated files, or broad project scope
Solution:
1. Limit to 20 files per category (default behavior)
2. Exclude noise directories
3. Focus on representative samples, not exhaustive coverage
4. Note in report: "Examined N of M files as representative samples"

### Error: "Permission Denied Reading File"
Cause: File permissions prevent reading
Solution: Skip the inaccessible file. Note in the "Files Examined" section which files were inaccessible. Continue with remaining files in that category.

---

## Anti-Patterns

### Anti-Pattern 1: Exploring Without Detecting Project Type
**What it looks like**: Reading random source files before checking config files
**Why wrong**: Wastes time, misinterprets code without framework context, produces inaccurate conclusions
**Do instead**: Complete Phase 1 (DETECT) first. Always read config before code.

### Anti-Pattern 2: Claims Without File Evidence
**What it looks like**: "This appears to use microservices" without citing any examined file
**Why wrong**: Violates evidence-required hardcoded behavior. Misleads readers. Cannot be verified.
**Do instead**: Every claim cites a file. Example: "Uses PostgreSQL (confirmed in `/abs/path/config/database.py`: `postgresql://...`)"

### Anti-Pattern 3: Exhaustive File Reading
**What it looks like**: Reading all 50+ files in `models/` directory instead of 3-5 representatives
**Why wrong**: Token bloat without proportional value. Violates over-engineering prevention.
**Do instead**: Limit to 20 files per category. Read representative samples. Note coverage in report.

### Anti-Pattern 4: Skipping Phase Gates
**What it looks like**: Jumping to MAP before finishing EXPLORE, or generating report with missing sections
**Why wrong**: Incomplete overview with critical gaps. Wrong architectural assumptions.
**Do instead**: Verify every gate condition before proceeding. Return to previous phase if information is missing.

### Anti-Pattern 5: Generic Report Output
**What it looks like**: Report with "This module handles business logic" and no file paths or specifics
**Why wrong**: Not actionable for onboarding. No better than reading a README.
**Do instead**: Include specific paths, line references, and exact commands from config files.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can infer the architecture from the README" | README may be outdated or incomplete | Examine actual source files |
| "Config files are enough to understand the project" | Config shows dependencies, not architecture | Read entry points and core modules |
| "20 files is enough for any project" | Some areas need deeper sampling | Adjust per category, note limitations |
| "Report looks complete" | Looking complete != being complete | Verify every section has file-backed evidence |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Standard markdown report template with all sections
- `${CLAUDE_SKILL_DIR}/references/exploration-strategies.md`: Language-specific discovery commands and patterns
