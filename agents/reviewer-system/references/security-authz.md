# Authorization Security Patterns

Load when reviewing code that handles permissions, access control, RBAC, IDOR, JWT validation, session management, or any route/endpoint that serves protected resources.

Authorization answers one question: is this principal permitted to perform this action on this resource? The patterns below show how to answer it correctly across frameworks.

---

## Scope Querysets to the Authenticated User

Every database query for a user-owned resource must filter by the authenticated principal. The query itself is the authorization boundary — not the route decorator, not the frontend, not the URL structure.

### Correct Pattern

**Django/DRF:**
```python
class OrderViewSet(ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Scope every query to the requesting user's organization
        return Order.objects.filter(organization=self.request.user.organization)
```

**Express/Prisma:**
```ts
router.get('/orders/:id', requireAuth, async (req, res) => {
  // Include ownership filter in the WHERE clause
  const order = await db.order.findFirst({
    where: { id: req.params.id, userId: req.user.id },
  });
  if (!order) return res.sendStatus(404);
  res.json(order);
});
```

**FastAPI:**
```python
@router.get("/orders/{order_id}")
async def get_order(order_id: int, user: User = Depends(get_current_user)):
    order = await Order.filter(id=order_id, owner=user).first()
    if not order:
        raise HTTPException(status_code=404)
    return order
```

**Go:**
```go
func (h *Handler) GetOrder(w http.ResponseWriter, r *http.Request) {
    userID := auth.UserIDFromContext(r.Context())
    orderID := chi.URLParam(r, "orderID")
    // Scope the query to the authenticated user
    order, err := h.store.GetOrderForUser(r.Context(), orderID, userID)
    if err != nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    json.NewEncoder(w).Encode(order)
}
```

### Why This Matters

Unscoped queries are the most common authorization vulnerability in web applications. When `Order.objects.get(id=order_id)` runs without a user filter, any authenticated user can read any order by guessing or enumerating IDs. This is IDOR — Insecure Direct Object Reference.

Real incidents: Shopify HackerOne #2207248 (BillingInvoice lookup by global ID without shop scoping), SingleStore HackerOne #3219944 (cross-tenant data access via unscoped queries).

**CVEs:** OWASP A01:2021 Broken Access Control is the #1 web vulnerability category.

### Detection

```bash
# Django: ModelViewSet without get_queryset override (likely uses unscoped queryset)
rg -n 'class \w+ViewSet.*ModelViewSet' --type py -l | xargs rg -L 'def get_queryset'

# Django: Direct objects.get with id from request
rg -n 'objects\.(get|filter)\(id=.*kwargs\[|id=.*request\.(GET|POST|data)' --type py

# Express/Prisma: findUnique without ownership filter
rg -n 'findUnique\(\{.*where:.*req\.params' --type ts

# Go: database queries using only URL parameter without user context
rg -n 'GetOrder|FindOrder|FetchOrder' --type go -l | xargs rg -n 'func.*http\.Request'
```

---

## Close Permission Functions with an Explicit Default Deny

Every permission-checking function must end with `return False` (or equivalent). When a role string, permission name, or scope value is unrecognized, the function must deny access. There is no safe default other than denial.

### Correct Pattern

**Python:**
```python
def can_edit(user, resource):
    if user.role == "admin":
        return True
    if user.role == "editor" and resource.owner_id == user.id:
        return True
    # Explicit deny for all unrecognized roles
    return False
```

**TypeScript:**
```ts
function canEdit(user: User, resource: Resource): boolean {
  if (user.role === 'admin') return true;
  if (user.role === 'editor' && resource.ownerId === user.id) return true;
  // Explicit deny — never fall through
  return false;
}
```

**Go:**
```go
func canEdit(user *User, resource *Resource) bool {
    switch user.Role {
    case "admin":
        return true
    case "editor":
        return resource.OwnerID == user.ID
    default:
        // Explicit deny for unknown roles
        return false
    }
}
```

### Why This Matters

Missing final `return False` causes the function to return `None` (Python) or `undefined` (JS), which are falsy but can leak through callers that check for truthiness differently. A role string not covered by any branch silently falls through. Apollo Router CVE-2025-64347 demonstrated this: a directive renamed via `@link` was not recognized by the authorization check, so the default path allowed the request.

### Detection

