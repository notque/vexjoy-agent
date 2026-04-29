# Python Secure Implementation Patterns

Secure-by-default patterns for Python 3.11+ applications. Each section shows what correct code looks like and why it matters. Load this reference when the task involves security, auth, injection, XSS, CSRF, SSRF, deserialization, file handling, or any vulnerability-related code.

---

## Use List Arguments for Subprocess Calls

Pass command arguments as a list with `shell=False` (the default). This prevents shell metacharacter injection because each argument is passed directly to the target binary as a single argv entry.

```python
import subprocess

# Correct: list args, no shell
subprocess.run(["git", "clone", "--", user_url], check=True)
subprocess.run(["convert", user_input, "output.png"], check=True)

# Use "--" separator when user input could start with "-"
# to prevent argument injection even without a shell
subprocess.run(["git", "checkout", "--", branch_name], check=True)
```

**Why this matters**: `shell=True` interprets metacharacters (`;`, `|`, `&`, `$()`) as shell syntax, allowing attackers to chain arbitrary commands. List arguments bypass the shell entirely. CVE-2021-22205 (GitLab ExifTool, CVSS 10.0) is a canonical example of command injection via shelled invocation.

**Detection**:
```bash
rg -n 'subprocess\.(run|call|Popen|check_call|check_output).*shell\s*=\s*True' .
rg -n 'os\.system\(|os\.popen\(' .
```

---

## Use tarfile Extraction Filters for Safe Archive Handling

On Python 3.12+, use `filter="data"` when extracting archives from untrusted sources. On older Python, validate each member path before extraction.

```python
import tarfile
from pathlib import Path

# Correct (Python 3.12+): filter rejects unsafe members
with tarfile.open(uploaded_archive) as tar:
    tar.extractall(target_dir, filter="data")

# Correct (pre-3.12): manual containment check
def safe_extract(tar: tarfile.TarFile, target: str) -> None:
    target_path = Path(target).resolve()
    for member in tar.getmembers():
        member_path = (target_path / member.name).resolve()
        if not member_path.is_relative_to(target_path):
            raise RuntimeError(f"unsafe path in archive: {member.name}")
    tar.extractall(target)
```

For zipfile, validate paths even though Python 3.6.2+ sanitizes `..`, because absolute paths and symlinks remain risks on some platforms:

```python
import zipfile
from pathlib import Path

def safe_extract_zip(zf: zipfile.ZipFile, target: str) -> None:
    target_path = Path(target).resolve()
    for info in zf.infolist():
        member_path = (target_path / info.filename).resolve()
        if not member_path.is_relative_to(target_path):
            raise RuntimeError(f"unsafe path in zip: {info.filename}")
    zf.extractall(target)
```

**Why this matters**: CVE-2007-4559 is eighteen years old and still recurring. Tar archives can contain `..` or absolute paths that write anywhere the process has permission. The `filter="data"` parameter was added specifically to address this.

**Detection**:
```bash
rg -n 'tarfile\.open|\.extractall\(' . --type py
rg -n "filter\s*=\s*['\"]data['\"]" . --type py
```

---

## Use Template Files Instead of Template Strings

Render templates from disk files, never from user-supplied strings. Flask's `render_template_string` with user input is the canonical SSTI vulnerability.

```python
# Correct: render from a file with user data as context variables
from flask import render_template

@app.route("/preview")
def preview():
    return render_template("preview.html", body=request.args["body"])

# Correct: Django always renders from files by default
from django.shortcuts import render

def preview(request):
    return render(request, "preview.html", {"body": request.GET["body"]})

# Correct: FastAPI Jinja2 with literal template name
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

@app.get("/page")
async def page(request: Request):
    return templates.TemplateResponse("page.html", {"request": request})
```

**Why this matters**: `render_template_string(user_input)` passes attacker-controlled text through Jinja2's template engine, which evaluates expressions like `{{7*'7'}}` and can reach code execution through sandbox escapes (CVE-2019-10906, CVE-2016-10745).

**Detection**:
```bash
rg -n 'render_template_string|jinja2\.Template\(' . --type py
```

---

## Use JSON or yaml.safe_load for Untrusted Data

Deserialize untrusted data with `json.loads` or `yaml.safe_load`. Never use `pickle`, `marshal`, `cloudpickle`, `dill`, or `joblib` on data from outside the trust boundary.

```python
import json
import yaml

# Correct: JSON for API payloads and configuration
config = json.loads(request_body)

# Correct: yaml.safe_load restricts to primitive types
config = yaml.safe_load(config_string)

# Correct: Pydantic for structured validation
from pydantic import BaseModel

class UserConfig(BaseModel):
    theme: str
    language: str

validated = UserConfig.model_validate_json(request_body)
```

**Why this matters**: `pickle.loads` executes arbitrary code via `__reduce__`. `yaml.load` without `SafeLoader` allows `!!python/object` tags that reach `os.system`. CVE-2020-1747 (PyYAML FullLoader before 5.3.1) and GHSA-g8c6-8fjj-2r4m (python-socketio pickle across servers) demonstrate the real-world impact. ML model files (`.pkl`, `.joblib`) are a live attack surface (CVE-2025-1716).

