# Code Review Detection Patterns

> **Scope**: grep/rg detection commands for common code anti-patterns across languages. Load this when performing any perspective review on a real codebase — these commands surface concrete evidence to cite in findings.
> **Version range**: Language-specific commands noted inline
> **Generated**: 2026-04-13

---

## Overview

Each perspective produces better findings when supported by concrete codebase evidence. This reference provides detection commands that surfaces real instances of common anti-patterns — so findings cite `file.go:42` rather than "this might exist somewhere." Each section maps to the perspective most likely to raise the issue.

---

## Anti-Pattern Catalog

### ❌ Ignored Errors (Skeptical Senior, Pedant)

Silent failures that turn bugs into production mysteries.

**Detection**:
```bash
# Go: blank identifier discarding errors
rg -n ',\s*_\s*:?=\s*\w+' --type go

# Python: bare except clauses
rg -n 'except:' --type py

# JavaScript/TypeScript: promise without .catch() or await
rg -n '\.then\(' --type ts | rg -v '\.catch|async'

# Shell: unchecked command exits
grep -rn '^\s*[a-z].*&&\|;\s*$' --include="*.sh" | grep -v 'if\|then\|else'
```

**What it looks like**:
```go
result, _ := db.Query("SELECT * FROM users WHERE id = ?", id)
```

**Why wrong**: Silent error discard means data corruption or partial writes proceed undetected. In production, this surfaces as corrupted records with no error logs.

**Do instead:**
```go
result, err := db.Query("SELECT * FROM users WHERE id = ?", id)
if err != nil {
    return fmt.Errorf("query users by id %d: %w", id, err)
}
```

**Version note**: Go 1.13+ error wrapping (`%w`) preserves the error chain. Use `errors.Is()` / `errors.As()` for unwrapping.

---

### ❌ HTTP Status Code Misuse (Pedant)

Violates RFC 7231 — breaks API clients that inspect status codes.

**Detection**:
```bash
# 200 returned on explicit error paths
rg -n 'status.*200|StatusOK' --type go | rg -i 'err\|fail\|error'
rg -n 'res\.status\(200\)' --type ts | rg -i 'error\|fail'

# 500 used for client errors (should be 4xx)
rg -n 'InternalServerError|status.*500' --type go | rg -i 'invalid\|bad.request\|not.found'

# 404 used for authorization failures (should be 403 or 401)
rg -n 'NotFound|status.*404' --type go | rg -i 'auth\|permission\|forbidden'
```

**What it looks like**:
```go
func handler(w http.ResponseWriter, r *http.Request) {
    user, err := getUser(id)
    if err != nil {
        http.Error(w, err.Error(), http.StatusOK) // wrong: 200 on error
    }
}
```

**Why wrong**: RFC 7231 §6 defines status code semantics. Clients (including monitoring tools and API gateways) use status codes to route errors — a 200 error bypasses all error-handling middleware.

**Do instead:** Use `http.StatusBadRequest` (400) for invalid input, `http.StatusNotFound` (404) for missing resources, `http.StatusUnauthorized` (401) for missing auth, `http.StatusForbidden` (403) for insufficient permissions.

---

### ❌ Hardcoded Credentials (Skeptical Senior, Pedant)

Secrets in source code survive beyond rotation.

**Detection**:
```bash
# Common credential patterns
rg -n 'password\s*=\s*"[^"]{4,}"' --type py --type go --type ts -i
rg -n 'api[_-]?key\s*=\s*"[^"]{8,}"' -i
rg -n 'secret\s*=\s*"[^"]{8,}"' -i
rg -n 'token\s*=\s*"[^"]{20,}"' -i

# AWS patterns
rg -n 'AKIA[0-9A-Z]{16}'
rg -n 'aws_secret_access_key\s*='

# Connection strings
grep -rn 'postgres://\|mysql://\|mongodb://' --include="*.go" --include="*.ts" --include="*.py" | grep -v '_test\|example\|sample'
```

**Why wrong**: Credentials in version history are permanent — `git filter-branch` does not remove them from forks or cached copies. Leaked credentials require key rotation even after removal.

**Do instead:** Load from environment variables (`os.Getenv`, `process.env`, `os.environ`) or a secrets manager. Never commit `.env` files containing real values.

---

### ❌ Missing Pagination on List Queries (Skeptical Senior)

Unbounded queries that work in development, fail in production with real data volumes.

**Detection**:
```bash
# SQL without LIMIT
rg -n 'SELECT.*FROM' --type go --type py | rg -v 'LIMIT\|COUNT\|SUM\|MIN\|MAX'

# ORM queries without limit/paginate
rg -n '\.find\(\|\.all\(\|\.fetch\(' --type py | rg -v 'limit\|paginate\|first\|count'
rg -n 'find\(\{\}' --type ts | rg -v 'limit\|skip\|take'

# GraphQL resolvers returning all items
grep -rn 'findAll\|getAll\|fetchAll' --include="*.ts" --include="*.go"
```

**Why wrong**: A query returning 1,000 rows in development returns 50 million in production, causing OOM crashes or 30-second response times that cascade into timeouts.