```bash
# Python: permission functions without explicit return False at end
rg -n 'def (can_|has_|check_|is_allowed|is_authorized)' --type py

# TypeScript: permission functions — check each for exhaustive return
rg -n 'function (can|has|check|isAllowed|isAuthorized)' --type ts
```

---

## Restrict Writable Fields with an Explicit Allowlist

Serializers and update handlers must declare exactly which fields a client can write. Spreading request body directly into a database create or update operation allows mass assignment — an attacker adds `{"role": "admin"}` or `{"is_staff": true}` to the payload and elevates their own privileges.

### Correct Pattern

**Django/DRF:**
```python
class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = User
        # Explicit field list — only these are writable
        fields = ['display_name', 'avatar_url', 'timezone']
```

**Express/Zod:**
```ts
const ProfileUpdate = z.object({
  displayName: z.string().max(80).optional(),
  avatarUrl: z.string().url().optional(),
  timezone: z.string().optional(),
});

router.patch('/me', requireAuth, async (req, res) => {
  // Parse strips unknown fields — role, is_staff, org_id cannot pass
  const data = ProfileUpdate.parse(req.body);
  const user = await db.user.update({ where: { id: req.user.id }, data });
  res.json(user);
});
```

**FastAPI/Pydantic:**
```python
class ProfileUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: HttpUrl | None = None
    timezone: str | None = None

    class Config:
        extra = "forbid"  # Reject unknown fields entirely
```

### Why This Matters

Mass assignment is one of the most common privilege escalation vectors. DRF's `fields = '__all__'` on a write endpoint exposes every model field including `is_staff`, `is_superuser`, and `organization_id`. Spreading `req.body` into Prisma's `data` parameter does the same.

**CVEs:** OWASP A01:2021, Ruby on Rails CVE-2012-2661 (mass assignment), GitHub's 2012 mass-assignment incident on public keys.

### Detection

```bash
# DRF: serializers with fields = '__all__' — check if used on write endpoints
rg -n "fields = '__all__'" --type py

# Express: spreading req.body into database operations
rg -n 'data: req\.body|\.create\(req\.body\)|\.update\(.*req\.body' --type ts

# FastAPI/Pydantic: models allowing extra fields
rg -n "extra = .allow." --type py
```

---

## Apply Authorization Guards at the Router Level

Mount permission middleware on the router or controller, not individually on each handler. When authorization is applied per-handler, a new endpoint added without the decorator is silently unprotected.

### Correct Pattern

**FastAPI:**
```python
# Authorization applied at the router level — every endpoint inherits it
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)]
)

@admin_router.get("/users")
async def list_users():
    return await db.users.find_all()
```

**Express:**
```ts
// Admin middleware applied to the entire router
app.use('/admin', requireAuth, requireAdmin, adminRouter);
```

**NestJS:**
```ts
@UseGuards(AuthGuard, AdminGuard)  // Applied at the controller level
@Controller('admin')
export class AdminController {
  @Get('users')
  findAll() {
    return this.userService.findAll();
  }
}
```

**Django:**
```python
# Django 5.1+ LoginRequiredMiddleware covers all views by default
# Pair with per-view permission_classes for object-level access
MIDDLEWARE = [
    ...
    'django.contrib.auth.middleware.LoginRequiredMiddleware',
]
```

### Why This Matters

When guards are declared but not applied, the code has an authorization definition with no enforcement. MLflow ajax-api endpoints shipped without the shared `Depends()` — the guard existed but was never attached to the router. Every new route added to an unguarded router is a potential privilege escalation.

### Detection

```bash
# FastAPI: routers without dependencies (potential missing auth)
rg -n 'APIRouter\(' --type py | rg -v 'dependencies='

# Express: route mounting without auth middleware
rg -n "app\.use\('/(admin|api|internal)" --type ts

# NestJS: controllers without UseGuards
rg -n '@Controller' --type ts -l | xargs rg -L '@UseGuards'
```

---

## Validate JWT Claims with Algorithm Pinning and Scope Verification

Decode JWTs with signature verification enabled and the algorithm explicitly pinned. After verification, confirm that the token's claims (org, tenant, scope) match the resource being accessed.

### Correct Pattern

**Python (PyJWT):**
```python
# Pin the algorithm and verify signature
payload = jwt.decode(token, public_key, algorithms=["RS256"])

# Verify the token's org claim matches the requested resource
if payload["org_id"] != request.org.id:
    raise PermissionDenied("token org mismatch")

if "org:admin" not in payload.get("scope", []):
    raise PermissionDenied("insufficient scope")
```

