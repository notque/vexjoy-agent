# PII Exposure Patterns

Load when reviewing code that handles personal data in logs, test fixtures, error responses, serialized output, URLs, telemetry, or git history.

PII exposure occurs when personally identifiable information appears in a context with broader visibility, longer retention, or lower trust than intended. The correct approach is to use synthetic data in tests, structured identifiers (not raw PII) in logs, and explicit field selection in API responses. Every exposure path should be justified by a documented purpose.

---

## Use Synthetic Data in Test Fixtures

Test data, fixtures, snapshots, cassettes, and seed files must use obviously synthetic identifiers. Replace real customer emails, names, account slugs, and business data with RFC-standard examples or clearly fake values. Real data copied from support tickets, CRM exports, or production databases becomes part of permanent git history.

### Correct Pattern

**Python:**
```python
# Use RFC 2606 reserved domains — unambiguously synthetic
fixture = {
    "email": "user@example.com",
    "org_slug": "org-slug",
    "name": "Jane Doe",
    "ip": "198.51.100.23",       # RFC 5737 documentation range
    "arr_usd": 120000,            # Round number — obviously synthetic
    "renewal_date": "2026-01-01",
}
```

**TypeScript:**
```ts
const fixture = {
  email: 'user@example.com',
  orgSlug: 'org-slug',
  name: 'John Doe',
  ip: '203.0.113.42',  // RFC 5737 TEST-NET-3
  monthlySpend: 1000,
  seatCount: 25,
};
```

### Safe Domains and IP Ranges

| Type | Safe Values | Standard |
|------|-------------|----------|
| Email domains | `example.com`, `example.org`, `example.net`, `example.edu`, `.invalid` | RFC 2606 |
| IPv4 addresses | `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` | RFC 5737 |
| IPv6 addresses | `2001:db8::/32` | RFC 3849 |
| Names | `Jane Doe`, `John Doe`, `Alice`, `Bob`, `Acme Corp` | Convention |
| Org identifiers | `org-slug`, `example-org`, `demo-customer` | Convention |

### Why This Matters

Real customer data in git history cannot be fully purged. Force-pushing rewrites break collaborators, and the data persists in forks, CI caches, and local clones. A single real email address in a test fixture is a GDPR data subject access request waiting to happen. Real customer revenue, contract values, or account health data in fixtures violates confidentiality obligations even in private repositories.

### Detection

```bash
# Find email addresses in test files (excluding example.com and common safe patterns)
rg -n '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' tests/ fixtures/ --type py --type ts | \
  rg -v 'example\.(com|org|net)|noreply|test@|foo@|user@'

# Find IP addresses in test files (excluding documentation ranges)
rg -n '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b' tests/ fixtures/ | \
  rg -v '192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|127\.0\.0\.|0\.0\.0\.0|10\.\|172\.(1[6-9]|2|3[01])\.|192\.168\.'

# Find potential customer data in fixtures
rg -n 'customer|account.*slug|org.*slug|tenant' tests/ fixtures/ --type py --type ts
```

---

## Log Structured Identifiers Instead of Raw PII

Log the user's internal ID, a salted hash of their email, or a correlation ID — never the raw email, IP address, phone number, or request body. Operational logs are retained for months or years, shipped to third-party log aggregators, and accessible to broad operations teams.

### Correct Pattern

**Python:**
```python
import hashlib

def hash_email(email: str) -> str:
    """Stable hash for log correlation without exposing the address."""
    return hashlib.sha256(f"salt:{email}".encode()).hexdigest()[:12]

# Log with internal identifiers only
logger.warning(
    "identity lookup failed",
    extra={"user_id": user.id, "email_hash": hash_email(user.email)},
)
```

**TypeScript:**
```ts
// Log internal ID and reason, not the raw PII
logger.warn('signup failed', {
  userId: user.id,
  reason: 'validation_failed',
  // Never: email: req.body.email, ip: req.ip, body: req.body
});
```

**Go:**
```go
// Structured logging with internal identifiers
slog.Warn("identity lookup failed",
    "user_id", user.ID,
    "error", err,
    // Never: "email", user.Email, "ip", r.RemoteAddr
)
```

### Why This Matters

