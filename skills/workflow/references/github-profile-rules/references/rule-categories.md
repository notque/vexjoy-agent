# Rule Categories Taxonomy

Reference for categorizing extracted programming rules from GitHub profile analysis.
Each category defines the types of patterns to look for and how to express them as actionable rules.

---

## 1. Naming Conventions

Patterns in how the developer names things.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Variable naming style | Source files | "Use camelCase for local variables in JavaScript" |
| Function/method naming | Source files | "Prefix boolean-returning functions with is/has/can" |
| File naming | Repo file trees | "Use kebab-case for file names" |
| Package/module naming | Directory structure | "Use singular nouns for package names" |
| Constant naming | Source files | "Use SCREAMING_SNAKE_CASE for constants" |
| Type/class naming | Source files | "Use PascalCase for types and interfaces" |

---

## 2. Code Style

Patterns in code formatting and structural preferences.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Indentation | Source files | "Use tabs for indentation (Go convention)" |
| Line length | Source files | "Keep lines under 100 characters" |
| Brace style | Source files | "Opening brace on same line as statement" |
| Import ordering | Source files | "Group imports: stdlib, external, internal" |
| String quoting | Source files | "Prefer double quotes for strings" |
| Trailing commas | Source files | "Always use trailing commas in multi-line structures" |
| Blank lines | Source files | "Two blank lines between top-level definitions" |

---

## 3. Architecture & Design

Patterns in code organization and design decisions.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Project structure | File trees | "Separate cmd/ and pkg/ directories in Go projects" |
| Dependency injection | Source files | "Pass dependencies as constructor arguments" |
| Error handling style | Source files | "Return errors, don't panic" |
| Interface design | Source files | "Define interfaces where they're used, not where they're implemented" |
| Configuration | Source files, configs | "Use environment variables for configuration" |
| Package boundaries | Source files | "Keep packages focused on single responsibility" |

---

## 4. Testing

Patterns in testing approaches and conventions.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Test file naming | File trees | "Test files use _test.go suffix" |
| Test structure | Test files | "Use table-driven tests for multiple cases" |
| Test coverage | CI configs, READMEs | "Maintain >80% test coverage" |
| Mock usage | Test files | "Prefer interfaces for testability over mocking frameworks" |
| Test naming | Test files | "Name tests as Test{Function}_{scenario}_{expected}" |
| Integration tests | Test files, CI | "Separate unit and integration tests with build tags" |

---

## 5. Error Handling

Patterns in how errors are created, propagated, and handled.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Error wrapping | Source files | "Wrap errors with context using fmt.Errorf with %w" |
| Error types | Source files | "Define sentinel errors for expected failure modes" |
| Error checking | Source files, PR reviews | "Always check error returns, never use _" |
| Panic usage | Source files | "Never panic in library code" |
| Error messages | Source files | "Start error messages lowercase, no trailing punctuation" |
| Error recovery | Source files | "Use defer/recover only at goroutine boundaries" |

---

## 6. Documentation

Patterns in documentation style and coverage.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| README structure | READMEs | "README includes: purpose, install, usage, contributing" |
| Code comments | Source files | "Comment exported functions with godoc-style comments" |
| Commit messages | Commit history | "Use conventional commit format (feat:, fix:, docs:)" |
| API documentation | Source files | "Document all public API endpoints with examples" |
| Changelog | Repo root files | "Maintain a CHANGELOG.md with semver sections" |
| Inline comments | Source files, PR reviews | "Explain WHY, not WHAT -- code should be self-documenting for the what" |

---

## 7. Dependencies & Tooling

Patterns in dependency management and toolchain preferences.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Dependency minimalism | go.mod, package.json | "Prefer stdlib over external dependencies" |
| Linter config | .golangci.yml, .eslintrc | "Run linters in CI, fix all warnings" |
| Build tools | Makefile, CI configs | "Use Makefiles for build automation" |
| Version pinning | Lock files | "Pin all dependency versions" |
| CI/CD | .github/workflows | "Run tests on every PR" |

---

## 8. Git & Workflow

Patterns in version control and development workflow.

| Signal | Where to Find | Example Rule |
|--------|---------------|--------------|
| Branch naming | PR titles, branches | "Use feature/ and fix/ branch prefixes" |
| Commit granularity | Commit history | "One logical change per commit" |
| PR size | PR reviews | "Keep PRs under 400 lines of changes" |
| Review thoroughness | PR reviews given | "Review for correctness, style, and test coverage" |
| Merge strategy | Repo settings | "Use squash-and-merge for feature branches" |

---

## Confidence Scoring

| Level | Criteria | Meaning |
|-------|----------|---------|
| **High** | Seen in 3+ repos OR 2+ repos + review signal | Strong personal preference, safe to adopt as rule |
| **Medium** | Seen in 2 repos | Likely preference, may be project-influenced |
| **Low** | Seen in 1 repo only | Possible preference, needs more evidence |
| **Review-Boosted** | Any frequency + reinforced by PR review comments | Developer actively enforces this pattern |

---

## Rule Output Format

### CLAUDE.md Entry
```markdown
## [Category]: [Rule Name]

**Confidence**: [high/medium/low] (seen in N repos, M review comments)

[One-sentence actionable rule]

**Evidence**:
- Repo: {repo_name} -- {file_path}: {specific pattern observed}
- Review: PR #{number} in {repo} -- "{comment excerpt}"
```

### JSON Entry
```json
{
  "category": "naming",
  "name": "camelCase variables",
  "rule": "Use camelCase for local variables and function parameters",
  "confidence": "high",
  "score": 0.85,
  "repos_observed": ["repo1", "repo2", "repo3"],
  "review_signals": 2,
  "examples": [
    {"repo": "repo1", "file": "main.go", "line": "userName := getUser()"}
  ],
  "language_scope": ["go", "javascript"],
  "contradicts": []
}
```
