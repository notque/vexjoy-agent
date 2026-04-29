# Security Finding Template

Every security finding must fill ALL fields below. If you cannot fill the "Exploitation Path" with concrete variable names and file references, the finding does not qualify. Drop it or report it as an observation, not a finding.

## Finding Structure

```
### [SEVERITY] [N]: [Title — states the vulnerability, not the fix]

- **File**: `path/to/file.ext:line`
- **Vulnerability Class**: [One of: Authorization, Injection, Data Exfiltration, CI/CD, PII Exposure]
- **Exploitation Path**: [source] → [intermediate steps with variable names] → [sink]
  Example: `request.query.id` → `OrderController.get()` → `db.order.findUnique({ where: { id } })` — no ownership filter
- **Severity**: [CRITICAL | HIGH | MEDIUM | LOW]
  Evidence: [Why this severity — blast radius, auth requirement, data sensitivity]
  When uncertain, pick the lower severity and state why.
- **Verified**: `rg -n 'pattern' path/to/file.ext` → [output excerpt proving the finding]
- **Correct Pattern**:
  ```language
  // The fix, with explanatory comments
  ```
```

## Severity Criteria

| Level | Criteria | Example |
|-------|----------|---------|
| CRITICAL | Unauthenticated access to sensitive data or code execution | Unauthenticated SSRF to cloud metadata, unauthenticated RCE via deserialization |
| HIGH | Authenticated but cross-tenant/cross-user access, or authenticated code execution | IDOR exposing other users' data, authenticated command injection |
| MEDIUM | Requires specific preconditions or produces bounded impact | Fail-open permission check needing unknown role string, path traversal bounded by directory |
| LOW | Defense-in-depth gap where primary control holds | Missing secondary authorization layer, verbose error in internal service |

## Qualification Gate

A finding qualifies only when all three conditions are true:

1. **The source is attacker-reachable.** Values from request body, query, headers, URL path, uploaded files, webhook payloads, PR titles, comment bodies, or user-controlled database fields. Hardcoded constants and server-derived values do not qualify.

2. **The sink produces impact.** The data reaches a code-execution API, crosses a trust boundary, exposes non-public information, or bypasses an authorization decision.

3. **The path is traceable.** You followed the data from source through every intermediate function, middleware, and validation layer to the sink. Pattern-matching a function name is not tracing.

## Verification Commands

Every finding must include a verification command that another reviewer can run to confirm the issue exists. Examples:

```bash
# Find unscoped ORM lookups in Django views
rg -n 'objects\.(get|filter)\(id=' --type py

# Find shell=True subprocess calls
rg -n 'shell=True' --type py

# Find raw SQL with string interpolation
rg -n '\$queryRawUnsafe|\.raw\(f"|\.extra\(where=\[f"' --type py

# Find user-controlled URLs passed to fetch/requests
rg -n 'requests\.get\(|fetch\(|axios\.(get|post)\(' --type py --type ts

# Find pickle.loads on request data
rg -n 'pickle\.loads|cloudpickle\.loads|joblib\.load' --type py

# Find expression injection in GitHub Actions
rg -n '\$\{\{.*github\.event\.' .github/workflows/
```

## Cross-Reference Rule

A single code location that spans multiple vulnerability classes is one finding with multiple class tags, not separate findings. Example: an unscoped ORM query that also leaks PII in the response is one finding tagged `[Authorization, PII Exposure]`.
