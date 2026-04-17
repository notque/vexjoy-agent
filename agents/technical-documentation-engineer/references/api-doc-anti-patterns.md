# API Documentation Anti-Patterns

<!-- no-pair-required: document introduction, not an individual anti-pattern block -->

> **Scope**: Detectable anti-patterns in API documentation — hallucinated params, untested examples, missing source verification. Does NOT cover style/structure standards (see `documentation-standards.md`).
> **Version range**: REST APIs, OpenAPI 3.x, curl 7.x+
> **Generated**: 2026-04-15

---

## Overview

API documentation fails in two modes: structural (bad formatting) and semantic (documenting the wrong thing). Semantic failures are harder to spot because they look correct. A parameter table with beautifully formatted rows for a field that doesn't exist in the source is a documentation defect, not a style issue. Every anti-pattern here is detectable by comparing the documentation against the source code or a running API.

---

## Pattern Catalog

<!-- no-pair-required: section header with no content -->

### ❌ Documenting Parameters Not in Source (Hallucinated Params)

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

**Why wrong**: Integration failures happen silently. The caller sends `metadata`, the API ignores it, and the caller assumes it was accepted. Edge cases: some frameworks quietly drop unknown fields, others return 400. Either way, the doc is lying.

**Do instead:** Before writing any parameter, grep the source route handler for its exact name to confirm it exists. Zero grep results means the parameter is not real — remove it from the doc rather than publishing a lie.

**Fix**: Before writing any parameter, grep the source route handler for its exact name:
```bash
# For Go
grep -n "metadata\|user_id" handlers/users.go

# For Python/Flask
grep -n "request.json.get\|request.form.get" routes/users.py
rg "\.get\(['\"]metadata['\"]" src/
```

Zero results = parameter does not exist. Remove it from the doc.

---

### ❌ Type Mismatches Between Doc and Source

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

**Why wrong**: The caller sends `"50"` (string) and gets a 400. Or worse: the API coerces it silently and the caller never learns the real type. Type contracts are part of the API surface.

**Do instead:** Read the type from the validation struct or Pydantic model declaration, not from how the value is used in the handler. Document the type that the input binding layer enforces, which is the type the caller must send.

**Fix**: Read the validation code, not the handler call site:
```bash
# Find validation or binding in Go
grep -n "ShouldBindJSON\|ShouldBindQuery\|validate.Struct" handlers/*.go

# Find pydantic model in FastAPI
grep -n "class.*BaseModel\|: int\|: str\|: Optional" models/*.py
```

---

### ❌ Untested curl Examples

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

**Why wrong**: Copy-pasted examples become stale. If `role` was removed and the example still includes it, the API may return 400 and the new user thinks the docs are wrong — which they are.

**Do instead:** Run every curl example against a staging or test environment before publishing. Capture the actual response and confirm it matches the documented response example. If no live environment is available, add an explicit "verified against source at commit X" note.

**Fix**: Test the curl against a running service before publishing:
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

### ❌ Documented Error Codes Not Returned by Source

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

**Why wrong**: Readers write error handling code for 418. That code path is dead. The actual error they get from the API is 400 with an unhelpful message, and they have no documented path to resolution.

**Do instead:** Build the error table by grepping the handler file first, then documenting only the codes found. Start from source, not from assumption. Every row in the error table must have a corresponding `grep` hit in the handler.

**Fix**: Only document error codes that appear in the source. `grep` the handler for every HTTP status code before including it in the error table.

---

### ❌ Response Example Out of Sync With Source Schema

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

**Why wrong**: Callers write code like `response["owner"]` and get a KeyError or undefined in production. The doc is a lie.

**Do instead:** Extract response field names directly from the serialization layer — `json:` tags in Go structs, Pydantic model field definitions in Python, or serializer `fields` declarations in Django REST Framework. Document what the serializer actually emits, not what you expect it to emit.

**Fix**: Find the serialization struct/model and use its exact field names. For Go, look for `json:` tags. For Python, look for the Pydantic model or serializer.

---

### ❌ Missing Authentication Requirements on Individual Endpoints

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

**Do instead:** Add an `**Authentication:**` line immediately after every endpoint description, before the parameters section. State the credential type and required scope explicitly. Do not rely on a shared "Authentication" section at the top of the page -- endpoint-level auth notes eliminate the 401-then-hunt pattern for new users.

**What it looks like**:
```markdown
### GET /api/v1/resources

Returns a list of resources.

**Parameters:**
| Parameter | Type | Required | Description |
...
```
*(no mention of authentication)*

**Why wrong**: New users hit 401 without any documentation telling them what credential is needed or how to obtain it.

**Do instead:** Place an `**Authentication:**` line as the first item after the endpoint description, before the parameters section, on every endpoint that requires credentials. Specify the credential type and required scope so the reader knows exactly what to obtain before constructing a request.

**Fix**: Add authentication immediately after the endpoint description, before parameters:
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
