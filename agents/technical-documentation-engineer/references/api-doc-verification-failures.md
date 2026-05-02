# API Documentation Verification Failures

<!-- no-pair-required: document introduction, not an individual anti-pattern block -->

> **Scope**: Detectable verification failures in API documentation — hallucinated params, untested examples, missing source verification. Does NOT cover style/structure standards (see `documentation-standards.md`).
> **Version range**: REST APIs, OpenAPI 3.x, curl 7.x+
> **Generated**: 2026-04-15

---

## Overview

Two failure modes: structural (formatting) and semantic (wrong content). Semantic failures look correct — a well-formatted table for a nonexistent parameter is a defect. Every failure here is detectable by comparing docs against source.

---

## Pattern Catalog

<!-- no-pair-required: section header with no content -->

### Documenting Parameters Not in Source (Hallucinated Params)

**Detection**:
```bash
# Extract all documented parameter names from a doc file
grep -oP "(?<=\| )\w+" docs/api/endpoint.md | sort -u

# Then verify each one exists in the source
grep -rn "PARAM_NAME" src/ --include="*.go"
grep -rn "PARAM_NAME" src/ --include="*.py"
rg "PARAM_NAME" src/
```

**What it looks like**:
```markdown
| user_id  | string | Yes | The user's unique identifier |
| metadata | object | No  | Optional metadata key-value pairs |
```
*(where `metadata` doesn't exist in the route handler)*

**Why wrong**: Caller sends `metadata`, API ignores it silently or returns 400. The doc is lying.

**Fix**: Grep the source route handler for every parameter name:
```bash
# For Go
grep -n "metadata\|user_id" handlers/users.go

# For Python/Flask
grep -n "request.json.get\|request.form.get" routes/users.py
rg "\.get\(['\"]metadata['\"]" src/
```

Zero results = parameter does not exist. Remove it from the doc.

---

### Type Mismatches Between Doc and Source

**Detection**:
```bash
# Find integer params documented as string (common copy-paste error)
rg "int.*string|string.*int" docs/**/*.md

# Find the actual type in source (Go example)
grep -n "int\|string\|bool\|float" handlers/*.go | grep "PARAM_NAME"
```

**What it looks like**:
```markdown
| page_size | string | No | Number of results per page. Default: 20 |
```
*(where the handler actually validates it as `int`)*

**Why wrong**: Caller sends wrong type, gets 400 or silent coercion. Type contracts are API surface.

**Fix**: Read the validation struct or Pydantic model, not handler usage:
```bash
# Find validation or binding in Go
grep -n "ShouldBindJSON\|ShouldBindQuery\|validate.Struct" handlers/*.go

# Find pydantic model in FastAPI
grep -n "class.*BaseModel\|: int\|: str\|: Optional" models/*.py
```

---

### Untested curl Examples

**Detection** (check examples don't use placeholder values in actual requests):
```bash
# Find placeholder patterns in curl examples
grep -n "YOUR_TOKEN\|<token>\|example\.com\|placeholder" docs/**/*.md | grep "curl"
rg "Authorization: Bearer YOUR_" --glob "*.md"
```

**What it looks like**:
```bash
curl -X POST https://api.example.com/v1/users \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name": "John", "role": "admin"}'
```
*(where `role` was removed from the API last sprint)*

**Why wrong**: Stale examples include removed fields. API returns 400, user blames docs — correctly.

**Fix**: Test curl against running service. If unavailable, note "verified against source at commit X":
```bash
# Test with a real token against staging
TOKEN=$(cat .env | grep API_TOKEN | cut -d= -f2)
curl -X POST https://api-staging.example.com/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "testuser"}' \
  -w "\nHTTP Status: %{http_code}\n"
```

If the test environment is unavailable, mark the example explicitly:
```markdown
> **Note:** Example not verified against running service. Endpoint paths and parameters
> were verified against source as of commit `abc1234`.
```

---

### Documented Error Codes Not Returned by Source

**Detection**:
```bash
# Find all error codes in docs
grep -oP "\b[45]\d\d\b" docs/api/endpoint.md | sort -u

# Verify each code is returned by source (Go example)
grep -rn "StatusBadRequest\|http.StatusUnauthorized\|400\|401\|403" handlers/endpoint.go

# Python/Flask
grep -rn "abort(400)\|abort(401)\|jsonify.*400\|make_response.*400" routes/
```

**What it looks like**:
```markdown
| 418 | Teapot mode enabled | Disable teapot mode in config |
```
*(where the handler never returns 418)*

**Why wrong**: Dead error handling code for a status never returned. No resolution for the actual error.

**Fix**: Build error table from source grep results. Every row needs a corresponding handler hit.

---

### Response Example Out of Sync With Source Schema

**Detection**:
```bash
# Find all field names in a JSON response example
grep -oP '"\w+"(?=:)' docs/api/endpoint.md | tr -d '"' | sort -u

# Verify each field exists in the response struct/model
# Go: look for json tags
grep -n 'json:"FIELD_NAME"' models/resource.go

# Python/Pydantic
grep -n "FIELD_NAME.*:" models/resource.py
```

**What it looks like**:
```json
{
  "id": "res_abc123",
  "name": "my-resource",
  "owner": "user_xyz",
  "created_at": "2025-01-15T10:30:00Z"
}
```
*(where the API removed `owner` and renamed it `created_by_id` in v2)*

**Why wrong**: `response["owner"]` -> KeyError in production.

**Fix**: Extract field names from serialization layer (`json:` tags in Go, Pydantic model in Python). Document what the serializer emits.

---

### Missing Authentication Requirements on Individual Endpoints

**Detection**:
```bash
# Find endpoint headings without nearby "Authentication" or "Bearer" mentions
<!-- no-pair-required: detection code fragment inside bash block, not an anti-pattern block -->
grep -n "^### [A-Z]\{2,6\} /" docs/**/*.md | while read line; do
  lineno=$(echo "$line" | cut -d: -f2)
  # Check if auth documented within 10 lines after endpoint heading
  sed -n "$((lineno+1)),$((lineno+10))p" docs/**/*.md | grep -q "Auth\|Bearer\|token\|API[- ]key" || echo "MISSING AUTH: $line"
done
```

**What it looks like**:
```markdown
### GET /api/v1/resources

Returns a list of resources.

**Parameters:**
| Parameter | Type | Required | Description |
...
```
*(no mention of authentication)*

**Why wrong**: Users hit 401 with no documented credential requirement.

**Fix**: Add `**Authentication:**` after endpoint description, before parameters:
```markdown
### GET /api/v1/resources

Returns a list of resources in the workspace.

**Authentication:** Bearer token with `resources:read` scope.
```

---

## Error-Fix Mappings

| Documentation Error | Detection Command | Fix |
|--------------------|-------------------|-----|
| Hallucinated parameter | `grep -rn "PARAM" src/` returns 0 results | Remove parameter from doc |
| Wrong type (string vs int) | `grep -n ": int\|: str" models/` doesn't match doc | Update type from actual model/struct |
| Stale curl example | `curl` returns 400 with "unknown field" | Re-test, remove extra fields |
| Documented 4xx code not in source | `grep -rn "Status404\|abort(404)" handlers/` returns 0 | Remove code from error table |
| Response field doesn't exist | `grep -rn '"FIELD"' models/` returns 0 | Replace with field from actual JSON serializer |

---

## Verification Workflow

Use this sequence before finalizing any endpoint doc:

```bash
# 1. List all params you documented
PARAMS=("name" "config" "tags")  # from your doc

# 2. Verify each exists in source
for param in "${PARAMS[@]}"; do
  count=$(grep -rn "\"$param\"\|'$param'" src/ | wc -l)
  echo "$param: $count occurrences"
done
# Any param with 0 occurrences is hallucinated

# 3. List all error codes you documented
CODES=("400" "401" "403" "404" "409")

# 4. Verify each is returned by the handler
for code in "${CODES[@]}"; do
  count=$(grep -rn "Status$code\|http\.Status\|$code," handlers/ | wc -l)
  echo "$code: $count occurrences in handlers"
done

# 5. Check response fields against model
# (run against the actual serializer/model file)
grep -n 'json:"' models/resource.go | grep -oP '(?<=json:")[^"]*' | sort
```

---

## See Also

- `documentation-standards.md` — Style guide: parameter table format, heading hierarchy, prose standards
- `runbook-patterns.md` — Operational documentation: troubleshooting structure, runbook format
