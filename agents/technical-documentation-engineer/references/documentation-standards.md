# Documentation Standards Reference

> **Scope**: Style guide rules, parameter table quality, heading structure, and prose standards for API and technical documentation. Does NOT cover code example verification (see `api-doc-anti-patterns.md`).
> **Version range**: Google Developer Documentation Style Guide (current), OpenAPI 3.x
> **Generated**: 2026-04-15 — verify against Google style guide current release

---

## Overview

Technical documentation accuracy depends on two orthogonal concerns: structural correctness (tables well-formed, headings consistent, links working) and semantic correctness (params match source, types verified, examples tested). This file covers structural standards. The most common failure mode is documenting the wrong thing correctly — a perfectly formatted table describing a parameter that doesn't exist.

---

## Pattern Table

| Pattern | Standard | Use When | Avoid When |
|---------|----------|----------|------------|
| Parameter tables | Google style: Type, Required, Description cols | All endpoint params | Fewer than 2 params (use inline) |
| Heading hierarchy | H2 for top sections, H3 for endpoints, H4 for sub-sections | All long docs | Jumping from H2 to H4 |
| Code blocks with language tag | ` ```bash `, ` ```json `, ` ```yaml ` | All code samples | Short inline values (use backticks) |
| Admonition for warnings | `> **Note:**` or `> **Warning:**` | Destructive ops, gotchas | Every paragraph |
| Versioning notes | `**Changed in v2.0:**` prefix | Breaking API changes | Minor doc updates |

---

## Correct Patterns

### Parameter Tables — Required Column Order

Google style requires Type before Description. Putting Description before Type is the most common table error.

```markdown
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name      | string | Yes    | Resource name (3-63 chars, alphanumeric + hyphens) |
| timeout   | integer | No   | Request timeout in seconds. Default: 30. Range: 1-300 |
| tags      | array of strings | No | Labels for filtering. Max 10 items |
```

**Why**: Google Developer Style Guide §parameter-tables — Type comes second so readers can scan the type column without reading Description. "Required" as a boolean column (not embedded in Description) enables table sorting in rendered docs.

---

### Error Response Tables — Code, Cause, Resolution

Every endpoint needs an error table. "Returns 400 if invalid" is not documentation.

```markdown
| Code | Cause | Resolution |
|------|-------|------------|
| 400  | `name` is missing or empty | Include `name` field in request body |
| 400  | `name` exceeds 63 characters | Use a name with 3-63 alphanumeric chars or hyphens |
| 401  | Missing `Authorization` header | Add `Authorization: Bearer <token>` header |
| 403  | Token lacks `write` scope | Request a token with the `write` scope from auth service |
| 409  | Resource with this `name` already exists | Choose a unique name or use PUT to update |
| 429  | Rate limit exceeded (100 req/min) | Wait 60 seconds or implement exponential backoff |
| 500  | Internal error | Retry with exponential backoff; contact support with `X-Request-ID` |
```

**Why**: Each row answers "what do I DO when this happens?" — not just what went wrong. Resolution must be actionable.

---

### Authentication Section Placement

Authentication must appear before parameters, not after examples. Readers need auth context before attempting to construct a request.

```markdown
### POST /api/v1/resources

Creates a new resource.

**Authentication:** Bearer token with `resources:write` scope required.

**Request Parameters:**
...

**Request Example:**
...
```

**Why**: If auth is after the example, readers copy the example, hit 401, and then hunt for the auth section. Front-loaded auth reduces time-to-first-success.

---

### Endpoint Description — 30-Word Limit

Each endpoint description must be one sentence under 30 words.

```markdown
<!-- Good: 11 words, tells you what the endpoint does -->
Creates a new resource in the specified workspace.

