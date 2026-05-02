# Security Finding Template

Every security finding must fill ALL fields below. If "Exploitation Path" cannot be filled with concrete variable names and file references, the finding does not qualify. Drop it or report as observation.

## Finding Structure

```
### [SEVERITY] [N]: [Title — states the vulnerability, not the fix]

- **File**: `path/to/file.ext:line`
- **Vulnerability Class**: [Authorization | Injection | Data Exfiltration | CI/CD | PII Exposure]
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
| CRITICAL | Unauthenticated access to sensitive data or code execution | Unauthenticated SSRF to cloud metadata, unauthenticated RCE |
| HIGH | Authenticated cross-tenant/cross-user access, or authenticated code execution | IDOR exposing other users' data, authenticated command injection |
| MEDIUM | Requires specific preconditions or bounded impact | Fail-open permission check needing unknown role string |
| LOW | Defense-in-depth gap where primary control holds | Missing secondary auth layer, verbose error in internal service |

## Qualification Gate

A finding qualifies only when all three are true:

1. **Source is attacker-reachable.** Request body, query, headers, URL path, uploaded files, webhook payloads, PR titles, comment bodies, user-controlled DB fields. Hardcoded constants do not qualify.

2. **Sink produces impact.** Reaches code-execution API, crosses trust boundary, exposes non-public information, or bypasses authorization.

3. **Path is traceable.** Data followed from source through every intermediate function, middleware, and validation layer to sink. Pattern-matching a function name is not tracing.

## Verification Commands

Every finding must include a runnable verification command:

```bash
# Unscoped ORM lookups
rg -n 'objects\.(get|filter)\(id=' --type py

# shell=True subprocess calls
rg -n 'shell=True' --type py

# Raw SQL with string interpolation
rg -n '\$queryRawUnsafe|\.raw\(f"|\.extra\(where=\[f"' --type py

# User-controlled URLs passed to fetch/requests
rg -n 'requests\.get\(|fetch\(|axios\.(get|post)\(' --type py --type ts

# pickle.loads on request data
rg -n 'pickle\.loads|cloudpickle\.loads|joblib\.load' --type py

# Expression injection in GitHub Actions
rg -n '\$\{\{.*github\.event\.' .github/workflows/
```

## Cross-Reference Rule

A single code location spanning multiple vulnerability classes is one finding with multiple class tags, not separate findings.
