# Data Exfiltration Patterns

Load when reviewing code that handles URL fetching, file paths, raw SQL queries, XML parsing, response serialization, debug modes, or error handling that may expose internal data.

Data exfiltration occurs when data crosses a trust boundary it should not: internal services exposed via SSRF, filesystem contents leaked via path traversal, database contents dumped via SQL injection, or internal fields shipped to clients via over-broad serialization. The correct approach is to validate inputs at the boundary and expose only the fields the caller needs.

---

## Validate URLs at the IP Layer Before Fetching

When the application fetches a URL provided by the user (webhooks, image proxies, import-from-URL flows), validate the resolved IP address against a blocklist of internal ranges. String-based URL checks fail because DNS rebinding, IP encoding tricks, and redirects all bypass hostname validation.

### Correct Pattern

**Python:**
```python
import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local, includes cloud metadata
]

def safe_fetch(user_url: str) -> bytes:
    parsed = urlparse(user_url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('scheme not allowed')

    # Resolve hostname to IP and check against blocklist
    addr = socket.getaddrinfo(parsed.hostname, parsed.port or 443)[0][4][0]
    ip = ipaddress.ip_address(addr)
    if any(ip in net for net in BLOCKED_RANGES):
        raise ValueError('internal IP not allowed')

    # Disable redirect following — redirects can point to internal IPs
    resp = requests.get(user_url, allow_redirects=False, timeout=10)
    return resp.content
```

**TypeScript:**
```ts
import { lookup } from 'dns/promises';
import ipaddr from 'ipaddr.js';

const BLOCKED_RANGES = ['private', 'linkLocal', 'loopback', 'uniqueLocal', 'unspecified'];

async function safeFetch(userUrl: string): Promise<Response> {
  const parsed = new URL(userUrl);
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('scheme not allowed');
  }

  // Resolve and validate IP before connecting
  const { address } = await lookup(parsed.hostname);
  const ip = ipaddr.parse(address);
  if (BLOCKED_RANGES.includes(ip.range())) {
    throw new Error('internal IP not allowed');
  }

  return fetch(parsed.href, { redirect: 'manual' });
}
```

### Why This Matters

SSRF lets an attacker use the server as a proxy to reach internal services, cloud metadata endpoints, and other resources invisible from the internet. The most damaging target is the cloud metadata service at `169.254.169.254`, which returns IAM credentials, instance identity, and user data. String-based URL blocklists fail because DNS can return any IP for an attacker-owned domain, and redirects move the request mid-flight.

**CVEs:** Capital One 2019 (SSRF to IMDSv1 stole IAM credentials, 30GB exfiltrated from S3), CVE-2021-26855 (Exchange ProxyLogon — unauthenticated SSRF with domain-computer credentials), CVE-2024-34351 (Next.js Server Actions SSRF — Host header manipulation redirected internal fetches), CVE-2020-28168 (axios redirect bypass — proxy validation applied only to first request), CVE-2024-21893 (Ivanti Connect Secure SAML SSRF chained with auth bypass).

### Detection

```bash
# Python: requests/urllib with user-controlled URL
rg -n 'requests\.(get|post|put)\(|urlopen\(|urllib\.request' --type py

# TypeScript: fetch/axios/got with user URL variable
rg -n 'fetch\(|axios\.(get|post)\(|got\(' --type ts --type js

# Look for webhook/callback URL handling
rg -n 'callback_url|webhook_url|target_url|redirect_url' --type py --type ts

# Check for missing IP validation
rg -n 'allow_redirects=True' --type py
```

---

## Contain File Paths with Realpath Validation

When serving files based on user-supplied names or paths, resolve the full path and verify it stays within the intended base directory. Use `Path.resolve()` or `os.path.realpath()` and confirm the result starts with the base directory.

### Correct Pattern

**Python:**
```python
from pathlib import Path
from flask import abort, send_file

def serve_export(name: str):
    base = Path("/var/app/exports").resolve()
    target = (base / name).resolve()

    # Verify the resolved path is still inside the base directory
    if not target.is_relative_to(base):
        abort(403)

    return send_file(target)
```

**TypeScript:**
```ts
import path from 'path';

function serveFile(name: string, res: Response) {
  const base = path.resolve('/var/app/exports');
  const target = path.resolve(base, name);

  // Verify containment after resolving symlinks and ../
  if (!target.startsWith(base + path.sep)) {
    return res.sendStatus(403);
  }

  res.sendFile(target);
}
```

**Go:**
```go
func serveExport(w http.ResponseWriter, r *http.Request) {
    base := "/var/app/exports"
    name := filepath.Base(r.URL.Query().Get("name")) // Strip directory components
    target := filepath.Join(base, name)

    // filepath.Base already strips ../ but verify containment
    clean, err := filepath.EvalSymlinks(target)
    if err != nil || !strings.HasPrefix(clean, base) {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }

    http.ServeFile(w, r, clean)
}
```

