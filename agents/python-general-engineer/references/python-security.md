# Python Secure Implementation Patterns

Secure-by-default patterns for Python 3.11+. Load when the task involves security, auth, injection, XSS, CSRF, SSRF, deserialization, or file handling.

---

## Use List Arguments for Subprocess Calls

Pass command arguments as a list with `shell=False` (default). Prevents shell metacharacter injection.

```python
subprocess.run(["git", "clone", "--", user_url], check=True)
subprocess.run(["git", "checkout", "--", branch_name], check=True)  # "--" prevents arg injection
```

CVE-2021-22205 (GitLab ExifTool, CVSS 10.0): command injection via shelled invocation.

**Detection**:
```bash
rg -n 'subprocess\.(run|call|Popen|check_call|check_output).*shell\s*=\s*True' .
rg -n 'os\.system\(|os\.popen\(' .
```

---

## Use tarfile Extraction Filters for Safe Archive Handling

```python
# Python 3.12+: filter rejects unsafe members
with tarfile.open(uploaded_archive) as tar:
    tar.extractall(target_dir, filter="data")

# Pre-3.12: manual containment check
def safe_extract(tar: tarfile.TarFile, target: str) -> None:
    target_path = Path(target).resolve()
    for member in tar.getmembers():
        member_path = (target_path / member.name).resolve()
        if not member_path.is_relative_to(target_path):
            raise RuntimeError(f"unsafe path in archive: {member.name}")
    tar.extractall(target)
```

CVE-2007-4559: tar path traversal. `filter="data"` added to fix this.

**Detection**:
```bash
rg -n 'tarfile\.open|\.extractall\(' . --type py
rg -n "filter\s*=\s*['\"]data['\"]" . --type py
```

---

## Use Template Files Instead of Template Strings

Render from disk files, never from user-supplied strings. `render_template_string(user_input)` is SSTI.

```python
# Flask
return render_template("preview.html", body=request.args["body"])

# FastAPI Jinja2
templates = Jinja2Templates(directory="templates")
return templates.TemplateResponse("page.html", {"request": request})
```

CVE-2019-10906, CVE-2016-10745: Jinja2 sandbox escapes.

**Detection**:
```bash
rg -n 'render_template_string|jinja2\.Template\(' . --type py
```

---

## Use JSON or yaml.safe_load for Untrusted Data

Never `pickle`, `marshal`, `cloudpickle`, `dill`, or `joblib` on untrusted data.

```python
config = json.loads(request_body)
config = yaml.safe_load(config_string)
validated = UserConfig.model_validate_json(request_body)  # Pydantic
```

CVE-2020-1747 (PyYAML FullLoader), GHSA-g8c6-8fjj-2r4m (python-socketio pickle), CVE-2025-1716 (ML model files).

**Detection**:
```bash
rg -n 'pickle\.loads?|cloudpickle|joblib\.load|dill\.loads?|marshal\.loads?' . --type py
rg -n 'yaml\.load\b' . --type py | rg -v 'safe_load|SafeLoader'
```

---

## Scope Django Querysets to the Requesting User

Never expose `Model.objects.all()` or lookup by raw ID without scoping.

```python
class InvoiceViewSet(ModelViewSet):
    def get_queryset(self):
        return Invoice.objects.filter(organization=self.request.user.organization)
```

IDOR vulnerability without ownership scoping.

**Detection**:
```bash
rg -n 'objects\.(get|filter)\(.*id\s*=' . --type py | rg -v 'request\.user|organization|owner|user_id'
rg -n "fields\s*=\s*['\"]__all__['\"]" . --type py
```

---

## Declare Explicit Fields on DRF Serializers

Never `fields = '__all__'` on external serializers.

```python
class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "display_name", "avatar_url", "timezone"]
```

`'__all__'` exposes `password_hash`, `api_token`, `is_staff` and enables mass assignment.