**TypeScript (jsonwebtoken):**
```ts
// Pin algorithm — prevents RS256/HS256 confusion attacks
const claims = jwt.verify(token, publicKey, { algorithms: ['RS256'] });

// Verify org-level claims match the target resource
if (claims.orgId !== req.org.id) {
  throw new ForbiddenError('token org mismatch');
}
```

### Why This Matters

Unverified JWT claims are attacker-controlled strings. `jwt.decode()` without verification returns whatever the client sent — including `{"role": "admin"}`. Algorithm confusion attacks (RS256 key used as HS256 secret) let attackers forge tokens with a public key.

**CVEs:** jsonwebtoken CVE-2022-23540 (default algorithm bypass), CVE-2022-23541 (RS-to-HS confusion), PyJWT CVE-2022-29217 (algorithm confusion), Java ECDSA CVE-2022-21449 ("psychic signatures" — any signature accepted).

### Detection

```bash
# Python: JWT decode without signature verification
rg -n 'jwt\.decode.*verify_signature.*False|jwt\.decode\(.*options=' --type py

# Python: JWT decode without algorithm pinning
rg -n 'jwt\.decode' --type py | rg -v 'algorithms='

# TypeScript: jwt.decode (returns claims without verification)
rg -n 'jwt\.decode\(' --type ts

# TypeScript: jwt.verify without algorithms pin
rg -n 'jwt\.verify' --type ts | rg -v 'algorithms'
```

---

## Enforce Authorization Inside Server Actions

Next.js Server Actions are directly invokable HTTP endpoints. Page-level authentication checks do not protect the action — every Server Action must verify the caller's identity and permissions independently.

### Correct Pattern

```ts
'use server';

export async function deleteUser(userId: string) {
  // Re-authenticate inside the action — page-level checks do not apply here
  const session = await auth();
  if (!session?.user?.isAdmin) {
    throw new Error('unauthorized');
  }
  await db.user.delete({ where: { id: userId } });
}
```

### Why This Matters

Server Actions are HTTP POST endpoints. A page component that checks `session?.user?.isAdmin` before rendering a form does not protect the action the form calls. The action is invokable by anyone who can construct the POST request, bypassing the page entirely.

**CVEs:** CVE-2025-55182 (React2Shell) demonstrated that Next.js Server Actions re-expose handlers regardless of page-level guards. The Next.js data-security documentation explicitly requires re-authentication in every action.

### Detection

```bash
# Find Server Actions without auth checks
rg -rn "'use server'" --type ts -l | xargs rg -L 'auth\(\)|getSession\(\)|getServerSession'

# Find Server Actions that perform mutations
rg -A5 "'use server'" --type ts | rg 'delete|update|create|insert'
```

---

## Verify Session Integrity Before Trusting Identity Claims

Session-derived identity claims (user ID, role, tenant) must come from a verified session store, not from client-modifiable cookies or unsigned tokens. After password reset, login-as, or impersonation flows, re-validate that the session maps to the intended principal.

### Correct Pattern

**Django:**
```python
# Django's session framework stores session data server-side by default.
# The session cookie contains only the session ID, not the claims.
# Verify the session is valid and maps to the expected user.
user = request.user  # Resolved from session middleware
if not user.is_authenticated:
    return HttpResponseForbidden()
```

**Express:**
```ts
// Use server-side session store — not client-side JWT for session state
app.use(session({
  store: new RedisStore({ client: redisClient }),
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { secure: true, httpOnly: true, sameSite: 'strict' },
}));
```

### Why This Matters

Impersonation endpoints ("log in as user" / support tools) without staff-role gates, session binding, or audit logging allow horizontal and vertical privilege escalation. Password-reset identity claims that feed role or tenant checks without re-verification let attackers hijack sessions.

**CVEs:** ruby-saml CVE-2024-45409 (SAML response signature bypass enabling impersonation).

### Detection

```bash
# Find impersonation or login-as endpoints
rg -n 'login.as|impersonate|switch.user|view.as|act.as' --type py --type ts -i

# Find session configuration without secure flags
rg -n 'cookie:.*secure.*false|httpOnly.*false|sameSite.*none' --type ts
```
