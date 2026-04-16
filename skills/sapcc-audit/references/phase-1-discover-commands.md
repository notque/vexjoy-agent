# Phase 1: DISCOVER — Detection Commands

> **Load when**: Phase 1 (DISCOVER) begins.
> **Purpose**: Go grep/vet detection commands for mapping the repository and validating it is an sapcc project.

---

## Step 1: Verify sapcc Project

```bash
head -5 go.mod  # Check module path
grep "sapcc" go.mod  # Check for sapcc imports
```

If neither command surfaces an sapcc module path or sapcc imports, stop immediately and report: "This does not appear to be an SAP CC Go project (no sapcc imports in go.mod)."

---

## Step 2: Map All Packages

```bash
find . -name "*.go" -not -path "./vendor/*" | sed 's|/[^/]*$||' | sort -u
```

Count files per package. This determines how to segment for parallel agents.

---

## Step 3: Plan Agent Segmentation

Group packages so each agent gets 5–15 files (sweet spot for thorough review). Target 5–8 agents.

Example segmentation for a typical sapcc repo:

| Agent | Packages | Focus |
|-------|----------|-------|
| 1 | `cmd/` + `main.go` files | Startup patterns, CLI structure |
| 2 | `internal/api/` | HTTP handlers, error responses, routing |
| 3 | `internal/config/` + `internal/auth/` | Configuration, auth patterns |
| 4 | `internal/storage/` + `internal/wal/` | Storage, persistence, error handling |
| 5 | `internal/router/` + `internal/source/` | Core logic, concurrency |
| 6 | `internal/integrity/` + `internal/limiter/` + remaining | Crypto, rate limiting |
| 7 | All `*_test.go` files | Testing patterns, assertions |

Adjust to actual package sizes.

---

## Additional Discovery Commands

```bash
# Count .go files per package for sizing agents
find . -name "*.go" -not -path "./vendor/*" | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn

# List all test files separately (often warrants a dedicated agent)
find . -name "*_test.go" -not -path "./vendor/*" | sort

# Quick project scale check
find . -name "*.go" -not -path "./vendor/*" | wc -l
```

---

## Gate

Packages mapped, agents planned, segmentation table drafted. Proceed to Phase 2.

If more than 30 packages, plan >8 agents. Keep 5–15 files per agent for review depth.