**Detection**:
```bash
rg -n "fields\s*=\s*['\"]__all__['\"]" . --type py
```

---

## Use Parameterized Queries for All Database Access

Never interpolate user data into SQL with f-strings, `%`, or `.format()`.

```python
Invoice.objects.filter(customer_id=customer_id)  # ORM
Invoice.objects.raw("SELECT * FROM invoices WHERE customer_id = %s", [customer_id])
session.execute(text("SELECT * FROM users WHERE name = :name"), {"name": name})  # SQLAlchemy
```

**Detection**:
```bash
rg -n '\.raw\(f"|\.extra\(.*f"|RawSQL\(f"|cursor\.execute\(f"' . --type py
rg -n 'session\.execute\(f"|text\(f"' . --type py
```

---

## Use Dependency Injection for FastAPI Auth

Every protected endpoint must declare a dependency that verifies the session.

```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["RS256"])
        user = await db.fetch_user(payload["sub"])
        if user is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
        return user
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid credentials")

@app.get("/users/me", response_model=UserPublic)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user

# Apply to entire router
router = APIRouter(dependencies=[Depends(get_current_user)])
```

**Detection**:
```bash
rg -n '@app\.(get|post|put|delete|patch)\(' . --type py | rg -v 'Depends|dependencies'
```

---

## Use response_model on FastAPI Endpoints

Declare `response_model` on every endpoint returning database data. Filters response to declared fields.

```python
class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Never "allow" on response DTOs
    id: int
    display_name: str
    avatar_url: str | None

@app.get("/users/{user_id}", response_model=UserPublic)
async def get_user(user_id: int):
    return await db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": user_id})
```

**Detection**:
```bash
rg -n '@app\.(get|post|put|delete|patch)\(' . --type py | rg -v 'response_model'
rg -n "extra\s*=\s*['\"]allow['\"]" . --type py
```

---

## Use Path Containment Checks for File Operations

Resolve paths and verify within base directory before opening.

```python
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

**Detection**:
```bash
rg -n 'send_file\(|FileResponse\(' . --type py
rg -n 'os\.path\.join\(.*request' . --type py
```

---

## Configure Flask for Production Security

```python
app.config["DEBUG"] = False
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
```

`debug=True` exposes Werkzeug debugger (Python REPL at `/console`).

**Detection**:
```bash
rg -n "debug\s*=\s*True|DEBUG\s*=\s*True" . --type py
rg -n "SECRET_KEY\s*=\s*['\"]" . --type py | rg -v 'environ|getenv|secrets'
```

---

## Configure Django Security Settings for Production

```python
DEBUG = False
ALLOWED_HOSTS = ["app.example.com", "api.example.com"]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"  # Never PickleSerializer
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

`ALLOWED_HOSTS = ['*']` enables Host header poisoning. `PickleSerializer` = deserialization RCE.

**Detection**:
```bash
rg -n "^DEBUG\s*=|^ALLOWED_HOSTS\s*=" . --type py
rg -n 'PickleSerializer|SESSION_SERIALIZER' . --type py
```

---

## Validate URLs Before Making Outbound Requests

Validate at IP layer after DNS resolution. String checks fail against DNS rebinding.

```python
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
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("invalid scheme")
    addr = socket.gethostbyname(parsed.hostname)
    ip = ipaddress.ip_address(addr)
    for net in DISALLOWED_NETWORKS:
        if ip in net:
            raise ValueError(f"disallowed IP range: {net}")
    return url
```

Capital One breach (2019): SSRF to EC2 metadata. CVE-2024-34351, CVE-2026-40175.

**Detection**:
```bash
rg -n 'requests\.(get|post|put|delete)|urlopen|urllib\.request' . --type py
```

---

## Configure FastAPI CORS With Explicit Origins

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com", "https://admin.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Detection**:
```bash
rg -n 'allow_origins|CORSMiddleware' . --type py
```