**Archive extraction (Python):**
```python
import tarfile

def safe_extract(archive_path: str, dest: str):
    with tarfile.open(archive_path) as tar:
        # Python 3.12+: filter="data" blocks path traversal and special files
        tar.extractall(path=dest, filter="data")
```

### Why This Matters

Path traversal allows reading arbitrary files from the server filesystem. `../../../etc/passwd` is the classic payload, but the real targets are configuration files with credentials, application source code, and database files. Archive extraction (tar, zip) compounds the risk — a malicious archive can write files outside the extraction directory (zip-slip).

**CVEs:** CVE-2007-4559 (Python tarfile — extractall without path validation, 15+ years unpatched), CVE-2022-48285 (jszip path traversal), CVE-2023-26111 (node-static path traversal).

### Detection

```bash
# Python: os.path.join or Path with user input, without containment check
rg -n 'os\.path\.join\(|Path\(' --type py | rg -v 'resolve\(\)|realpath'

# Python: tarfile.extractall without filter (pre-3.12 pattern)
rg -n 'extractall\(' --type py | rg -v 'filter='

# TypeScript: sendFile or readFile with user path
rg -n 'sendFile\(|readFile\(|readFileSync\(' --type ts

# Python: open() with user-supplied path
rg -n 'open\(.*request\.|open\(.*user_' --type py
```

---

## Use Parameterized Queries for All Database Access

Pass user values as parameters, never as interpolated strings. Every ORM and database driver supports parameterized queries — use them. When the ORM cannot express a query, use the driver's parameter binding, not string formatting.

### Correct Pattern

**Python (Django):**
```python
# ORM query — parameterized by default
invoices = Invoice.objects.filter(customer_id=request.GET["cid"])

# When raw SQL is unavoidable, use parameter binding
Invoice.objects.extra(
    where=["customer_id = %s"],
    params=[request.GET["cid"]]
)

# Or use RawSQL with params
from django.db.models.expressions import RawSQL
Invoice.objects.annotate(
    val=RawSQL("SELECT balance FROM accounts WHERE id = %s", [account_id])
)
```

**TypeScript (Prisma):**
```ts
// Tagged template — automatically parameterized
const users = await prisma.$queryRaw`
  SELECT * FROM users WHERE name = ${name}
`;

// NEVER use $queryRawUnsafe with user input
// await prisma.$queryRawUnsafe(`SELECT * FROM users WHERE name = '${name}'`);  // SQL injection
```

**Go:**
```go
// Use query parameters — ? or $1 depending on driver
row := db.QueryRowContext(ctx,
    "SELECT * FROM orders WHERE id = $1 AND user_id = $2",
    orderID, userID,
)
```

### Why This Matters

SQL injection through string interpolation in queries remains one of the most exploited vulnerability classes. Even ORMs provide escape hatches (`.raw()`, `.extra()`, `$queryRawUnsafe`) that bypass parameterization. When these methods receive f-strings or template literals with user data, the application is vulnerable to data exfiltration, authentication bypass, and in some databases, code execution.

**CVEs:** CVE-2023-25813 (Sequelize `literal()` injection), CVE-2025-23061 (Mongoose `populate({match: userObj})` NoSQL injection).

### Detection

```bash
# Django: raw SQL with string formatting
rg -n '\.raw\(f"|\.extra\(where=\[f"|cursor\.execute\(f"|RawSQL\(f"' --type py

# SQLAlchemy: text() with f-string
rg -n 'text\(f"|session\.execute\(f"' --type py

# Prisma: $queryRawUnsafe (always review)
rg -n '\$queryRawUnsafe|\$executeRawUnsafe' --type ts

# Sequelize: literal with user data
rg -n 'literal\(|sequelize\.query\(' --type ts --type js

# Go: string concatenation in SQL
rg -n 'fmt\.Sprintf.*SELECT|fmt\.Sprintf.*INSERT|fmt\.Sprintf.*UPDATE' --type go
```

---

## Disable External Entity Resolution in XML Parsers

Configure XML parsers to reject Document Type Definitions (DTDs) and external entity references before parsing untrusted XML. Use `defusedxml` in Python. In Java, set the four companion feature flags on `DocumentBuilderFactory`.

### Correct Pattern

**Python:**
```python
# Use defusedxml — safe defaults for all XML operations
from defusedxml import ElementTree as ET
tree = ET.fromstring(request.data)

# Or configure lxml explicitly
from lxml import etree
parser = etree.XMLParser(resolve_entities=False, no_network=True)
tree = etree.fromstring(request.data, parser=parser)
```

**Java:**
```java
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
// Disable all external entity processing
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
DocumentBuilder builder = factory.newDocumentBuilder();
```

**TypeScript/Node:**
```ts
// libxmljs: disable entity resolution
const doc = libxmljs.parseXml(xmlString, { noent: false, nonet: true });
```