<!-- Bad: 35 words, describes the implementation not the interface -->
This endpoint processes the incoming request data, validates the fields against the schema,
and if all validations pass, creates a new resource entry in the database.
```

**Why**: Google style §method-descriptions — description is the *interface*, not the implementation. The implementation details belong in architecture docs, not API reference.

---

## Pattern Catalog

<!-- no-pair-required: section header with no content -->

### ❌ Vague Parameter Descriptions

**Detection**:
```bash
grep -n "the [a-z]* to\|value of\|represents the\|specifies the" docs/**/*.md
rg "the \w+ to use|value of the|this is the" --glob "*.md"
```

**What it looks like**:
```markdown
| config | object | No | The config object to use |
| data   | string | No | The data value |
```

**Why wrong**: "The config object to use" tells the reader nothing they couldn't infer from the parameter name. It's word-count theater. Readers need to know: what keys does `config` contain? What is the valid range for `data`?

**Do instead:** Write parameter descriptions that answer what the value means and what constraints apply. Include: the valid range or set of values, the unit (seconds, bytes, count), the effect of omitting an optional field, and any related parameters.

**Fix**:
```markdown
| config | object | No | Configuration overrides. Keys: `timeout` (int, seconds), `retries` (int, 0-5) |
| data   | string | No | Base64-encoded payload. Max 1MB after encoding |
```

---

### ❌ Missing Required/Optional Distinction

**Detection**:
```bash
grep -n "| Parameter | Type | Description |" docs/**/*.md
rg "\| Parameter \| Type \| Description \|" --glob "*.md"
```

**What it looks like**:
```markdown
| Parameter | Type | Description |
|-----------|------|-------------|
| name      | string | Resource name |
| config    | object | Configuration |
```

**Why wrong**: Reader cannot tell which parameters are mandatory without making a failed request. A missing `name` returns 400, and the reader discovers this through failure rather than documentation.

**Do instead:** Always use the four-column format `Parameter | Type | Required | Description`. The `Required` column must be a boolean Yes/No, not embedded prose like "optional if X is set." Readers scan tables; they should not have to read descriptions to determine whether a field is mandatory.

**Fix**: Always include a `Required` column as the third column:
```markdown
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name      | string | Yes    | Resource name (3-63 chars) |
| config    | object | No     | Configuration overrides |
```

---

### ❌ Prose Error Documentation

**Detection**:
```bash
grep -n "returns.*400\|returns.*401\|returns.*500\|will return an error" docs/**/*.md
rg "returns? (a )?4\d\d|returns? (a )?5\d\d" --glob "*.md"
```

**What it looks like**:
```markdown
The endpoint will return a 400 error if the name is invalid, or a 500 error if there
is an internal server error. Authentication failures result in a 401.
```

**Why wrong**: Prose error documentation cannot be scanned. The reader must parse English sentences to find the error code they care about. No resolution guidance is provided.

**Do instead:** Use a `Code | Cause | Resolution` table with one row per error code. Each Resolution cell must be an actionable instruction, not a restatement of the cause. If multiple inputs can produce the same code, add a row for each distinct cause.

**Fix**: Use the error table format (see Correct Patterns above). Every error code gets its own row with Cause and Resolution.

---

### ❌ Undated Version Notes

**Detection**:
```bash
grep -n "changed\|deprecated\|removed\|added in" docs/**/*.md | grep -v "v[0-9]\|[0-9]\.[0-9]"
rg "(changed|deprecated|removed|added) in" --glob "*.md" | grep -v "v\d|\d\.\d"
```

**What it looks like**:
```markdown
> **Note:** The `legacy_mode` parameter was deprecated in a recent release.
```

**Why wrong**: "Recent release" becomes meaningless after time passes. Readers cannot determine if the deprecation applies to the version they're running.

**Do instead:** Prefix every version note with the exact version using the `**Changed in vX.Y.Z:**` or `**Deprecated in vX.Y.Z:**` pattern. Include the removal target version and the migration path in the same sentence so the reader has everything needed to act.

**Fix**:
```markdown
> **Deprecated in v3.2.0:** The `legacy_mode` parameter is deprecated and will be removed in v4.0.0.
> Use `compatibility_level: "v2"` instead.
```

---

## Error-Fix Mappings

| Documentation Error | Root Cause | Fix |
|--------------------|------------|-----|
| Parameter in docs not found by `grep` in source | Hallucinated parameter name | Remove from docs; use exact name from source |
| Response example doesn't match actual API response | Example not tested against running service | Test with `curl`, update to match actual response |
| Error code documented but not in source handlers | Code copied from similar endpoint | `grep -rn "400\|401\|403"` in route handlers to verify |
| Link to another doc section returns 404 | Section heading renamed or removed | Search for heading text in target file |
| `Required: Yes` but param has a default in source | Conflated "required in request" with "must exist" | Check validation code; document the default value |

---

## Detection Commands Reference

```bash
# Vague parameter descriptions
grep -n "the [a-z]* to use\|value of the\|represents the" docs/**/*.md

# Missing Required column in tables
rg "\| Parameter \| Type \| Description \|" --glob "*.md"

# Prose error documentation instead of table
rg "returns? (a )?[45]\d\d" --glob "*.md"

# Undated version notes
grep -n "deprecated\|changed\|removed" docs/**/*.md | grep -v "v[0-9]\|[0-9]\.[0-9]"

# All endpoint descriptions (check 30-word limit)
grep -n "^Creates\|^Updates\|^Deletes\|^Returns\|^Lists\|^Fetches" docs/**/*.md
```

---

## See Also

- `api-doc-anti-patterns.md` — Verification anti-patterns: hallucinated parameters, untested examples
- `runbook-patterns.md` — Operational documentation structure
- [Google Developer Documentation Style Guide](https://developers.google.com/style)
- [OpenAPI 3.1 Specification](https://spec.openapis.org/oas/v3.1.0)