**Detection**:
```bash
rg -n 'pickle\.loads?|cloudpickle|joblib\.load|dill\.loads?|marshal\.loads?' . --type py
rg -n 'yaml\.load\b' . --type py | rg -v 'safe_load|SafeLoader'
```

---

## Scope Django Querysets to the Requesting User

Filter Django ORM queries by the authenticated user's ownership or organization. Never expose `Model.objects.all()` or lookup by raw ID without scoping.

```python
# Correct: scope queryset in DRF ViewSet
class InvoiceViewSet(ModelViewSet):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(organization=self.request.user.organization)

# Correct: scope individual lookups
def get_invoice(request, invoice_id: int):
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        organization=request.user.organization,
    )
    return JsonResponse(InvoiceSerializer(invoice).data)
```

**Why this matters**: `Invoice.objects.get(id=kwargs['id'])` without ownership scoping is an IDOR vulnerability. Any authenticated user can access any other user's data by guessing or enumerating IDs.

**Detection**:
```bash
rg -n 'objects\.(get|filter)\(.*id\s*=' . --type py | rg -v 'request\.user|organization|owner|user_id'
rg -n "fields\s*=\s*['\"]__all__['\"]" . --type py
```

---

## Declare Explicit Fields on DRF Serializers

Always use an explicit field allowlist on Django REST Framework serializers. Never use `fields = '__all__'` on serializers exposed to external clients.

```python
from rest_framework import serializers

# Correct: explicit field allowlist
class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "display_name", "avatar_url", "timezone"]

# Correct: mark sensitive fields as write-only
class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "display_name", "password"]
        extra_kwargs = {
            "password": {"write_only": True},
        }
```

**Why this matters**: `fields = '__all__'` exposes every column including `password_hash`, `api_token`, `is_staff`, and any column added by future migrations. On write endpoints, it enables mass assignment where an attacker can POST `{"is_staff": true}`.

**Detection**:
```bash
rg -n "fields\s*=\s*['\"]__all__['\"]" . --type py
```

---

## Use Parameterized Queries for All Database Access

Use ORM methods or parameterized queries with bind variables. Never interpolate user data into SQL strings with f-strings, `%`, or `.format()`.

```python
# Correct: Django ORM (parameterized by default)
invoices = Invoice.objects.filter(customer_id=customer_id)

# Correct: Django raw SQL with parameters
Invoice.objects.raw("SELECT * FROM invoices WHERE customer_id = %s", [customer_id])

# Correct: Django cursor with parameters
with connection.cursor() as cur:
    cur.execute("SELECT * FROM invoices WHERE id = %s", [invoice_id])

# Correct: SQLAlchemy with named bind parameters
from sqlalchemy import text
session.execute(text("SELECT * FROM users WHERE name = :name"), {"name": name})

# Correct: SQLAlchemy expression form
session.query(User).filter_by(name=name).all()
```

**Why this matters**: SQL injection through string interpolation enables data exfiltration, data modification, and in some databases, command execution. The first argument to Django's `.raw()`, `.extra()`, `RawSQL()`, and `cursor.execute()` is not parameterized. Parameterization happens only via the separate `params` argument.

**Detection**:
```bash
rg -n '\.raw\(f"|\.extra\(.*f"|RawSQL\(f"|cursor\.execute\(f"' . --type py
rg -n 'session\.execute\(f"|text\(f"' . --type py
```

---

## Use Dependency Injection for FastAPI Auth

Enforce authentication and authorization through FastAPI's dependency injection system. Every endpoint that accesses protected data must declare a dependency that verifies the session.

```python
from fastapi import Depends, HTTPException

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Verify JWT and return the authenticated user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["RS256"])
        user = await db.fetch_user(payload["sub"])
        if user is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
        return user
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid credentials")

# Correct: auth enforced via dependency
@app.get("/users/me", response_model=UserPublic)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user

# Correct: apply to entire router
router = APIRouter(dependencies=[Depends(get_current_user)])
```

**Why this matters**: Without dependency injection, auth checks rely on manual calls at the top of each handler, which are easy to forget. FastAPI's `Depends()` system makes missing auth a visible gap (the parameter is absent) rather than a silent omission.

**Detection**:
```bash
rg -n '@app\.(get|post|put|delete|patch)\(' . --type py | rg -v 'Depends|dependencies'
```

---

## Use response_model on FastAPI Endpoints

Declare a `response_model` Pydantic schema on every endpoint that returns database data. This filters the response to declared fields only.

```python
from pydantic import BaseModel, ConfigDict

class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Never "allow" on response DTOs

    id: int
    display_name: str
    avatar_url: str | None

@app.get("/users/{user_id}", response_model=UserPublic)
async def get_user(user_id: int):
    return await db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})
```

**Why this matters**: Without `response_model`, FastAPI returns whatever the handler produces. A raw ORM row includes every column (password hash, internal flags, API tokens). Pydantic DTOs with `extra="allow"` pass arbitrary fields through to the response (Sentry commit `0c0aae90ac1`).

