# Code Review Detection Patterns

> **Scope**: Detection commands for common anti-patterns across languages. Load during any perspective review on a real codebase.
> **Generated**: 2026-04-13

---

## Pattern Catalog

### Handle All Errors (Skeptical Senior, Pedant)

**Detection**:
```bash
rg -n ',\s*_\s*:?=\s*\w+' --type go             # Go: blank identifier discarding errors
rg -n 'except:' --type py                         # Python: bare except
rg -n '\.then\(' --type ts | rg -v '\.catch|async' # JS: promise without catch
```

**Signal**: `result, _ := db.Query(...)` — silent error discard means undetected corruption.

**Preferred action**: Handle error, wrap with `%w` (Go 1.13+), use `errors.Is()`/`errors.As()`.

---

### Use Correct HTTP Status Codes (Pedant)

**Detection**:
```bash
rg -n 'status.*200|StatusOK' --type go | rg -i 'err\|fail\|error'     # 200 on error
rg -n 'InternalServerError|status.*500' --type go | rg -i 'invalid\|bad.request' # 500 for client error
rg -n 'NotFound|status.*404' --type go | rg -i 'auth\|permission'     # 404 for authz
```

Per RFC 7231: 400 invalid input, 404 missing resource, 401 missing auth, 403 insufficient permissions.

---

### Load Credentials from Environment (Skeptical Senior, Pedant)

**Detection**:
```bash
rg -n 'password\s*=\s*"[^"]{4,}"' --type py --type go --type ts -i
rg -n 'api[_-]?key\s*=\s*"[^"]{8,}"' -i
rg -n 'AKIA[0-9A-Z]{16}'                          # AWS key pattern
grep -rn 'postgres://\|mysql://\|mongodb://' --include="*.go" --include="*.ts" --include="*.py" | grep -v '_test\|example'
```

Credentials in git history are permanent. Load from env vars or secrets manager.

---

### Paginate All List Queries (Skeptical Senior)

**Detection**:
```bash
rg -n 'SELECT.*FROM' --type go --type py | rg -v 'LIMIT\|COUNT\|SUM\|MIN\|MAX'
rg -n '\.find\(\|\.all\(\|\.fetch\(' --type py | rg -v 'limit\|paginate\|first\|count'
grep -rn 'findAll\|getAll\|fetchAll' --include="*.ts" --include="*.go"
```

1,000 rows in dev = 50 million in prod. Add LIMIT/OFFSET or cursor pagination.

---

### Use Atomic Operations (Skeptical Senior)

**Detection**:
```bash
grep -rn 'os.path.exists\|path.exists' --include="*.py" | rg -v 'test\|check'  # TOCTOU
rg -n 'await.*get\|await.*find' --type ts -A2 | rg 'await.*set\|await.*update'   # async race
```

**Preferred action**: `sync.Map.LoadOrStore()`, mutex-wrapped check-and-store, or `INSERT ON CONFLICT`.

---

### Batch Related Queries (Skeptical Senior)

**Detection**:
```bash
rg -n 'for.*in.*\.(all|filter|objects)' --type py -A3 | rg '\.(name|id|title|email)\b'
rg -n 'for.*range' --type go -A5 | rg 'db\.Query\|\.Find\|\.Get'
rg -n 'for.*of\|for.*in' --type ts -A3 | rg 'await.*find\|await.*get'
```

100 posts = 101 queries. Use `select_related`, `JOIN`, or batch `IN (...)`.

---

### Enforce Authorization on Every Resource (Skeptical Senior, Pedant)

**Detection**:
```bash
rg -n 'userID|user_id' --type go --type py --type ts -A5 | rg 'db\.\|query\|find' | rg -v 'WHERE.*user_id\|filter.*user_id'
grep -rn 'def get\|def post\|def put' --include="*.py" | rg -v '@login_required\|@permission_required'
rg -n 'router\.(get|post|put|delete)\(' --type ts -B2 | rg -v 'auth\|verify\|require'
```

IDOR: OWASP A01:2021. Always filter by authenticated user's ID.

---

## Error-Fix Mappings

| Error Pattern | Root Cause | Fix |
|---------------|------------|-----|
| `panic: index out of range` | No bounds check | `len(slice) > idx` |
| `context deadline exceeded` | No timeout | `context.WithTimeout()` |
| `429 Too Many Requests` | No backoff | Exponential backoff with jitter |
| `200 OK` with error body | Wrong status | Appropriate 4xx/5xx |
| `UNIQUE constraint failed` | No ON CONFLICT | Upsert or explicit check |

---

## Detection Commands Reference

```bash
rg -n ',\s*_\s*:?=\s*\w+' --type go                          # Ignored errors
rg -n 'StatusOK' --type go | rg -i 'err\|fail'                # HTTP status misuse
rg -n 'password\s*=\s*"[^"]{4,}"' -i                          # Hardcoded secrets
rg -n 'SELECT.*FROM' --type go | rg -v 'LIMIT'                # Missing pagination
grep -rn 'os.path.exists' --include="*.py"                     # TOCTOU race
rg -n 'for.*range' --type go -A5 | rg 'db\.Query'             # N+1
rg -n 'userID' --type go -A5 | rg 'db\.' | rg -v 'WHERE.*user' # Missing authz
```

---

## See Also

- `skeptical-senior.md` — production readiness framework
- `pedant.md` — RFC/spec compliance
- `contrarian.md` — assumption auditing, lock-in detection