**Do instead:** Add `LIMIT`/`OFFSET` or cursor-based pagination. Default page size should be 100 or fewer records.

---

### ❌ Race Condition: Check-Then-Act (Skeptical Senior)

Non-atomic read-modify-write sequences that fail under concurrent load.

**Detection**:
```bash
# Separate read + write without lock (Go)
rg -n 'mu\.Lock\(\)|sync\.Mutex' --type go -l | xargs -I{} sh -c 'grep -n "if.*==.*{" {} | head -5'

# File existence check followed by open (TOCTOU)
grep -rn 'os.path.exists\|path.exists' --include="*.py" | rg -v 'test\|check'

# JavaScript: async race (read then write without transaction)
rg -n 'await.*get\|await.*find' --type ts -A2 | rg 'await.*set\|await.*update\|await.*save'
```

**What it looks like**:
```go
if _, exists := cache[key]; !exists {
    cache[key] = computeExpensive(key) // not atomic — two goroutines can reach this
}
```

**Why wrong**: Two goroutines can both pass the `!exists` check before either writes, causing double computation or overwriting a valid value.

**Do instead:** Use `sync.Map.LoadOrStore()`, a mutex-wrapped check-and-store, or database-level `INSERT ... ON CONFLICT DO NOTHING`.

---

### ❌ N+1 Query Pattern (Skeptical Senior)

Queries inside loops that scale linearly with record count.

**Detection**:
```bash
# Python ORM: loop with model access
rg -n 'for.*in.*\.(all|filter|objects)' --type py -A3 | rg '\.(name|id|title|email)\b'

# Go: query inside loop
rg -n 'for.*range' --type go -A5 | rg 'db\.Query\|\.Find\|\.Get'

# TypeScript: await in for loop with DB calls
rg -n 'for.*of\|for.*in' --type ts -A3 | rg 'await.*find\|await.*get\|await.*fetch'
```

**What it looks like**:
```python
posts = Post.objects.all()
for post in posts:
    print(post.author.name)  # SELECT for every iteration
```

**Why wrong**: 100 posts = 101 queries. 10,000 posts = 10,001 queries. Degrades exponentially with data growth.

**Do instead:** Use `select_related`/`prefetch_related` (Django), `JOIN` (raw SQL), or batch fetch with `IN (...)`.

---

### ❌ Missing Authorization Check (Skeptical Senior, Pedant)

Authentication (who are you?) verified but authorization (what can you do?) missing.

**Detection**:
```bash
# Handlers that read user id from token but don't check ownership
rg -n 'userID|user_id|userId' --type go --type py --type ts -A5 | rg 'db\.\|query\|find' | rg -v 'WHERE.*user_id\|filter.*user_id\|user_id.*=='

# Django views without permission checks
grep -rn 'def get\|def post\|def put' --include="*.py" | rg -v '@login_required\|@permission_required\|IsAuthenticated'

# Express routes without auth middleware
rg -n 'router\.(get|post|put|delete)\(' --type ts -B2 | rg -v 'auth\|verify\|require'
```

**Why wrong**: Authenticated users can access other users' resources. Classic IDOR (Insecure Direct Object Reference) vulnerability — OWASP A01:2021.

**Do instead:** Always filter queries by the authenticated user's ID: `WHERE user_id = $currentUser`. For operations that modify resources, verify ownership before executing.

---

## Error-Fix Mappings

| Error Pattern | Root Cause | Perspective | Fix |
|---------------|------------|-------------|-----|
| `panic: runtime error: index out of range` | Slice access without bounds check | Skeptical Senior | Check `len(slice) > idx` before indexing |
| `context deadline exceeded` | No timeout set on HTTP client or DB query | Skeptical Senior | Set `context.WithTimeout()` |
| `429 Too Many Requests` from downstream | No retry backoff, no rate limit | Skeptical Senior | Add exponential backoff with jitter |
| `200 OK` with error body | Wrong HTTP status code on error path | Pedant (RFC 7231) | Return appropriate 4xx/5xx |
| `UNIQUE constraint failed` | No ON CONFLICT handling | Skeptical Senior | Handle with upsert or explicit check |

---

## Detection Commands Reference

```bash
# Ignored errors (Go)
rg -n ',\s*_\s*:?=\s*\w+' --type go

# HTTP status misuse
rg -n 'StatusOK' --type go | rg -i 'err\|fail'

# Hardcoded secrets
rg -n 'password\s*=\s*"[^"]{4,}"' -i

# Missing pagination
rg -n 'SELECT.*FROM' --type go | rg -v 'LIMIT'

# Race: check-then-act
grep -rn 'os.path.exists' --include="*.py"

# N+1 query
rg -n 'for.*range' --type go -A5 | rg 'db\.Query'

# Missing authz
rg -n 'userID' --type go -A5 | rg 'db\.' | rg -v 'WHERE.*user'
```

---

## See Also

- `skeptical-senior.md` — production readiness framework and severity classification
- `pedant.md` — RFC/spec compliance and terminology precision
- `contrarian.md` — assumption auditing and lock-in detection
