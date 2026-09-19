# Codebase Overview — Examples, Error Handling, and Parallel Agent Template

## Phase Output Templates

### DETECT Results Template

```markdown
## DETECT Results
- Language: [detected language + version]
- Framework: [detected framework + version]
- Build system: [build tool]
- Key dependencies: [top 5-10]
- Run command: [from scripts/Makefile]
- Test command: [from scripts/Makefile]
```

### Data Layer Findings Template

```markdown
## Data Layer Findings
- Database: [technology]
- ORM: [library, if any]
- Key models:
  - [ModelName] ([file path]): [primary fields, relationships]
- Migrations: [tool and location]
```

### API Surface Findings Template

```markdown
## API Surface Findings
- Type: [REST/GraphQL/gRPC]
- Auth: [JWT/OAuth/API keys/none]
- Key endpoints:
  - [METHOD] /path - [purpose] ([handler file])
- Versioning: [strategy, if any]
```

### Design Patterns Template (MAP Phase)

```markdown
## Design Patterns
- Architecture: [MVC/layered/microservices/etc.] (evidence: [file paths])
- Organization: [by-feature/by-layer] (evidence: [directory structure])
- Error handling: [exceptions/error returns/result types] (evidence: [file paths])
- Async patterns: [promises/async-await/goroutines/callbacks] (evidence: [file paths])
- DI approach: [manual/framework/none] (evidence: [file paths])
```

### Key Abstractions Template (MAP Phase)

```markdown
## Key Abstractions
1. [TypeName] ([file path]): [responsibility, what depends on it]
```

### Request Flow Template (MAP Phase)

```markdown
## Request Flow (typical)
1. [/abs/path/main.py] - Starts server, registers routes
2. [/abs/path/routes/api.py] - Maps URL to handler
3. [/abs/path/handlers/user.py] - Validates input, calls service
4. [/abs/path/services/user.py] - Applies business logic
5. [/abs/path/models/user.py] - Persists to database
6. Response flows back through handler
```

### Directory Layer Categorization

| Pattern | Layer |
|---------|-------|
| `models/`, `db/`, `schema/`, `entities/` | Data |
| `api/`, `routes/`, `handlers/`, `controllers/` | API |
| `services/`, `lib/`, `core/`, `domain/` | Business logic |
| `utils/`, `helpers/`, `common/` | Utilities |
| `tests/`, `test/`, `__tests__/` | Tests |
| `config/`, `settings/` | Configuration |
| `cmd/`, `cli/` | CLI |

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

---

### Example 2: Pre-Review Context Building

User says: "I need to review a PR in this repo but am unfamiliar with the codebase"

Actions:
1. Detect Go project with `go.mod`, identify Gin framework (DETECT)
2. Find `cmd/server/main.go` entry point, map `internal/` packages (EXPLORE)
3. Map handler -> service -> repository pattern, document gRPC + REST dual API (MAP)
4. Generate report focused on architecture and conventions (SUMMARIZE)

Result: Reviewer has architectural context for informed code review

---

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

---

### Error: "Not a Git Repository"

Cause: Directory lacks `.git/` or git is not initialized

Solution: Skip git-related steps (recent commits, development activity). Note in report that version control info is unavailable. Continue with all other phases.

---

### Error: "Too Many Files to Examine"

Cause: Large monorepo, generated files, or broad project scope

Solution:
1. Limit to 20 files per category (default behavior)
2. Exclude noise directories
3. Focus on representative samples, not exhaustive coverage
4. Note in report: "Examined N of M files as representative samples"

---

### Error: "Permission Denied Reading File"

Cause: File permissions prevent reading

Solution: Skip the inaccessible file. Note in the "Files Examined" section which files were inaccessible. Continue with remaining files in that category.

---

## Parallel Agent Instructions Template (Deep Dive Mode)

Each parallel agent receives these instructions:

```
You are exploring a [language/framework] codebase focused on [DOMAIN].
Project root: [absolute path]
Project type: [from DETECT phase]

RULES:
- Read-only. keep modifications out of scope — files.
- Skip files matching sensitive patterns: .env, .env.*, *.pem, *.key, credentials.json, secrets.*, *secret*, *credential*, *password*, token.json, .npmrc, .pypirc, .aws/credentials, .gcloud/, service-account*.json
- All file paths in output MUST be absolute.
- Every claim MUST cite an examined file.

Write your findings to: exploration/[domain].md
```

### Deep Dive Agent Domains

| Agent | Focus | Output File |
|-------|-------|-------------|
| **Technology Stack** | Languages, frameworks, dependencies, build tools, CI/CD pipelines, runtime requirements | `exploration/tech-stack.md` |
| **Architecture** | Module structure, data flow, API boundaries, state management, component relationships, entry points | `exploration/architecture.md` |
| **Code Quality** | Test coverage patterns, linting config, type safety, documentation density, code style conventions | `exploration/code-quality.md` |
| **Risks & Concerns** | Technical debt indicators, security patterns, dependency health, TODO/FIXME/HACK density, deprecated APIs | `exploration/risks.md` |

### Orchestration Rules

1. Phase 1 (DETECT) runs first, sequentially — all agents need the project type context before exploring
2. Agents launch after DETECT gate passes — spawn all 4 agents in parallel using Task
3. Each agent writes its own output file — agents operate independently without sharing context
4. Timeout: 5 minutes per agent — if an agent times out, proceed with completed results; minimum 3 of 4 agents MUST complete
5. Orchestrator does NOT merge results — the parallel documents ARE the output; the orchestrator collects confirmations and line counts, then runs the post-exploration secret scan across all output files
6. Slight redundancy is acceptable — both Architecture and Risks agents may note the same coupling issue; this is preferable to gaps from trying to deduplicate