### Why This Matters

XXE (XML External Entity) attacks use DTD references to read files from the server (`file:///etc/passwd`), make SSRF requests (`http://169.254.169.254/`), or in Java environments, reach deserialization gadgets via JNDI lookups. Python's standard library `xml.etree.ElementTree` resolves entities by default. SAML, OOXML, and SOAP parsers that wrap unsafe XML stages inherit the vulnerability.

**CVEs:** CVE-2024-6508 (lxml entity resolution bypass family).

### Detection

```bash
# Python: stdlib XML parsers on untrusted input (use defusedxml instead)
rg -n 'xml\.etree|xml\.sax|xml\.dom\.minidom|xml\.parsers\.expat' --type py

# Python: lxml without safe configuration
rg -n 'etree\.fromstring\(|etree\.parse\(' --type py | rg -v 'resolve_entities=False'

# Java: DocumentBuilder without entity restrictions
rg -n 'DocumentBuilderFactory|SAXParserFactory' --type java

# Check for defusedxml usage (safe)
rg -n 'defusedxml' --type py
```

---

## Expose Only Required Fields in API Responses

Define explicit field lists or DTOs for every API response. The database row is never the API response — select only the fields the client needs and exclude internal identifiers, password hashes, tokens, and debug information.

### Correct Pattern

**Python (DRF):**
```python
class UserPublicSerializer(ModelSerializer):
    class Meta:
        model = User
        # Explicit field list — password_hash, 2fa_secret, internal flags excluded
        fields = ['id', 'display_name', 'avatar_url']
```

**Python (FastAPI/Pydantic):**
```python
class UserResponse(BaseModel):
    id: int
    display_name: str
    avatar_url: str | None

    class Config:
        extra = "ignore"  # Silently drop unknown fields from ORM row

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    user = await User.get(id=user_id)
    return user  # Pydantic response_model filters to declared fields only
```

**TypeScript (Prisma):**
```ts
// Select only the fields needed — never return the raw row
const user = await prisma.user.findUnique({
  where: { id },
  select: { id: true, displayName: true, avatarUrl: true },
});
return res.json(user);
```

**Go:**
```go
// Define a response struct separate from the database model
type UserResponse struct {
    ID          string `json:"id"`
    DisplayName string `json:"display_name"`
    AvatarURL   string `json:"avatar_url,omitempty"`
}
```

### Why This Matters

Returning raw database rows leaks internal fields to clients: password hashes, API tokens, internal feature flags, billing details, and fields added by future migrations. Pydantic models with `extra = "allow"` pass through unexpected fields transparently. DRF serializers with `fields = '__all__'` expose every column.

Real incident: Sentry commit `0c0aae90ac1` — Pydantic model with `extra = "allow"` leaked internal `SeerRunState` fields in the API response.

### Detection

```bash
# DRF: serializers that expose all fields
rg -n "fields = '__all__'" --type py

# FastAPI: endpoints without response_model (raw ORM row returned)
rg -n '@app\.(get|post|put|patch)' --type py | rg -v 'response_model='

# Pydantic: models allowing extra fields
rg -n 'extra = .allow.' --type py

# Prisma/Sequelize: queries without select
rg -n 'findUnique\(|findFirst\(|findMany\(' --type ts | rg -v 'select:'

# Debug mode in production
rg -n 'DEBUG = True|debug: true|stackTrace.*true' --type py --type ts --type js
```

---

## Disable Debug Modes and Verbose Error Responses in Production

Production error responses must return a generic message to the client and log the full stack trace server-side. Framework debug modes (Django `DEBUG=True`, Flask `debug=True`, Express `err.stack` in responses) expose source code, configuration, SQL queries, and internal paths.

### Correct Pattern

**Python (Flask):**
```python
@app.errorhandler(500)
def internal_error(error):
    # Log full details server-side
    app.logger.error("Internal error", exc_info=error)
    # Return generic message to client
    return {"error": "internal server error"}, 500
```

**TypeScript (Express):**
```ts
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  // Log full stack server-side
  console.error(err.stack);
  // Generic response to client — no stack trace, no SQL, no paths
  res.status(500).json({ error: 'internal server error' });
});
```

### Why This Matters

Debug error pages reveal the application's internal structure: file paths, database queries, configuration values, environment variables, and sometimes credentials. Django's debug page shows the full settings dictionary. Flask's Werkzeug debugger provides an interactive Python console. Express's default error handler includes `err.stack` which contains file paths and line numbers.

### Detection

```bash
# Django/Flask debug mode
rg -n 'DEBUG = True|debug=True|app\.debug' --type py

# Express: error stack in response
rg -n 'err\.stack|error\.stack|traceback' --type ts --type js

# Python: traceback in response body
rg -n 'traceback\.format_exc\(\)|traceback\.print_exc\(\)' --type py
```