PII in logs creates a secondary data store that bypasses the application's access controls. Log aggregators (Datadog, Splunk, Elasticsearch) retain data for months, index it for full-text search, and make it available to operations teams who should not have access to individual user data. Logging `request.body` or `request.headers` wholesale captures passwords, tokens, and personal data indiscriminately.

### Detection

```bash
# Python: logging with email, IP, or request body
rg -n 'logger\.\w+\(.*email|logger\.\w+\(.*REMOTE_ADDR|logger\.\w+\(.*request\.(body|data|META)' --type py

# TypeScript: logging with PII fields
rg -n 'logger\.\w+\(.*email|logger\.\w+\(.*req\.(body|ip)|console\.\w+\(.*email' --type ts

# Find Sentry scope setting with PII
rg -n 'set_user\(|set_tag\(.*email|set_extra\(.*email' --type py

# Find metrics/analytics with PII tags
rg -n 'metrics\.\w+\(.*email|tags.*email|dimensions.*email' --type py --type ts

# Go: logging with PII
rg -n 'slog\.\w+\(.*email|log\.\w+\(.*email|zap\.\w+\(.*email' --type go
```

---

## Keep PII Out of URL Query Strings and Path Segments

Emails, phone numbers, names, and user identifiers in URLs appear in browser history, server access logs, CDN logs, referrer headers, and analytics tools. Use server-side sessions, POST bodies, or opaque tokens to pass identity information between pages.

### Correct Pattern

**Python:**
```python
# Store error context in the session, not the URL
request.session["login_error"] = "invalid_magic_code"
return redirect("/login/error")
```

**TypeScript:**
```ts
// Use an opaque error code, not the email
return redirect('/oauth/error?reason=invalid_code');
```

### Why This Matters

URL query parameters appear in HTTP access logs (which are retained for months), browser history (accessible to anyone with physical access), CDN logs (managed by third parties), and the `Referer` header (sent to every resource loaded on the target page). An email in a redirect URL like `/login/error?email=user@company.com` leaks the address to every downstream system that processes the URL.

### Detection

```bash
# Find redirects with email-like parameters
rg -n 'redirect.*email=|redirect.*user=|redirect.*phone=' --type py --type ts

# Find URL construction with PII
rg -n 'f".*\?.*email|`.*\?.*email|\?.*email=' --type py --type ts

# Find PII in URL path segments
rg -n 'url.*email|path.*email|route.*email' --type py --type ts
```

---

## Exclude PII Fields from Serialized API Responses

API serializers and GraphQL resolvers must declare an explicit field list that excludes PII not required by the caller. When an endpoint returns user data, include only the fields the client needs — not the full database row with email, IP, phone, and internal identifiers.

### Correct Pattern

**Python (DRF):**
```python
class UserPublicSerializer(ModelSerializer):
    class Meta:
        model = User
        # Only fields the public client needs
        fields = ['id', 'display_name', 'avatar_url']
        # Explicitly NOT included: email, phone, ip_address, password_hash
```

**TypeScript (Prisma):**
```ts
// Select only public fields — email and internal data excluded
const user = await prisma.user.findUnique({
  where: { id },
  select: { id: true, displayName: true, avatarUrl: true },
});
return res.json(user);
```

**GraphQL:**
```graphql
type UserPublic {
  id: ID!
  displayName: String!
  avatarUrl: String
  # email, phone, ipAddress intentionally excluded from public type
}
```

### Why This Matters

Over-broad serialization leaks PII to callers who do not need it. A `fields = '__all__'` serializer on a DRF endpoint exposes every column, including fields added by future database migrations. GraphQL introspection with broad types lets callers request any field. Full-row Prisma queries without `select` return password hashes, 2FA secrets, and internal flags. The problem compounds when API responses are cached by CDNs or stored by clients.

### Detection

```bash
# DRF: serializers that expose all fields
rg -n "fields = '__all__'" --type py

# Find GraphQL types exposing email or phone
rg -n 'email|phone|ipAddress|password' --type graphql --type ts | rg 'type |interface '

