# CLAUDE.md Template

This template defines the structure for generated CLAUDE.md files. Fill each section from actual repo analysis — never leave placeholders.

## Principles

1. **Project-specific over generic** — document what's unique to THIS repo, not general language advice
2. **Verifiable** — every command must actually work, every path must actually exist
3. **Concise** — one line per concept, tables over paragraphs
4. **Actionable** — a new Claude session should be productive within 30 seconds of reading this

---

## Required Sections

### Section 1: Project Overview (always include)

```markdown
# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

{Project name} is {one-sentence description of what it does}.

**Key Concepts:**
- **{Concept}**: {Brief explanation}
- **{Concept}**: {Brief explanation}
```

### Section 2: Build and Test Commands (always include)

```markdown
## Build and Testing Commands

### Essential Commands
| Command | Description |
|---------|-------------|
| `{build command}` | Build the project |
| `{test command}` | Run tests |
| `{lint command}` | Run linters |
| `{check command}` | Run all checks (USE THIS AFTER EVERY CHANGE) |

### Running Specific Tests
| Command | Description |
|---------|-------------|
| `{single test command}` | Run a single test |
| `{package test command}` | Run tests for a package |
```

### Section 3: Architecture (always include)

```markdown
## Architecture

### Directory Structure
```
{root}/
  {dir}/    # {purpose}
  {dir}/    # {purpose}
  {dir}/    # {purpose}
```

### Key Components
1. **{Component}** (`{path}`): {What it does}
2. **{Component}** (`{path}`): {What it does}
```

### Section 4: Code Style (always include)

```markdown
## Code Style

- {Convention specific to this project}
- {Import ordering rule}
- {Naming convention}
- {Tooling that enforces style — e.g., "go-makefile-maker manages the Makefile"}
```

### Section 5: Testing Conventions (always include)

```markdown
## Testing Conventions

- {Test framework and assertion library}
- {Test file naming: e.g., "*_test.go in same package"}
- {Mocking approach: e.g., "Fake implementations in internal/test/"}
- {Integration test requirements: e.g., "PostgreSQL required for integration tests"}
```

### Section 6: Common Pitfalls (always include)

```markdown
## Common Pitfalls

1. **{Pitfall}**: {What goes wrong and how to avoid it}
2. **{Pitfall}**: {What goes wrong and how to avoid it}
3. **{Pitfall}**: {What goes wrong and how to avoid it}
```

---

## Optional Sections (include when relevant)

### Error Handling (include for Go, Rust, or any project with strong error conventions)

```markdown
## Error Handling

- {Wrapping convention: e.g., "Always wrap errors with context: fmt.Errorf('context: %w', err)"}
- {Error checking tool: e.g., "errcheck linter — all errors must be handled"}
- {Logging convention: e.g., "Log errors with structured fields"}
```

### Database Patterns (include when project uses a database)

```markdown
## Database Patterns

- {Driver/ORM: e.g., "pgx v5 with squirrel query builder"}
- {Migration tool}
- {Key patterns: e.g., "LISTEN/NOTIFY for real-time change propagation"}
```

### API Patterns (include for API services)

```markdown
## API Patterns

- {Framework: e.g., "go-swagger generated handlers"}
- {Auth: e.g., "Keystone tokens in X-Auth-Token header"}
- {Response format}
```

### Configuration (include when non-trivial)

```markdown
## Configuration

- {Config source: env vars, INI files, YAML, etc.}
- {Key variables or config sections}
- {Override precedence}
```

### Development Workflow (include when workflow has specific steps)

```markdown
## Development Workflow

1. Make code changes
2. Run `{check command}`
3. Fix any issues
4. Commit
```

---

## Scope Boundaries

- Generic language advice ("use meaningful variable names")
- IDE setup instructions (user-specific)
- CI/CD pipeline details (that's for CI config, not CLAUDE.md)
- Full API documentation (that belongs in docs/)
- Dependency installation beyond the basics (that's README territory)