**Detection**:
```bash
rg -n '@app\.(get|post|put|delete|patch)\(' . --type py | rg -v 'response_model'
rg -n "extra\s*=\s*['\"]allow['\"]" . --type py
```

---

## Use Path Containment Checks for File Operations

Resolve paths and verify they remain within the intended base directory before opening or serving files. Use `pathlib.Path.is_relative_to()` (Python 3.9+) for the containment check.

```python
from pathlib import Path
from flask import send_from_directory, abort

BASE_DIR = Path("/var/app/exports").resolve()

@app.route("/download")
def download():
    name = request.args["name"]
    target = (BASE_DIR / name).resolve()
    if not target.is_relative_to(BASE_DIR):
        abort(403)
    if not target.is_file():
        abort(404)
    return send_from_directory(BASE_DIR, name)
```

For file uploads, sanitize the filename:

```python
import uuid

def user_upload_path(instance, filename: str) -> str:
    # Replace user-supplied filename with UUID to prevent path traversal
    ext = Path(filename).suffix
    return f"uploads/{instance.user_id}/{uuid.uuid4()}{ext}"
```

**Why this matters**: `os.path.join("/base", user_path)` discards the base entirely if `user_path` is absolute. `../` sequences escape the intended directory. `Path.resolve()` normalizes all these before the containment check catches them.

**Detection**:
```bash
rg -n 'send_file\(|FileResponse\(' . --type py
rg -n 'os\.path\.join\(.*request' . --type py
rg -n 'is_relative_to|startswith' . --type py
```

---

## Configure Flask for Production Security

Set `debug=False`, use a strong random secret key, and serve files through `send_from_directory` instead of `send_file` with manual path joining.

```python
import os
import secrets

# Correct: production configuration
app.config["DEBUG"] = False
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True  # HTTPS only
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Correct: use send_from_directory (applies safe_join internally)
@app.route("/download/<filename>")
def download(filename: str):
    return send_from_directory("/var/app/exports", filename)
```

**Why this matters**: `debug=True` exposes the Werkzeug debugger at `/console`, which is a Python REPL allowing direct code execution. The PIN protection is derivable from server-local facts (machine ID, username, app path). Stack traces in debug mode leak local variables, settings, and SQL queries.

**Detection**:
```bash
rg -n "debug\s*=\s*True|DEBUG\s*=\s*True" . --type py
rg -n "SECRET_KEY\s*=\s*['\"]" . --type py | rg -v 'environ|getenv|secrets'
```

---

## Configure Django Security Settings for Production

Set security-critical Django settings explicitly. Never deploy with `DEBUG = True` or `ALLOWED_HOSTS = ['*']`.

```python
# settings/production.py
DEBUG = False
ALLOWED_HOSTS = ["app.example.com", "api.example.com"]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Session security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"  # Never PickleSerializer

# CSRF
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True

# Security middleware
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
```

**Why this matters**: `DEBUG = True` exposes full tracebacks with local variables. `ALLOWED_HOSTS = ['*']` enables Host header poisoning for password-reset token theft. `PickleSerializer` for sessions reintroduces deserialization RCE. Django defaults to `JSONSerializer` since 1.6 specifically to prevent this.

**Detection**:
```bash
rg -n "^DEBUG\s*=|^ALLOWED_HOSTS\s*=" . --type py
rg -n 'PickleSerializer|SESSION_SERIALIZER' . --type py
```

---

## Validate URLs Before Making Outbound Requests

When making HTTP requests to user-supplied URLs, validate at the IP layer after DNS resolution. String-based checks fail against DNS rebinding, IP encoding tricks, and redirects.

```python
import ipaddress
import socket
from urllib.parse import urlparse

DISALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

def validate_url(url: str) -> str:
    """Validate a user-supplied URL is safe to fetch."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("invalid scheme")
    addr = socket.gethostbyname(parsed.hostname)
    ip = ipaddress.ip_address(addr)
    for net in DISALLOWED_NETWORKS:
        if ip in net:
            raise ValueError(f"disallowed IP range: {net}")
    return url

# Usage
validated = validate_url(user_url)
resp = requests.get(validated, allow_redirects=False, timeout=10)
```

**Why this matters**: SSRF through user-controlled URLs is a top-tier cloud vulnerability. The Capital One breach (2019) exploited SSRF to reach the EC2 metadata service at `169.254.169.254`, stealing IAM credentials and dumping 30GB from S3. CVE-2024-34351 (Next.js Server Actions SSRF) and CVE-2026-40175 (axios header injection bypassing IMDSv2) demonstrate the attack surface remains active.

**Detection**:
```bash
rg -n 'requests\.(get|post|put|delete)|urlopen|urllib\.request' . --type py
rg -n 'allow_redirects' . --type py
```

---

## Configure FastAPI CORS With Explicit Origins

Set CORS origins to explicit allowed domains. Never use wildcard origins with credentials.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com", "https://admin.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Why this matters**: `allow_origins=["*"]` with `allow_credentials=True` is rejected by browsers, but `allow_origins=["*"]` without credentials still allows any site to read API responses. Explicit origins prevent cross-origin data theft.

**Detection**:
```bash
rg -n 'allow_origins|CORSMiddleware' . --type py
```