# Check for full-row returns in API handlers
rg -n 'findUnique\(|findFirst\(' --type ts | rg -v 'select:'
```

---

## Scrub PII from Error Responses and Exception Handlers

Error responses sent to clients must contain only a generic message and a correlation ID for server-side lookup. Stack traces, SQL queries, request bodies, and user identifiers belong in server-side logs behind access controls.

### Correct Pattern

**Python:**
```python
import uuid

@app.errorhandler(Exception)
def handle_error(error):
    correlation_id = str(uuid.uuid4())
    # Full details stay server-side
    app.logger.error(
        "unhandled exception",
        extra={"correlation_id": correlation_id, "error": str(error)},
        exc_info=True,
    )
    # Client gets only the correlation ID for support reference
    return {"error": "internal server error", "reference": correlation_id}, 500
```

**TypeScript:**
```ts
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  const correlationId = crypto.randomUUID();
  console.error({ correlationId, error: err.stack });
  // Client sees only the reference — no stack, no SQL, no paths
  res.status(500).json({ error: 'internal server error', reference: correlationId });
});
```

### Why This Matters

Unhandled exception responses routinely include SQL query fragments (exposing table names and WHERE clauses with user data), file paths (revealing application structure), environment variables (sometimes including credentials), and the user's request data echoed back (including any PII they submitted). These details aid attackers in refining subsequent attacks and violate privacy expectations when user data appears in error pages viewed by third parties.

### Detection

```bash
# Find error handlers that may leak details
rg -n 'err\.stack|error\.stack|traceback|exc_info' --type py --type ts | rg -v 'logger\.|console\.'

# Find exception responses with request data
rg -n 'request\.(body|data|form)|req\.body' --type py --type ts | rg 'return |res\.(json|send)'

# Check for PII fields in Sentry/error tracking context
rg -n 'set_user\(|set_context\(|set_extra\(' --type py | rg 'email|phone|ip|address'
```

---

## Detect Common PII Patterns in Code

Use these detection commands during review to scan for PII that may have been committed inadvertently. These patterns catch the most common cases — real email addresses, phone numbers, and social security numbers in source files.

### Detection Commands

```bash
# Email addresses (excluding safe domains and common patterns)
rg -n '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' --type py --type ts --type js \
  --glob '!node_modules/*' --glob '!vendor/*' | \
  rg -v 'example\.(com|org|net)|noreply|test@|foo@|bar@|user@|\.invalid'

# US phone numbers (XXX-XXX-XXXX, (XXX) XXX-XXXX, XXX.XXX.XXXX)
rg -n '\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b' --type py --type ts --type js \
  --glob '!node_modules/*'

# US Social Security Numbers (XXX-XX-XXXX)
rg -n '\b\d{3}-\d{2}-\d{4}\b' --type py --type ts --type js \
  --glob '!node_modules/*'

# Credit card patterns (13-19 digits, possibly separated by spaces or dashes)
rg -n '\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,7}\b' --type py --type ts --type js \
  --glob '!node_modules/*'

# IP addresses in non-test code (excluding documentation ranges)
rg -n '\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b' --type py --type ts \
  --glob '!tests/*' --glob '!*test*' --glob '!node_modules/*' | \
  rg -v '0\.0\.0\.0|127\.0\.0\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.'

# AWS access keys (starts with AKIA)
rg -n 'AKIA[0-9A-Z]{16}' --type py --type ts --type js

# Customer-specific data patterns in fixtures and tests
rg -n 'customer.*email|real.*email|production.*data|copied.*from.*ticket' \
  tests/ fixtures/ --type py --type ts
```

### Distinguishing Real PII from Safe Placeholders

Before reporting, verify the finding is real:

1. **Check the domain.** RFC 2606 domains (`example.com`, `example.org`, `example.net`, `.invalid`) are safe by design.
2. **Check the context.** Git author metadata, translator credits, `Co-authored-by` headers, and public package maintainer info are public by choice.
3. **Check the IP range.** RFC 5737 documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and RFC 3849 (`2001:db8::/32`) are reserved for examples.
4. **Check the file role.** A file in `tests/` with obviously synthetic names and round numbers is fixture data, not a leak.
5. **Check the sink.** A user email in application memory is normal. The same email in a log statement, URL, metric tag, or error response is a finding.
