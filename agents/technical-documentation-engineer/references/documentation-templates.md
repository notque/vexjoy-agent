# Documentation Templates Reference

> Loaded by technical-documentation-engineer when writing API endpoint docs, integration guides, or source code verification workflows from scratch.

## API Endpoint Documentation Template

```markdown
### POST /api/v1/resource

Creates a new resource with the specified configuration.

**Authentication:** Bearer token required

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | Yes | Resource name (3-63 chars) |
| config | object | Yes | Configuration object |
| tags | array | No | Optional resource tags |

**Request Example:**

\`\`\`bash
curl -X POST https://api.example.com/api/v1/resource \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-resource",
    "config": {
      "setting1": "value1"
    },
    "tags": ["production"]
  }'
\`\`\`

**Response (201 Created):**

\`\`\`json
{
  "id": "res_abc123",
  "name": "my-resource",
  "status": "active",
  "created_at": "2025-01-15T10:30:00Z"
}
\`\`\`

**Error Responses:**

| Code | Cause | Resolution |
|------|-------|------------|
| 400 | Invalid name format | Use 3-63 alphanumeric chars |
| 401 | Missing/invalid token | Provide valid Bearer token |
| 409 | Resource name exists | Choose unique name |
| 500 | Internal server error | Contact support with request ID |

**Troubleshooting:**

- **Issue:** 400 error with "Invalid config"
  - **Cause:** Missing required config fields
  - **Resolution:** Include all required config parameters

- **Issue:** Slow response (>5s)
  - **Cause:** Large tag arrays
  - **Resolution:** Limit tags to 10 per resource
```

## Integration Guide Template

```markdown
## Service Integration Guide

### Prerequisites
- Service A running on port 8080
- Service B credentials configured
- Network connectivity between services

### Configuration

**Service A config.yaml:**
\`\`\`yaml
service_b:
  endpoint: https://service-b.example.com
  api_key: ${SERVICE_B_API_KEY}
  timeout: 30s
  retry: 3
\`\`\`

### Authentication Flow

1. Service A requests token from Service B
2. Service B validates credentials and returns JWT
3. Service A includes JWT in subsequent requests
4. Token expires after 1 hour (automatic refresh)

### Common Integration Issues

**Issue: Connection refused**
- Verify Service B is running: `curl https://service-b.example.com/health`
- Check network policies allow traffic
- Confirm firewall rules permit port 443

**Issue: Authentication failures**
- Verify API key is correct in config
- Check Service B logs for specific error
- Ensure credentials haven't expired
```

## Source Code Verification Workflow

### Phase 1: Gather Source Files
1. Identify relevant source files for documented feature
2. Read route handlers, API controllers, model definitions
3. Extract actual parameter names, types, validation rules
4. Note error codes returned by implementation

### Phase 2: Cross-Reference Documentation (with constraints at point of failure)

1. Compare documented parameters vs actual code
2. Verify parameter types match implementation
3. Confirm error codes exist in codebase
4. Check authentication requirements match middleware

**When documenting parameters:** Every parameter you document MUST exist in the source code. If you cannot find a parameter by grep/search, it is hallucinated. STOP and remove it rather than guessing. Because hallucinated parameters in docs cause integration failures that are harder to debug than missing docs.

**When documenting return values:** Return types must match the actual function signature. Do not infer types from usage -- read the declaration.

> **STOP.** Did you verify each parameter exists in the source? Grep for it. If grep returns 0 results, the parameter is hallucinated. Remove it now.

### Phase 3: Example Verification

1. Test curl examples against running service (if available)
2. Verify request/response formats match actual API
3. Confirm error scenarios produce documented error codes
4. Validate authentication flows work as described

> **STOP.** Does this example actually compile/run? If you haven't tested it or verified the imports exist, it's fiction, not documentation.

### Phase 4: Quality Assurance

1. Check documentation completeness (all parameters documented)
2. Verify consistency across related endpoints
3. Validate cross-references to other documentation
4. Confirm professional quality standards met

> **STOP.** Count the endpoints in source vs endpoints in your doc. If they don't match, you missed something or invented something.

## Preferred Patterns

### Verify Against Source Before Documenting

**What it looks like (wrong):**
```markdown
### POST /api/users
Creates a user with name and email.

Parameters: name (string), email (string), age (number)
```

**Why wrong:** Parameters may not match actual implementation, missing required fields

**Do instead:**
1. Read actual route handler code
2. Extract exact parameter names and types from validation
3. Identify which fields are required vs optional
4. Document complete parameter set with correct types

### Test All Code Examples

**What it looks like (wrong):**
```bash
curl -X POST https://api.example.com/users \
  -d '{"name": "John"}'  # Example never tested
```

**Why wrong:** Example may have syntax errors, missing headers, wrong endpoint

**Do instead:**
1. Test curl command against actual API
2. Verify it returns expected response
3. Include all required headers (Content-Type, Authorization)
4. Show complete working example

### Document All Error Codes With Resolutions

**What it looks like (wrong):**
```markdown
**Errors:** Returns 400 if invalid, 500 if server error
```

**Why wrong:** Doesn't specify what makes request invalid, no resolution guidance

**Do instead:**
```markdown
**Error Responses:**

| Code | Cause | Resolution |
|------|-------|------------|
| 400 | Missing required field "email" | Include email in request body |
| 400 | Invalid email format | Use valid email: user@example.com |
| 409 | Email already registered | Use different email or login |
| 500 | Database connection failed | Retry or contact support |
```

### Specific Root-Cause Troubleshooting

**What it looks like (wrong):**
```markdown
**Troubleshooting:**
- If it doesn't work, check your configuration
- Contact support if problems persist
```

**Why wrong:** No specific guidance, no root cause analysis

**Do instead:**
```markdown
**Troubleshooting:**

**Issue:** 401 Unauthorized error
- **Cause:** Missing or invalid API key
- **Resolution:**
  1. Verify API key in config: `cat config.yaml | grep api_key`
  2. Test key validity: `curl -H "X-API-Key: $KEY" /validate`
  3. Regenerate key if needed: `service admin regenerate-key`

**Issue:** Timeout after 30 seconds
- **Cause:** Large response payload exceeding default timeout
- **Resolution:** Increase timeout in config: `timeout: 60s`
```

## Adversarial Self-Check (run before finalizing ANY documentation)

Before declaring documentation complete, execute this checklist literally as actual tool invocations:

1. **Grep every parameter name** you documented against the source. Any name returning 0 results is hallucinated. Remove it.
2. **Grep every endpoint path** you documented. If it doesn't exist in route definitions, you invented it. Remove it.
3. **Grep every return type** you documented. If it doesn't match the function signature, your doc has a type bug. Fix it.
4. **Count source endpoints** vs documented endpoints. If the counts differ, find the discrepancy and resolve it.
5. **For each code example**, verify that every import, function call, and type reference exists in the codebase. Fictional imports are a documentation defect.
